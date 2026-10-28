from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.integration import Integration, IntegrationCredentialVersion


class IntegrationRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def get(self, integration_id: int) -> Integration | None:
        return (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.organization_id == self.organization_id,
            )
            .first()
        )

    def next_credential_version(self, integration_id: int) -> int:
        current = (
            self.db.query(func.max(IntegrationCredentialVersion.version))
            .join(Integration, Integration.id == IntegrationCredentialVersion.integration_id)
            .filter(
                IntegrationCredentialVersion.integration_id == integration_id,
                Integration.organization_id == self.organization_id,
            )
            .scalar()
        )
        return int(current or 0) + 1

    def list_credential_versions(
        self,
        integration_id: int,
    ) -> list[IntegrationCredentialVersion]:
        return (
            self.db.query(IntegrationCredentialVersion)
            .join(Integration, Integration.id == IntegrationCredentialVersion.integration_id)
            .filter(
                IntegrationCredentialVersion.integration_id == integration_id,
                Integration.organization_id == self.organization_id,
            )
            .order_by(IntegrationCredentialVersion.version.desc())
            .all()
        )
