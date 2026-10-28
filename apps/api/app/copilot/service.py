from sqlalchemy.orm import Session

from app.copilot.confirmation import ConfirmationService
from app.copilot.planner import plan_message
from app.copilot.tools import registry
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.user import User

SUGGESTED_QUESTIONS = [
    "Which claims should my team prioritize today?",
    "Show unpaid claims over KSh 50,000",
    "Which payer gives us the highest recovery rate?",
    "Show pending appeals",
    "How much are we likely to recover this quarter?",
    "Why are orthopedic denials increasing?",
]

GUIDED_FALLBACK = (
    "What would you like me to investigate? Choose a suggested question below, "
    "or ask about a specific claim, payer, denial, appeal, or recovery period."
)
VAGUE_TITLES = {"hi", "hello", "hey", "help", "please do"}


class CopilotService:
    def __init__(self, db: Session, organization_id: int, user: User) -> None:
        self.db = db
        self.organization_id = organization_id
        self.user = user

    def _conversation(self, conversation_id: int | None, message: str) -> CopilotConversation:
        if conversation_id is not None:
            conversation = (
                self.db.query(CopilotConversation)
                .filter(
                    CopilotConversation.id == conversation_id,
                    CopilotConversation.organization_id == self.organization_id,
                    CopilotConversation.user_id == self.user.id,
                )
                .first()
            )
            if conversation is None:
                raise ValueError("Conversation not found")
            return conversation
        conversation = CopilotConversation(
            organization_id=self.organization_id,
            user_id=self.user.id,
            title=message[:80],
            context={},
        )
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def chat(self, message: str, conversation_id: int | None = None):
        conversation = self._conversation(conversation_id, message)
        self.db.add(
            CopilotMessage(
                organization_id=self.organization_id,
                conversation_id=conversation.id,
                role="user",
                content=message,
            )
        )
        plan = plan_message(message, conversation.context)
        if (
            conversation_id is not None
            and conversation.title.strip().lower() in VAGUE_TITLES
            and (plan.tool_name or plan.action)
        ):
            conversation.title = message[:80]
        confirmation_payload = None
        if plan.action == "assign_claims":
            confirmation, raw_token = ConfirmationService(
                self.db, self.organization_id, self.user
            ).preview_assignment(conversation.id, plan.arguments or {})
            answer = confirmation.summary + " Confirm this action to continue."
            assistant = CopilotMessage(
                organization_id=self.organization_id,
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                tool_name="assign_claims",
                tool_input=plan.arguments,
                tool_output={"status": "confirmation_required", "confirmation_id": confirmation.id},
                evidence=[],
            )
            confirmation_payload = {
                "token": raw_token,
                "summary": confirmation.summary,
                "expires_at": confirmation.expires_at,
            }
        elif plan.tool_name:
            result = registry.execute(
                plan.tool_name, self.db, self.organization_id, plan.arguments or {}
            )
            assistant = CopilotMessage(
                organization_id=self.organization_id,
                conversation_id=conversation.id,
                role="assistant",
                content=result.answer,
                tool_name=plan.tool_name,
                tool_input=plan.arguments,
                tool_output=result.data,
                evidence=result.evidence,
                navigation_path=result.navigation_path,
            )
            conversation.context = {"tool_name": plan.tool_name, "arguments": plan.arguments or {}}
        else:
            assistant = CopilotMessage(
                organization_id=self.organization_id,
                conversation_id=conversation.id,
                role="assistant",
                content=GUIDED_FALLBACK,
                evidence=[],
            )
        self.db.add(assistant)
        self.db.commit()
        self.db.refresh(assistant)
        return conversation, assistant, confirmation_payload

    def confirm(self, token: str):
        confirmation, answer = ConfirmationService(
            self.db, self.organization_id, self.user
        ).confirm(token)
        message = CopilotMessage(
            organization_id=self.organization_id,
            conversation_id=confirmation.conversation_id,
            role="assistant",
            content=answer,
            tool_name=confirmation.action,
            tool_input=confirmation.arguments,
            tool_output={"status": "executed"},
            evidence=[
                {
                    "label": "Assigned claims",
                    "path": "/claims",
                    "value": len(confirmation.arguments["claim_ids"]),
                }
            ],
            navigation_path="/claims",
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return confirmation.conversation_id, message

    def list_conversations(self) -> list[CopilotConversation]:
        return (
            self.db.query(CopilotConversation)
            .filter(
                CopilotConversation.organization_id == self.organization_id,
                CopilotConversation.user_id == self.user.id,
            )
            .order_by(CopilotConversation.updated_at.desc())
            .limit(50)
            .all()
        )

    def get_conversation(self, conversation_id: int) -> CopilotConversation:
        conversation = (
            self.db.query(CopilotConversation)
            .filter(
                CopilotConversation.id == conversation_id,
                CopilotConversation.organization_id == self.organization_id,
                CopilotConversation.user_id == self.user.id,
            )
            .first()
        )
        if conversation is None:
            raise ValueError("Conversation not found")
        return conversation
