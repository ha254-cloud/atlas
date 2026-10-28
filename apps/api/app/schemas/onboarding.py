from pydantic import BaseModel, EmailStr


class OnboardingRequest(BaseModel):
    organization_name: str
    organization_email: EmailStr
    organization_phone: str | None = None

    first_name: str
    last_name: str

    admin_email: EmailStr
    password: str


class OnboardingResponse(BaseModel):
    organization_id: int
    organization_name: str

    user_id: int
    email: EmailStr

    access_token: str
    token_type: str = "bearer"
