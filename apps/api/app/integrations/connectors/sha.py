import re
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse

import httpx

from app.integrations.base import (
    BaseConnector,
    EClaimsConnector,
    EClaimsTransportResponse,
)
from app.integrations.exceptions import AuthenticationError, IntegrationError, SyncError
from app.integrations.models import CanonicalClaim, CanonicalPatient, CanonicalPayment

FHIR_JSON = "application/fhir+json"
DEFAULT_SCOPES = (
    "system/Claim.write system/ClaimResponse.read system/Coverage.read"
)


class SHAConnectorError(IntegrationError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_sha256: str | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_sha256 = response_sha256
        self.issues = issues or []


class SHAConnector(BaseConnector, EClaimsConnector):
    provider = "sha"
    supports_sync = False

    def __init__(
        self,
        organization_id: int,
        client_secret: str | None = None,
        client_id: str | None = None,
        token_url: str | None = None,
        base_url: str | None = None,
        scopes: str = DEFAULT_SCOPES,
        token_auth_method: str = "client_secret_basic",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        **_: Any,
    ) -> None:
        self.organization_id = organization_id
        self.client_secret = client_secret
        self.client_id = client_id
        self.token_url = self._https_url(token_url, "token_url")
        self.base_url = self._https_url(base_url, "base_url").rstrip("/")
        self.scopes = scopes
        self.token_auth_method = token_auth_method
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

        if token_auth_method not in {"client_secret_basic", "client_secret_post"}:
            raise ValueError(
                "SHA token_auth_method must be client_secret_basic or client_secret_post"
            )
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("SHA timeout_seconds must be greater than 0 and at most 120")

    async def authenticate(self) -> None:
        if (
            self._access_token
            and self._token_expires_at
            and self._token_expires_at > datetime.now(UTC) + timedelta(seconds=30)
        ):
            return
        if not self.client_id or not self.client_secret:
            raise AuthenticationError(
                "SHA OAuth client_id and encrypted client_secret are required"
            )

        data = {"grant_type": "client_credentials", "scope": self.scopes}
        auth: httpx.BasicAuth | None = None
        if self.token_auth_method == "client_secret_basic":
            auth = httpx.BasicAuth(self.client_id, self.client_secret)
        else:
            data.update({"client_id": self.client_id, "client_secret": self.client_secret})

        try:
            async with self._client() as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    auth=auth,
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise AuthenticationError(
                f"SHA OAuth token request failed: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            raise AuthenticationError(
                f"SHA OAuth token request returned HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthenticationError("SHA OAuth token response was not valid JSON") from exc
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise AuthenticationError("SHA OAuth token response did not include access_token")
        expires_in = payload.get("expires_in", 3600)
        try:
            expires_seconds = float(expires_in)
        except (TypeError, ValueError) as exc:
            raise AuthenticationError(
                "SHA OAuth token response included invalid expires_in"
            ) from exc
        if expires_seconds <= 0:
            raise AuthenticationError("SHA OAuth token response included invalid expires_in")
        self._access_token = token
        self._token_expires_at = datetime.now(UTC) + timedelta(
            seconds=min(expires_seconds, 3600)
        )

    async def submit_claim_bundle(
        self,
        bundle: dict[str, Any],
        *,
        correlation_id: str,
    ) -> EClaimsTransportResponse:
        return await self._fhir_request(
            "POST",
            "Bundle",
            correlation_id=correlation_id,
            payload=bundle,
            expected_statuses={200, 201, 202},
        )

    async def get_claim_response(
        self,
        external_reference: str,
        *,
        correlation_id: str,
    ) -> EClaimsTransportResponse:
        if not re.fullmatch(r"[A-Za-z0-9\-.]{1,64}", external_reference):
            raise ValueError("Invalid SHA ClaimResponse reference")
        return await self._fhir_request(
            "GET",
            f"ClaimResponse/{external_reference}",
            correlation_id=correlation_id,
            expected_statuses={200},
        )

    async def health_check(self) -> dict[str, Any]:
        started = time.monotonic()
        result = await self._fhir_request(
            "GET",
            "metadata",
            correlation_id=f"health-{self.organization_id}",
            expected_statuses={200},
        )
        return {
            "connected": result.resource.get("resourceType") == "CapabilityStatement",
            "provider": self.provider,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "api_version": result.resource.get("fhirVersion"),
        }

    async def sync_claims(self) -> list[CanonicalClaim]:
        raise SyncError("SHA is an outbound eClaims exchange, not a claim import source")

    async def sync_patients(self) -> list[CanonicalPatient]:
        raise SyncError("SHA is an outbound eClaims exchange, not a patient import source")

    async def sync_payments(self) -> list[CanonicalPayment]:
        raise SyncError(
            "SHA payments are received as PaymentNotice resources, not pull synchronization"
        )

    async def _fhir_request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str,
        expected_statuses: set[int],
        payload: dict[str, Any] | None = None,
    ) -> EClaimsTransportResponse:
        await self.authenticate()
        headers = {
            "Accept": FHIR_JSON,
            "Authorization": f"Bearer {self._access_token}",
            "X-Correlation-ID": correlation_id,
        }
        if payload is not None:
            headers["Content-Type"] = FHIR_JSON
        try:
            async with self._client() as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path}",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise SHAConnectorError(
                f"SHA FHIR request failed: {type(exc).__name__}"
            ) from exc

        body = response.content
        body_hash = sha256(body).hexdigest()
        if not body and response.status_code in expected_statuses:
            resource = {"resourceType": "Bundle"}
        else:
            try:
                resource = response.json()
            except ValueError as exc:
                raise SHAConnectorError(
                    "SHA FHIR response was not valid JSON",
                    http_status=response.status_code,
                    response_sha256=body_hash,
                ) from exc
        if not isinstance(resource, dict):
            raise SHAConnectorError(
                "SHA FHIR response must be a JSON object",
                http_status=response.status_code,
                response_sha256=body_hash,
            )
        issues = self._operation_outcome_issues(resource)
        if response.status_code not in expected_statuses or resource.get("resourceType") == (
            "OperationOutcome"
        ):
            raise SHAConnectorError(
                self._error_message(response.status_code, issues),
                http_status=response.status_code,
                response_sha256=body_hash,
                issues=issues,
            )
        external_reference = self._external_reference(response, resource)
        return EClaimsTransportResponse(
            http_status=response.status_code,
            resource=resource,
            response_sha256=body_hash,
            external_reference=external_reference,
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=False,
            transport=self._transport,
        )

    @staticmethod
    def _https_url(value: str | None, field: str) -> str:
        if not value:
            raise ValueError(f"SHA {field} is required")
        parsed = urlparse(value)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError(f"SHA {field} must be an absolute HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError(f"SHA {field} must not contain credentials")
        return value

    @staticmethod
    def _operation_outcome_issues(resource: dict[str, Any]) -> list[dict[str, Any]]:
        if resource.get("resourceType") != "OperationOutcome":
            return []
        issues = []
        for issue in resource.get("issue", []):
            details = issue.get("details") or {}
            diagnostics = issue.get("diagnostics")
            issues.append(
                {
                    "severity": issue.get("severity"),
                    "code": issue.get("code"),
                    "details": details.get("text"),
                    "diagnostics": diagnostics[:500]
                    if isinstance(diagnostics, str)
                    else None,
                    "expression": list(issue.get("expression") or []),
                }
            )
        return issues

    @staticmethod
    def _error_message(status: int, issues: list[dict[str, Any]]) -> str:
        if not issues:
            return f"SHA FHIR request returned HTTP {status}"
        first = issues[0]
        detail = first.get("details") or first.get("code") or "FHIR validation failed"
        return f"SHA FHIR request returned HTTP {status}: {detail}"

    @staticmethod
    def _external_reference(
        response: httpx.Response,
        resource: dict[str, Any],
    ) -> str | None:
        if resource.get("resourceType") == "ClaimResponse":
            resource_id = resource.get("id")
            if isinstance(resource_id, str) and resource_id:
                return resource_id
        if resource.get("resourceType") == "Bundle":
            for entry in resource.get("entry", []):
                candidate = entry.get("resource") or {}
                if candidate.get("resourceType") == "ClaimResponse":
                    resource_id = candidate.get("id")
                    if isinstance(resource_id, str) and resource_id:
                        return resource_id
        resource_id = resource.get("id")
        if isinstance(resource_id, str) and resource_id:
            return resource_id
        for header in ("Location", "Content-Location"):
            value = response.headers.get(header)
            if not value:
                continue
            segments = [segment for segment in urlparse(value).path.split("/") if segment]
            if "ClaimResponse" in segments:
                index = segments.index("ClaimResponse")
                if len(segments) > index + 1:
                    return segments[index + 1]
        return None
