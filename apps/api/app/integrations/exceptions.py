class IntegrationError(Exception):
    """Base class for all integration errors."""


class ConnectorNotFoundError(IntegrationError):
    """Raised when an unknown connector name is requested."""


class AuthenticationError(IntegrationError):
    """Raised when a connector fails to authenticate with the external system."""


class SyncError(IntegrationError):
    """Raised when a data synchronization operation fails."""


class TokenExpiredError(AuthenticationError):
    """Raised when an OAuth token has expired and cannot be refreshed."""


class HealthCheckError(IntegrationError):
    """Raised when a connector health check reports an unhealthy state."""
