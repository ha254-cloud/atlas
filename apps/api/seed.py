"""
Seed script — loads realistic demo data into the database.

Usage:
    cd apps/api
    python seed.py

Or via Makefile:
    make seed-demo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.claim import Claim
from app.models.denial import Denial, DenialType
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole
from app.security.hashing import hash_password

# ---------------------------------------------------------------------------
# Demo data fixtures
# ---------------------------------------------------------------------------

PAYERS = [
    {"name": "Social Health Authority", "payer_code": "SHA"},
    {"name": "Jubilee Health Insurance", "payer_code": "JUBILEE"},
    {"name": "AAR Insurance Kenya", "payer_code": "AAR"},
    {"name": "CIC General Insurance", "payer_code": "CIC"},
    {"name": "Britam General Insurance", "payer_code": "BRITAM"},
]

PATIENTS = [
    ("James", "Wilson", "MRN-001", date(1965, 3, 14)),
    ("Patricia", "Moore", "MRN-002", date(1978, 7, 22)),
    ("Robert", "Taylor", "MRN-003", date(1952, 11, 5)),
    ("Linda", "Anderson", "MRN-004", date(1989, 1, 30)),
    ("Michael", "Thomas", "MRN-005", date(1971, 9, 18)),
    ("Barbara", "Jackson", "MRN-006", date(1983, 4, 6)),
    ("William", "White", "MRN-007", date(1945, 8, 25)),
    ("Margaret", "Harris", "MRN-008", date(1960, 12, 3)),
    ("David", "Martin", "MRN-009", date(1995, 6, 11)),
    ("Susan", "Garcia", "MRN-010", date(1968, 2, 28)),
]

CLAIM_STATUSES = ["paid", "denied", "pending", "imported", "appealed"]

# Demo denials pick a real code from the denial knowledge base (seeded by
# migration d3a8f1c6b9e2) so recovery-workspace/claim-detail views show a
# realistic category + recovery strategy instead of a random fake code.
DENIAL_CODE_CHOICES = [
    (entry["code"], DenialType[entry["category"]]) for entry in DENIAL_CODE_SEED_DATA
]


def seed():
    if settings.APP_ENV.lower() == "production":
        raise RuntimeError("Demo data seeding is disabled in production")

    db: Session = SessionLocal()
    try:
        print("Seeding demo data...")

        # Organization
        org = Organization(
            name="Atlas Demo Clinic",
            slug="atlas-demo-clinic",
            organization_type="clinic",
            country="KE",
            timezone="Africa/Nairobi",
            currency="KES",
            plan="trial",
            status="active",
            email="admin@atlasdemo.com",
            phone="+254700000001",
            is_active=True,
        )
        db.add(org)
        db.flush()
        print(f"  ✓ Organization: {org.name} (id={org.id})")

        # Admin user
        admin = User(
            organization_id=org.id,
            email="admin@atlasdemo.com",
            password_hash=hash_password("AtlasDemo2026!"),
            first_name="Demo",
            last_name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=False,
            email_verified=True,
        )
        db.add(admin)
        db.flush()
        print(f"  ✓ Admin user: {admin.email}")

        platform_admin = User(
            organization_id=org.id,
            email="platform-admin@atlasdemo.com",
            password_hash=hash_password("AtlasPlatform2026!"),
            first_name="Atlas",
            last_name="Platform Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
            email_verified=True,
        )
        db.add(platform_admin)
        db.flush()
        print(f"  ✓ Platform admin user: {platform_admin.email}")

        # Payers
        payers = []
        for p in PAYERS:
            payer = Payer(
                organization_id=org.id,
                name=p["name"],
                payer_code=p["payer_code"],
            )
            db.add(payer)
            payers.append(payer)
        db.flush()
        print(f"  ✓ Payers: {len(payers)}")

        # Patients
        patients = []
        for first, last, mrn, dob in PATIENTS:
            patient = Patient(
                organization_id=org.id,
                first_name=first,
                last_name=last,
                medical_record_number=mrn,
                date_of_birth=dob,
            )
            db.add(patient)
            patients.append(patient)
        db.flush()
        print(f"  ✓ Patients: {len(patients)}")

        # Claims
        claims = []
        base_date = date.today() - timedelta(days=180)
        for i in range(50):
            service_date = base_date + timedelta(days=random.randint(0, 170))
            billed = Decimal(str(round(random.uniform(250, 15000), 2)))
            status = random.choice(CLAIM_STATUSES)
            paid = (
                billed
                if status == "paid"
                else Decimal(str(round(random.uniform(0, float(billed) * 0.6), 2)))
            )

            claim = Claim(
                organization_id=org.id,
                patient_id=random.choice(patients).id,
                payer_id=random.choice(payers).id,
                claim_number=f"CLM-2026-{i + 1:04d}",
                status=status,
                billed_amount=billed,
                paid_amount=paid,
                service_date=service_date,
            )
            db.add(claim)
            claims.append(claim)
        db.flush()
        print(f"  ✓ Claims: {len(claims)}")

        # Denials for denied claims
        denied_claims = [c for c in claims if c.status == "denied"]
        for claim in denied_claims:
            code, denial_type = random.choice(DENIAL_CODE_CHOICES)
            denial = Denial(
                organization_id=org.id,
                claim_id=claim.id,
                denial_code=code,
                denial_type=denial_type,
                description="Claim denied — see denial type for details.",
            )
            db.add(denial)
        db.flush()
        print(f"  ✓ Denials: {len(denied_claims)}")

        # Recovery cases for denied + pending claims
        recovery_targets = [c for c in claims if c.status in ("denied", "pending")]
        for claim in recovery_targets:
            balance = claim.billed_amount - claim.paid_amount
            score = Decimal(str(round(random.uniform(30, 95), 2)))
            recovery_case = RecoveryCase(
                organization_id=org.id,
                claim_id=claim.id,
                recovery_score=score,
                estimated_value=balance * score / Decimal("100"),
                status=RecoveryStatus.OPEN,
                recommendation="Review denial category and evaluate appeal readiness.",
            )
            db.add(recovery_case)
        db.flush()
        print(f"  ✓ Recovery cases: {len(recovery_targets)}")

        db.commit()
        print("\nSeed complete.")
        print(f"\n  Hospital login: {admin.email}")
        print("  Password: AtlasDemo2026!")
        print(f"  Platform login: {platform_admin.email}")
        print("  Password: AtlasPlatform2026!")
        print(f"  Organization: {org.name}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
