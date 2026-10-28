from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.denial import Denial
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus


def _priority(score: Decimal) -> str:
    if score >= Decimal("90"):
        return "critical"
    if score >= Decimal("70"):
        return "high"
    if score >= Decimal("40"):
        return "medium"
    return "low"


class RecoveryWorkspaceRepository:
    """
    Read-optimised repository for the recovery workspace.
    One JOIN query returns all data needed to render the work queue — no N+1.
    """

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def get_workspace_cases(
        self,
        status_filter: list[str] | None = None,
        priority_filter: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        active_statuses = status_filter or [
            RecoveryStatus.OPEN.value,
            RecoveryStatus.IN_PROGRESS.value,
            RecoveryStatus.APPEALED.value,
        ]

        # Single join — all the data the workspace needs
        query = (
            self.db.query(
                RecoveryCase,
                Claim,
                Payer,
                Patient,
                Denial,
            )
            .join(Claim, RecoveryCase.claim_id == Claim.id)
            .join(Payer, Claim.payer_id == Payer.id)
            .join(Patient, Claim.patient_id == Patient.id)
            .outerjoin(
                Denial,
                (Denial.claim_id == Claim.id) & (Denial.organization_id == self.organization_id),
            )
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_(active_statuses),
            )
        )

        if search:
            query = query.filter(Claim.claim_number.ilike(f"%{search}%"))

        if priority_filter:
            thresholds = {
                "critical": (Decimal("90"), Decimal("100")),
                "high": (Decimal("70"), Decimal("89.99")),
                "medium": (Decimal("40"), Decimal("69.99")),
                "low": (Decimal("0"), Decimal("39.99")),
            }
            if priority_filter in thresholds:
                lo, hi = thresholds[priority_filter]
                query = query.filter(
                    RecoveryCase.recovery_score >= lo,
                    RecoveryCase.recovery_score <= hi,
                )

        total = query.count()

        # Sort by expected recoverable revenue (balance * probability), not
        # by the 0-100 recovery_score alone — the score caps its amount
        # factor at a $1,000 balance, so on its own it would under-rank
        # large-dollar claims relative to small ones with a similar score.
        rows = query.order_by(RecoveryCase.estimated_value.desc()).offset(offset).limit(limit).all()

        results = []
        seen_claim_ids: set[int] = set()  # deduplicate multi-denial joins

        for rc, claim, payer, patient, denial in rows:
            if rc.claim_id in seen_claim_ids:
                continue
            seen_claim_ids.add(rc.claim_id)

            priority = _priority(rc.recovery_score)
            balance = float(claim.billed_amount) - float(claim.paid_amount)

            results.append(
                {
                    "id": rc.id,
                    "claim_id": claim.id,
                    "claim_number": claim.claim_number,
                    "payer_name": payer.name,
                    "payer_code": payer.payer_code,
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "patient_mrn": patient.medical_record_number,
                    "service_date": str(claim.service_date) if claim.service_date else None,
                    "billed_amount": float(claim.billed_amount),
                    "paid_amount": float(claim.paid_amount),
                    "balance": balance,
                    "estimated_recovery": float(rc.estimated_value),
                    "recovery_score": float(rc.recovery_score),
                    "confidence": min(100, int(rc.recovery_score)),
                    "priority": priority,
                    "status": rc.status.value,
                    "recommendation": rc.recommendation,
                    "ai_review": rc.ai_review.value if rc.ai_review else None,
                    "recovered_amount": float(rc.recovered_amount) if rc.recovered_amount else None,
                    "invoice_generated": rc.invoice_generated,
                    "denial": {
                        "denial_code": denial.denial_code,
                        "denial_type": denial.denial_type.value
                        if denial and denial.denial_type
                        else None,
                        "description": denial.description if denial else None,
                    }
                    if denial
                    else None,
                }
            )

        return results, total

    def get_summary(self) -> dict:
        rows = (
            self.db.query(
                RecoveryCase.recovery_score,
                RecoveryCase.estimated_value,
                RecoveryCase.status,
            )
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_(
                    [
                        RecoveryStatus.OPEN,
                        RecoveryStatus.IN_PROGRESS,
                        RecoveryStatus.APPEALED,
                    ]
                ),
            )
            .all()
        )

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        open_count = in_progress_count = 0
        total_recovery = Decimal("0")

        for score, estimated, status in rows:
            p = _priority(score)
            counts[p] += 1
            total_recovery += estimated
            if status == RecoveryStatus.OPEN:
                open_count += 1
            elif status == RecoveryStatus.IN_PROGRESS:
                in_progress_count += 1

        return {
            **counts,
            "total": sum(counts.values()),
            "estimated_recovery": float(total_recovery),
            "open_cases": open_count,
            "in_progress_cases": in_progress_count,
        }
