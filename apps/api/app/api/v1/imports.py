from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.imports.import_service import ImportService
from app.models.import_job import ImportJob
from app.schemas.import_job import ImportJobResponse

router = APIRouter(
    prefix="/imports",
    tags=["Imports"],
)


@router.post("", response_model=ImportJobResponse, status_code=201)
async def create_import_job(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    """
    Creates an import job from an uploaded CSV file.

    The actual row processing happens asynchronously in Celery;
    poll GET /{job_id} for progress.
    """
    return ImportService(db, organization_id).create_from_upload(file)


@router.get("/{job_id}")
def get_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    """
    Poll the status/summary of a queued or completed import job.

    Response shape mirrors the CSV import summary:
        total_rows, imported, duplicates, invalid, queued_for_ai
    """
    job = (
        db.query(ImportJob)
        .filter(
            ImportJob.id == job_id,
            ImportJob.organization_id == organization_id,
        )
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "filename": job.filename,
        "processed": job.total_records,
        "total": job.expected_total,
        "total_rows": job.total_records,
        "valid_rows": (job.successful_records or 0) + (job.duplicate_records or 0),
        "imported": job.successful_records,
        "duplicates": job.duplicate_records,
        "invalid": job.failed_records,
        "queued_for_ai": job.successful_records,
        "duration_ms": job.duration_ms,
        "errors": job.error_details,
        "error_message": job.error_message,
    }
