"""
Sync orchestration — ties together the connector result and the import pipeline.

Flow:
    Manager.sync()
        → connector.sync_claims()  → [CanonicalClaim, ...]
        → SyncOrchestrator.process(result)
            → import each canonical claim / patient / payment
            → publish events
"""

from sqlalchemy.orm import Session

from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.integrations.models import SyncResult
from app.processing.exceptions import DuplicateClaimError


class SyncOrchestrator:
    """
    Receives a SyncResult (canonical data) from the manager and hands it
    to the import pipeline.  Publishes events so downstream workers
    (AI analysis, recovery engine) can react without coupling to this layer.
    """

    def __init__(self, db: Session, organization_id: int, integration_id: int | None = None):
        self.db = db
        self.organization_id = organization_id
        self.integration_id = integration_id
        self.publisher = EventPublisher()

    def process(self, result: SyncResult) -> dict:
        """
        Persist canonical claims/patients/payments and publish events.
        Returns a summary dict.
        """
        imported_claims = self._import_claims(result)
        imported_patients = self._import_patients(result)

        if self.integration_id is not None and imported_claims:
            self._record_claims_imported(len(imported_claims))

        self.publisher.publish(
            EventType.CLAIMS_SYNCED,
            {
                "provider": result.provider,
                "organization_id": result.organization_id,
                "claim_count": len(imported_claims),
                "patient_count": len(imported_patients),
            },
        )

        return {
            "provider": result.provider,
            "claims_imported": len(imported_claims),
            "patients_imported": len(imported_patients),
            "errors": result.errors,
        }

    def _record_claims_imported(self, count: int) -> None:
        """Bump the running lifetime counter shown on the Integration Health
        Dashboard — the source claims aren't tagged with the integration_id
        that produced them, so this is tracked as a simple running total
        instead of a COUNT(*) query."""
        from app.models.integration import Integration

        row = (
            self.db.query(Integration)
            .filter(
                Integration.id == self.integration_id,
                Integration.organization_id == self.organization_id,
            )
            .first()
        )
        if row is not None:
            row.claims_imported_count = (row.claims_imported_count or 0) + count
            self.db.commit()

    def _import_claims(self, result: SyncResult) -> list:
        from app.imports.claim_import_service import ClaimImportService

        service = ClaimImportService(self.db, self.organization_id)
        imported = []

        for canonical in result.claims:
            try:
                claim = service.import_canonical(canonical)
                imported.append(claim)
                self.publisher.publish(
                    EventType.CLAIM_IMPORTED,
                    {
                        "claim_id": claim.id,
                        "claim_number": claim.claim_number,
                        "organization_id": self.organization_id,
                        "source": result.provider,
                    },
                )
            except DuplicateClaimError:
                continue
            except Exception as exc:
                message = f"Failed to import claim {canonical.claim_number}: {exc}"
                result.errors.append(message)
                result.rejection_details.append(
                    {
                        "row_number": None,
                        "source_field": None,
                        "error_code": "import_failed",
                        "message": message,
                    }
                )

        return imported

    def _import_patients(self, result: SyncResult) -> list:
        # Patients imported via patient service — stubbed for FHIR sprint
        return []
