from collections import Counter

from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.payer_statistics import PayerStatistics


class PayerAnalytics:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def aggregate(self, payer_id: int) -> dict:
        payer = (
            self.db.query(Payer)
            .filter(
                Payer.id == payer_id,
                Payer.organization_id == self.organization_id,
            )
            .first()
        )
        if payer is None:
            raise ValueError("Payer not found")
        claims = (
            self.db.query(Claim)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.payer_id == payer_id,
            )
            .all()
        )
        claim_ids = [claim.id for claim in claims]
        denials = (
            self.db.query(Denial)
            .filter(
                Denial.organization_id == self.organization_id,
                Denial.claim_id.in_(claim_ids),
            )
            .all()
            if claim_ids
            else []
        )
        appeals = (
            self.db.query(Appeal)
            .filter(
                Appeal.organization_id == self.organization_id,
                Appeal.claim_id.in_(claim_ids),
            )
            .all()
            if claim_ids
            else []
        )
        statistics = (
            self.db.query(PayerStatistics)
            .filter(
                PayerStatistics.organization_id == self.organization_id,
                PayerStatistics.payer_id == payer_id,
            )
            .first()
        )
        denial_counts = Counter(denial.denial_type.value for denial in denials)
        accepted = [appeal for appeal in appeals if appeal.status == AppealStatus.ACCEPTED]
        document_counts: Counter[str] = Counter()
        for appeal in accepted:
            document_counts.update(
                set((appeal.required_documents or []) + (appeal.attachments or []))
            )
        return {
            "sample_size": len(claims),
            "denial_rate": (len({denial.claim_id for denial in denials}) / len(claims) * 100)
            if claims
            else None,
            "average_payment_days": statistics.average_payment_time if statistics else None,
            "appeal_success_rate": statistics.appeal_success_rate if statistics else None,
            "average_recovery": statistics.average_recovery if statistics else None,
            "common_denial_reasons": [
                {"reason": reason, "count": count, "rate": count / len(denials) * 100}
                for reason, count in denial_counts.most_common(5)
            ],
            "successful_appeal_documents": [
                {
                    "document": document,
                    "successful_appeals": count,
                    "rate": count / len(accepted) * 100,
                }
                for document, count in document_counts.most_common(10)
            ]
            if accepted
            else [],
        }
