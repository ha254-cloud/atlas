import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import settings
from app.db.database import engine
from app.events.handlers import register_all as register_event_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.observability.tracing import TracingMiddleware

register_event_handlers()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Atlas API",
    version="0.2.0",
    description="Healthcare claims recovery and denial management platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing middleware
app.add_middleware(TracingMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "application": "Atlas",
        "version": "0.2.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    checks = {"database": "ok", "redis": "ok"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database readiness check failed")
        checks["database"] = "error"

    try:
        Redis.from_url(settings.redis_url).ping()
    except RedisError:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "error"

    if "error" in checks.values():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )

    return {"status": "ready", "checks": checks}
