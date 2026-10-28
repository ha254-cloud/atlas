from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.imports.import_service import ImportService

router = APIRouter(
    prefix="/uploads",
    tags=["Uploads"],
)


@router.post("/claims")
async def upload_claims(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    job = ImportService(db, organization_id).create_from_upload(file)

    return {
        "job_id": job.id,
        "filename": file.filename,
        "status": job.status,
    }
