from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.appeal_submission import AppealSubmission, AppealSubmissionStatus


class PayerConnectivityAnalytics:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def executive_summary(self) -> dict:
        rows = self.db.query(AppealSubmission).filter(
            AppealSubmission.organization_id == self.organization_id
        ).all()
        today = datetime.utcnow().date()
        response_days = [
            (row.updated_at - row.submitted_at).days
            for row in rows
            if row.submitted_at is not None
            and row.status in {
                AppealSubmissionStatus.ACCEPTED,
                AppealSubmissionStatus.REJECTED,
                AppealSubmissionStatus.DENIED,
                AppealSubmissionStatus.PAID,
            }
        ]
        paid = [row for row in rows if row.status == AppealSubmissionStatus.PAID]
        submitted = [row for row in rows if row.status == AppealSubmissionStatus.SUBMITTED]
        waiting = [row for row in rows if row.status in {
            AppealSubmissionStatus.ACKNOWLEDGED,
            AppealSubmissionStatus.IN_REVIEW,
            AppealSubmissionStatus.UNDER_REVIEW,
            AppealSubmissionStatus.ADDITIONAL_INFO_REQUIRED,
        }]
        denied = [row for row in rows if row.status in {
            AppealSubmissionStatus.DENIED,
            AppealSubmissionStatus.REJECTED,
        }]
        recovered = Decimal("0")
        for row in paid:
            payload = row.response_payload or {}
            if payload.get("paid_amount") is not None:
                recovered += Decimal(str(payload["paid_amount"]))
        return {
            "submitted_today": sum(1 for row in rows if row.submitted_at and row.submitted_at.date() == today),
            "acknowledged": sum(1 for row in rows if row.status == AppealSubmissionStatus.ACKNOWLEDGED),
            "pending": sum(1 for row in rows if row.status in {
                AppealSubmissionStatus.PENDING,
                AppealSubmissionStatus.SUBMITTING,
                AppealSubmissionStatus.SUBMITTED,
                AppealSubmissionStatus.UNDER_REVIEW,
                AppealSubmissionStatus.ADDITIONAL_INFO_REQUIRED,
            }),
            "paid": len(paid),
            "submitted": len(submitted),
            "waiting": len(waiting),
            "denied": len(denied),
            "recovered": float(recovered),
            "average_response_days": round(sum(response_days) / len(response_days), 1) if response_days else None,
            "average_processing_time": round(sum(response_days) / len(response_days), 1) if response_days else None,
            "recovery_pipeline": {
                status.value: sum(1 for row in rows if row.status == status)
                for status in AppealSubmissionStatus
            },
            "follow_ups_due": sum(
                1 for row in rows
                if row.next_follow_up_at is not None
                and row.next_follow_up_at <= datetime.utcnow()
                and row.status in {
                    AppealSubmissionStatus.SUBMITTED,
                    AppealSubmissionStatus.ACKNOWLEDGED,
                    AppealSubmissionStatus.UNDER_REVIEW,
                }
            ),
        }
