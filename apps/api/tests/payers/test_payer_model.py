from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.db.database import Base
from app.models.organization import Organization
from app.models.payer import Payer


def test_payer_defaults_are_kenya_first_and_manual_safe():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    organization = Organization(name="Nairobi Hospital", email="billing@hospital.test")
    db.add(organization)
    db.flush()

    payer = Payer(
        organization_id=organization.id,
        name="SHA",
        payer_code="SHA",
    )
    db.add(payer)
    db.commit()
    db.refresh(payer)

    assert payer.country == "KE"
    assert payer.submission_method == "manual"
    assert payer.status_method == "manual"
    assert payer.payment_method == "report"
    assert payer.supports_manual is True
    assert payer.connector_name is None
