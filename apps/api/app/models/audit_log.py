from sqlalchemy import DDL, JSON, ForeignKey, Index, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class AuditLog(Base, TimestampMixin):
    """
    Immutable record of every significant action in the system.
    Used for compliance, debugging, and security auditing.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_resource", "organization_id", "entity", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )


event.listen(
    AuditLog.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT, 'audit logs are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    AuditLog.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT, 'audit logs are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
