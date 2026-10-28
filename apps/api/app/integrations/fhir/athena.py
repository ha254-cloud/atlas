from typing import Any

from app.integrations.fhir.base import FHIRConnector


class AthenaFHIRConnector(FHIRConnector):
    """
    Athena Health FHIR connector.
    Stub — full implementation in FHIR sprint.
    """

    async def fetch_claims(
        self,
        organization_id: int,
        since_days: int = 30,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Athena FHIR integration coming in FHIR sprint")

    async def fetch_patient(
        self,
        organization_id: int,
        patient_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("Athena FHIR integration coming in FHIR sprint")
