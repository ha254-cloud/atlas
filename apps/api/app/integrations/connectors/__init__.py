from app.integrations.base import BaseConnector
from app.integrations.connectors.athena import AthenaConnector
from app.integrations.connectors.availity import AvailityConnector
from app.integrations.connectors.cerner import CernerConnector
from app.integrations.connectors.change import ChangeHealthcareConnector
from app.integrations.connectors.ecw import EClinicalWorksConnector
from app.integrations.connectors.epic import EpicConnector
from app.integrations.connectors.sftp import SFTPConnector
from app.integrations.connectors.waystar import WaystarConnector
from app.integrations.registry import registry

# Register all connectors at import time
registry.register("epic", EpicConnector)
registry.register("athena", AthenaConnector)
registry.register("cerner", CernerConnector)
registry.register("ecw", EClinicalWorksConnector)
registry.register("waystar", WaystarConnector)
registry.register("availity", AvailityConnector)
registry.register("change", ChangeHealthcareConnector)
registry.register("sftp", SFTPConnector)

__all__ = [
    "BaseConnector",
    "EpicConnector",
    "AthenaConnector",
    "CernerConnector",
    "EClinicalWorksConnector",
    "WaystarConnector",
    "AvailityConnector",
    "ChangeHealthcareConnector",
    "SFTPConnector",
    "registry",
]
