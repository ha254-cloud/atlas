import hashlib
import shutil
import socket
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO

import boto3
from fastapi import UploadFile

from app.core.config import settings

# Deliberately permissive-but-bounded — hospitals export evidence as PDFs,
# scanned images, and occasionally plain text (e.g. exported EHR notes).
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class UnsupportedFileType(ValueError):
    pass


class FileTooLarge(ValueError):
    pass


class MalwareDetected(ValueError):
    def __init__(self, signature: str, quarantine_locator: str | None = None):
        super().__init__(f"Malware detected: {signature}")
        self.signature = signature
        self.quarantine_locator = quarantine_locator


class MalwareScannerUnavailable(RuntimeError):
    pass


class QuarantinedObjectUnavailable(PermissionError):
    pass


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def store(self, source: Path, organization_id: int, extension: str) -> str:
        destination = self.root / "active" / str(organization_id) / f"{uuid.uuid4()}{extension}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), destination)
        return str(destination)

    def quarantine(self, source: Path, organization_id: int, extension: str) -> str:
        destination = self.root / "quarantine" / str(organization_id) / f"{uuid.uuid4()}{extension}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), destination)
        return str(destination)

    def read(self, locator: str) -> bytes:
        path = Path(locator).resolve()
        quarantine_root = self.root / "quarantine"
        if path.is_relative_to(quarantine_root):
            raise QuarantinedObjectUnavailable("Quarantined documents cannot be read")
        if not path.is_relative_to(self.root / "active"):
            if settings.test_connectors_allowed and path.is_file():
                return path.read_bytes()
            raise ValueError("Document locator is outside the configured storage root")
        return path.read_bytes()

    def delete(self, locator: str) -> None:
        path = Path(locator).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Document locator is outside the configured storage root")
        path.unlink(missing_ok=True)


class S3Storage:
    def __init__(self, bucket: str, prefix: str = "documents", client=None):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client or boto3.client(
            "s3",
            region_name=settings.DOCUMENT_S3_REGION or None,
            endpoint_url=settings.DOCUMENT_S3_ENDPOINT_URL or None,
        )

    def store(self, source: Path, organization_id: int, extension: str) -> str:
        key = f"{self.prefix}/active/{organization_id}/{uuid.uuid4()}{extension}"
        encryption = settings.DOCUMENT_S3_SERVER_SIDE_ENCRYPTION
        extra_args = {"ServerSideEncryption": encryption}
        if settings.DOCUMENT_S3_KMS_KEY_ID:
            extra_args = {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": settings.DOCUMENT_S3_KMS_KEY_ID,
            }
        self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra_args)
        source.unlink(missing_ok=True)
        return f"s3://{self.bucket}/{key}"

    def read(self, locator: str) -> bytes:
        bucket, key = _parse_s3_locator(locator)
        if "/quarantine/" in f"/{key}":
            raise QuarantinedObjectUnavailable("Quarantined documents cannot be read")
        return self.client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def delete(self, locator: str) -> None:
        bucket, key = _parse_s3_locator(locator)
        self.client.delete_object(Bucket=bucket, Key=key)


def _backend():
    if settings.DOCUMENT_STORAGE_BACKEND.strip().lower() == "s3":
        return S3Storage(settings.DOCUMENT_S3_BUCKET, settings.DOCUMENT_S3_PREFIX)
    return LocalStorage(settings.DOCUMENT_LOCAL_STORAGE_ROOT)


def _validate_extension(filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return extension


def _stage(stream: BinaryIO) -> tuple[Path, int, str]:
    checksum = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(delete=False) as staged:
        staged_path = Path(staged.name)
        try:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    raise FileTooLarge(
                        f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit."
                    )
                checksum.update(chunk)
                staged.write(chunk)
        except Exception:
            staged_path.unlink(missing_ok=True)
            raise
    return staged_path, size, checksum.hexdigest()


def save_upload(file: UploadFile, organization_id: int) -> tuple[str, int, str]:
    extension = _validate_extension(file.filename)
    staged, size, checksum = _stage(file.file)
    backend = _backend()
    try:
        if settings.DOCUMENT_MALWARE_SCAN_ENABLED:
            try:
                _scan_staged_file(staged)
            except MalwareDetected as exc:
                if not isinstance(backend, LocalStorage):
                    staged.unlink(missing_ok=True)
                    raise
                locator = backend.quarantine(staged, organization_id, extension)
                raise MalwareDetected(exc.signature, locator) from exc
        locator = backend.store(staged, organization_id, extension)
        return locator, size, checksum
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def save_bytes(
    content: bytes,
    organization_id: int,
    extension: str,
) -> tuple[str, int]:
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(f"Unsupported generated file type '{extension}'.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise FileTooLarge(f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit.")

    staged, size, _checksum = _stage_bytes(content)
    try:
        return _backend().store(staged, organization_id, extension), size
    finally:
        staged.unlink(missing_ok=True)


def delete_file(storage_path: str) -> None:
    _backend_for_locator(storage_path).delete(storage_path)


def read_file(storage_path: str) -> bytes:
    return _backend_for_locator(storage_path).read(storage_path)


def _stage_bytes(content: bytes) -> tuple[Path, int, str]:
    return _stage(BytesReader(content))


class BytesReader:
    def __init__(self, content: bytes):
        self.content = content
        self.consumed = False

    def read(self, _size: int) -> bytes:
        if self.consumed:
            return b""
        self.consumed = True
        return self.content


def _backend_for_locator(locator: str):
    if locator.startswith("s3://"):
        bucket, _key = _parse_s3_locator(locator)
        return S3Storage(bucket, settings.DOCUMENT_S3_PREFIX)
    return LocalStorage(settings.DOCUMENT_LOCAL_STORAGE_ROOT)


def _parse_s3_locator(locator: str) -> tuple[str, str]:
    if not locator.startswith("s3://"):
        raise ValueError("Invalid S3 document locator")
    bucket, separator, key = locator[5:].partition("/")
    if not bucket or not separator or not key:
        raise ValueError("Invalid S3 document locator")
    return bucket, key


def _scan_staged_file(path: Path) -> None:
    try:
        with socket.create_connection(
            (settings.DOCUMENT_MALWARE_SCAN_HOST, settings.DOCUMENT_MALWARE_SCAN_PORT),
            timeout=settings.DOCUMENT_MALWARE_SCAN_TIMEOUT_SECONDS,
        ) as connection:
            connection.sendall(b"zINSTREAM\0")
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    connection.sendall(len(chunk).to_bytes(4, "big") + chunk)
            connection.sendall(b"\x00\x00\x00\x00")
            response = connection.recv(4096).decode(errors="replace").strip("\0\n")
    except OSError as exc:
        raise MalwareScannerUnavailable(f"Malware scanner unavailable: {exc}") from exc
    if response.endswith(" FOUND"):
        signature = response.rsplit(": ", 1)[-1].removesuffix(" FOUND")
        raise MalwareDetected(signature)
    if not response.endswith(" OK"):
        raise MalwareScannerUnavailable(f"Unexpected malware scanner response: {response}")


def malware_scanner_ready() -> None:
    try:
        with socket.create_connection(
            (settings.DOCUMENT_MALWARE_SCAN_HOST, settings.DOCUMENT_MALWARE_SCAN_PORT),
            timeout=settings.DOCUMENT_MALWARE_SCAN_TIMEOUT_SECONDS,
        ) as connection:
            connection.sendall(b"zPING\0")
            response = connection.recv(4096).decode(errors="replace").strip("\0\n")
    except OSError as exc:
        raise MalwareScannerUnavailable(f"Malware scanner unavailable: {exc}") from exc
    if response != "PONG":
        raise MalwareScannerUnavailable(f"Unexpected malware scanner response: {response}")
