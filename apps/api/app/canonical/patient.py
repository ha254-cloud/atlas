from dataclasses import dataclass
from datetime import date


@dataclass
class CanonicalPatient:
    first_name: str
    last_name: str
    date_of_birth: date
    medical_record_number: str
    external_id: str | None = None
    source_system: str | None = None
