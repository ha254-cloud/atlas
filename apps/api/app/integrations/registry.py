from app.integrations.base import BaseConnector, PayerConnector
from app.integrations.contracts import PROVIDER_CREDENTIAL_KINDS
from app.integrations.exceptions import ConnectorNotFoundError


class IntegrationRegistry:
    """
    Central registry for all connector implementations.
    Connectors self-register at import time; the manager dispatches by name.

    Usage:
        registry.register("epic", EpicConnector)
        connector = registry.get("epic", config)
    """

    def __init__(self):
        self._connectors: dict[str, type[BaseConnector]] = {}

    def register(self, provider: str, connector_class: type[BaseConnector]) -> None:
        if provider.lower() not in PROVIDER_CREDENTIAL_KINDS:
            raise ValueError(f"Connector '{provider}' must declare a credential contract")
        self._connectors[provider.lower()] = connector_class

    def get(self, provider: str, **kwargs) -> BaseConnector:
        cls = self._connectors.get(provider.lower())
        if cls is None:
            supported = list(self._connectors.keys())
            raise ConnectorNotFoundError(
                f"No connector registered for '{provider}'. "
                f"Supported providers: {supported}"
            )
        return cls(**kwargs)

    def list_providers(self) -> list[str]:
        return list(self._connectors.keys())


# Module-level singleton
registry = IntegrationRegistry()


class SubmissionConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, type[PayerConnector]] = {}

    def register(self, name: str, connector_class: type[PayerConnector]) -> None:
        self._connectors[name.lower()] = connector_class

    def get(self, name: str, **config) -> PayerConnector:
        connector_class = self._connectors.get(name.lower())
        if connector_class is None:
            supported = sorted(self._connectors)
            raise ConnectorNotFoundError(
                f"No submission connector registered for '{name}'. "
                f"Supported providers: {supported}"
            )
        return connector_class(**config)

    def list_providers(self) -> list[str]:
        return sorted(self._connectors)


submission_registry = SubmissionConnectorRegistry()
