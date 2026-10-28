from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.models.user import User
from app.recovery.models import (
    RecoveryAccount,
    RecoveryEventType,
    RecoveryLifecycleEvent,
    RecoveryLifecycleState,
)
from app.recovery.repository import RecoveryRepository
from app.recovery.schemas import FinancialPositionRead

_MONEY = Decimal("0.01")
_ALLOWED_TRANSITIONS: dict[RecoveryLifecycleState, set[RecoveryLifecycleState]] = {
    RecoveryLifecycleState.DRAFT: {
        RecoveryLifecycleState.SUBMITTED,
        RecoveryLifecycleState.OUTSTANDING,
    },
    RecoveryLifecycleState.SUBMITTED: {
        RecoveryLifecycleState.UNDER_REVIEW,
        RecoveryLifecycleState.APPROVED,
        RecoveryLifecycleState.OUTSTANDING,
        RecoveryLifecycleState.APPEAL,
    },
    RecoveryLifecycleState.UNDER_REVIEW: {
        RecoveryLifecycleState.APPROVED,
        RecoveryLifecycleState.PARTIALLY_PAID,
        RecoveryLifecycleState.OUTSTANDING,
        RecoveryLifecycleState.APPEAL,
    },
    RecoveryLifecycleState.APPROVED: {
        RecoveryLifecycleState.PARTIALLY_PAID,
        RecoveryLifecycleState.OUTSTANDING,
        RecoveryLifecycleState.RECOVERED,
    },
    RecoveryLifecycleState.PARTIALLY_PAID: {
        RecoveryLifecycleState.OUTSTANDING,
        RecoveryLifecycleState.APPEAL,
        RecoveryLifecycleState.RECOVERED,
    },
    RecoveryLifecycleState.OUTSTANDING: {
        RecoveryLifecycleState.APPEAL,
        RecoveryLifecycleState.PARTIALLY_PAID,
        RecoveryLifecycleState.RECOVERED,
        RecoveryLifecycleState.WRITTEN_OFF,
    },
    RecoveryLifecycleState.APPEAL: {
        RecoveryLifecycleState.UNDER_REVIEW,
        RecoveryLifecycleState.PARTIALLY_PAID,
        RecoveryLifecycleState.OUTSTANDING,
        RecoveryLifecycleState.RECOVERED,
        RecoveryLifecycleState.WRITTEN_OFF,
    },
    RecoveryLifecycleState.RECOVERED: {
        RecoveryLifecycleState.CLOSED,
        RecoveryLifecycleState.OUTSTANDING,
    },
    RecoveryLifecycleState.WRITTEN_OFF: {
        RecoveryLifecycleState.CLOSED,
        RecoveryLifecycleState.OUTSTANDING,
    },
    RecoveryLifecycleState.CLOSED: {RecoveryLifecycleState.OUTSTANDING},
}


class RecoveryLifecycleService:
    def __init__(self, db: Session, organization_id: int, currency: str) -> None:
        self.db = db
        self.organization_id = organization_id
        self.currency = currency
        self.repository = RecoveryRepository(db, organization_id)

    def open_account(
        self,
        claim_id: int,
        *,
        actor_id: int | None,
        actor_type: str,
        reason: str,
        correlation_id: str | None,
    ) -> RecoveryAccount:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        existing = self.repository.get_account_for_claim(claim_id)
        if existing is not None:
            return existing
        account = RecoveryAccount(
            organization_id=self.organization_id,
            claim_id=claim_id,
            currency=self.currency,
            state=RecoveryLifecycleState.DRAFT,
            version=1,
        )
        self.db.add(account)
        self.db.flush()
        self._append_event(
            account,
            event_type=RecoveryEventType.ACCOUNT_OPENED,
            from_state=None,
            to_state=account.state,
            reason=reason,
            actor_id=actor_id,
            actor_type=actor_type,
            correlation_id=correlation_id,
            idempotency_key=f"recovery-account:{claim_id}",
        )
        return account

    def position(self, account: RecoveryAccount) -> FinancialPositionRead:
        claim = self.repository.get_claim(account.claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        original = Decimal(claim.billed_amount or 0).quantize(_MONEY)
        recovered = sum(
            (
                Decimal(item.recovered_amount)
                for item in self.repository.verified_recoveries(claim.id)
            ),
            Decimal(0),
        ).quantize(_MONEY)
        contract_adjustment = self.repository.allocation_total(
            account.id, RecoveryEventType.CONTRACT_ADJUSTMENT
        ).quantize(_MONEY)
        write_off = (
            self.repository.allocation_total(account.id, RecoveryEventType.WRITE_OFF_APPROVED)
            - self.repository.allocation_total(account.id, RecoveryEventType.WRITE_OFF_REVERSED)
        ).quantize(_MONEY)
        outstanding = max(
            original - recovered - contract_adjustment - write_off, Decimal(0)
        ).quantize(_MONEY)
        recovery_case = self.repository.latest_case(claim.id)
        probability = Decimal(recovery_case.recovery_score if recovery_case else 0).quantize(_MONEY)
        recoverable = min(
            outstanding,
            Decimal(recovery_case.estimated_value if recovery_case else 0),
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        return FinancialPositionRead(
            claim_id=claim.id,
            account_id=account.id,
            currency=account.currency,
            original_amount=original,
            recovered_amount=recovered,
            outstanding_amount=outstanding,
            recoverable_amount=recoverable,
            expected_recovery_amount=recoverable,
            contract_adjustment_amount=contract_adjustment,
            written_off_amount=write_off,
            recovery_probability_pct=probability,
            fully_accounted=outstanding == 0,
            as_of=datetime.now(UTC),
        )

    def transition(
        self,
        account: RecoveryAccount,
        *,
        to_state: RecoveryLifecycleState,
        expected_version: int,
        reason: str,
        actor_id: int,
        correlation_id: str | None,
        idempotency_key: str,
    ) -> RecoveryAccount:
        duplicate = self._idempotent_event(account, idempotency_key)
        if duplicate is not None:
            return account
        self._check_version(account, expected_version)
        if to_state not in _ALLOWED_TRANSITIONS[account.state]:
            raise ValueError(
                f"Invalid recovery transition: {account.state.value} -> {to_state.value}"
            )
        position = self.position(account)
        if to_state == RecoveryLifecycleState.CLOSED and not position.fully_accounted:
            raise ValueError("Recovery account cannot close while a balance remains unaccounted")
        if to_state == RecoveryLifecycleState.RECOVERED and not position.fully_accounted:
            raise ValueError("Recovered state requires a fully accounted financial position")
        previous = account.state
        event_type = (
            RecoveryEventType.ACCOUNT_CLOSED
            if to_state == RecoveryLifecycleState.CLOSED
            else RecoveryEventType.ACCOUNT_REOPENED
            if previous == RecoveryLifecycleState.CLOSED
            else RecoveryEventType.STATE_TRANSITIONED
        )
        account.state = to_state
        account.version += 1
        account.closed_at = datetime.now(UTC) if to_state == RecoveryLifecycleState.CLOSED else None
        self._append_event(
            account,
            event_type=event_type,
            from_state=previous,
            to_state=to_state,
            reason=reason,
            actor_id=actor_id,
            actor_type="user",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        return account

    def allocate(
        self,
        account: RecoveryAccount,
        *,
        event_type: RecoveryEventType,
        amount: Decimal,
        reason_code: str,
        reason: str,
        expected_version: int,
        actor_id: int,
        correlation_id: str | None,
        idempotency_key: str,
    ) -> RecoveryAccount:
        duplicate = self._idempotent_event(account, idempotency_key)
        if duplicate is not None:
            return account
        self._check_version(account, expected_version)
        position = self.position(account)
        if event_type == RecoveryEventType.WRITE_OFF_REVERSED:
            if amount > position.written_off_amount:
                raise ValueError("Write-off reversal exceeds the approved written-off amount")
        elif amount > position.outstanding_amount:
            raise ValueError("Allocation exceeds the outstanding balance")
        previous = account.state
        if event_type == RecoveryEventType.WRITE_OFF_APPROVED:
            account.state = RecoveryLifecycleState.WRITTEN_OFF
        elif event_type == RecoveryEventType.WRITE_OFF_REVERSED:
            account.state = RecoveryLifecycleState.OUTSTANDING
        account.version += 1
        self._append_event(
            account,
            event_type=event_type,
            from_state=previous,
            to_state=account.state,
            amount=amount.quantize(_MONEY, rounding=ROUND_HALF_UP),
            reason_code=reason_code,
            reason=reason,
            actor_id=actor_id,
            actor_type="user",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        return account

    def assign(
        self,
        account: RecoveryAccount,
        *,
        assigned_user_id: int | None,
        expected_version: int,
        reason: str,
        actor_id: int,
        correlation_id: str | None,
        idempotency_key: str,
    ) -> RecoveryAccount:
        duplicate = self._idempotent_event(account, idempotency_key)
        if duplicate is not None:
            return account
        self._check_version(account, expected_version)
        if assigned_user_id is not None:
            user = (
                self.db.query(User)
                .filter(
                    User.id == assigned_user_id,
                    User.organization_id == self.organization_id,
                )
                .first()
            )
            if user is None:
                raise ValueError("Assigned user not found")
        previous_user_id = account.assigned_user_id
        account.assigned_user_id = assigned_user_id
        account.version += 1
        self._append_event(
            account,
            event_type=RecoveryEventType.RESPONSIBILITY_ASSIGNED,
            from_state=account.state,
            to_state=account.state,
            reason=reason,
            actor_id=actor_id,
            actor_type="user",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            event_metadata={
                "before_assigned_user_id": previous_user_id,
                "after_assigned_user_id": assigned_user_id,
            },
        )
        return account

    def synchronize_verified_recoveries(
        self,
        account: RecoveryAccount,
        *,
        actor_id: int | None,
        actor_type: str,
        correlation_id: str | None,
    ) -> RecoveryAccount:
        for recovery in self.repository.verified_recoveries(account.claim_id):
            key = f"verified-recovery:{recovery.id}"
            if self.repository.event_for_idempotency(key) is not None:
                continue
            previous = account.state
            self._append_event(
                account,
                event_type=RecoveryEventType.PAYMENT_CONFIRMED,
                from_state=previous,
                to_state=previous,
                amount=recovery.recovered_amount,
                reason="Verified cash recovery recorded in the lifecycle timeline",
                actor_id=actor_id or recovery.verified_by,
                actor_type=actor_type,
                source_type="recovery",
                source_id=recovery.id,
                correlation_id=correlation_id,
                idempotency_key=key,
            )
            account.version += 1
        position = self.position(account)
        if position.recovered_amount > 0 and position.outstanding_amount > 0:
            account.state = RecoveryLifecycleState.PARTIALLY_PAID
        elif position.recovered_amount > 0 and position.fully_accounted:
            account.state = RecoveryLifecycleState.RECOVERED
        return account

    @staticmethod
    def _check_version(account: RecoveryAccount, expected_version: int) -> None:
        if account.version != expected_version:
            raise ValueError(
                f"Recovery account version conflict: expected {expected_version}, current {account.version}"
            )

    def _idempotent_event(
        self, account: RecoveryAccount, idempotency_key: str
    ) -> RecoveryLifecycleEvent | None:
        event = self.repository.event_for_idempotency(idempotency_key)
        if event is not None and event.account_id != account.id:
            raise ValueError("Idempotency key belongs to another recovery account")
        return event

    def _append_event(
        self,
        account: RecoveryAccount,
        *,
        event_type: RecoveryEventType,
        from_state: RecoveryLifecycleState | None,
        to_state: RecoveryLifecycleState,
        reason: str,
        actor_id: int | None,
        actor_type: str,
        correlation_id: str | None,
        idempotency_key: str,
        amount: Decimal | None = None,
        reason_code: str | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
        event_metadata: dict | None = None,
    ) -> RecoveryLifecycleEvent:
        event = RecoveryLifecycleEvent(
            organization_id=self.organization_id,
            account_id=account.id,
            sequence=self.repository.next_sequence(account.id),
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            amount=amount,
            currency=account.currency,
            reason_code=reason_code,
            reason=reason.strip(),
            actor_id=actor_id,
            actor_type=actor_type,
            source_type=source_type,
            source_id=source_id,
            occurred_at=datetime.now(UTC),
            idempotency_key=idempotency_key,
            event_metadata=event_metadata or {},
        )
        self.db.add(event)
        self.db.flush()
        if actor_id is not None:
            AuditService(self.db).log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.RECOVERY_LIFECYCLE_EVENT_RECORDED,
                entity="recovery_account",
                entity_id=account.id,
                metadata={
                    "before": {"state": from_state.value if from_state else None},
                    "after": {
                        "state": to_state.value,
                        "event_id": event.id,
                        "event_type": event_type.value,
                        "amount": str(amount) if amount is not None else None,
                        "currency": account.currency,
                    },
                    "reason": reason.strip(),
                    "correlation_id": correlation_id,
                },
            )
        return event
