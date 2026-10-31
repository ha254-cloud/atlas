from decimal import Decimal
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """
    Atlas Application Settings
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Atlas"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    SEED_DEMO_DATA: bool = False

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # PostgreSQL
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: str = ""

    # Redis
    REDIS_HOST: str = ""
    REDIS_PORT: int = 6379
    REDIS_URL: str = ""

    # Transactional domain-event outbox
    EVENT_OUTBOX_BATCH_SIZE: int = 100
    EVENT_OUTBOX_MAX_ATTEMPTS: int = 5
    EVENT_OUTBOX_BASE_RETRY_SECONDS: int = 5
    EVENT_OUTBOX_MAX_RETRY_SECONDS: int = 300
    EVENT_OUTBOX_LEASE_SECONDS: int = 60
    EVENT_OUTBOX_DISPATCH_INTERVAL_SECONDS: int = 5

    # AI
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4.1"
    # Cheaper/faster model for high-volume classification-style tasks
    # (claim analysis, denial/coding/eligibility checks) — see
    # app/ai/gateway.py's per-task model selection.
    AI_MODEL_FAST: str = "gpt-4.1-mini"
    OPENAI_API_KEY: str = ""
    COPILOT_ENABLED: bool = True
    AI_APPEAL_POLICY_SOURCE_MAX_CHARS: int = 2500
    AI_APPEAL_POLICY_CONTEXT_MAX_CHARS: int = 8000

    # Integrations — Fernet key for encrypting OAuth tokens at rest.
    # Generate with: python -c
    # "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    INTEGRATION_ENCRYPTION_KEY: str = ""
    INTEGRATION_HEALTH_TIMEOUT_SECONDS: float = 10.0
    INTEGRATION_HEALTH_RETRIES: int = 1

    # Used to build links in transactional emails (verification, invites, password reset)
    FRONTEND_URL: str = "http://localhost:3000"

    # SMTP — when SMTP_HOST is unset, EmailService falls back to logging
    # what would be sent (keeps auth flows fully testable without a real
    # mail server configured).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@atlas.health"
    SMTP_USE_TLS: bool = True

    # Document storage — "local" keeps evidence on disk under
    # DOCUMENT_LOCAL_STORAGE_ROOT; "s3" routes through S3Storage using the
    # DOCUMENT_S3_* settings below.
    DOCUMENT_STORAGE_BACKEND: str = "local"
    DOCUMENT_LOCAL_STORAGE_ROOT: str = "uploads/documents"
    DOCUMENT_S3_BUCKET: str = ""
    DOCUMENT_S3_PREFIX: str = "documents"
    DOCUMENT_S3_REGION: str = ""
    DOCUMENT_S3_ENDPOINT_URL: str = ""
    DOCUMENT_S3_SERVER_SIDE_ENCRYPTION: str = "AES256"
    DOCUMENT_S3_KMS_KEY_ID: str = ""

    # ClamAV-compatible malware scanning (INSTREAM protocol) applied to every
    # uploaded document before it is stored. Failure-closed: scan failures or
    # an unavailable scanner must prevent storage, never bypass it.
    DOCUMENT_MALWARE_SCAN_ENABLED: bool = False
    DOCUMENT_MALWARE_SCAN_HOST: str = "clamav"
    DOCUMENT_MALWARE_SCAN_PORT: int = 3310
    DOCUMENT_MALWARE_SCAN_TIMEOUT_SECONDS: float = 10.0

    # Recovery opportunity scoring thresholds — Decimal strings are coerced by
    # pydantic. Keep in the organization's configured currency.
    RECOVERY_DEFAULT_COST_TO_RECOVER: Decimal = Decimal("25.00")
    RECOVERY_CRITICAL_EXPECTED_AMOUNT: Decimal = Decimal("100000.00")
    RECOVERY_HIGH_EXPECTED_AMOUNT: Decimal = Decimal("25000.00")
    RECOVERY_DEFAULT_COLLECTION_DAYS: int = 90

    @model_validator(mode="after")
    def _enforce_production_document_security(self) -> "Settings":
        """Fail closed: production must not run with throwaway document
        storage or with malware scanning disabled on uploaded evidence."""
        postgres_values = {
            "POSTGRES_HOST": self.POSTGRES_HOST,
            "POSTGRES_DB": self.POSTGRES_DB,
            "POSTGRES_USER": self.POSTGRES_USER,
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
        }
        if not self.DATABASE_URL:
            missing = [name for name, value in postgres_values.items() if not value]
            if missing:
                raise ValueError(
                    "Set DATABASE_URL or all PostgreSQL settings; missing " + ", ".join(missing)
                )
        if not self.REDIS_URL and not self.REDIS_HOST:
            raise ValueError("Set REDIS_URL or REDIS_HOST")

        if self.APP_ENV == "production":
            if self.SEED_DEMO_DATA:
                raise ValueError("Production environments must not seed demo data")
            if self.DOCUMENT_STORAGE_BACKEND == "local":
                raise ValueError(
                    "Production environments require a durable object backend for "
                    "document storage; set DOCUMENT_STORAGE_BACKEND=s3 (local storage "
                    "is not durable and is only permitted outside production)"
                )
            if not self.DOCUMENT_MALWARE_SCAN_ENABLED:
                raise ValueError(
                    "Production environments require malware scanning to be enabled "
                    "for uploaded documents; set DOCUMENT_MALWARE_SCAN_ENABLED=true"
                )
        return self

    @property
    def test_connectors_allowed(self) -> bool:
        """Mock/sandbox payer connectors and relaxed document-locator reads
        are only available outside production environments."""
        return self.APP_ENV != "production"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = make_url(self.DATABASE_URL)
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg2")
            return url.render_as_string(hide_password=False)

        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL or (f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
