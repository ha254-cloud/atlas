import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.integrations.base import SubmissionConnector, SubmissionPayload, SubmissionResponse
from app.integrations.registry import submission_registry
from app.models.submission import SubmissionStatus


class MockConnector(SubmissionConnector):
    provider = "mock"
    _responses: dict[str, SubmissionResponse] = {}

    def __init__(self, **config: Any) -> None:
        status = config.get("initial_status", SubmissionStatus.SUBMITTED)
        self.initial_status = self._coerce_status(status)
        amount = config.get("paid_amount")
        self.paid_amount = Decimal(str(amount)) if amount is not None else None

    async def submit(self, payload: SubmissionPayload) -> SubmissionResponse:
        await asyncio.sleep(0)
        external_reference = f"ATLAS-{uuid4().hex[:12].upper()}"
        polled = SubmissionResponse(
            external_reference=external_reference,
            status=self.initial_status,
            message="Mock connector status response",
            paid_amount=self.paid_amount,
            payload={"claim_number": payload.claim_number},
        )
        self._responses[external_reference] = polled
        return SubmissionResponse(
            external_reference=external_reference,
            status=SubmissionStatus.SUBMITTED,
            message="Mock connector accepted the appeal",
            payload={"claim_number": payload.claim_number, "environment": "mock"},
        )

    async def status(self, external_reference: str) -> SubmissionResponse:
        await asyncio.sleep(0)
        response = self._responses.get(external_reference)
        if response is None:
            raise LookupError(f"Mock tracking id {external_reference} was not found")
        return response

    async def cancel(self, external_reference: str) -> SubmissionResponse:
        await asyncio.sleep(0)
        if external_reference not in self._responses:
            raise LookupError(f"Mock tracking id {external_reference} was not found")
        response = SubmissionResponse(
            external_reference=external_reference,
            status=SubmissionStatus.FAILED,
            message="Mock submission cancelled",
        )
        self._responses[external_reference] = response
        return response

    @staticmethod
    def _coerce_status(value: Any) -> SubmissionStatus:
        if isinstance(value, SubmissionStatus):
            return value
        normalized = str(value).strip().lower().replace(" ", "_")
        aliases = {
            "in_medical_review": SubmissionStatus.UNDER_REVIEW,
            "accepted": SubmissionStatus.ACKNOWLEDGED,
        }
        return aliases.get(normalized, SubmissionStatus(normalized))


submission_registry.register("mock", MockConnector)
submission_registry.register("sandbox", MockConnector)
