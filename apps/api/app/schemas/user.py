from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserCreate(BaseModel):
    organization_id: int
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserResponse(BaseModel):
    id: int
    organization_id: int
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    email_verified: bool

    model_config = {"from_attributes": True}
