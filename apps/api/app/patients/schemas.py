from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    medical_record_number: str = Field(min_length=1, max_length=100)
    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_cannot_be_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    medical_record_number: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_cannot_be_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    medical_record_number: str = Field(max_length=100)
    date_of_birth: date
    created_at: datetime
    updated_at: datetime
