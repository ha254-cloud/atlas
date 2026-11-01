import json
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any

from app.eclaims.schemas import SHAClaimSubmit
from app.models.claim import Claim
from app.models.organization import Organization

IG_VERSION = "0.1.0"
PROFILE_BASE = "https://fhir.dha.go.ke/claims/StructureDefinition"
TERMINOLOGY_BASE = "https://fhir.dha.go.ke/terminology/CodeSystem"
FHIR_ACT_CODE = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
FHIR_SERVICE_TYPE = "http://terminology.hl7.org/CodeSystem/service-type"
FHIR_BENEFIT_CATEGORY = "http://terminology.hl7.org/CodeSystem/ex-benefitcategory"

CLAIM_TYPE_DISPLAY = {
    "institutional": "Institutional",
    "professional": "Professional",
    "oral": "Oral",
    "pharmacy": "Pharmacy",
    "vision": "Vision",
}
CLAIM_SUBTYPE_DISPLAY = {
    "day-case": "Day Case",
    "rehabilitation": "Rehabilitation",
    "inpatient": "Inpatient",
    "outpatient": "Outpatient",
    "emergency": "Emergency",
}


def canonical_json_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


class SHABundleBuilder:
    def __init__(self, integration_settings: dict[str, Any]) -> None:
        self.settings = integration_settings
        self.base_url = str(integration_settings["base_url"]).rstrip("/")
        self.provider_number = str(integration_settings["provider_number"])
        self.facility_name = str(integration_settings["facility_name"])
        self.insurer_identifier = str(
            integration_settings.get("insurer_identifier", "SHA-KE-001")
        )

    def build(
        self,
        claim: Claim,
        organization: Organization,
        payload: SHAClaimSubmit,
        *,
        requested_at: datetime,
    ) -> dict[str, Any]:
        self._validate_mappings(claim, payload)
        requested_at = self._aware(requested_at)
        suffix = f"{organization.id}-{claim.id}"
        patient_id = f"atlas-patient-{claim.patient_id}"
        coverage_id = f"atlas-coverage-{suffix}"
        provider_id = f"atlas-provider-{organization.id}"
        insurer_id = "sha-insurer"
        encounter_id = f"atlas-encounter-{suffix}"
        practitioner_id = f"atlas-practitioner-{suffix}"
        claim_id = f"atlas-claim-{suffix}"

        patient = self._patient(claim, payload, patient_id)
        provider = self._provider(organization, provider_id)
        insurer = self._insurer(insurer_id)
        practitioner = self._practitioner(payload, practitioner_id)
        coverage = self._coverage(payload, coverage_id, patient_id, insurer_id)
        encounter = self._encounter(
            payload, encounter_id, patient_id, provider_id
        )
        conditions = self._conditions(
            claim, payload, patient_id, encounter_id, practitioner_id, suffix
        )
        claim_resource = self._claim(
            claim,
            payload,
            claim_id,
            patient_id,
            coverage_id,
            provider_id,
            insurer_id,
            encounter_id,
            requested_at,
        )
        resources = [
            claim_resource,
            patient,
            coverage,
            provider,
            insurer,
            practitioner,
            encounter,
            *conditions,
        ]
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "meta": {"lastUpdated": requested_at.isoformat()},
            "identifier": {
                "system": f"{self.base_url}/Identifier/bundle",
                "value": payload.idempotency_key,
            },
            "timestamp": requested_at.isoformat(),
            "entry": [
                {
                    "fullUrl": f"{self.base_url}/{resource['resourceType']}/{resource['id']}",
                    "resource": resource,
                }
                for resource in resources
            ],
        }

    def _patient(
        self,
        claim: Claim,
        payload: SHAClaimSubmit,
        resource_id: str,
    ) -> dict[str, Any]:
        patient = claim.patient
        identifier_slug = (
            "sha-number"
            if payload.patient_identifier_type == "SHA-NUMBER"
            else "national-id"
        )
        identifier_display = (
            "SHA Number"
            if payload.patient_identifier_type == "SHA-NUMBER"
            else "National ID"
        )
        return {
            "resourceType": "Patient",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-patient"]},
            "identifier": [
                {
                    "use": "official",
                    "type": {
                        "coding": [
                            {
                                "system": f"{TERMINOLOGY_BASE}/identifier-types-cs",
                                "code": payload.patient_identifier_type,
                                "display": identifier_display,
                            }
                        ]
                    },
                    "system": f"{self.base_url}/Identifier/{identifier_slug}",
                    "value": payload.patient_identifier,
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": patient.last_name,
                    "given": [patient.first_name],
                }
            ],
            "telecom": [
                {
                    "system": "phone",
                    "value": payload.patient_phone,
                    "use": "mobile",
                }
            ],
            "gender": payload.patient_gender,
            "birthDate": patient.date_of_birth.isoformat(),
            "contact": [
                {
                    "name": {
                        "family": payload.patient_contact.family_name,
                        "given": payload.patient_contact.given_names,
                    },
                    "telecom": [
                        {
                            "system": "phone",
                            "value": payload.patient_contact.phone,
                        }
                    ],
                }
            ],
        }

    def _practitioner(
        self,
        payload: SHAClaimSubmit,
        resource_id: str,
    ) -> dict[str, Any]:
        identifier_display = (
            "SHA Number"
            if payload.practitioner.identifier_type == "SHA-NUMBER"
            else "National ID"
        )
        return {
            "resourceType": "Practitioner",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-practitioner"]},
            "identifier": [
                {
                    "use": "official",
                    "type": {
                        "coding": [
                            {
                                "system": f"{TERMINOLOGY_BASE}/identifier-types-cs",
                                "code": payload.practitioner.identifier_type,
                                "display": identifier_display,
                            }
                        ]
                    },
                    "system": f"{self.base_url}/Identifier/practitioner-number",
                    "value": payload.practitioner.identifier,
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": payload.practitioner.family_name,
                    "given": payload.practitioner.given_names,
                }
            ],
            "telecom": [
                {
                    "system": "phone",
                    "value": payload.practitioner.phone,
                    "use": "work",
                }
            ],
            "gender": payload.practitioner.gender,
            "birthDate": payload.practitioner.birth_date.isoformat(),
        }

    def _provider(
        self,
        organization: Organization,
        resource_id: str,
    ) -> dict[str, Any]:
        return {
            "resourceType": "Organization",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-organization"]},
            "identifier": [
                {
                    "use": "official",
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "PRN",
                                "display": "Provider number",
                            }
                        ]
                    },
                    "value": self.provider_number,
                }
            ],
            "active": True,
            "type": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                            "code": "prov",
                            "display": "Healthcare Provider",
                        }
                    ]
                }
            ],
            "name": self.facility_name or organization.name,
        }

    def _insurer(self, resource_id: str) -> dict[str, Any]:
        return {
            "resourceType": "Organization",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-organization"]},
            "identifier": [{"use": "official", "value": self.insurer_identifier}],
            "active": True,
            "type": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                            "code": "ins",
                            "display": "Insurance Company",
                        }
                    ]
                }
            ],
            "name": "Social Health Authority",
        }

    def _coverage(
        self,
        payload: SHAClaimSubmit,
        resource_id: str,
        patient_id: str,
        insurer_id: str,
    ) -> dict[str, Any]:
        coverage: dict[str, Any] = {
            "resourceType": "Coverage",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-coverage"]},
            "extension": [
                {
                    "url": (
                        f"{PROFILE_BASE}/"
                        "eclaims-annual-limit-category-extension"
                    ),
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem/"
                                    "service-category"
                                ),
                                "code": payload.coverage.annual_limit_category_code,
                                "display": (
                                    payload.coverage.annual_limit_category_display
                                ),
                            }
                        ]
                    },
                }
            ],
            "identifier": [
                {
                    "system": f"{self.base_url}/Identifier/coverage-number",
                    "value": payload.coverage.number,
                }
            ],
            "status": "active",
            "type": {
                "coding": [
                    {
                        "system": f"{TERMINOLOGY_BASE}/coverage-type-cs",
                        "code": "MEDICAL",
                        "display": "Medical",
                    }
                ]
            },
            "subscriber": {"reference": f"Patient/{patient_id}"},
            "beneficiary": {
                "reference": f"Patient/{patient_id}",
                "type": "Patient",
            },
            "relationship": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/subscriber-relationship",
                        "code": "self",
                        "display": "Self",
                    }
                ]
            },
            "payor": [{"reference": f"Organization/{insurer_id}"}],
            "class": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": f"{TERMINOLOGY_BASE}/coverage-class-cs",
                                "code": payload.coverage.class_code,
                                "display": payload.coverage.class_display,
                            }
                        ]
                    },
                    "value": payload.coverage.class_value,
                    "name": payload.coverage.class_name,
                }
            ],
        }
        if payload.coverage.period_start or payload.coverage.period_end:
            coverage["period"] = {}
            if payload.coverage.period_start:
                coverage["period"]["start"] = payload.coverage.period_start.isoformat()
            if payload.coverage.period_end:
                coverage["period"]["end"] = payload.coverage.period_end.isoformat()
        return coverage

    def _encounter(
        self,
        payload: SHAClaimSubmit,
        resource_id: str,
        patient_id: str,
        provider_id: str,
    ) -> dict[str, Any]:
        return {
            "resourceType": "Encounter",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-encounter"]},
            "identifier": [
                {
                    "system": f"{self.base_url}/Identifier/encounter-number",
                    "value": payload.encounter.number,
                }
            ],
            "status": "finished",
            "class": {
                "system": FHIR_ACT_CODE,
                "code": payload.encounter.class_code,
                "display": payload.encounter.class_display,
            },
            "serviceType": {
                "coding": [
                    {
                        "system": FHIR_SERVICE_TYPE,
                        "code": payload.encounter.service_type_code,
                        "display": payload.encounter.service_type_display,
                    }
                ]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "period": {
                "start": self._aware(payload.encounter.period_start).isoformat(),
                "end": self._aware(payload.encounter.period_end).isoformat(),
            },
            "serviceProvider": {"reference": f"Organization/{provider_id}"},
        }

    def _conditions(
        self,
        claim: Claim,
        payload: SHAClaimSubmit,
        patient_id: str,
        encounter_id: str,
        practitioner_id: str,
        suffix: str,
    ) -> list[dict[str, Any]]:
        diagnosis_by_id = {diagnosis.id: diagnosis for diagnosis in claim.diagnoses}
        conditions = []
        for sequence, mapping in enumerate(payload.diagnoses, start=1):
            diagnosis = diagnosis_by_id[mapping.claim_diagnosis_id]
            conditions.append(
                {
                    "resourceType": "Condition",
                    "id": f"atlas-condition-{suffix}-{sequence}",
                    "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-condition"]},
                    "identifier": [
                        {
                            "system": f"{self.base_url}/Identifier/condition-number",
                            "value": f"{claim.claim_number}-{diagnosis.id}",
                        }
                    ],
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem/"
                                    "condition-clinical"
                                ),
                                "code": "active",
                                "display": "Active",
                            }
                        ]
                    },
                    "verificationStatus": {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem/"
                                    "condition-ver-status"
                                ),
                                "code": "confirmed",
                                "display": "Confirmed",
                            }
                        ]
                    },
                    "category": [
                        {
                            "coding": [
                                {
                                    "system": f"{TERMINOLOGY_BASE}/condition-category-cs",
                                    "code": "ENCOUNTER-DIAGNOSIS",
                                    "display": "Encounter Diagnosis",
                                }
                            ]
                        }
                    ],
                    "code": {
                        "coding": [
                            {
                                "system": f"{TERMINOLOGY_BASE}/icd11-codes-cs",
                                "code": mapping.icd11_code,
                                "display": mapping.display,
                            }
                        ]
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{encounter_id}"},
                    "onsetDateTime": claim.service_date.isoformat(),
                    "recorder": {
                        "reference": f"Practitioner/{practitioner_id}"
                    },
                }
            )
        return conditions

    def _claim(
        self,
        claim: Claim,
        payload: SHAClaimSubmit,
        resource_id: str,
        patient_id: str,
        coverage_id: str,
        provider_id: str,
        insurer_id: str,
        encounter_id: str,
        requested_at: datetime,
    ) -> dict[str, Any]:
        diagnosis_by_id = {diagnosis.id: diagnosis for diagnosis in claim.diagnoses}
        line_by_id = {line.id: line for line in claim.claim_lines}
        diagnoses = [
            {
                "sequence": sequence,
                "diagnosisCodeableConcept": {
                    "coding": [
                        {
                            "system": f"{TERMINOLOGY_BASE}/icd11-codes-cs",
                            "code": mapping.icd11_code,
                            "display": mapping.display,
                        }
                    ]
                },
            }
            for sequence, mapping in enumerate(payload.diagnoses, start=1)
            if mapping.claim_diagnosis_id in diagnosis_by_id
        ]
        items = []
        for sequence, mapping in enumerate(payload.line_items, start=1):
            line = line_by_id[mapping.claim_line_id]
            net = Decimal(line.charge_amount).quantize(Decimal("0.01"))
            unit_price = (net / line.units).quantize(Decimal("0.01"))
            items.append(
                {
                    "sequence": sequence,
                    "category": {
                        "coding": [
                            {
                                "system": FHIR_BENEFIT_CATEGORY,
                                "code": mapping.benefit_category_code,
                                "display": mapping.benefit_category_display,
                            }
                        ]
                    },
                    "productOrService": {
                        "coding": [
                            {
                                "system": (
                                    f"{TERMINOLOGY_BASE}/"
                                    "kenya-social-health-authority-intervention-cs"
                                ),
                                "code": mapping.intervention_code,
                                "display": mapping.intervention_display,
                            }
                        ]
                    },
                    "encounter": [{"reference": f"Encounter/{encounter_id}"}],
                    "quantity": {"value": line.units},
                    "unitPrice": {"value": float(unit_price), "currency": claim.currency},
                    "net": {"value": float(net), "currency": claim.currency},
                }
            )
        return {
            "resourceType": "Claim",
            "id": resource_id,
            "meta": {"profile": [f"{PROFILE_BASE}/ke-eclaims-claimsubmission"]},
            "extension": [
                {
                    "url": f"{PROFILE_BASE}/eclaims-patient-invoice",
                    "extension": [
                        {
                            "url": "invoiceNumber",
                            "valueString": payload.invoice.number,
                        },
                        {
                            "url": "invoiceDate",
                            "valueDate": payload.invoice.date.isoformat(),
                        },
                        {
                            "url": "invoiceAmount",
                            "valueMoney": {
                                "value": float(
                                    Decimal(claim.billed_amount).quantize(
                                        Decimal("0.01")
                                    )
                                ),
                                "currency": claim.currency,
                            },
                        },
                        {
                            "url": "patientShare",
                            "valueMoney": {
                                "value": float(payload.invoice.patient_share),
                                "currency": claim.currency,
                            },
                        },
                    ],
                }
            ],
            "identifier": [
                {
                    "system": f"{self.base_url}/Identifier/claim-number",
                    "value": claim.claim_number,
                }
            ],
            "status": "active",
            "type": {
                "coding": [
                    {
                        "system": f"{TERMINOLOGY_BASE}/claim-type-cs",
                        "code": payload.claim_type,
                        "display": CLAIM_TYPE_DISPLAY[payload.claim_type],
                    }
                ]
            },
            "subType": {
                "coding": [
                    {
                        "system": f"{TERMINOLOGY_BASE}/claim-subtype-cs",
                        "code": payload.claim_subtype,
                        "display": CLAIM_SUBTYPE_DISPLAY[payload.claim_subtype],
                    }
                ]
            },
            "use": "claim",
            "patient": {"reference": f"Patient/{patient_id}"},
            "billablePeriod": {
                "start": claim.service_date.isoformat(),
                "end": claim.service_date.isoformat(),
            },
            "created": requested_at.isoformat(),
            "insurer": {"reference": f"Organization/{insurer_id}"},
            "provider": {"reference": f"Organization/{provider_id}"},
            "priority": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                        "code": "normal",
                        "display": "Normal",
                    }
                ]
            },
            "payee": {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/payeetype",
                            "code": "provider",
                            "display": "Provider",
                        }
                    ]
                }
            },
            "diagnosis": diagnoses,
            "insurance": [
                {
                    "sequence": 1,
                    "focal": True,
                    "coverage": {"reference": f"Coverage/{coverage_id}"},
                }
            ],
            "item": items,
            "total": {
                "value": float(Decimal(claim.billed_amount).quantize(Decimal("0.01"))),
                "currency": claim.currency,
            },
        }

    @staticmethod
    def _validate_mappings(claim: Claim, payload: SHAClaimSubmit) -> None:
        expected_diagnoses = {diagnosis.id for diagnosis in claim.diagnoses}
        mapped_diagnoses = {
            mapping.claim_diagnosis_id for mapping in payload.diagnoses
        }
        if mapped_diagnoses != expected_diagnoses:
            raise ValueError(
                "SHA diagnosis mappings must cover every claim diagnosis exactly once"
            )
        if len(mapped_diagnoses) != len(payload.diagnoses):
            raise ValueError("SHA diagnosis mappings contain duplicate claim_diagnosis_id values")

        expected_lines = {line.id for line in claim.claim_lines}
        mapped_lines = {mapping.claim_line_id for mapping in payload.line_items}
        if mapped_lines != expected_lines:
            raise ValueError(
                "SHA line mappings must cover every claim line exactly once"
            )
        if len(mapped_lines) != len(payload.line_items):
            raise ValueError("SHA line mappings contain duplicate claim_line_id values")
        if claim.currency != "KES":
            raise ValueError("SHA eClaims submissions currently require KES claims")
        if payload.invoice.patient_share > claim.billed_amount:
            raise ValueError("SHA invoice patient_share cannot exceed the billed amount")
        if not claim.claim_number:
            raise ValueError("SHA eClaims submission requires a claim number")

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def claim_response_summary(resource: dict[str, Any]) -> dict[str, Any]:
    if resource.get("resourceType") == "Bundle":
        for entry in resource.get("entry", []):
            candidate = entry.get("resource") or {}
            if candidate.get("resourceType") == "ClaimResponse":
                resource = candidate
                break
    if resource.get("resourceType") != "ClaimResponse":
        return {
            "resource_type": resource.get("resourceType"),
            "claim_response_id": None,
            "outcome": None,
            "workflow_state": None,
            "approved_amount": None,
            "currency": None,
            "notes": [],
        }

    workflow_state = None
    for extension in resource.get("extension", []):
        if str(extension.get("url", "")).endswith("eclaim-state-extension"):
            coding = (extension.get("valueCodeableConcept") or {}).get("coding") or []
            if coding:
                workflow_state = coding[0].get("code")
                break
    approved_amount = None
    currency = None
    for total in resource.get("total", []):
        coding = (total.get("category") or {}).get("coding") or []
        if coding and coding[0].get("code") == "benefit":
            amount = total.get("amount") or {}
            approved_amount = amount.get("value")
            currency = amount.get("currency")
            break
    notes = [
        note["text"][:500]
        for note in resource.get("processNote", [])
        if isinstance(note.get("text"), str)
    ]
    return {
        "resource_type": "ClaimResponse",
        "claim_response_id": resource.get("id"),
        "outcome": resource.get("outcome"),
        "workflow_state": workflow_state,
        "approved_amount": approved_amount,
        "currency": currency,
        "notes": notes,
    }
