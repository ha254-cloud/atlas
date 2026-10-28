from sqlalchemy.orm import Session

from app.core.repository import BaseRepository
from app.models.document import Document


class DocumentRepository(BaseRepository):
    def __init__(self, db: Session, organization_id: int):
        super().__init__(db, organization_id)

    def _query(self):
        return self.db.query(Document).filter(Document.organization_id == self.organization_id)

    def add(self, document: Document) -> Document:
        self.db.add(document)
        return document

    def get(self, document_id: int) -> Document | None:
        return self._query().filter(Document.id == document_id).first()

    def get_by_claim_checksum(self, claim_id: int, checksum: str) -> Document | None:
        return (
            self._query()
            .filter(Document.claim_id == claim_id, Document.checksum == checksum)
            .first()
        )

    def list_for_claim(self, claim_id: int, search: str | None = None) -> list[Document]:
        query = self._query().filter(Document.claim_id == claim_id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                (Document.filename.ilike(like)) | (Document.extracted_text.ilike(like))
            )
        return query.order_by(Document.created_at.desc()).all()

    def delete(self, document: Document) -> None:
        self.db.delete(document)
