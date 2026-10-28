"""
Sliding-window rate limiter middleware.
Uses an in-memory store keyed by IP + JWT subject.
For multi-worker deployments, replace with Redis-backed counting.
"""

import time
from collections import defaultdict, deque

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

# (key) → deque of request timestamps
_windows: dict[str, deque] = defaultdict(deque)

DEFAULT_LIMIT = 120  # requests per window
DEFAULT_WINDOW = 60  # seconds

# Endpoints that are more expensive get tighter limits
ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/mcp/tools": (20, 60),  # AI tools: 20/min
    "/api/v1/appeals": (10, 60),  # Appeal generation: 10/min
    "/api/v1/auth/login": (10, 60),  # Login: 10/min
    "/api/v1/auth/register": (5, 60),  # Signup: 5/min
    "/api/v1/auth/forgot-password": (5, 60),  # Password reset requests: 5/min
    "/api/v1/users/invite": (10, 60),  # Team invites: 10/min
}


def _get_limit(path: str) -> tuple[int, int]:
    for prefix, limit in ENDPOINT_LIMITS.items():
        if path.startswith(prefix):
            return limit
    return DEFAULT_LIMIT, DEFAULT_WINDOW


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        limit, window = _get_limit(path)

        key = f"{client_ip}:{path}"
        now = time.monotonic()

        bucket = _windows[key]

        # Evict timestamps older than the window
        while bucket and bucket[0] < now - window:
            bucket.popleft()

        if len(bucket) >= limit:
            return Response(
                content='{"detail": "Rate limit exceeded. Please slow down."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        bucket.append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - len(bucket))
        return response
