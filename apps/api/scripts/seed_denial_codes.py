"""
Idempotent reseed script for Atlas' denial knowledge base.

Unlike the Alembic migrations that originally created and populated the
`denial_codes` table, this script is meant for iterating on the knowledge
base day-to-day: add/edit entries in
`app/ai/denial_code_seed_data.py::DENIAL_CODE_SEED_DATA` and rerun this
script to upsert them, without needing a new migration for every code.

Usage:
    cd apps/api
    python scripts/seed_denial_codes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session

from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA
from app.db.database import SessionLocal
from app.models.denial import DenialType
from app.models.denial_code import DenialCode, DenialCodeRecoverability, DenialCodeSeverity


def _fields_from_entry(entry: dict) -> dict:
    return {
        "category": DenialType[entry["category"]],
        "description": entry["description"],
        "recovery_strategy": entry["recovery_strategy"],
        "ai_guidance": entry.get("ai_guidance"),
        "severity": DenialCodeSeverity(entry["severity"]) if entry.get("severity") else None,
        "recoverability": (
            DenialCodeRecoverability(entry["recoverability"])
            if entry.get("recoverability")
            else None
        ),
        "typical_recovery_rate": entry.get("typical_recovery_rate"),
        "required_documents": entry.get("required_documents"),
        "typical_resolution_days": entry.get("typical_resolution_days"),
        "common_payers": entry.get("common_payers"),
        "references": entry.get("references"),
    }


def seed_denial_codes(db: Session) -> tuple[int, int]:
    """Upsert every entry in DENIAL_CODE_SEED_DATA. Returns (created, updated)."""
    created = updated = 0

    for entry in DENIAL_CODE_SEED_DATA:
        code = entry["code"]
        existing = db.query(DenialCode).filter(DenialCode.code == code).first()
        fields = _fields_from_entry(entry)

        if existing is None:
            db.add(DenialCode(code=code, **fields))
            created += 1
        else:
            for attr, value in fields.items():
                setattr(existing, attr, value)
            updated += 1

    db.commit()
    return created, updated


def main() -> None:
    db = SessionLocal()
    try:
        created, updated = seed_denial_codes(db)
        print(f"Denial knowledge base seeded: {created} created, {updated} updated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
