from datetime import date
from enum import Enum
from typing import Any

from app.models.claim import Claim
from app.models.document import DocumentType


class ClaimContextBuilder:
    """Normalize a loaded Atlas claim into provider-independent AI context."""

    def build(self, claim: Claim) -> dict[str, Any]:
        patient = claim.patient
        payer = claim.payer
        denials = list(claim.denials or [])
        documents = list(claim.documents or [])
        latest_denial = max(denials, key=lambda denial: denial.id or 0, default=None)

        return {
            "claim_number": claim.claim_number,
            "claim_amount": float(claim.billed_amount),
            "paid_amount": float(claim.paid_amount),
            "status": claim.status,
            "service_date": self._date_value(claim.service_date),
            "diagnosis_codes": [diagnosis.icd_code for diagnosis in claim.diagnoses],
            "procedure_codes": list(dict.fromkeys(line.cpt_code for line in claim.claim_lines)),
            "denial_reason": latest_denial.description if latest_denial else None,
            "patient_name": self._patient_name(patient),
            "date_of_birth": self._date_value(patient.date_of_birth) if patient else None,
            "gender": getattr(patient, "gender", None) if patient else None,
            "patient_age": self._age_on_service_date(patient, claim.service_date),
            "payer_name": payer.name if payer else None,
            "plan": getattr(payer, "plan", None) if payer else None,
            "policy_number": getattr(payer, "policy_number", None) if payer else None,
            "organization_name": self._organization_name(claim),
            "previous_denials": [self._denial_context(denial) for denial in denials],
            "previous_appeals": [
                self._appeal_context(appeal) for appeal in (getattr(claim, "appeals", None) or [])
            ],
            "claim_events": [
                self._event_context(event) for event in (getattr(claim, "claim_events", None) or [])
            ],
            "operative_report": self._documents_of_type(documents, DocumentType.OPERATIVE_REPORT),
            "authorization": {
                "number": claim.authorization_number,
                "expiration": self._date_value(claim.authorization_expiration),
                "documents": self._documents_of_type(documents, DocumentType.AUTHORIZATION),
            },
            "medical_notes": self._documents_of_type(documents, DocumentType.PHYSICIAN_NOTES),
        }

    @staticmethod
    def _patient_name(patient: Any) -> str | None:
        if patient is None:
            return None
        name = " ".join(part for part in (patient.first_name, patient.last_name) if part)
        return name or None

    @staticmethod
    def _age_on_service_date(patient: Any, service_date: date | None) -> int | None:
        if patient is None or patient.date_of_birth is None or service_date is None:
            return None
        born = patient.date_of_birth
        return (
            service_date.year
            - born.year
            - ((service_date.month, service_date.day) < (born.month, born.day))
        )

    @staticmethod
    def _organization_name(claim: Claim) -> str | None:
        organization = getattr(claim, "organization", None)
        return organization.name if organization else None

    @classmethod
    def _denial_context(cls, denial: Any) -> dict[str, Any]:
        return {
            "code": denial.denial_code,
            "type": cls._enum_value(denial.denial_type),
            "description": denial.description,
            "created_at": cls._date_value(getattr(denial, "created_at", None)),
        }

    @classmethod
    def _appeal_context(cls, appeal: Any) -> dict[str, Any]:
        return {
            "status": cls._enum_value(appeal.status),
            "title": appeal.title,
            "summary": appeal.summary,
            "created_at": cls._date_value(getattr(appeal, "created_at", None)),
        }

    @classmethod
    def _event_context(cls, event: Any) -> dict[str, Any]:
        return {
            "event_type": cls._enum_value(event.event_type),
            "description": event.description,
            "metadata": event.event_metadata,
            "occurred_at": cls._date_value(event.occurred_at),
        }

    @classmethod
    def _documents_of_type(
        cls, documents: list[Any], document_type: DocumentType
    ) -> list[dict[str, Any]]:
        return [
            {
                "filename": document.filename,
                "extracted_text": document.extracted_text,
                "summary": document.ai_summary,
            }
            for document in documents
            if document.document_type == document_type
        ]

    @staticmethod
    def _date_value(value: Any) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return value.value if isinstance(value, Enum) else value
