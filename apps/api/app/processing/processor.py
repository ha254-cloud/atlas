from app.canonical.claim import CanonicalClaim
from app.canonical.normalizers.csv import CSVNormalizer
from app.claims.timeline import ClaimTimeline
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim_event import ClaimEventType
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.processing.exceptions import ClaimValidationError, ValidationError
from app.processing.persistence import PersistenceLayer
from app.recovery.engine import RecoveryEngine
from app.validation.engine import ValidationEngine


class ClaimProcessor:
    """
    Thin orchestrator for the full claim ingestion cycle:
        1. Normalize raw input → CanonicalClaim
        2. Persist patient, payer, claim, claim lines
        3. Record a ClaimEvent audit entry
        4. Run recovery engine → create RecoveryCase
        5. Publish CLAIM_IMPORTED event — AI analysis dispatch, dashboard
           push, and webhook delivery all happen as a *reaction* to this
           event (see app/events/handlers/), not as direct calls from here.
    """

    def __init__(self, db, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.normalizer = CSVNormalizer()
        self.persistence = PersistenceLayer(db, organization_id)
        self.recovery_engine = RecoveryEngine()
        self.validation_engine = ValidationEngine()
        self.publisher = EventPublisher()
        self.timeline = ClaimTimeline(db)

    def process(self, row: dict):
        """Process a single raw CSV row end-to-end."""
        # Validate required fields before normalizing
        required = ["claim_number", "payer_code", "billed_amount", "paid_amount", "service_date"]
        missing = [f for f in required if not row.get(f)]
        if missing:
            raise ValidationError(missing)

        canonical: CanonicalClaim = self.normalizer.normalize(row)
        return self.process_canonical(canonical)

    def process_canonical(self, canonical: CanonicalClaim):
        """Process a pre-normalized CanonicalClaim (from any source)."""
        issues = self.validation_engine.run(canonical)
        blocking = self.validation_engine.blocking_issues(issues)
        if blocking:
            raise ClaimValidationError(blocking)

        patient = self.persistence.upsert_patient(canonical)
        payer = self.persistence.upsert_payer(canonical)
        claim = self.persistence.create_claim(canonical, patient.id, payer.id)

        if canonical.procedure_codes:
            self.persistence.create_claim_lines(claim.id, canonical)

        if canonical.diagnosis_codes:
            self.persistence.create_claim_diagnoses(claim.id, canonical)

        denial = self.persistence.create_denial_if_present(claim.id, canonical)
        if denial is not None:
            self.timeline.record(
                organization_id=self.organization_id,
                claim_id=claim.id,
                event_type=ClaimEventType.DENIAL_RECORDED,
                description=f"Denial recorded from source file: {denial.denial_code}",
                metadata={"denial_id": denial.id},
            )

        warnings = self.validation_engine.warnings(issues)
        if warnings:
            self.persistence.save_validation_issues(claim.id, warnings)

        self.timeline.record(
            organization_id=self.organization_id,
            claim_id=claim.id,
            event_type=ClaimEventType.IMPORTED,
            description=f"Claim {claim.claim_number} imported",
            metadata={"source": "import_pipeline"},
        )

        # Recovery Workflow Engine: starting the workflow row is deliberately
        # NOT done here. This method runs inside the import pipeline's
        # per-row SAVEPOINT (see ImportPipeline.run()), and WorkflowService's
        # transition() commits the session — calling that while a SAVEPOINT
        # is still active would prematurely end the outer transaction.
        # ImportPipeline starts the workflow itself, after the SAVEPOINT for
        # this row has been released.

        # Run recovery engine synchronously — fast, no I/O
        self._run_recovery(claim)

        return claim

    def _run_recovery(self, claim):
        # Age unknown at import time — use 0 days (will be updated by scheduler)
        opportunity = self.recovery_engine.analyze(claim, denial_probability=0.5, claim_age_days=0)
        if opportunity is None:
            return

        recovery_case = RecoveryCase(
            organization_id=self.organization_id,
            claim_id=claim.id,
            recovery_score=opportunity.score,
            estimated_value=opportunity.estimated_recovery,
            status=RecoveryStatus.OPEN,
            recommendation=opportunity.next_action or "Review claim and pursue recovery",
        )
        self.db.add(recovery_case)
        self.db.flush()

        self.publisher.publish(
            EventType.RECOVERY_CREATED,
            {"claim_id": claim.id, "recovery_case_id": recovery_case.id},
        )
