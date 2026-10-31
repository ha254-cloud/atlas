from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, settings
from app.main import app


def test_hcode_connection_urls_and_cors_are_supported():
    values = settings.model_dump()
    values.update(
        DATABASE_URL="postgresql://atlas:p%40ss@private-postgres:5432/atlas",
        REDIS_URL="redis://:secret@private-redis:6379/0",
        CORS_ALLOWED_ORIGINS="https://www.atlashealth.ke, https://atlashealth.ke/",
    )

    configured = Settings(**values)

    assert configured.database_url == (
        "postgresql+psycopg2://atlas:p%40ss@private-postgres:5432/atlas"
    )
    assert configured.redis_url == "redis://:secret@private-redis:6379/0"
    assert configured.cors_allowed_origins == [
        "https://www.atlashealth.ke",
        "https://atlashealth.ke",
    ]


def test_readiness_reports_database_and_redis(monkeypatch):
    import app.main as main_module

    connection = MagicMock()
    main_module.engine = MagicMock()
    main_module.engine.connect.return_value.__enter__.return_value = connection
    redis_client = MagicMock()
    monkeypatch.setattr(main_module.Redis, "from_url", lambda _url: redis_client)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }
    connection.execute.assert_called_once()
    redis_client.ping.assert_called_once()


def test_readiness_fails_closed_without_dependencies(monkeypatch):
    import app.main as main_module

    main_module.engine = MagicMock()
    main_module.engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception())
    monkeypatch.setattr(
        main_module.Redis,
        "from_url",
        lambda _url: MagicMock(ping=MagicMock(side_effect=RedisConnectionError())),
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "error"},
    }
