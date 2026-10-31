from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.models.invitation import Invitation
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.security.hashing import hash_password
from app.security.jwt import create_access_token
from app.security.tokens import generate_token, is_expired
from app.services.email_service import EmailService

INVITE_TOKEN_TTL = timedelta(days=7)


class InvitationService:
    """Lets an existing organization admin invite teammates by email/role.
    The invited person never creates a new organization — accepting the
    invite joins the inviter's existing organization_id."""

    def __init__(self, db: Session, organization_id: int | None = None):
        self.db = db
        self.organization_id = organization_id
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.email_service = EmailService()

    def invite(self, email: str, role, invited_by: int) -> Invitation:
        if self.organization_id is None:
            raise ValueError("organization_id is required to invite a user")
        if self.user_repo.get_by_email(email) is not None:
            raise ValueError("A user with this email already exists")

        existing = (
            self.db.query(Invitation)
            .filter(
                Invitation.organization_id == self.organization_id,
                Invitation.email == email,
                Invitation.accepted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            raise ValueError("An invitation is already pending for this email")

        organization = self.org_repo.get_by_id(self.organization_id)
        token = generate_token()

        invitation = Invitation(
            organization_id=self.organization_id,
            email=email,
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=datetime.now(UTC) + INVITE_TOKEN_TTL,
        )
        self.db.add(invitation)
        self.db.flush()

        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=invited_by,
            action=AuditAction.USER_INVITED,
            entity="invitation",
            entity_id=invitation.id,
            metadata={"email": email, "role": role.value if hasattr(role, "value") else role},
        )
        self.email_service.send_invitation_email(
            email, token, organization.name if organization else "Atlas"
        )

        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def accept(self, token: str, first_name: str, last_name: str, password: str) -> dict:
        invitation = self.db.query(Invitation).filter(Invitation.token == token).first()
        if invitation is None or invitation.accepted_at is not None:
            raise ValueError("Invalid or already-used invitation")
        if is_expired(invitation.expires_at):
            raise ValueError("Invitation has expired")
        if self.user_repo.get_by_email(invitation.email) is not None:
            raise ValueError("A user with this email already exists")

        user = User(
            organization_id=invitation.organization_id,
            email=invitation.email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=invitation.role,
            # The invite link itself proves ownership of the invited email address.
            email_verified=True,
        )
        self.user_repo.create(user)
        self.db.flush()

        invitation.accepted_at = datetime.now(UTC)

        AuditService(self.db).log(
            organization_id=invitation.organization_id,
            user_id=user.id,
            action=AuditAction.USER_INVITE_ACCEPTED,
            entity="user",
            entity_id=user.id,
        )
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token(
            subject=str(user.id),
            extra_claims={
                "organization_id": user.organization_id,
                "email": user.email,
                "role": user.role.value,
            },
        )
        return {"access_token": token, "token_type": "bearer"}
