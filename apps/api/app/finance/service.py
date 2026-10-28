from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.finance.analytics import money, outstanding, percentage, revenue_health_score
from app.finance.forecasting import build_cash_forecast
from app.finance.models import FinanceDataDimension
from app.finance.reconciliation import build_reconciliation_summary
from app.finance.repository import FinanceRepository
from app.finance.schemas import (
    CashForecast,
    DenialLeakageItem,
    ExecutiveFinanceSnapshot,
    FinanceDataGap,
    FinanceOverview,
    PayerFinanceScorecard,
)
from app.organizations.service import OrganizationService


class FinanceIntelligenceService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.repository = FinanceRepository(db, organization_id)
        self.currency = OrganizationService(db, organization_id).get().currency

    def executive_snapshot(self) -> ExecutiveFinanceSnapshot:
        claims = self.repository.claims()
        recoverable = self.repository.recoverable_by_claim()
        payments = self.repository.payments()
        currency_payments = [row for row in payments if row[2] == self.currency]
        potential = sum((claim.billed_amount or Decimal(0) for claim in claims), Decimal(0))
        collected = sum((claim.paid_amount or Decimal(0) for claim in claims), Decimal(0))
        outstanding_total = sum(
            (
                outstanding(claim.billed_amount or Decimal(0), claim.paid_amount or Decimal(0))
                for claim in claims
            ),
            Decimal(0),
        )
        recoverable_total = sum(
            (
                min(
                    amount,
                    outstanding(claim.billed_amount or Decimal(0), claim.paid_amount or Decimal(0)),
                )
                for claim in claims
                for amount, _ in [recoverable.get(claim.id, (Decimal(0), Decimal(0)))]
            ),
            Decimal(0),
        )
        denied = sum(1 for claim in claims if claim.status == "denied")
        payment_days = [
            max((payment_date - claim.service_date).days, 0)
            for claim_id, _, _, payment_date in currency_payments
            for claim in claims
            if claim.id == claim_id
        ]
        avg_days = round(sum(payment_days) / len(payment_days), 1) if payment_days else 0.0
        collection_rate = percentage(collected, potential)
        denial_rate = round(denied / len(claims) * 100, 1) if claims else 0.0
        return ExecutiveFinanceSnapshot(
            as_of=datetime.now(UTC),
            currency=self.currency,
            todays_collections=money(
                sum(
                    (
                        amount
                        for _, amount, _, payment_date in currency_payments
                        if payment_date == date.today()
                    ),
                    Decimal(0),
                )
            ),
            potential_revenue=money(potential),
            collected_revenue=money(collected),
            outstanding_claims=money(outstanding_total),
            recoverable_revenue=money(recoverable_total),
            atlas_attributed_recoveries=money(
                self.repository.attributed_recoveries_total(self.currency)
            ),
            unclassified_leakage=money(max(outstanding_total - recoverable_total, Decimal(0))),
            collection_rate_pct=collection_rate,
            denial_rate_pct=denial_rate,
            average_payment_days=avg_days,
            hospital_revenue_health_pct=revenue_health_score(
                collection_rate, denial_rate, avg_days
            ),
            data_gaps=[
                FinanceDataGap(
                    dimension=FinanceDataDimension.DEPARTMENT,
                    reason="Claims do not yet carry a tenant-owned department reference.",
                ),
                FinanceDataGap(
                    dimension=FinanceDataDimension.CLINICIAN,
                    reason="Claims currently store provider as free text, not a governed clinician identity.",
                ),
            ],
        )

    def payer_scorecards(self) -> list[PayerFinanceScorecard]:
        results = []
        for row in self.repository.payer_rows(self.currency):
            days = row["payment_days"]
            results.append(
                PayerFinanceScorecard(
                    payer_id=row["payer_id"],
                    payer=row["payer"],
                    claim_count=row["claim_count"],
                    outstanding_amount=money(row["outstanding"]),
                    recovered_amount=money(row["recovered"]),
                    average_payment_days=round(sum(days) / len(days), 1) if days else 0.0,
                    denial_rate_pct=round(row["denied_count"] / row["claim_count"] * 100, 1)
                    if row["claim_count"]
                    else 0.0,
                )
            )
        return sorted(results, key=lambda item: item.outstanding_amount, reverse=True)

    def denial_leakage(self) -> list[DenialLeakageItem]:
        grouped: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {"amount": Decimal(0), "count": 0}
        )
        seen_claims: set[int] = set()
        for denial, claim in self.repository.denial_rows():
            if claim.id in seen_claims:
                continue
            seen_claims.add(claim.id)
            key = denial.denial_type.value
            grouped[key]["amount"] += outstanding(
                claim.billed_amount or Decimal(0), claim.paid_amount or Decimal(0)
            )
            grouped[key]["count"] += 1
        return sorted(
            [
                DenialLeakageItem(
                    denial_type=denial_type,
                    claim_count=int(values["count"]),
                    outstanding_amount=money(values["amount"]),
                )
                for denial_type, values in grouped.items()
            ],
            key=lambda item: item.outstanding_amount,
            reverse=True,
        )

    def forecast(self, days: int = 30) -> CashForecast:
        cases = list(self.repository.recoverable_by_claim().values())
        return build_cash_forecast(cases, currency=self.currency, days=days)

    def overview(self, days: int = 30) -> FinanceOverview:
        payments = self.repository.payments()
        return FinanceOverview(
            executive=self.executive_snapshot(),
            payers=self.payer_scorecards(),
            denial_leakage=self.denial_leakage(),
            forecast=self.forecast(days),
            reconciliation=build_reconciliation_summary(
                [(claim_id, amount, currency) for claim_id, amount, currency, _ in payments],
                overpaid_claim_count=self.repository.overpaid_claim_count(),
            ),
        )
