"""
Oracle Health (Cerner) connector.

Authentication: SMART on FHIR (OAuth2)
API:            FHIR R4
Quirks:         Tenant ID required. Millennium platform quirks around
                EOB and coverage resources.

Full implementation deferred to FHIR sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class CernerConnector(BaseConnector):
    provider = "cerner"

    def __init__(
        self,
        organization_id: int,
        access_token: str | None = None,
        refresh_token: str | None = None,
        tenant_id: str | None = None,
        base_url: str | None = None,
        **_,
    ):
        self.organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self.tenant_id = tenant_id
        self.base_url = base_url or "https://fhir-myrecord.cerner.com/r4"

    async def authenticate(self) -> None:
        if not self._access_token:
            raise AuthenticationError(
                "Cerner access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise NotImplementedError("Cerner claim sync — coming in FHIR sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        raise NotImplementedError("Cerner patient sync — coming in FHIR sprint")

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise NotImplementedError("Cerner payment sync — coming in FHIR sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "R4",
        }
