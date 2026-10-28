from sqlalchemy.orm import Session

from app.integrations.fhir.base import FHIRConnector
from app.integrations.fhir.registry import get_fhir_connector
from app.mcp.schemas.responses import MCPResponse
from app.mcp.tools import BaseTool


class SyncClaimsTool(BaseTool):
    """
    Sync claims from an EHR/payer via a FHIR connector.

    The connector is resolved by name so this tool is provider-agnostic:
        connector="epic"     -> EpicFHIRConnector
        connector="athena"   -> AthenaFHIRConnector
        connector="cerner"   -> CernerFHIRConnector

    This avoids vendor lock-in — adding a new source is a connector
    registration, not a change to this tool.
    """

    name = "sync_claims"

    async def execute(
        self,
        db: Session,
        organization_id: int,
        connector: str = "epic",
        since_days: int = 30,
        **_,
    ) -> MCPResponse:
        fhir: FHIRConnector = get_fhir_connector(connector)

        claims = await fhir.fetch_claims(
            organization_id=organization_id,
            since_days=since_days,
        )

        return self._ok(
            {
                "connector": connector,
                "synced_count": len(claims),
                "claims": claims,
            }
        )
