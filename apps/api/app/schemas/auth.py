from pydantic import BaseModel, EmailStr, field_validator

from app.security.password_policy import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    organization_name: str
    organization_type: str | None = None
    country: str | None = None

    first_name: str
    last_name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class RegisterResponse(BaseModel):
    organization_id: int
    user_id: int
    message: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class MessageResponse(BaseModel):
    message: str
