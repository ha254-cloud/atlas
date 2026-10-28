from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CredentialContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OAuth2Credentials(CredentialContract):
    kind: Literal["oauth2"] = "oauth2"
    access_token: str | None = Field(default=None, min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def require_token(self):
        if not self.access_token and not self.refresh_token:
            raise ValueError("OAuth2 credentials require an access or refresh token")
        return self


class APIKeyCredentials(CredentialContract):
    kind: Literal["api_key"] = "api_key"
    api_key: str = Field(min_length=1)


class SFTPCredentials(CredentialContract):
    kind: Literal["sftp"] = "sftp"
    password: str | None = Field(default=None, min_length=1)
    private_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_authentication_secret(self):
        if bool(self.password) == bool(self.private_key):
            raise ValueError("SFTP credentials require exactly one of password or private_key")
        return self


ConnectorCredentials = Annotated[
    OAuth2Credentials | APIKeyCredentials | SFTPCredentials,
    Field(discriminator="kind"),
]


PROVIDER_CREDENTIAL_KINDS: dict[str, str] = {
    "epic": "oauth2",
    "athena": "oauth2",
    "cerner": "oauth2",
    "ecw": "oauth2",
    "availity": "oauth2",
    "change": "oauth2",
    "waystar": "api_key",
    "sftp": "sftp",
}


def validate_provider_credentials(provider: str, credentials: CredentialContract) -> None:
    expected_kind = PROVIDER_CREDENTIAL_KINDS.get(provider.lower())
    if expected_kind is None:
        raise ValueError(f"No credential contract is registered for provider '{provider}'")
    if credentials.kind != expected_kind:
        raise ValueError(
            f"Provider '{provider}' requires {expected_kind} credentials, "
            f"not {credentials.kind}"
        )


def credential_storage_values(
    credentials: CredentialContract,
) -> tuple[str | None, str | None, datetime | None]:
    if isinstance(credentials, OAuth2Credentials):
        return credentials.access_token, credentials.refresh_token, credentials.expires_at
    if isinstance(credentials, APIKeyCredentials):
        return credentials.api_key, None, None
    if isinstance(credentials, SFTPCredentials):
        return credentials.password, credentials.private_key, None
    raise TypeError(f"Unsupported credential contract: {type(credentials).__name__}")


def credential_fingerprints(credentials: CredentialContract) -> dict[str, str]:
    primary, secondary, _ = credential_storage_values(credentials)
    fingerprints = {}
    if primary:
        fingerprints["primary"] = sha256(primary.encode()).hexdigest()[:16]
    if secondary:
        fingerprints["secondary"] = sha256(secondary.encode()).hexdigest()[:16]
    return fingerprints
