"""
Waystar clearinghouse connector.

Authentication: API key
Protocol:       X12 EDI (837/835/277) via Waystar REST API
Primary use:    Claim submission, ERA (835) retrieval, claim status (277)

Waystar is a clearinghouse, not an EHR — it sits between Atlas and payers.
Payments flow back through here as X12 835 files.

Full implementation deferred to clearinghouse sprint.
"""

import time
from typing import Any

from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class WaystarConnector(BaseConnector):
    provider = "waystar"

    def __init__(
        self,
        organization_id: int,
        api_key: str | None = None,
        base_url: str | None = None,
        **_,
    ):
        self.organization_id = organization_id
        self._api_key = api_key
        self.base_url = base_url or "https://api.waystar.com/v1"

    async def authenticate(self) -> None:
        if not self._api_key:
            raise AuthenticationError("Waystar API key not configured.")

    async def sync_claims(self) -> list[CanonicalClaim]:
        # Will parse X12 837 responses and map to CanonicalClaim
        raise NotImplementedError("Waystar claim sync — coming in clearinghouse sprint")

    async def sync_patients(self) -> list[CanonicalPatient]:
        # Patients not directly available from clearinghouses
        return []

    async def sync_payments(self) -> list[CanonicalPayment]:
        # Will parse X12 835 (ERA) and map to CanonicalPayment
        raise NotImplementedError("Waystar payment sync (X12 835) — coming in clearinghouse sprint")

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected": bool(self._api_key),
            "provider": self.provider,
            "latency_ms": latency_ms,
            "api_version": "v1",
        }
