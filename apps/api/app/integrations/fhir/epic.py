from typing import Any

from app.integrations.fhir.base import FHIRConnector


class EpicFHIRConnector(FHIRConnector):
    """
    Epic on FHIR connector.
    Implements SMART on FHIR OAuth2 + R4 endpoints.
    Stub — full implementation in FHIR sprint.
    """

    async def fetch_claims(
        self,
        organization_id: int,
        since_days: int = 30,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Epic FHIR integration coming in FHIR sprint")

    async def fetch_patient(
        self,
        organization_id: int,
        patient_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("Epic FHIR integration coming in FHIR sprint")
