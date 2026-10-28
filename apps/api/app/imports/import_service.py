import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.models.import_job import ImportJob
from app.repositories.import_repository import ImportRepository
from app.workers.tasks import process_import

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".csv"}


class ImportService:
    def __init__(self, db, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = ImportRepository(db, organization_id)

    def create_from_upload(self, file: UploadFile):
        """Validate, persist to disk, and queue an uploaded CSV file for import."""
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension}'. Only CSV files are supported.",
            )

        filename = f"{uuid.uuid4()}{extension}"
        filepath = UPLOAD_DIR / filename

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return self.create_import_job(source="csv", filename=str(filepath))

    def create_import_job(self, source: str, filename: str | None = None):
        job = ImportJob(
            organization_id=self.organization_id,
            source=source,
            status="queued",
            filename=filename,
        )

        created_job = self.repository.create_job(job)
        self.db.commit()
        self.db.refresh(created_job)

        if filename:
            process_import.delay(created_job.id)

        return created_job
