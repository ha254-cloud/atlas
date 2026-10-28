"""
eClinicalWorks connector.

Authentication: OAuth2 (eCW proprietary)
API:            FHIR R4 (limited) + eCW REST API
Quirks:         FHIR support is newer and incomplete. Many billing workflows
                require the proprietary API. Patient matching is non-standard.

Full implementation deferred to FHIR sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class EClinicalWorksConnector(BaseConnector):
    provider = "ecw"

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
        self.base_url = base_url or "https://api.eclinicalworks.com"

    async def authenticate(self) -> None:
        if not self._access_token:
            raise AuthenticationError(
                "eClinicalWorks access token not available. Complete OAuth flow before syncing."
            )

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise NotImplementedError("eClinicalWorks claim sync — coming in FHIR sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        raise NotImplementedError("eClinicalWorks patient sync — coming in FHIR sprint")

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise NotImplementedError("eClinicalWorks payment sync — coming in FHIR sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._access_token),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "v1",
        }
