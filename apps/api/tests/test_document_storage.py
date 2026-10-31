from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.core.config import Settings
from app.documents import storage


def upload(name: str = "evidence.txt", content: bytes = b"clinical evidence") -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def configure_local(monkeypatch, root: Path, *, scan: bool = False) -> None:
    monkeypatch.setattr(storage.settings, "DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage.settings, "DOCUMENT_LOCAL_STORAGE_ROOT", str(root))
    monkeypatch.setattr(storage.settings, "DOCUMENT_MALWARE_SCAN_ENABLED", scan)


def test_local_storage_uses_tenant_scoped_locator(monkeypatch, tmp_path):
    configure_local(monkeypatch, tmp_path)

    locator, size, checksum = storage.save_upload(upload(), organization_id=42)

    assert Path(locator).is_relative_to(tmp_path / "active" / "42")
    assert size == len(b"clinical evidence")
    assert len(checksum) == 64
    assert storage.read_file(locator) == b"clinical evidence"


def test_clean_scanned_upload_is_stored(monkeypatch, tmp_path):
    configure_local(monkeypatch, tmp_path, scan=True)
    scanned = []
    monkeypatch.setattr(storage, "_scan_staged_file", lambda path: scanned.append(path))

    locator, size, _checksum = storage.save_upload(upload(), organization_id=42)

    assert len(scanned) == 1
    assert size == len(b"clinical evidence")
    assert storage.read_file(locator) == b"clinical evidence"


def test_detected_malware_is_quarantined_and_not_available(monkeypatch, tmp_path):
    configure_local(monkeypatch, tmp_path, scan=True)

    def infected(_path: Path) -> None:
        raise storage.MalwareDetected("Eicar-Test-Signature")

    monkeypatch.setattr(storage, "_scan_staged_file", infected)

    with pytest.raises(storage.MalwareDetected) as exc_info:
        storage.save_upload(upload(content=b"infected"), organization_id=42)

    quarantine_locator = exc_info.value.quarantine_locator
    assert quarantine_locator is not None
    assert Path(quarantine_locator).is_relative_to(tmp_path / "quarantine" / "42")
    assert Path(quarantine_locator).read_bytes() == b"infected"
    assert list((tmp_path / "active" / "42").glob("*")) == []
    with pytest.raises(storage.QuarantinedObjectUnavailable):
        storage.read_file(quarantine_locator)


def test_scanner_failure_rejects_upload_without_persisting(monkeypatch, tmp_path):
    configure_local(monkeypatch, tmp_path, scan=True)

    def unavailable(_path: Path) -> None:
        raise storage.MalwareScannerUnavailable("scanner offline")

    monkeypatch.setattr(storage, "_scan_staged_file", unavailable)

    with pytest.raises(storage.MalwareScannerUnavailable):
        storage.save_upload(upload(), organization_id=42)

    assert not (tmp_path / "active").exists()
    assert not (tmp_path / "quarantine").exists()


class FakeS3Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.extra_args = None

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs=None) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()
        self.extra_args = ExtraArgs

    def get_object(self, Bucket: str, Key: str):
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


def test_s3_backend_returns_opaque_tenant_scoped_locator(tmp_path):
    client = FakeS3Client()
    backend = storage.S3Storage(
        bucket="atlas-documents",
        prefix="evidence",
        client=client,
    )
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf bytes")

    locator = backend.store(source, organization_id=7, extension=".pdf")

    assert locator.startswith("s3://atlas-documents/evidence/active/7/")
    assert backend.read(locator) == b"pdf bytes"
    backend.delete(locator)
    assert client.objects == {}


def test_s3_backend_uses_configured_encryption(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.settings, "DOCUMENT_S3_SERVER_SIDE_ENCRYPTION", "aws:kms")
    monkeypatch.setattr(storage.settings, "DOCUMENT_S3_KMS_KEY_ID", "test-kms-key")
    client = FakeS3Client()
    backend = storage.S3Storage(bucket="atlas-documents", client=client)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf bytes")

    backend.store(source, organization_id=7, extension=".pdf")

    assert client.extra_args == {
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": "test-kms-key",
    }


@pytest.mark.parametrize(
    ("backend", "scan", "message"),
    [
        ("local", True, "durable object backend"),
        ("s3", False, "malware scanning"),
    ],
)
def test_production_document_security_fails_closed(backend, scan, message):
    values = storage.settings.model_dump()
    values.update(
        APP_ENV="production",
        DOCUMENT_STORAGE_BACKEND=backend,
        DOCUMENT_S3_BUCKET="atlas-documents",
        DOCUMENT_MALWARE_SCAN_ENABLED=scan,
    )

    with pytest.raises(ValidationError, match=message):
        Settings(**values)
