"""Scheduled SFTP CSV claim ingestion connector."""

import asyncio
import base64
import csv
import fnmatch
import hashlib
import io
import posixpath
import time
from types import SimpleNamespace
from typing import Any

import paramiko

from app.canonical.normalizers.csv import CSVNormalizer
from app.integrations.base import BaseConnector
from app.integrations.exceptions import AuthenticationError, IntegrationError
from app.integrations.mapping import MappingError, apply_mapping
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment


class _FingerprintPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected: str):
        self.expected = expected.removeprefix("SHA256:")

    def missing_host_key(self, client, hostname, key):
        actual = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
        if actual != self.expected:
            raise paramiko.SSHException(f"SFTP host key mismatch for {hostname}")
        client.get_host_keys().add(hostname, key.get_name(), key)


class SFTPConnector(BaseConnector):
    provider = "sftp"

    def __init__(
        self,
        organization_id: int,
        hostname: str | None = None,
        port: int = 22,
        username: str | None = None,
        remote_path: str = "/claims",
        file_pattern: str = "*.csv",
        host_key_sha256: str | None = None,
        known_hosts_path: str | None = None,
        allow_unknown_host: bool = False,
        access_token: str | None = None,
        refresh_token: str | None = None,
        processed_files: list[str] | None = None,
        field_mapping: list[dict] | None = None,
        mapping_profile_id: int | None = None,
        **_,
    ):
        self.organization_id = organization_id
        self.hostname = hostname
        self.port = port
        self.username = username
        self.remote_path = remote_path
        self.file_pattern = file_pattern
        self.host_key_sha256 = host_key_sha256
        self.known_hosts_path = known_hosts_path
        self.allow_unknown_host = allow_unknown_host
        self.password = access_token
        self.private_key = refresh_token
        self.processed_files = set(processed_files or [])
        self.field_mapping = [SimpleNamespace(**field) for field in field_mapping or []]
        self.mapping_profile_id = mapping_profile_id
        self.rejection_details: list[dict] = []
        self.normalizer = CSVNormalizer()

    async def authenticate(self) -> None:
        await asyncio.to_thread(self._check_connection)

    async def sync_claims(self) -> list[CanonicalClaim]:
        return await asyncio.to_thread(self._fetch_claims)

    async def sync_patients(self) -> list[CanonicalPatient]:
        return []

    async def sync_payments(self) -> list[CanonicalPayment]:
        return []

    async def health_check(self) -> dict[str, Any]:
        start = time.monotonic()
        await asyncio.to_thread(self._check_connection)
        return {
            "connected": True,
            "provider": self.provider,
            "latency_ms": int((time.monotonic() - start) * 1000),
        }

    def _client(self) -> paramiko.SSHClient:
        if not self.hostname or not self.username:
            raise AuthenticationError("SFTP hostname and username are required")
        if not self.password and not self.private_key:
            raise AuthenticationError("SFTP password or private key is required")

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.known_hosts_path:
            client.load_host_keys(self.known_hosts_path)
        if self.host_key_sha256:
            client.set_missing_host_key_policy(_FingerprintPolicy(self.host_key_sha256))
        elif self.allow_unknown_host:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        connect_kwargs: dict[str, Any] = {
            "hostname": self.hostname,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "look_for_keys": False,
            "allow_agent": False,
            "timeout": 15,
        }
        if self.private_key:
            connect_kwargs["pkey"] = self._parse_private_key(self.private_key)
            connect_kwargs["password"] = None
        client.connect(**connect_kwargs)
        return client

    @staticmethod
    def _parse_private_key(value: str) -> paramiko.PKey:
        for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                return key_class.from_private_key(io.StringIO(value))
            except (paramiko.SSHException, ValueError):
                continue
        raise AuthenticationError("Unsupported or invalid SFTP private key")

    def _check_connection(self) -> None:
        client = self._client()
        try:
            sftp = client.open_sftp()
            try:
                sftp.stat(self.remote_path)
            finally:
                sftp.close()
        finally:
            client.close()

    def _fetch_claims(self) -> list[CanonicalClaim]:
        client = self._client()
        claims: list[CanonicalClaim] = []
        try:
            sftp = client.open_sftp()
            try:
                for entry in sorted(
                    sftp.listdir_attr(self.remote_path), key=lambda item: item.filename
                ):
                    if not fnmatch.fnmatch(entry.filename, self.file_pattern):
                        continue
                    remote_file = posixpath.join(self.remote_path, entry.filename)
                    file_id = f"{remote_file}:{entry.st_size}:{entry.st_mtime}"
                    if file_id in self.processed_files:
                        continue
                    with sftp.open(remote_file, "r") as stream:
                        payload = stream.read()
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8-sig")
                    claims.extend(self._parse_csv(payload, file_id, remote_file))
            finally:
                sftp.close()
        finally:
            client.close()
        return claims

    def _parse_csv(self, payload: str, file_id: str, remote_file: str) -> list[CanonicalClaim]:
        claims: list[CanonicalClaim] = []
        try:
            rows = csv.DictReader(io.StringIO(payload))
            for row_number, row in enumerate(rows, start=2):
                try:
                    mapped = apply_mapping(row, self.field_mapping) if self.field_mapping else row
                    canonical = self.normalizer.normalize(mapped)
                    canonical.external_id = file_id
                    canonical.source_system = f"sftp:{remote_file}"
                    claims.append(canonical)
                except MappingError as exc:
                    self.rejection_details.append(
                        {
                            "row_number": row_number,
                            "source_field": exc.source_field,
                            "error_code": exc.code,
                            "message": str(exc),
                        }
                    )
                except (KeyError, ValueError, TypeError) as exc:
                    self.rejection_details.append(
                        {
                            "row_number": row_number,
                            "source_field": None,
                            "error_code": "invalid_record",
                            "message": f"Row {row_number} could not be normalized: {exc}",
                        }
                    )
        except Exception as exc:
            raise IntegrationError(f"Invalid claim CSV {remote_file}: {exc}") from exc
        return claims
