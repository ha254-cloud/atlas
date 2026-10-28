from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.organizations.schemas import OrganizationSettings
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.security.hashing import hash_password
from app.security.jwt import create_access_token


class OnboardingService:
    def __init__(self, db: Session):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.user_repo = UserRepository(db)

    def onboard(self, data):

        existing = self.org_repo.get_by_email(data.organization_email)

        if existing:
            raise ValueError("Organization already exists.")

        organization_settings = OrganizationSettings()
        organization = Organization(
            name=data.organization_name,
            email=data.organization_email,
            phone=data.organization_phone,
            country="KE",
            timezone="Africa/Nairobi",
            currency=organization_settings.billing.currency,
            success_fee_percentage=(organization_settings.billing.success_fee_percentage),
            billing_email=data.organization_email,
            settings=organization_settings.model_dump(mode="json"),
        )

        self.org_repo.create(organization)

        self.db.flush()

        user = User(
            organization_id=organization.id,
            email=data.admin_email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_superuser=True,
        )

        self.user_repo.create(user)

        self.db.commit()

        self.db.refresh(organization)
        self.db.refresh(user)

        token = create_access_token(subject=str(user.id))

        return {
            "organization_id": organization.id,
            "organization_name": organization.name,
            "user_id": user.id,
            "email": user.email,
            "access_token": token,
            "token_type": "bearer",
        }
