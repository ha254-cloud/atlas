from abc import ABC, abstractmethod
from typing import Any


class FHIRConnector(ABC):
    """
    Provider-agnostic interface for fetching FHIR resources.

    Every EHR connector implements this interface:
        EpicFHIRConnector
        AthenaFHIRConnector
        eClinicalWorksFHIRConnector
        CernerFHIRConnector

    The sync_claims MCP tool depends on this interface, not on any
    specific vendor — so swapping or adding EHRs never touches tool code.
    """

    @abstractmethod
    async def fetch_claims(
        self,
        organization_id: int,
        since_days: int = 30,
    ) -> list[dict[str, Any]]:
        """Return a list of normalized claim dicts."""
        ...

    @abstractmethod
    async def fetch_patient(
        self,
        organization_id: int,
        patient_id: str,
    ) -> dict[str, Any]:
        """Return a normalized patient dict (FHIR Patient resource)."""
        ...
