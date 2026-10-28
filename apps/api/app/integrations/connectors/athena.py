"""
Athena Health connector.

Authentication: OAuth2 (Athena proprietary + FHIR R4 where available)
API:            Athena REST + FHIR R4 endpoints
Quirks:         Practice ID required in every request path.
                Separate endpoints for professional and facility claims.

Full implementation deferred to FHIR sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class AthenaConnector(BaseConnector):
    provider = "athena"

    def __init__(
        self,
        organization_id: int,
        access_token: str | None = None,
        refresh_token: str | None = None,
        practice_id: str | None = None,
        base_url: str | None = None,
        **_,
    ):
        self.organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self.practice_id = practice_id
        self.base_url = base_url or "https://api.athenahealth.com"

    async def authenticate(self) -> None:
        if not self._access_token:
            raise AuthenticationError(
                "Athena access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise NotImplementedError("Athena claim sync — coming in FHIR sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        raise NotImplementedError("Athena patient sync — coming in FHIR sprint")

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise NotImplementedError("Athena payment sync — coming in FHIR sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "v1",
        }
