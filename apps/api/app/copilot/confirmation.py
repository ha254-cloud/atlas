import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim import Claim
from app.models.copilot import CopilotConfirmation
from app.models.user import User
from app.security.permissions import Permission, role_has_permission


def _expired(expires_at: datetime) -> bool:
    value = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    return value < datetime.now(UTC)


class ConfirmationService:
    def __init__(self, db: Session, organization_id: int, user: User) -> None:
        self.db = db
        self.organization_id = organization_id
        self.user = user

    def preview_assignment(
        self, conversation_id: int, arguments: dict
    ) -> tuple[CopilotConfirmation, str]:
        provider = arguments["provider"]
        assignee_name = arguments["assignee"]
        assignee = (
            self.db.query(User)
            .filter(
                User.organization_id == self.organization_id,
                User.is_active.is_(True),
                (func.lower(User.first_name) == assignee_name.lower())
                | (func.lower(User.first_name + " " + User.last_name) == assignee_name.lower()),
            )
            .first()
        )
        if assignee is None:
            raise ValueError(f"No active user named {assignee_name} was found in this organization")
        claims = (
            self.db.query(Claim)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.provider.ilike(f"%{provider}%"),
            )
            .order_by(Claim.billed_amount.desc())
            .limit(201)
            .all()
        )
        if len(claims) > 200:
            raise ValueError(
                "This action matches more than 200 claims; narrow the request before assigning"
            )
        if not claims:
            raise ValueError(f"No claims have provider text matching “{provider}”")
        raw_token = secrets.token_urlsafe(32)
        summary = f"Assign {len(claims)} claims matching provider text “{provider}” to {assignee.first_name} {assignee.last_name}."
        confirmation = CopilotConfirmation(
            organization_id=self.organization_id,
            conversation_id=conversation_id,
            requested_by=self.user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            action="assign_claims",
            arguments={"claim_ids": [claim.id for claim in claims], "assignee_id": assignee.id},
            summary=summary,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        self.db.add(confirmation)
        self.db.flush()
        return confirmation, raw_token

    def confirm(self, raw_token: str) -> tuple[CopilotConfirmation, str]:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        confirmation = (
            self.db.query(CopilotConfirmation)
            .filter(
                CopilotConfirmation.token_hash == token_hash,
                CopilotConfirmation.organization_id == self.organization_id,
                CopilotConfirmation.requested_by == self.user.id,
            )
            .first()
        )
        if confirmation is None:
            raise ValueError("Confirmation was not found")
        if confirmation.status != "pending":
            raise ValueError(f"Confirmation is already {confirmation.status}")
        if _expired(confirmation.expires_at):
            confirmation.status = "expired"
            self.db.commit()
            raise ValueError("Confirmation has expired")
        if not self.user.is_superuser and not role_has_permission(
            self.user.role, Permission.COPILOT_WRITE_ACTIONS
        ):
            raise PermissionError("You do not have permission to execute Copilot write actions")
        if confirmation.action != "assign_claims":
            raise ValueError(f"Unsupported confirmation action: {confirmation.action}")
        claim_ids = confirmation.arguments["claim_ids"]
        count = (
            self.db.query(Claim)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.id.in_(claim_ids),
            )
            .update(
                {Claim.assigned_user_id: confirmation.arguments["assignee_id"]},
                synchronize_session=False,
            )
        )
        if count != len(claim_ids):
            self.db.rollback()
            raise ValueError(
                "One or more claims are no longer available; the action was not executed"
            )
        confirmation.status = "executed"
        confirmation.executed_at = datetime.now(UTC)
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=self.user.id,
            action=AuditAction.CLAIM_UPDATED,
            entity="copilot_bulk_assignment",
            entity_id=confirmation.id,
            metadata={"claim_count": count, "assignee_id": confirmation.arguments["assignee_id"]},
        )
        self.db.commit()
        EventPublisher().publish(
            EventType.CLAIM_UPDATED,
            {
                "organization_id": self.organization_id,
                "source": "copilot",
                "claim_count": count,
                "assignee_id": confirmation.arguments["assignee_id"],
            },
        )
        return confirmation, f"Assigned {count} claims successfully."


from sqlalchemy import func  # noqa: E402 - kept near the SQL expression that uses it
