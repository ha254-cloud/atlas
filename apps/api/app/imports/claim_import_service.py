from sqlalchemy.orm import Session

from app.canonical.normalizers.csv import CSVNormalizer
from app.integrations.models import CanonicalClaim
from app.models.claim import Claim


class ClaimImportService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def import_claim(self, payload: dict) -> int:
        """Normalize a raw queued row and process it through canonical ingestion."""
        return self.import_canonical(CSVNormalizer().normalize(payload)).id

    def import_canonical(self, canonical: CanonicalClaim) -> Claim:
        """Process a connector claim through the same path as CSV imports."""
        from app.processing.processor import ClaimProcessor
        from app.workflows.service import WorkflowService

        try:
            claim = ClaimProcessor(self.db, self.organization_id).process_canonical(canonical)
            self.db.commit()
            WorkflowService(self.db, self.organization_id).start_workflow(claim)
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(claim)
        return claim
