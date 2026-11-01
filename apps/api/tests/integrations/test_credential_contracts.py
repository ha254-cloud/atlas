import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from app.integrations.contracts import (
    PROVIDER_CREDENTIAL_KINDS,
    APIKeyCredentials,
    ConnectorCredentials,
    OAuth2ClientCredentials,
    OAuth2Credentials,
    SFTPCredentials,
)
from app.integrations.exceptions import IntegrationError
from app.integrations.manager import IntegrationManager
from app.integrations.registry import registry

credential_adapter = TypeAdapter(ConnectorCredentials)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"kind": "oauth2", "access_token": "token"}, OAuth2Credentials),
        (
            {"kind": "oauth2_client_credentials", "client_secret": "secret"},
            OAuth2ClientCredentials,
        ),
        ({"kind": "api_key", "api_key": "key"}, APIKeyCredentials),
        ({"kind": "sftp", "password": "password"}, SFTPCredentials),
    ],
)
def test_connector_credentials_select_typed_contract(payload, expected_type):
    assert isinstance(credential_adapter.validate_python(payload), expected_type)


def test_oauth2_contract_preserves_timezone_aware_expiry():
    expires_at = datetime(2026, 8, 1, 12, tzinfo=UTC)

    credentials = credential_adapter.validate_python(
        {"kind": "oauth2", "refresh_token": "refresh", "expires_at": expires_at}
    )

    assert credentials.expires_at == expires_at


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "oauth2"},
        {"kind": "oauth2_client_credentials", "client_secret": ""},
        {"kind": "api_key", "api_key": ""},
        {"kind": "sftp"},
        {"kind": "sftp", "password": "password", "private_key": "private-key"},
        {"kind": "api_key", "api_key": "key", "unexpected": "value"},
    ],
)
def test_connector_credentials_reject_invalid_contract(payload):
    with pytest.raises(ValidationError):
        credential_adapter.validate_python(payload)


def test_every_registered_connector_declares_credential_contract():
    assert set(registry.list_providers()) <= set(PROVIDER_CREDENTIAL_KINDS)


def test_waystar_primary_secret_maps_to_api_key(monkeypatch):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.integrations.encryption import encrypt_token

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        row = SimpleNamespace(
            organization_id=1,
            provider="waystar",
            encrypted_access_token=encrypt_token("api-key"),
            encrypted_refresh_token=None,
            settings=None,
        )

        assert IntegrationManager(None)._build_config(row)["api_key"] == "api-key"
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_sha_primary_secret_maps_to_oauth_client_secret():
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.integrations.encryption import encrypt_token

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        row = SimpleNamespace(
            organization_id=1,
            provider="sha",
            encrypted_access_token=encrypt_token("client-secret"),
            encrypted_refresh_token=None,
            settings={"client_id": "atlas-client"},
        )

        config = IntegrationManager(None)._build_config(row)
        assert config["client_secret"] == "client-secret"
        assert config["client_id"] == "atlas-client"
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_health_check_retries_timeout_and_returns_controlled_error(monkeypatch):
    from app.core.config import settings

    class SlowConnector:
        calls = 0

        async def authenticate(self):
            self.calls += 1
            await asyncio.sleep(0.02)

        async def health_check(self):
            return {"connected": True}

    connector = SlowConnector()
    row = SimpleNamespace(
        id=1,
        organization_id=7,
        provider="epic",
        token_expires_at=None,
        encrypted_access_token=None,
        encrypted_refresh_token=None,
        settings=None,
    )
    manager = IntegrationManager(None)
    monkeypatch.setattr(manager, "get_integration", lambda *_: row)
    monkeypatch.setattr(registry, "get", lambda *_args, **_kwargs: connector)
    monkeypatch.setattr(settings, "INTEGRATION_HEALTH_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(settings, "INTEGRATION_HEALTH_RETRIES", 1)

    with pytest.raises(IntegrationError, match="after 2 attempt"):
        asyncio.run(manager.health_check(1, 7, correlation_id="test-correlation"))

    assert connector.calls == 2
