from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BranchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class BranchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    branch_id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchMembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    role_template: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


class BranchMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    branch_id: int
    user_id: int
    role_template: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
