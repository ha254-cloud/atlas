from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus


class SubmissionRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, submission_id: int) -> Submission | None:
        return self.db.query(Submission).filter(
            Submission.id == submission_id,
            Submission.organization_id == self.organization_id,
        ).first()

    def for_appeal(self, appeal_id: int) -> Submission | None:
        return self.db.query(Submission).filter(
            Submission.appeal_id == appeal_id,
            Submission.organization_id == self.organization_id,
        ).first()

    def list(self, status: SubmissionStatus | None = None) -> list[Submission]:
        query = self.db.query(Submission).filter(
            Submission.organization_id == self.organization_id
        )
        if status is not None:
            query = query.filter(Submission.status == status)
        return query.order_by(Submission.created_at.desc()).all()
