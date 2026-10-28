"""
Tests for the fail-fast CSV schema check in ImportPipeline — an upload with
entirely wrong columns should be rejected before any row is processed,
instead of failing every row individually for the same reason.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.db.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def org_id():
    return 1


def _write_csv(tmp_path, header: str, rows: list[str]):
    path = tmp_path / "upload.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return str(path)


def test_pipeline_rejects_file_with_wrong_columns(db, org_id, tmp_path):
    from app.processing.exceptions import CSVSchemaError
    from app.processing.pipeline import ImportPipeline

    filepath = _write_csv(
        tmp_path,
        "patient,payer,amount",
        ["Jane Doe,BCBS,100.00"],
    )

    with pytest.raises(CSVSchemaError) as exc_info:
        ImportPipeline(db, org_id).run(filepath)

    assert "claim_number" in str(exc_info.value)
    assert "service_date" in str(exc_info.value)


def test_pipeline_processes_file_with_correct_columns(db, org_id, tmp_path):
    from app.processing.pipeline import ImportPipeline

    filepath = _write_csv(
        tmp_path,
        "claim_number,patient_first_name,patient_last_name,payer_code,billed_amount,paid_amount,service_date",
        ["CLM-CSV-001,Jane,Doe,BCBS,500.00,0.00,2026-01-10"],
    )

    result = ImportPipeline(db, org_id).run(filepath)

    assert result["total"] == 1
    assert result["successful"] == 1
    assert result["failed"] == 0
