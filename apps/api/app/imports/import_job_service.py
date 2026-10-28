from app.repositories.import_repository import ImportRepository


class ImportJobService:
    """
    Owns ImportJob lifecycle transitions (start / progress / complete / fail)
    so the Celery worker — and any future retry or scheduled-import logic —
    all go through the same business logic instead of duplicating status
    handling inline.
    """

    def __init__(self, db, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = ImportRepository(db, organization_id)

    def start(self, job_id: int):
        job = self.repository.update(job_id, status="processing")
        self.db.commit()
        return job

    def update_progress(
        self,
        job_id: int,
        *,
        total: int,
        successful: int,
        failed: int,
        duplicates: int,
        expected_total: int | None = None,
    ):
        job = self.repository.update(
            job_id,
            total_records=total,
            successful_records=successful,
            failed_records=failed,
            duplicate_records=duplicates,
            expected_total=expected_total,
        )
        self.db.commit()
        return job

    def complete(self, job_id: int, result: dict):
        job = self.repository.update(
            job_id,
            status="completed",
            total_records=result["total"],
            successful_records=result["successful"],
            failed_records=result["failed"],
            duplicate_records=result["duplicates"],
            error_details=result.get("errors") or None,
            duration_ms=result.get("duration_ms"),
            expected_total=result.get("expected_total"),
        )
        self.db.commit()
        return job

    def fail(self, job_id: int, message: str):
        job = self.repository.update(
            job_id,
            status="failed",
            error_message=message[:1000],
        )
        self.db.commit()
        return job
