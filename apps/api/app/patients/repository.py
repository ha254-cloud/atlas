from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core.repository import BaseRepository
from app.models.patient import Patient


class PatientRepository(BaseRepository):
    """Database access for patients within one authenticated organization."""

    def __init__(self, db: Session, organization_id: int):
        super().__init__(db, organization_id)

    def _base_query(self) -> Query:
        return self.db.query(Patient).filter(Patient.organization_id == self.organization_id)

    def create(self, patient: Patient) -> Patient:
        self.db.add(patient)
        return patient

    def get(self, patient_id: int) -> Patient | None:
        return self._base_query().filter(Patient.id == patient_id).first()

    def get_by_medical_record_number(self, medical_record_number: str) -> Patient | None:
        return (
            self._base_query()
            .filter(Patient.medical_record_number == medical_record_number)
            .first()
        )

    def list(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        date_of_birth: date | None = None,
    ) -> list[Patient]:
        query = self._base_query()
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Patient.first_name.ilike(pattern),
                    Patient.last_name.ilike(pattern),
                    Patient.medical_record_number.ilike(pattern),
                )
            )
        if date_of_birth is not None:
            query = query.filter(Patient.date_of_birth == date_of_birth)
        return (
            query.order_by(Patient.last_name, Patient.first_name, Patient.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, patient: Patient, fields: dict) -> Patient:
        for field, value in fields.items():
            setattr(patient, field, value)
        return patient
