from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.denial_code_repository import DenialCodeRepository
from app.schemas.denial_code import DenialCodeRead
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/denial-codes", tags=["Denial Knowledge Base"])


@router.get("", response_model=list[DenialCodeRead])
def list_denial_codes(
    category: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[DenialCodeRead]:
    """
    Return Atlas' denial knowledge base — standardized payer denial codes
    mapped to a category, description, and recommended recovery strategy.

    This is global reference data (not organization-scoped): any
    authenticated user can view it. Optionally filter by `category` (e.g.
    "timely_filing") and/or restrict to `active_only=true`.
    """
    repo = DenialCodeRepository(db)
    if category:
        codes = repo.find_by_category(category)
    elif active_only:
        codes = repo.list_active()
    else:
        codes = repo.list_all()
    return [DenialCodeRead.model_validate(c) for c in codes]


@router.get("/{code}", response_model=DenialCodeRead)
def get_denial_code(
    code: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> DenialCodeRead:
    """Look up a single denial code (e.g. "CO16", "CO-16", "co16" all match)."""
    entry = DenialCodeRepository(db).get_by_code(code)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown denial code: {code}",
        )
    return DenialCodeRead.model_validate(entry)
