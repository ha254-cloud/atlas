"""
Availity clearinghouse connector.

Authentication: OAuth2 (client credentials)
Protocol:       Availity REST API + X12 EDI
Primary use:    Eligibility verification, claim status (277), ERA (835)

Full implementation deferred to clearinghouse sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class AvailityConnector(BaseConnector):
    provider = "availity"

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
        self.base_url = base_url or "https://api.availity.com/availity/v1"

    async def authenticate(self) -> None:
        if not self._access_token:
            raise AuthenticationError(
                "Availity access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise NotImplementedError("Availity claim sync — coming in clearinghouse sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        return []

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise NotImplementedError("Availity ERA sync (X12 835) — coming in clearinghouse sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "v1",
        }
