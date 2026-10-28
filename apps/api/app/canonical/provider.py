from dataclasses import dataclass


@dataclass
class CanonicalProvider:
    npi: str
    first_name: str
    last_name: str
    specialty: str | None = None
    tax_id: str | None = None
    source_system: str | None = None
