from datetime import datetime

from pydantic import BaseModel


class ImportJobResponse(BaseModel):
    id: int
    filename: str | None = None
    status: str

    total_records: int
    successful_records: int
    failed_records: int
    duplicate_records: int
    expected_total: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }
