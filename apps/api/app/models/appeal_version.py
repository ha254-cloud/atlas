"""
AppealVersion — a snapshot of an appeal's text/sections taken every time it
is edited, providing a complete audit trail for compliance:

    Appeal v1 (AI draft) -> edited by reviewer -> Appeal v2 -> approved -> submitted

`Appeal.current_version` always reflects the *current* live version number;
each prior version's content lives here.
"""

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class AppealVersion(Base, TimestampMixin):
    __tablename__ = "appeal_versions"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    appeal_id: Mapped[int] = mapped_column(
        ForeignKey("appeals.id"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(nullable=False)

    appeal_text: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    edited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    appeal = relationship("Appeal", back_populates="versions")
