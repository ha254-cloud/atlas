from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: int | None = None


class ConfirmationRead(BaseModel):
    token: str
    summary: str
    expires_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tool_name: str | None
    tool_input: dict | None
    tool_output: Any | None
    evidence: list | None
    navigation_path: str | None
    created_at: datetime


class ChatResponse(BaseModel):
    conversation_id: int
    message: MessageRead
    confirmation: ConfirmationRead | None = None
    suggested_questions: list[str] = []


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


class ConfirmRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
