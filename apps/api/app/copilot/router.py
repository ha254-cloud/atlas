from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.copilot.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmationRead,
    ConfirmRequest,
    ConversationDetail,
    ConversationRead,
)
from app.copilot.service import SUGGESTED_QUESTIONS, CopilotService
from app.core.config import settings
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(
    prefix="/copilot",
    tags=["Atlas Copilot"],
    dependencies=[Depends(require_feature(Feature.COPILOT))],
)


def _enabled() -> None:
    if not settings.COPILOT_ENABLED:
        raise HTTPException(status_code=404, detail="Atlas Copilot is not enabled")


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.ACCESS_COPILOT)),
):
    _enabled()
    try:
        conversation, message, confirmation = CopilotService(
            db, organization_id, current_user
        ).chat(payload.message, payload.conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ChatResponse(
        conversation_id=conversation.id,
        message=message,
        confirmation=ConfirmationRead(**confirmation) if confirmation else None,
        suggested_questions=(
            SUGGESTED_QUESTIONS
            if message.tool_name is None or len(conversation.messages) <= 2
            else []
        ),
    )


@router.post("/confirm", response_model=ChatResponse)
def confirm(
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.ACCESS_COPILOT)),
):
    _enabled()
    try:
        conversation_id, message = CopilotService(db, organization_id, current_user).confirm(
            payload.token
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ChatResponse(conversation_id=conversation_id, message=message)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.ACCESS_COPILOT)),
):
    _enabled()
    return CopilotService(db, organization_id, current_user).list_conversations()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.ACCESS_COPILOT)),
):
    _enabled()
    try:
        return CopilotService(db, organization_id, current_user).get_conversation(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
