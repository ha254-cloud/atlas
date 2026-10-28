from enum import Enum
from typing import Any

from app.models.claim import Claim


class AppealContextBuilder:
    """Normalize all appeal evidence into a provider-independent object."""

    def build(self, claim: Claim) -> dict[str, Any]:
        analysis = claim.analysis
        patient = claim.patient
        payer = claim.payer
        organization = claim.organization

        return {
            "claim": {
                "id": claim.id,
                "claim_number": claim.claim_number,
                "status": self._value(claim.status),
                "service_date": self._date(claim.service_date),
                "billed_amount": float(claim.billed_amount),
                "paid_amount": float(claim.paid_amount),
                "diagnosis_codes": [item.icd_code for item in claim.diagnoses],
                "procedure_codes": list(dict.fromkeys(item.cpt_code for item in claim.claim_lines)),
                "denials": [
                    {
                        "code": denial.denial_code,
                        "type": self._value(denial.denial_type),
                        "description": denial.description,
                    }
                    for denial in claim.denials
                ],
            },
            "analysis": (
                {
                    "status": self._value(analysis.analysis_status),
                    "risk_score": self._number(analysis.risk_score),
                    "priority": analysis.priority,
                    "confidence": self._number(analysis.confidence_score),
                    "recovery_probability": self._number(analysis.recovery_probability),
                    "root_cause": analysis.root_cause,
                    "recommended_action": analysis.recommended_action,
                    "summary": analysis.ai_summary,
                    "required_documents": list(analysis.required_documents or []),
                }
                if analysis is not None
                else None
            ),
            "patient": (
                {
                    "name": " ".join(
                        part for part in (patient.first_name, patient.last_name) if part
                    ),
                    "medical_record_number": patient.medical_record_number,
                    "date_of_birth": self._date(patient.date_of_birth),
                }
                if patient is not None
                else None
            ),
            "payer": (
                {
                    "name": payer.name,
                    "payer_code": payer.payer_code,
                }
                if payer is not None
                else None
            ),
            "organization": (
                {
                    "name": organization.name,
                    "address": getattr(organization, "address", None),
                    "phone": organization.phone,
                    "email": organization.email,
                }
                if organization is not None
                else None
            ),
            "documents": [
                {
                    "id": document.id,
                    "type": self._value(document.document_type),
                    "filename": document.filename,
                    "extracted_text": document.extracted_text,
                    "summary": document.ai_summary,
                }
                for document in claim.documents
            ],
            "previous_appeals": [
                {
                    "id": appeal.id,
                    "status": self._value(appeal.status),
                    "version": appeal.current_version,
                    "title": appeal.title,
                    "body": appeal.appeal_text,
                    "created_at": self._date(appeal.created_at),
                }
                for appeal in claim.appeals
            ],
        }

    @staticmethod
    def _date(value: Any) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _value(value: Any) -> Any:
        return value.value if isinstance(value, Enum) else value
