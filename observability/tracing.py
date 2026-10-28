"""
Request tracing middleware.
Attaches a unique request_id to every request and logs latency.
"""

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.governance.audit.context import (
    AuditRequestContext,
    classify_device,
    reset_audit_context,
    set_audit_context,
)
from app.observability.logging import api_logger
from app.observability.metrics import metrics


class TracingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        request.state.request_id = request_id
        user_agent = request.headers.get("user-agent")
        context_token = set_audit_context(AuditRequestContext(
            correlation_id=request_id,
            ip_address=request.client.host if request.client else None,
            user_agent=user_agent,
            device=classify_device(user_agent),
        ))
        try:
            response = await call_next(request)
        finally:
            reset_audit_context(context_token)

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        metrics.record_timing("http.request_latency_ms", latency_ms)
        metrics.increment(f"http.status.{response.status_code}")

        api_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
