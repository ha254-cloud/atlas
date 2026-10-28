"""
Change Healthcare connector.

Authentication: OAuth2 (client credentials)
Protocol:       Change Healthcare REST API + X12 EDI
Primary use:    Claim submission, remittance (835), claim status (277),
                real-time eligibility

Note: Change Healthcare (now Optum) is one of the largest clearinghouses
in the US.  The 2024 cyberattack highlighted the systemic risk of this
dependency — Atlas should treat it as one of several clearinghouse options,
not a single point of failure.

Full implementation deferred to clearinghouse sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class ChangeHealthcareConnector(BaseConnector):
    provider = "change"

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
        self.base_url = base_url or "https://sandbox.apigw.changehealthcare.com"

    async def authenticate(self) -> None:
        if not self._access_token:
            raise AuthenticationError(
                "Change Healthcare access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise NotImplementedError("Change Healthcare claim sync — coming in clearinghouse sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        return []

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise NotImplementedError(
            "Change Healthcare ERA sync (X12 835) — coming in clearinghouse sprint"
        )

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "v1",
        }
