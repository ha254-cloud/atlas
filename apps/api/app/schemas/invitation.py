from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole
from app.security.password_policy import validate_password_strength


class InviteRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.VIEWER


class InviteResponse(BaseModel):
    invitation_id: int
    email: EmailStr
    role: UserRole
    message: str


class AcceptInviteRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class UserRead(BaseModel):
    id: int
    organization_id: int
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
