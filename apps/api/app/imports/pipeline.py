from datetime import date
from uuid import uuid4

from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.imports.normalizer import ClaimNormalizer
from app.imports.parser import CSVParser
from app.imports.validators import ClaimValidator
from app.models.claim import Claim
from app.models.patient import Patient
from app.models.payer import Payer


class ParseStage:
    def __init__(self):
        self.parser = CSVParser()

    def parse_batches(self, filepath: str, batch_size: int = 1000) -> list[list[dict]]:
        return self.parser.parse_batches(filepath, batch_size)


class ValidationStage:
    def __init__(self):
        self.validator = ClaimValidator()

    def validate(self, row: dict) -> list[str]:
        return self.validator.validate(row)


class NormalizationStage:
    def __init__(self):
        self.normalizer = ClaimNormalizer()

    def normalize(self, row: dict) -> dict:
        return self.normalizer.normalize(row)


class PersistStage:
    def __init__(self, db, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        from app.claims.repository import ClaimRepository

        self.claim_repo = ClaimRepository(db, organization_id)
        self._patient_cache: dict[tuple[str, str], Patient] = {}
        self._payer_cache: dict[str, Payer] = {}

    def _resolve_patient(self, data: dict) -> Patient:
        key = (data["patient_first_name"].lower(), data["patient_last_name"].lower())
        if key in self._patient_cache:
            return self._patient_cache[key]

        patient = (
            self.db.query(Patient)
            .filter(
                Patient.organization_id == self.organization_id,
                Patient.first_name.ilike(data["patient_first_name"]),
                Patient.last_name.ilike(data["patient_last_name"]),
            )
            .first()
        )
        if patient is None:
            patient = Patient(
                organization_id=self.organization_id,
                first_name=data["patient_first_name"],
                last_name=data["patient_last_name"],
                medical_record_number=f"IMP-{uuid4().hex[:10].upper()}",
                date_of_birth=date(1900, 1, 1),
            )
            self.db.add(patient)
            self.db.flush()

        self._patient_cache[key] = patient
        return patient

    def _resolve_payer(self, data: dict) -> Payer:
        code = data["payer_code"]
        if code in self._payer_cache:
            return self._payer_cache[code]

        payer = (
            self.db.query(Payer)
            .filter(
                Payer.organization_id == self.organization_id,
                Payer.payer_code == code,
            )
            .first()
        )
        if payer is None:
            payer = Payer(
                organization_id=self.organization_id,
                name=code,
                payer_code=code,
            )
            self.db.add(payer)
            self.db.flush()

        self._payer_cache[code] = payer
        return payer

    def persist_batch(self, rows: list[dict]) -> list[Claim]:
        claims = []
        for data in rows:
            patient = self._resolve_patient(data)
            payer = self._resolve_payer(data)

            claim = Claim(
                organization_id=self.organization_id,
                patient_id=patient.id,
                payer_id=payer.id,
                claim_number=data["claim_number"],
                status=data.get("status", "imported"),
                billed_amount=data["billed_amount"],
                paid_amount=data["paid_amount"],
                service_date=data["service_date"],
            )
            self.claim_repo.create(claim)
            claims.append(claim)

        self.db.commit()
        for claim in claims:
            self.db.refresh(claim)

        return claims


class PublishStage:
    def __init__(self):
        self.publisher = EventPublisher()

    def publish(self, claim: Claim):
        self.publisher.publish(
            EventType.CLAIM_IMPORTED,
            {
                "claim_id": claim.id,
                "claim_number": claim.claim_number,
                "organization_id": claim.organization_id,
            },
        )


class ImportPipeline:
    def __init__(self, db, organization_id: int):
        self.parse_stage = ParseStage()
        self.validation_stage = ValidationStage()
        self.normalization_stage = NormalizationStage()
        self.persist_stage = PersistStage(db, organization_id)
        self.publish_stage = PublishStage()

    def run(self, filepath: str, batch_size: int = 1000) -> dict:
        imported_ids = []
        failed_count = 0
        total_count = 0

        for batch in self.parse_stage.parse_batches(filepath, batch_size):
            valid_rows = []
            for row in batch:
                total_count += 1
                missing = self.validation_stage.validate(row)
                if missing:
                    failed_count += 1
                    continue

                normalized = self.normalization_stage.normalize(row)
                valid_rows.append(normalized)

            if not valid_rows:
                continue

            claims = self.persist_stage.persist_batch(valid_rows)
            for claim in claims:
                self.publish_stage.publish(claim)
                imported_ids.append(claim.id)

        return {
            "total_count": total_count,
            "successful_count": len(imported_ids),
            "failed_count": failed_count,
            "imported_ids": imported_ids,
        }
