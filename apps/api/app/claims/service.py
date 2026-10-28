from sqlalchemy.orm import Session

from app.branches.service import BranchService
from app.claims.events import ClaimEvents
from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.claims.validators import validate_create
from app.models.appeal import Appeal
from app.models.claim import Claim, ClaimPriority
from app.models.claim_analysis import ClaimAnalysis
from app.models.claim_diagnosis import ClaimDiagnosis
from app.models.claim_event import ClaimEventType
from app.models.claim_line import ClaimLine
from app.models.organization import Organization
from app.workflows.service import WorkflowService


class ClaimService:
    def __init__(
        self,
        db: Session,
        organization_id: int,
        accessible_branch_ids: list[int] | None = None,
    ):
        self.db = db
        self.organization_id = organization_id
        self.repo = ClaimRepository(db, organization_id, accessible_branch_ids)
        self.events = ClaimEvents()
        self.timeline = ClaimTimeline(db)

    def create_claim(self, payload: dict, actor_id: int | None = None) -> dict:
        # Validate
        validate_create(payload, self.repo)
        BranchService(self.db, self.organization_id).validate_claim_scope(
            payload.get("branch_id"), payload.get("department_id")
        )
        organization = (
            self.db.query(Organization).filter(Organization.id == self.organization_id).one()
        )

        # Build model — organization_id always comes from the JWT, never the client
        claim = Claim(
            organization_id=self.organization_id,
            branch_id=payload.get("branch_id"),
            department_id=payload.get("department_id"),
            currency=(payload.get("currency") or organization.currency).upper(),
            patient_id=payload["patient_id"],
            payer_id=payload["payer_id"],
            claim_number=payload.get("claim_number"),
            status=payload.get("status", "imported"),
            billed_amount=payload.get("billed_amount", 0),
            paid_amount=payload.get("paid_amount", 0),
            service_date=payload.get("service_date"),
            provider=payload.get("provider"),
            priority=ClaimPriority(payload.get("priority") or "medium"),
            assigned_user_id=payload.get("assigned_user_id"),
            ai_risk_score=payload.get("ai_risk_score"),
            recovery_probability=payload.get("recovery_probability"),
        )

        # Stage
        self.repo.create(claim)

        # Commit
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Refresh
        self.db.refresh(claim)

        # Attach billed procedure lines, if provided
        claim_lines = payload.get("claim_lines") or []
        if claim_lines:
            for line in claim_lines:
                self.db.add(
                    ClaimLine(
                        claim_id=claim.id,
                        cpt_code=line["cpt_code"],
                        modifier=line.get("modifier"),
                        description=line.get("description"),
                        units=line.get("units", 1),
                        charge_amount=line["charge_amount"],
                        allowed_amount=line.get("allowed_amount"),
                        paid_amount=line.get("paid_amount"),
                        status=line.get("status"),
                    )
                )
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            self.db.refresh(claim)

        # Attach diagnosis codes, if provided
        claim_diagnoses = payload.get("claim_diagnoses") or []
        if claim_diagnoses:
            for diagnosis in claim_diagnoses:
                self.db.add(
                    ClaimDiagnosis(
                        claim_id=claim.id,
                        icd_code=diagnosis["icd_code"],
                        description=diagnosis.get("description"),
                        is_primary=diagnosis.get("is_primary", False),
                    )
                )
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            self.db.refresh(claim)

        # Publish event
        self.events.created(claim)

        # Record on the immutable claim timeline
        self.timeline.record(
            organization_id=self.organization_id,
            claim_id=claim.id,
            event_type=ClaimEventType.CREATED,
            description=f"Claim {claim.claim_number or claim.id} created",
            actor_id=actor_id,
        )
        self.db.commit()

        # Recovery Workflow Engine: every claim gets a workflow row, starting
        # at IMPORTED and immediately advanced to VALIDATED (the payload
        # already passed validate_create() above).
        WorkflowService(self.db, self.organization_id).start_workflow(claim, actor_id=actor_id)

        claim = self.repo.get(claim.id)
        return self._serialize(claim)

    def get_claim(self, claim_id: int) -> dict | None:
        claim = self.repo.get(claim_id)
        if not claim:
            return None
        return self._serialize(claim, detail=True)

    def list_claims(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        status: str | None = None,
        payer_id: int | None = None,
        priority: str | None = None,
        assigned_user_id: int | None = None,
        min_risk_score: float | None = None,
    ) -> list[dict]:
        claims = self.repo.list(
            limit,
            offset,
            search=search,
            status=status,
            payer_id=payer_id,
            priority=priority,
            assigned_user_id=assigned_user_id,
            min_risk_score=min_risk_score,
        )
        return [self._serialize(c) for c in claims]

    def export_claims(self, *, limit: int = 10_000) -> list[dict]:
        claims = self.repo.list(limit=limit, offset=0)
        return [
            {
                "claim_number": claim.claim_number,
                "patient_first_name": claim.patient.first_name if claim.patient else "",
                "patient_last_name": claim.patient.last_name if claim.patient else "",
                "medical_record_number": (
                    claim.patient.medical_record_number if claim.patient else ""
                ),
                "payer_code": claim.payer.payer_code if claim.payer else "",
                "branch_code": claim.branch.code if claim.branch else "",
                "department_code": claim.department.code if claim.department else "",
                "currency": claim.currency,
                "billed_amount": str(claim.billed_amount),
                "paid_amount": str(claim.paid_amount),
                "service_date": claim.service_date.isoformat() if claim.service_date else "",
                "status": claim.status,
                "diagnosis_codes": ",".join(diagnosis.icd_code for diagnosis in claim.diagnoses),
                "procedure_codes": ",".join(line.cpt_code for line in claim.claim_lines),
            }
            for claim in claims
        ]

    def update_claim(self, claim_id: int, fields: dict, actor_id: int | None = None):
        previous = self.repo.get(claim_id)
        if not previous:
            return None
        previous_status = previous.status

        if "branch_id" in fields or "department_id" in fields:
            BranchService(self.db, self.organization_id).validate_claim_scope(
                fields.get("branch_id", previous.branch_id),
                fields.get("department_id", previous.department_id),
            )

        if "priority" in fields and fields["priority"] is not None:
            fields = {**fields, "priority": ClaimPriority(fields["priority"])}

        claim = self.repo.update(claim_id, **fields)
        if not claim:
            return None
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(claim)

        if "status" in fields and fields["status"] and fields["status"] != previous_status:
            self.timeline.record(
                organization_id=self.organization_id,
                claim_id=claim.id,
                event_type=ClaimEventType.STATUS_CHANGED,
                description=f"Status changed from {previous_status} to {claim.status}",
                actor_id=actor_id,
                metadata={"from": previous_status, "to": claim.status},
            )
            self.db.commit()

        return self._serialize(claim)

    def delete_claim(self, claim_id: int) -> bool:
        ok = self.repo.delete(claim_id)
        if not ok:
            return False
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def _serialize(self, claim: Claim, detail: bool = False) -> dict:
        """
        Build the API-facing claim representation, merging the claim row
        with the latest denial / recovery / appeal signals that live on
        related tables — so the client never has to stitch these together.
        """
        latest_denial = max(claim.denials, key=lambda d: d.created_at, default=None)
        latest_recovery = max(claim.recovery_cases, key=lambda r: r.created_at, default=None)
        latest_appeal = (
            self.db.query(Appeal)
            .filter(Appeal.claim_id == claim.id)
            .order_by(Appeal.created_at.desc())
            .first()
        )

        data = {
            "id": claim.id,
            "organization_id": claim.organization_id,
            "branch_id": claim.branch_id,
            "department_id": claim.department_id,
            "currency": claim.currency,
            "patient_id": claim.patient_id,
            "payer_id": claim.payer_id,
            "patient_name": f"{claim.patient.first_name} {claim.patient.last_name}"
            if claim.patient
            else None,
            "payer_name": claim.payer.name if claim.payer else None,
            "claim_number": claim.claim_number,
            "status": claim.status,
            "billed_amount": claim.billed_amount,
            "paid_amount": claim.paid_amount,
            "service_date": claim.service_date,
            "provider": claim.provider,
            "priority": claim.priority.value if claim.priority else None,
            "assigned_user_id": claim.assigned_user_id,
            "assigned_user_name": (
                f"{claim.assigned_user.first_name} {claim.assigned_user.last_name}"
                if claim.assigned_user
                else None
            ),
            "ai_risk_score": float(claim.ai_risk_score)
            if claim.ai_risk_score is not None
            else None,
            "recovery_probability": (
                float(claim.recovery_probability)
                if claim.recovery_probability is not None
                else None
            ),
            "diagnosis_codes": [d.icd_code for d in claim.diagnoses],
            "procedure_codes": [line.cpt_code for line in claim.claim_lines],
            "denial_code": latest_denial.denial_code if latest_denial else None,
            "appeal_status": latest_appeal.status.value if latest_appeal else None,
            "recovery_status": latest_recovery.status.value if latest_recovery else None,
            "ai_score": float(latest_recovery.recovery_score) if latest_recovery else None,
            "analysis_status": (
                claim.analysis.analysis_status.value if claim.analysis is not None else "pending"
            ),
        }

        if detail:
            data["denials"] = claim.denials
            data["recovery_cases"] = claim.recovery_cases
            data["claim_lines"] = claim.claim_lines
            data["claim_diagnoses"] = claim.diagnoses
            data["validation_issues"] = claim.validation_issues
            data["analysis"] = (
                self.db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).first()
            )

        return data
