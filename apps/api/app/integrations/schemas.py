from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.integrations.contracts import (
    ConnectorCredentials,
    CredentialContract,
    APIKeyCredentials,
    OAuth2Credentials,
    SFTPCredentials,
    validate_provider_credentials,
)
from app.models.integration import IntegrationStatus


class IntegrationCreate(BaseModel):
    provider: str = Field(..., description="Connector name, e.g. 'epic', 'athena', 'cerner'")
    settings: Optional[dict] = None
    credentials: ConnectorCredentials | None = None
    # Optional — many connectors are configured first and authorized later
    # via a separate OAuth flow. Never echoed back in responses.
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

    @model_validator(mode="after")
    def validate_provider_settings(self):
        if self.credentials:
            validate_provider_credentials(self.provider, self.credentials)
        if self.credentials and (self.access_token or self.refresh_token):
            raise ValueError("Use credentials or legacy token fields, not both")
        if self.provider.lower() != "sftp":
            return self

        settings = self.settings or {}
        plaintext_secrets = {"password", "private_key"}.intersection(settings)
        if plaintext_secrets:
            raise ValueError("SFTP secrets must use the encrypted credential fields")

        missing = [
            field
            for field in ("hostname", "username", "remote_path")
            if not settings.get(field)
        ]
        if missing:
            raise ValueError(f"Missing SFTP settings: {', '.join(missing)}")
        if not settings.get("host_key_sha256") and not settings.get("known_hosts_path"):
            raise ValueError("SFTP host key fingerprint is required")
        if not self.credentials and not self.access_token and not self.refresh_token:
            raise ValueError("SFTP password or private key is required")
        return self

    def credential_contract(self) -> CredentialContract | None:
        if self.credentials:
            return self.credentials
        if not self.access_token and not self.refresh_token:
            return None
        if self.provider.lower() == "sftp":
            return SFTPCredentials(password=self.access_token, private_key=self.refresh_token)
        if self.provider.lower() == "waystar":
            if self.refresh_token:
                raise ValueError("Waystar credentials accept one API key")
            return APIKeyCredentials(api_key=self.access_token)
        return OAuth2Credentials(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
        )


class IntegrationCredentialRotate(BaseModel):
    credentials: ConnectorCredentials
    reason: str = Field(min_length=3, max_length=500)


class IntegrationCredentialVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    credential_kind: str
    fingerprints: dict[str, str]
    expires_at: Optional[datetime]
    changed_by: int
    reason: str
    correlation_id: str
    created_at: datetime

class IntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    status: IntegrationStatus
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    claims_imported_count: int
    settings: Optional[dict]
    created_at: datetime

class IntegrationHealth(BaseModel):
    connected: bool
    latency_ms: Optional[int] = None
    provider: str
    status: IntegrationStatus
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
