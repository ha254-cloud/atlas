from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.payer_connectivity.base import (
    AppealPackage,
    BasePayerConnector,
    StatusResult,
    SubmissionResult,
)
from app.payer_connectivity.registry import registry


class ConnectorConfigurationError(RuntimeError):
    pass


class SandboxPayerConnector(BasePayerConnector):
    provider = "sandbox"
    _statuses: dict[str, StatusResult] = {}

    def __init__(self, **config: Any) -> None:
        self.initial_status = str(config.get("initial_status", "In Medical Review"))
        paid_amount = config.get("paid_amount")
        self.paid_amount = Decimal(str(paid_amount)) if paid_amount is not None else None

    async def submit_appeal(self, package: AppealPackage) -> SubmissionResult:
        tracking_id = f"ATLAS-{uuid4().hex[:12].upper()}"
        self._statuses[tracking_id] = StatusResult(
            external_status=self.initial_status,
            paid_amount=self.paid_amount,
            message="Sandbox payer accepted the appeal package",
            payload={"claim_number": package.claim_number},
        )
        return SubmissionResult(
            external_tracking_id=tracking_id,
            external_status="Submitted",
            payload={"claim_number": package.claim_number, "environment": "sandbox"},
        )

    async def check_status(self, external_tracking_id: str) -> StatusResult:
        result = self._statuses.get(external_tracking_id)
        if result is None:
            raise LookupError(f"Sandbox tracking id {external_tracking_id} was not found")
        return result

    async def upload_documents(
        self, external_tracking_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {"tracking_id": external_tracking_id, "uploaded": len(documents)}

    async def download_response(self, external_tracking_id: str) -> dict[str, Any]:
        result = await self.check_status(external_tracking_id)
        return result.payload


class _UnconfiguredVendorConnector(BasePayerConnector):
    def __init__(self, **config: Any) -> None:
        self.config = config

    def _unavailable(self) -> ConnectorConfigurationError:
        return ConnectorConfigurationError(
            f"{self.provider} appeal transport requires vendor credentials and a certified payload profile"
        )

    async def submit_appeal(self, package: AppealPackage) -> SubmissionResult:
        raise self._unavailable()

    async def check_status(self, external_tracking_id: str) -> StatusResult:
        raise self._unavailable()

    async def upload_documents(
        self, external_tracking_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        raise self._unavailable()

    async def download_response(self, external_tracking_id: str) -> dict[str, Any]:
        raise self._unavailable()


class AvailityPayerConnector(_UnconfiguredVendorConnector):
    provider = "availity"


class WaystarPayerConnector(_UnconfiguredVendorConnector):
    provider = "waystar"


class OfficeAllyPayerConnector(_UnconfiguredVendorConnector):
    provider = "office_ally"


class FHIRPayerConnector(_UnconfiguredVendorConnector):
    provider = "fhir"


def register_connectors() -> None:
    registry.register("sandbox", SandboxPayerConnector)
    registry.register("availity", AvailityPayerConnector)
    registry.register("waystar", WaystarPayerConnector)
    registry.register("office_ally", OfficeAllyPayerConnector)
    registry.register("fhir", FHIRPayerConnector)
