from sqlalchemy.orm import Session

from app.models.denial import DenialType
from app.models.denial_code import DenialCode


def normalize_code(code: str) -> str:
    """Normalize a denial code for lookup — payer remittance data and
    manually-entered codes show up in several equivalent forms (e.g.
    "CO-16", "co16", " CO16 "); strip separators/whitespace and uppercase
    so all of them resolve to the same knowledge base entry."""
    return code.strip().upper().replace("-", "").replace(" ", "")


class DenialCodeRepository:
    """Read-oriented access to Atlas' denial knowledge base. This is global
    reference data (shared across every organization), not tenant-scoped."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, code: str | None) -> DenialCode | None:
        if not code:
            return None
        normalized = normalize_code(code)
        return self.db.query(DenialCode).filter(DenialCode.code == normalized).first()

    def find_by_category(self, category: str) -> list[DenialCode]:
        try:
            denial_type = category if isinstance(category, DenialType) else DenialType(category)
        except ValueError:
            return []
        return (
            self.db.query(DenialCode)
            .filter(DenialCode.category == denial_type)
            .order_by(DenialCode.code)
            .all()
        )

    def list_active(self) -> list[DenialCode]:
        return (
            self.db.query(DenialCode)
            .filter(DenialCode.is_active.is_(True))
            .order_by(DenialCode.code)
            .all()
        )

    def list_all(self) -> list[DenialCode]:
        return self.db.query(DenialCode).order_by(DenialCode.code).all()
