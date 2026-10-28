from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.payer_statistics import PayerStatistics
from app.recovery.repository import RecoveryRepository
from app.recovery.schemas import FinancialPositionRead, ForecastBucketRead, RecoveryForecastRead

_MONEY = Decimal("0.01")


class RecoveryForecastService:
    def __init__(
        self,
        db: Session,
        organization_id: int,
        currency: str,
        default_collection_days: int,
    ) -> None:
        self.db = db
        self.organization_id = organization_id
        self.currency = currency
        self.default_collection_days = default_collection_days
        self.repository = RecoveryRepository(db, organization_id)

    def forecast(
        self,
        positions: list[FinancialPositionRead],
        *,
        horizon_days: int,
    ) -> RecoveryForecastRead:
        today = date.today()
        horizon_end = today + timedelta(days=horizon_days)
        buckets: dict[tuple[date, date], Decimal] = defaultdict(Decimal)
        weighted_days = Decimal(0)
        expected_total = Decimal(0)
        evidence_count = 0
        for position in positions:
            if position.expected_recovery_amount <= 0:
                continue
            claim = self.repository.get_claim(position.claim_id)
            if claim is None:
                continue
            statistics = (
                self.db.query(PayerStatistics)
                .filter(
                    PayerStatistics.organization_id == self.organization_id,
                    PayerStatistics.payer_id == claim.payer_id,
                )
                .first()
            )
            collection_days = (
                max(int(round(statistics.average_payment_time)), 1)
                if statistics and statistics.average_payment_time is not None
                else self.default_collection_days
            )
            if statistics and statistics.sample_size > 0:
                evidence_count += 1
            collection_date = today + timedelta(days=collection_days)
            if collection_date > horizon_end:
                continue
            bucket_start = collection_date - timedelta(days=collection_date.weekday())
            bucket_end = min(bucket_start + timedelta(days=6), horizon_end)
            buckets[(bucket_start, bucket_end)] += position.expected_recovery_amount
            expected_total += position.expected_recovery_amount
            weighted_days += Decimal(collection_days) * position.expected_recovery_amount
        outstanding_total = sum((item.outstanding_amount for item in positions), Decimal(0))
        expected_days = float(weighted_days / expected_total) if expected_total else 0.0
        confidence = (
            Decimal(evidence_count) / Decimal(len(positions)) * Decimal(100)
            if positions
            else Decimal(0)
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        return RecoveryForecastRead(
            currency=self.currency,
            outstanding_amount=outstanding_total.quantize(_MONEY),
            expected_recovery_amount=expected_total.quantize(_MONEY),
            expected_collection_days=round(expected_days, 1),
            confidence_pct=confidence,
            buckets=[
                ForecastBucketRead(
                    start_date=start,
                    end_date=end,
                    expected_amount=amount.quantize(_MONEY),
                )
                for (start, end), amount in sorted(buckets.items())
            ],
            as_of=datetime.now(UTC),
        )
