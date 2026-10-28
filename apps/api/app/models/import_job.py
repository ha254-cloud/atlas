from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
    )

    total_records: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    successful_records: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    failed_records: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_records: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    filename: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    error_details: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    expected_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
