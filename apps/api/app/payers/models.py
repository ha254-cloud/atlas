from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class Payer(Base, TimestampMixin):
    __tablename__ = "payers"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_code: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="KE",
        server_default="KE",
    )
    submission_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    status_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="report",
        server_default="report",
    )
    portal_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    api_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    submission_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    supports_api: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_sftp: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    connector_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    integration_id: Mapped[int | None] = mapped_column(
        ForeignKey("integrations.id"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
