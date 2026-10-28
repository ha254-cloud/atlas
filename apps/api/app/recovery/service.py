from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.organizations.service import OrganizationService
from app.recovery.attribution import RecoveryTimelineService
from app.recovery.billing import RecoveryBillingService
from app.recovery.forecasting import RecoveryForecastService
from app.recovery.lifecycle import RecoveryLifecycleService
from app.recovery.models import RecoveryAccount, RecoveryEventType
from app.recovery.repository import RecoveryRepository
from app.recovery.schemas import (
    BillingReadinessRead,
    FinancialAllocationRequest,
    LifecycleTransitionRequest,
    RecoveryAccountRead,
    RecoveryForecastRead,
    RecoveryLifecycleRead,
    RecoveryPortfolioRead,
    ResponsibilityRequest,
)
from app.recovery.scoring import RecoveryOpportunityScorer

_MONEY = Decimal("0.01")


class RevenueRecoveryService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.currency = OrganizationService(db, organization_id).get().currency
        self.repository = RecoveryRepository(db, organization_id)
        self.lifecycle = RecoveryLifecycleService(db, organization_id, self.currency)
        self.scorer = RecoveryOpportunityScorer(
            estimated_cost=settings.RECOVERY_DEFAULT_COST_TO_RECOVER,
            critical_expected_amount=settings.RECOVERY_CRITICAL_EXPECTED_AMOUNT,
            high_expected_amount=settings.RECOVERY_HIGH_EXPECTED_AMOUNT,
        )

    def open_account(
        self,
        claim_id: int,
        *,
        actor_id: int,
        reason: str,
        correlation_id: str | None,
    ) -> RecoveryLifecycleRead:
        account = self.lifecycle.open_account(
            claim_id,
            actor_id=actor_id,
            actor_type="user",
            reason=reason,
            correlation_id=correlation_id,
        )
        self.lifecycle.synchronize_verified_recoveries(
            account,
            actor_id=actor_id,
            actor_type="user",
            correlation_id=correlation_id,
        )
        self.db.commit()
        self.db.refresh(account)
        return self._detail(account)

    def get(self, account_id: int) -> RecoveryLifecycleRead:
        return self._detail(self._get_account(account_id))

    def transition(
        self,
        account_id: int,
        payload: LifecycleTransitionRequest,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> RecoveryLifecycleRead:
        account = self.lifecycle.transition(
            self._get_account(account_id),
            to_state=payload.to_state,
            expected_version=payload.expected_version,
            reason=payload.reason,
            actor_id=actor_id,
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
        )
        self.db.commit()
        self.db.refresh(account)
        return self._detail(account)

    def allocate(
        self,
        account_id: int,
        payload: FinancialAllocationRequest,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> RecoveryLifecycleRead:
        event_types = {
            "contract_adjustment": RecoveryEventType.CONTRACT_ADJUSTMENT,
            "write_off": RecoveryEventType.WRITE_OFF_APPROVED,
            "write_off_reversal": RecoveryEventType.WRITE_OFF_REVERSED,
        }
        account = self.lifecycle.allocate(
            self._get_account(account_id),
            event_type=event_types[payload.allocation_type],
            amount=payload.amount,
            reason_code=payload.reason_code,
            reason=payload.reason,
            expected_version=payload.expected_version,
            actor_id=actor_id,
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
        )
        self.db.commit()
        self.db.refresh(account)
        return self._detail(account)

    def assign(
        self,
        account_id: int,
        payload: ResponsibilityRequest,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> RecoveryLifecycleRead:
        account = self.lifecycle.assign(
            self._get_account(account_id),
            assigned_user_id=payload.assigned_user_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
            actor_id=actor_id,
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
        )
        self.db.commit()
        self.db.refresh(account)
        return self._detail(account)

    def synchronize(
        self,
        account_id: int,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> RecoveryLifecycleRead:
        account = self.lifecycle.synchronize_verified_recoveries(
            self._get_account(account_id),
            actor_id=actor_id,
            actor_type="user",
            correlation_id=correlation_id,
        )
        self.db.commit()
        self.db.refresh(account)
        return self._detail(account)

    def forecast(self, horizon_days: int) -> RecoveryForecastRead:
        positions = [
            self.lifecycle.position(account) for account in self.repository.list_accounts()
        ]
        return RecoveryForecastService(
            self.db,
            self.organization_id,
            self.currency,
            settings.RECOVERY_DEFAULT_COLLECTION_DAYS,
        ).forecast(positions, horizon_days=horizon_days)

    def portfolio(self) -> RecoveryPortfolioRead:
        accounts = self.repository.list_accounts()
        positions = [self.lifecycle.position(account) for account in accounts]
        original = sum((item.original_amount for item in positions), Decimal(0))
        recovered = sum((item.recovered_amount for item in positions), Decimal(0))
        outstanding = sum((item.outstanding_amount for item in positions), Decimal(0))
        recoverable = sum((item.recoverable_amount for item in positions), Decimal(0))
        high = sum(
            (
                item.expected_recovery_amount
                for item in positions
                if item.recovery_probability_pct >= Decimal("70")
            ),
            Decimal(0),
        )
        medium = sum(
            (
                item.expected_recovery_amount
                for item in positions
                if Decimal("40") <= item.recovery_probability_pct < Decimal("70")
            ),
            Decimal(0),
        )
        low = sum(
            (
                item.expected_recovery_amount
                for item in positions
                if item.recovery_probability_pct < Decimal("40")
            ),
            Decimal(0),
        )
        verified_recoveries = [
            recovery
            for account in accounts
            for recovery in self.repository.verified_recoveries(account.claim_id)
        ]
        atlas_recoveries = sum((item.recovered_amount for item in verified_recoveries), Decimal(0))
        atlas_fees = sum((item.atlas_fee_amount for item in verified_recoveries), Decimal(0))
        roi = (
            (atlas_recoveries - atlas_fees) / atlas_fees * Decimal(100) if atlas_fees > 0 else None
        )
        rri = recoverable / outstanding * Decimal(100) if outstanding > 0 else Decimal(0)
        return RecoveryPortfolioRead(
            currency=self.currency,
            original_amount=original.quantize(_MONEY),
            recovered_amount=recovered.quantize(_MONEY),
            outstanding_amount=outstanding.quantize(_MONEY),
            recoverable_amount=recoverable.quantize(_MONEY),
            expected_recovery_amount=recoverable.quantize(_MONEY),
            high_probability_amount=high.quantize(_MONEY),
            medium_probability_amount=medium.quantize(_MONEY),
            low_probability_amount=low.quantize(_MONEY),
            recoverable_revenue_index_pct=rri.quantize(_MONEY, rounding=ROUND_HALF_UP),
            atlas_recoveries=atlas_recoveries.quantize(_MONEY),
            atlas_fees=atlas_fees.quantize(_MONEY),
            return_on_investment_pct=(
                roi.quantize(_MONEY, rounding=ROUND_HALF_UP) if roi is not None else None
            ),
            account_count=len(accounts),
            as_of=datetime.now(UTC),
        )

    def billing_readiness(self, period_start: date, period_end: date) -> BillingReadinessRead:
        if period_end < period_start:
            raise ValueError("period_end must be on or after period_start")
        return RecoveryBillingService(self.db, self.organization_id, self.currency).readiness(
            period_start, period_end
        )

    def _detail(self, account: RecoveryAccount) -> RecoveryLifecycleRead:
        position = self.lifecycle.position(account)
        events = RecoveryTimelineService(self.db, self.organization_id, self.currency).timeline(
            account, synchronize=False
        )
        return RecoveryLifecycleRead(
            account=RecoveryAccountRead.model_validate(account),
            position=position,
            opportunity=self.scorer.score(position),
            events=events,
        )

    def _get_account(self, account_id: int) -> RecoveryAccount:
        account = self.repository.get_account(account_id)
        if account is None:
            raise ValueError("Recovery account not found")
        return account
