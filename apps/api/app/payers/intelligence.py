from sqlalchemy.orm import Session

from app.payers.analytics import PayerAnalytics
from app.payers.schemas import PayerIntelligenceRead


class PayerIntelligenceService:
    def __init__(self, db: Session, organization_id: int):
        self.analytics = PayerAnalytics(db, organization_id)

    def get(self, payer_id: int, *, minimum_sample_size: int) -> PayerIntelligenceRead:
        facts = self.analytics.aggregate(payer_id)
        sample_size = facts["sample_size"]
        if sample_size < minimum_sample_size:
            confidence = "insufficient"
        elif sample_size < minimum_sample_size * 5:
            confidence = "emerging"
        else:
            confidence = "established"
        recommendations: list[str] = []
        if confidence != "insufficient" and facts["common_denial_reasons"]:
            reason = facts["common_denial_reasons"][0]
            recommendations.append(
                f"Review {reason['reason'].replace('_', ' ')} controls; it represents "
                f"{reason['rate']:.1f}% of recorded denials for this payer."
            )
        if confidence != "insufficient" and facts["successful_appeal_documents"]:
            documents = ", ".join(
                item["document"] for item in facts["successful_appeal_documents"][:3]
            )
            recommendations.append(
                f"Successful appeals commonly included: {documents}. Confirm relevance before submission."
            )
        return PayerIntelligenceRead(
            payer_id=payer_id,
            confidence=confidence,
            recommendations=recommendations,
            **facts,
        )
