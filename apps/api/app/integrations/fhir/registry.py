from app.integrations.fhir.athena import AthenaFHIRConnector
from app.integrations.fhir.base import FHIRConnector
from app.integrations.fhir.epic import EpicFHIRConnector

_CONNECTORS: dict[str, FHIRConnector] = {
    "epic": EpicFHIRConnector(),
    "athena": AthenaFHIRConnector(),
}


def get_fhir_connector(name: str) -> FHIRConnector:
    connector = _CONNECTORS.get(name.lower())
    if connector is None:
        supported = list(_CONNECTORS.keys())
        raise ValueError(f"Unknown FHIR connector '{name}'. Supported: {supported}")
    return connector
