from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base as Base

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.APP_ENV == "development",
    # Bound how long a connection attempt can block. Without this, an
    # unreachable Postgres host (e.g. a standalone test container with no
    # compose networking) hangs for the OS-level TCP timeout (minutes)
    # instead of raising quickly — fatal for any code path (like the
    # Sprint 8 event handlers) that opens its own get_db() session outside
    # of a test's mocked/overridden dependency.
    connect_args={"connect_timeout": 1},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """
    Database dependency.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
