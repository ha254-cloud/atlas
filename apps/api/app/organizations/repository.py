from sqlalchemy import func
from sqlalchemy.orm import Session

from app.organizations.models import Organization, OrganizationSettingsVersion


class OrganizationRepository:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self) -> Organization | None:
        if self.organization_id is None:
            raise ValueError("organization_id is required for tenant access")
        return self.db.query(Organization).filter(Organization.id == self.organization_id).first()

    def get_by_id(self, organization_id: int) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def get_by_email(self, email: str) -> Organization | None:
        return self.db.query(Organization).filter(Organization.email == email).first()

    def create(self, organization: Organization) -> Organization:
        self.db.add(organization)
        return organization

    def next_settings_version(self) -> int:
        if self.organization_id is None:
            raise ValueError("organization_id is required for tenant access")
        current = (
            self.db.query(func.max(OrganizationSettingsVersion.version))
            .filter(OrganizationSettingsVersion.organization_id == self.organization_id)
            .scalar()
        )
        return (current or 0) + 1

    def add_settings_version(
        self,
        version: OrganizationSettingsVersion,
    ) -> OrganizationSettingsVersion:
        if version.organization_id != self.organization_id:
            raise ValueError("Settings version belongs to another organization")
        self.db.add(version)
        return version

    def list_settings_versions(self) -> list[OrganizationSettingsVersion]:
        if self.organization_id is None:
            raise ValueError("organization_id is required for tenant access")
        return (
            self.db.query(OrganizationSettingsVersion)
            .filter(OrganizationSettingsVersion.organization_id == self.organization_id)
            .order_by(OrganizationSettingsVersion.version.desc())
            .all()
        )
