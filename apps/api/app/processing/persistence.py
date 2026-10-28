from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.branches.models import Branch, Department
from app.canonical.claim import CanonicalClaim
from app.models.claim import Claim
from app.models.claim_diagnosis import ClaimDiagnosis
from app.models.claim_line import ClaimLine
from app.models.claim_validation_issue import ClaimValidationIssue
from app.models.denial import Denial, DenialType
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.processing.exceptions import DuplicateClaimError, PersistenceError
from app.validation.issue import ValidationIssue


class PersistenceLayer:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def upsert_patient(self, canonical: CanonicalClaim) -> Patient:
        # Only dedupe by MRN when one is actually present. Matching on an
        # empty string would cause every MRN-less claim to collapse onto the
        # same patient record (empty string == empty string), silently
        # merging distinct patients' claims together.
        patient = None
        if canonical.patient_mrn:
            patient = (
                self.db.query(Patient)
                .filter(
                    Patient.organization_id == self.organization_id,
                    Patient.medical_record_number == canonical.patient_mrn,
                )
                .first()
            )

        if not patient:
            patient = Patient(
                organization_id=self.organization_id,
                first_name=canonical.patient_first_name or "Unknown",
                last_name=canonical.patient_last_name or "Unknown",
                medical_record_number=canonical.patient_mrn or f"IMP-{uuid4().hex[:10].upper()}",
                date_of_birth=date(1900, 1, 1),
            )
            self.db.add(patient)
            self.db.flush()

        return patient

    def upsert_payer(self, canonical: CanonicalClaim) -> Payer:
        payer = (
            self.db.query(Payer)
            .filter(
                Payer.organization_id == self.organization_id,
                Payer.payer_code == canonical.payer_code,
            )
            .first()
        )

        if not payer:
            payer = Payer(
                organization_id=self.organization_id,
                name=canonical.payer_code,
                payer_code=canonical.payer_code,
            )
            self.db.add(payer)
            self.db.flush()

        return payer

    def create_claim(self, canonical: CanonicalClaim, patient_id: int, payer_id: int) -> Claim:
        existing = (
            self.db.query(Claim)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.claim_number == canonical.claim_number,
            )
            .first()
        )
        if existing:
            raise DuplicateClaimError(
                f"Claim {canonical.claim_number} already exists for this organization"
            )

        organization_currency = (
            self.db.query(Organization.currency)
            .filter(Organization.id == self.organization_id)
            .scalar()
            or "KES"
        )
        branch = None
        if canonical.branch_code:
            branch = (
                self.db.query(Branch)
                .filter(
                    Branch.organization_id == self.organization_id,
                    Branch.code == canonical.branch_code,
                    Branch.is_active.is_(True),
                )
                .first()
            )
            if branch is None:
                raise PersistenceError(f"Unknown branch code {canonical.branch_code}")
        department = None
        if canonical.department_code:
            if branch is None:
                raise PersistenceError("department_code requires branch_code")
            department = (
                self.db.query(Department)
                .filter(
                    Department.organization_id == self.organization_id,
                    Department.branch_id == branch.id,
                    Department.code == canonical.department_code,
                    Department.is_active.is_(True),
                )
                .first()
            )
            if department is None:
                raise PersistenceError(f"Unknown department code {canonical.department_code}")
        currency = (canonical.currency or organization_currency).upper()
        if len(currency) != 3 or not currency.isalpha():
            raise PersistenceError("currency must be a three-letter ISO 4217 code")
        claim = Claim(
            organization_id=self.organization_id,
            branch_id=branch.id if branch else None,
            department_id=department.id if department else None,
            currency=currency,
            patient_id=patient_id,
            payer_id=payer_id,
            claim_number=canonical.claim_number,
            status=canonical.status,
            billed_amount=canonical.billed_amount,
            paid_amount=canonical.paid_amount,
            service_date=canonical.service_date,
            authorization_number=canonical.authorization_number,
            authorization_expiration=canonical.authorization_expiration,
        )
        self.db.add(claim)
        self.db.flush()
        return claim

    def create_claim_lines(self, claim_id: int, canonical: CanonicalClaim) -> list[ClaimLine]:
        lines = []
        line_count = len(canonical.procedure_codes)
        for i, proc_code in enumerate(canonical.procedure_codes):
            modifier = canonical.modifiers[i] if i < len(canonical.modifiers) else None
            line = ClaimLine(
                claim_id=claim_id,
                cpt_code=proc_code,
                modifier=modifier,
                units=1,
                charge_amount=canonical.billed_amount / line_count,
            )
            self.db.add(line)
            lines.append(line)
        self.db.flush()
        return lines

    def create_claim_diagnoses(
        self, claim_id: int, canonical: CanonicalClaim
    ) -> list[ClaimDiagnosis]:
        diagnoses = []
        for i, icd_code in enumerate(canonical.diagnosis_codes):
            diagnosis = ClaimDiagnosis(
                claim_id=claim_id,
                icd_code=icd_code,
                is_primary=(i == 0),
            )
            self.db.add(diagnosis)
            diagnoses.append(diagnosis)
        self.db.flush()
        return diagnoses

    def save_validation_issues(
        self, claim_id: int, issues: list[ValidationIssue]
    ) -> list[ClaimValidationIssue]:
        """Persist non-blocking (warning) validation findings for later review."""
        rows = []
        for issue in issues:
            row = ClaimValidationIssue(
                organization_id=self.organization_id,
                claim_id=claim_id,
                code=issue.code,
                severity=issue.severity,
                field=issue.field,
                message=issue.message,
            )
            self.db.add(row)
            rows.append(row)
        if rows:
            self.db.flush()
        return rows

    def create_denial_if_present(self, claim_id: int, canonical: CanonicalClaim) -> Denial | None:
        """
        Persist the payer's stated denial reason, if the source file provided
        one. The real category (DenialType) isn't known yet at import time —
        that's what AI denial classification is for — so this is recorded as
        OTHER and left for the AI Claim Recovery Engine to refine.
        """
        if not canonical.denial_code and not canonical.denial_reason:
            return None

        denial = Denial(
            organization_id=self.organization_id,
            claim_id=claim_id,
            denial_code=canonical.denial_code or "UNKNOWN",
            denial_type=DenialType.OTHER,
            description=canonical.denial_reason or "No reason provided by source file.",
        )
        self.db.add(denial)
        self.db.flush()
        return denial

    def commit_batch(self):
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise PersistenceError(str(exc))
