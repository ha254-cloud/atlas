from app.core.repository import BaseRepository
from app.models.import_job import ImportJob


class ImportRepository(BaseRepository):
    def create_job(self, job: ImportJob):
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: int):
        return (
            self.db.query(ImportJob)
            .filter(
                ImportJob.id == job_id,
                ImportJob.organization_id == self.organization_id,
            )
            .first()
        )

    def update(self, job_id: int, **fields):
        job = self.get(job_id)
        if not job:
            return None
        for key, value in fields.items():
            setattr(job, key, value)
        self.db.flush()
        return job
