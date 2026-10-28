from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class DocumentType(StrEnum):
    OPERATIVE_REPORT = "operative_report"
    IMAGING = "imaging"
    REFERRAL = "referral"
    LAB_RESULTS = "lab_results"
    AUTHORIZATION = "authorization"
    PHYSICIAN_NOTES = "physician_notes"
    OTHER = "other"


class DocumentClassificationReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"


class DocumentRetentionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PENDING_DELETE = "pending_delete"
    DELETED = "deleted"


class DocumentHoldType(StrEnum):
    LEGAL = "legal"
    CLINICAL = "clinical"


class Document(Base, TimestampMixin):
    """
    A piece of supporting evidence attached to a claim — operative reports,
    imaging, referrals, lab results, authorizations, etc. Backs the Evidence
    Library (upload/preview/search/tagging) and feeds `EvidenceCollector` so
    appeal generation can verify required documents are actually on file
    instead of only inferring it from structural claim data.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "claim_id",
            "checksum",
            name="uq_documents_org_claim_checksum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    document_type: Mapped[DocumentType] = mapped_column(
        SqlEnum(DocumentType),
        default=DocumentType.OTHER,
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Text pulled from the file itself (PDF text layer; OCR when available —
    # see app.documents.extraction) so documents are searchable and can be
    # summarized/verified without a human opening the file.
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="unrecorded", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False)
    extraction_engine: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    extraction_engine_version: Mapped[str] = mapped_column(
        String(100), default="unknown", nullable=False
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)
    retention_status: Mapped[DocumentRetentionStatus] = mapped_column(
        SqlEnum(DocumentRetentionStatus),
        default=DocumentRetentionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    predicted_document_type: Mapped[DocumentType | None] = mapped_column(
        SqlEnum(DocumentType),
        nullable=True,
    )
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    classification_provider: Mapped[str | None] = mapped_column(String(50))
    classification_model: Mapped[str | None] = mapped_column(String(100))
    classification_prompt_version: Mapped[str | None] = mapped_column(String(20))
    classification_review_status: Mapped[DocumentClassificationReviewStatus | None] = mapped_column(
        SqlEnum(DocumentClassificationReviewStatus), nullable=True
    )
    classification_reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    classification_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    classification_review_reason: Mapped[str | None] = mapped_column(String(500))

    claim = relationship("Claim", back_populates="documents")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    classification_reviewed_by = relationship("User", foreign_keys=[classification_reviewed_by_id])
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )


class DocumentVersion(Base, TimestampMixin):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_versions_document_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predecessor_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extractor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document = relationship("Document", back_populates="versions")
    predecessor = relationship("DocumentVersion", remote_side=[id])


class DocumentHold(Base):
    __tablename__ = "document_holds"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "hold_type",
            "version",
            name="uq_document_holds_document_type_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hold_type: Mapped[DocumentHoldType] = mapped_column(SqlEnum(DocumentHoldType), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
