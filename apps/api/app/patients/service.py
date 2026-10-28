from datetime import date

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.governance.audit.service import AuditService
from app.models.patient import Patient
from app.patients.repository import PatientRepository
from app.patients.schemas import PatientCreate, PatientRead, PatientUpdate


class PatientConflictError(ValueError):
    """Raised when a tenant already owns the requested patient identifier."""


class PatientService:
    """Patient business rules and transaction boundaries for one organization."""

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PatientRepository(db, organization_id)
        self.audit = AuditService(db)
        self.events = EventPublisher()

    def list_patients(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        date_of_birth: date | None = None,
    ) -> list[Patient]:
        return self.repository.list(
            limit=limit,
            offset=offset,
            search=search,
            date_of_birth=date_of_birth,
        )

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.repository.get(patient_id)

    def create_patient(self, payload: PatientCreate, *, actor_id: int) -> Patient:
        self._ensure_identifier_available(payload.medical_record_number)
        patient = self.repository.create(
            Patient(organization_id=self.organization_id, **payload.model_dump())
        )
        try:
            self.db.flush()
            self.audit.log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.PATIENT_CREATED,
                entity="patient",
                entity_id=patient.id,
                after_state=self._audit_state(patient),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(patient)
        self.events.publish(
            EventType.PATIENT_CREATED,
            {"patient_id": patient.id, "organization_id": self.organization_id},
            self.organization_id,
        )
        return patient

    def update_patient(
        self,
        patient_id: int,
        payload: PatientUpdate,
        *,
        actor_id: int,
    ) -> Patient | None:
        patient = self.repository.get(patient_id)
        if patient is None:
            return None
        fields = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not fields:
            return patient
        medical_record_number = fields.get("medical_record_number")
        if medical_record_number != patient.medical_record_number:
            self._ensure_identifier_available(medical_record_number)
        before_state = self._audit_state(patient)
        self.repository.update(patient, fields)
        try:
            self.audit.log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.PATIENT_UPDATED,
                entity="patient",
                entity_id=patient.id,
                before_state=before_state,
                after_state=self._audit_state(patient),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(patient)
        self.events.publish(
            EventType.PATIENT_UPDATED,
            {
                "patient_id": patient.id,
                "organization_id": self.organization_id,
                "changed_fields": sorted(fields),
            },
            self.organization_id,
        )
        return patient

    def _ensure_identifier_available(self, medical_record_number: str | None) -> None:
        if medical_record_number and self.repository.get_by_medical_record_number(
            medical_record_number
        ):
            raise PatientConflictError("medical_record_number already exists")

    @staticmethod
    def _audit_state(patient: Patient) -> dict:
        return PatientRead.model_validate(patient).model_dump(mode="json")
