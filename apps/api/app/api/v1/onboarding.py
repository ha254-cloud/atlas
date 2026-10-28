from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse
from app.services.onboarding_service import OnboardingService

router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
)


@router.post("/", response_model=OnboardingResponse)
def onboarding(
    request: OnboardingRequest,
    db: Session = Depends(get_db),
):

    service = OnboardingService(db)

    try:
        return service.onboard(request)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
