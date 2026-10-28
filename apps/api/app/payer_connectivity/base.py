from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class AppealPackage:
    appeal_id: int
    claim_number: str
    payer_code: str
    appeal_text: str
    attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResult:
    external_tracking_id: str
    external_status: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StatusResult:
    external_status: str
    message: str | None = None
    paid_amount: Decimal | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class BasePayerConnector(ABC):
    provider: str

    @abstractmethod
    async def submit_appeal(self, package: AppealPackage) -> SubmissionResult:
        raise NotImplementedError

    @abstractmethod
    async def check_status(self, external_tracking_id: str) -> StatusResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_documents(
        self, external_tracking_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def download_response(self, external_tracking_id: str) -> dict[str, Any]:
        raise NotImplementedError
