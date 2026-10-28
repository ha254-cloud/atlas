from sqlalchemy.orm import Session


class BaseRepository:
    """
    All repositories inherit from this class.
    Every query must be scoped by organization_id
    to enforce multi-tenant data isolation.
    """

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
