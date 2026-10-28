from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Numeric, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "organization_id"],
            ["branches.id", "branches.organization_id"],
            name="fk_claims_branch_org",
        ),
        ForeignKeyConstraint(
            ["department_id", "branch_id", "organization_id"],
            ["departments.id", "departments.branch_id", "departments.organization_id"],
            name="fk_claims_department_branch_org",
        ),
        CheckConstraint(
            "department_id IS NULL OR branch_id IS NOT NULL",
            name="ck_claims_department_requires_branch",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    branch_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
    )

    payer_id: Mapped[int] = mapped_column(
        ForeignKey("payers.id"),
        nullable=False,
    )

    claim_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    billed_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )

    service_date: Mapped[date] = mapped_column(Date)

    provider: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    priority: Mapped[ClaimPriority] = mapped_column(
        SqlEnum(ClaimPriority),
        default=ClaimPriority.MEDIUM,
        nullable=False,
    )

    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    ai_risk_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    recovery_probability: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    authorization_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    authorization_expiration: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    claim_lines = relationship("ClaimLine", back_populates="claim", cascade="all, delete-orphan")
    diagnoses = relationship("ClaimDiagnosis", back_populates="claim", cascade="all, delete-orphan")
    validation_issues = relationship(
        "ClaimValidationIssue", back_populates="claim", cascade="all, delete-orphan"
    )
    patient = relationship("Patient", back_populates="claims")
    payer = relationship("Payer")
    organization = relationship("Organization", overlaps="branch,department")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    branch = relationship("Branch", overlaps="department,organization")
    department = relationship("Department", overlaps="branch,organization")
    denials = relationship("Denial", back_populates="claim", cascade="all, delete-orphan")
    recovery_cases = relationship(
        "RecoveryCase",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    documents = relationship("Document", back_populates="claim", cascade="all, delete-orphan")
    analysis = relationship(
        "ClaimAnalysis",
        back_populates="claim",
        uselist=False,
        cascade="all, delete-orphan",
    )
    appeals = relationship("Appeal", back_populates="claim")
