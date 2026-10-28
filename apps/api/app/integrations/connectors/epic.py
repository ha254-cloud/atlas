"""
Epic on FHIR connector.

Authentication: SMART on FHIR (OAuth2 + PKCE)
API:            FHIR R4
Quirks:         Requires client credentials registered in Epic's App Orchard.
                ExplanationOfBenefit resource used for claim data.

Full implementation deferred to FHIR sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class EpicConnector(BaseConnector):
    provider = "epic"

    def __init__(
        self,
        organization_id: int,
        access_token: str | None = None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        base_url: str | None = None,
        **_,
    ):
        self.organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self.client_id = client_id
        self.base_url = base_url or "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"

    async def authenticate(self) -> None:
        # SMART on FHIR token refresh — full implementation in FHIR sprint
        if not self._access_token:
            raise AuthenticationError(
                "Epic access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        # Will query FHIR ExplanationOfBenefit resources
        raise NotImplementedError("Epic claim sync — coming in FHIR sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        # Will query FHIR Patient resources
        raise NotImplementedError("Epic patient sync — coming in FHIR sprint")

    async def sync_payments(self) -> list[CanonicalPayment]:
        # Will query FHIR PaymentReconciliation resources
        raise NotImplementedError("Epic payment sync — coming in FHIR sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        # Will call FHIR metadata endpoint
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "R4",
        }
