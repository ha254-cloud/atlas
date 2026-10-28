from app.payer_connectivity.base import BasePayerConnector


class PayerConnectorNotFoundError(LookupError):
    pass


class PayerConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, type[BasePayerConnector]] = {}

    def register(self, name: str, connector: type[BasePayerConnector]) -> None:
        self._connectors[name.lower()] = connector

    def get(self, name: str, **config) -> BasePayerConnector:
        connector = self._connectors.get(name.lower())
        if connector is None:
            raise PayerConnectorNotFoundError(f"Payer connector '{name}' is not registered")
        return connector(**config)

    def list(self) -> list[str]:
        return sorted(self._connectors)


registry = PayerConnectorRegistry()
