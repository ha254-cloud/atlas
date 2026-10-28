from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment
from app.models.submission import SubmissionStatus


@dataclass(frozen=True)
class SubmissionPayload:
    appeal_id: int
    claim_id: int
    claim_number: str
    payer_code: str
    appeal_text: str
    attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResponse:
    external_reference: str
    status: SubmissionStatus
    message: str | None = None
    paid_amount: Decimal | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class PayerConnector(ABC):
    provider: str

    @abstractmethod
    async def submit(self, payload: SubmissionPayload) -> SubmissionResponse:
        raise NotImplementedError

    @abstractmethod
    async def status(self, external_reference: str) -> SubmissionResponse:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, external_reference: str) -> SubmissionResponse:
        raise NotImplementedError

    async def submit_appeal(self, payload: SubmissionPayload) -> SubmissionResponse:
        return await self.submit(payload)

    async def check_status(self, external_reference: str) -> SubmissionResponse:
        return await self.status(external_reference)

    async def submit_claim(self, payload: dict[str, Any]) -> SubmissionResponse:
        raise NotImplementedError(f"{self.provider} does not support direct claim submission")

    async def download_payment_report(self, **filters: Any) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{self.provider} does not support payment report download")

    async def download_denial_report(self, **filters: Any) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{self.provider} does not support denial report download")


SubmissionConnector = PayerConnector


class BaseConnector(ABC):
    """
    Every integration connector implements this interface.
    Atlas business logic never calls vendor APIs directly — it always goes
    through a connector.  Swapping or adding a vendor requires only a new
    class here; nothing else in the platform changes.
    """

    # Subclasses must declare their provider name.
    provider: str

    @abstractmethod
    async def authenticate(self) -> None:
        """
        Obtain or refresh credentials for the external system.
        Must be idempotent — safe to call before every sync.
        """
        ...

    @abstractmethod
    async def sync_claims(self) -> list[CanonicalClaim]:
        """
        Fetch claims from the external system.
        Returns CanonicalClaim objects — never raw vendor payloads.
        """
        ...

    @abstractmethod
    async def sync_patients(self) -> list[CanonicalPatient]:
        """
        Fetch patients from the external system.
        Returns CanonicalPatient objects.
        """
        ...

    @abstractmethod
    async def sync_payments(self) -> list[CanonicalPayment]:
        """
        Fetch payment / remittance data from the external system.
        Returns CanonicalPayment objects.
        """
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Verify the connection is live.
        Must return at minimum: {"connected": bool, "latency_ms": int}.
        """
        ...
