import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.config import settings
from app.governance.audit.context import classify_device
from app.governance.service import SessionService
from app.models.email_verification_token import EmailVerificationToken
from app.models.organization import Organization
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserRole
from app.organizations.models import OrganizationSettingsVersion
from app.organizations.schemas import OrganizationSettings
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.security.hashing import hash_password, verify_password
from app.security.jwt import create_access_token
from app.security.slug import unique_organization_slug
from app.security.tokens import generate_token, is_expired
from app.services.email_service import EmailDeliveryError, EmailService

VERIFICATION_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=1)
logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.email_service = EmailService()

    def login(
        self,
        email: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):

        user = self.repository.get_by_email(email)

        if not user:
            return None

        if not verify_password(password, user.password_hash):
            AuditService(self.db).log(
                organization_id=user.organization_id,
                user_id=user.id,
                action=AuditAction.USER_LOGIN_FAILED,
                entity="user",
                entity_id=user.id,
                reason="Invalid credentials",
            )
            self.db.commit()
            return None

        if not user.is_active:
            return None

        expires_at = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        session = SessionService(self.db, user.organization_id).create(
            user.id,
            expires_at,
            ip_address,
            user_agent,
            classify_device(user_agent),
        )

        AuditService(self.db).log(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.USER_LOGIN,
            entity="user",
            entity_id=user.id,
            after_state={"session_id": session.id},
        )
        self.db.commit()

        return create_access_token(
            subject=str(user.id),
            extra_claims={
                "organization_id": user.organization_id,
                "email": user.email,
                "role": user.role.value,
                "sid": session.id,
            },
        )

    def register(self, data) -> dict:
        """Organization-first registration: creates the Organization and its
        first (admin) User in one transaction, then sends a verification
        email. The new organization starts as 'pending_verification' and is
        activated once the admin confirms their email."""

        if self.repository.get_by_email(data.email) is not None:
            raise ValueError("Email already in use")

        organization_settings = OrganizationSettings()
        organization = Organization(
            name=data.organization_name,
            slug=unique_organization_slug(self.db, data.organization_name),
            organization_type=data.organization_type,
            country=data.country or "KE",
            email=data.email,
            plan="trial",
            timezone="Africa/Nairobi",
            currency=organization_settings.billing.currency,
            success_fee_percentage=(organization_settings.billing.success_fee_percentage),
            billing_email=data.email,
            settings=organization_settings.model_dump(mode="json"),
            status="pending_verification",
        )
        self.org_repo.create(organization)
        self.db.flush()

        user = User(
            organization_id=organization.id,
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=UserRole.ADMIN,
            is_superuser=False,
            email_verified=False,
        )
        self.repository.create(user)
        self.db.flush()

        self.db.add(
            OrganizationSettingsVersion(
                organization_id=organization.id,
                version=1,
                settings=organization.settings,
                changed_by=user.id,
                reason="Initial organization settings",
                correlation_id=str(uuid4()),
            )
        )

        token = generate_token()
        self.db.add(
            EmailVerificationToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.now(UTC) + VERIFICATION_TOKEN_TTL,
            )
        )

        AuditService(self.db).log(
            organization_id=organization.id,
            user_id=user.id,
            action=AuditAction.USER_REGISTER,
            entity="organization",
            entity_id=organization.id,
        )

        self.email_service.send_verification_email(user.email, token)

        self.db.commit()
        self.db.refresh(organization)
        self.db.refresh(user)

        return {
            "organization_id": organization.id,
            "user_id": user.id,
            "message": "Verification email sent",
        }

    def verify_email(self, token: str) -> None:
        record = (
            self.db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token == token)
            .first()
        )
        if record is None or record.used_at is not None:
            raise ValueError("Invalid or already-used verification token")
        if is_expired(record.expires_at):
            raise ValueError("Verification token has expired")

        user = self.repository.get_by_id(record.user_id)
        if user is None:
            raise ValueError("User not found")

        user.email_verified = True
        record.used_at = datetime.now(UTC)

        organization = self.org_repo.get_by_id(user.organization_id)
        if organization is not None and organization.status == "pending_verification":
            organization.status = "active"

        AuditService(self.db).log(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.EMAIL_VERIFIED,
            entity="user",
            entity_id=user.id,
        )
        self.db.commit()

    def forgot_password(self, email: str) -> None:
        """Always succeeds from the caller's perspective (no user enumeration) —
        only actually issues a reset token/email if the account exists."""
        user = self.repository.get_by_email(email)
        if user is None:
            return

        token = generate_token()
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.now(UTC) + RESET_TOKEN_TTL,
            )
        )
        AuditService(self.db).log(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.PASSWORD_RESET_REQUESTED,
            entity="user",
            entity_id=user.id,
        )
        self.db.flush()

        try:
            self.email_service.send_password_reset_email(user.email, token)
        except EmailDeliveryError:
            self.db.rollback()
            logger.exception(
                "Password reset email delivery failed for user_id=%s",
                user.id,
            )
            return

        self.db.commit()

    def reset_password(self, token: str, new_password: str) -> None:
        record = self.db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
        if record is None or record.used_at is not None:
            raise ValueError("Invalid or already-used reset token")
        if is_expired(record.expires_at):
            raise ValueError("Reset token has expired")

        user = self.repository.get_by_id(record.user_id)
        if user is None:
            raise ValueError("User not found")

        user.password_hash = hash_password(new_password)
        record.used_at = datetime.now(UTC)

        from app.governance.models import UserSession

        self.db.query(UserSession).filter(
            UserSession.organization_id == user.organization_id,
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        ).update(
            {
                UserSession.revoked_at: datetime.now(UTC),
                UserSession.revoked_by: user.id,
                UserSession.revoke_reason: "Password reset",
            },
            synchronize_session=False,
        )

        AuditService(self.db).log(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.PASSWORD_RESET_COMPLETED,
            entity="user",
            entity_id=user.id,
        )
        self.db.commit()
