"""
Server-Sent Events endpoint for real-time notifications.

Clients subscribe with:
    GET /api/v1/notifications/stream
    Authorization: Bearer <token>

The server pushes events as:
    data: {"type": "claim.analyzed", "payload": {...}}

Currently uses an in-process async queue per connection.
Future upgrade: replace with Redis Pub/Sub for multi-worker support.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_organization

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# In-process subscriber registry — keyed by organization_id
_subscribers: dict[int, list[asyncio.Queue]] = {}


def publish_notification(organization_id: int, event_type: str, payload: dict) -> None:
    """Push a notification to all SSE subscribers for this org."""
    queues = _subscribers.get(organization_id, [])
    message = json.dumps({"type": event_type, "payload": payload})
    for queue in queues:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass


async def _event_generator(
    request: Request,
    organization_id: int,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    if organization_id not in _subscribers:
        _subscribers[organization_id] = []
    _subscribers[organization_id].append(queue)

    try:
        yield 'data: {"type": "connected"}\n\n'

        while True:
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {message}\n\n"
            except TimeoutError:
                # Send keepalive ping
                yield ": ping\n\n"

    finally:
        _subscribers.get(organization_id, []).remove(queue)


@router.get("/stream")
async def notification_stream(
    request: Request,
    organization_id: int = Depends(get_current_organization),
):
    """
    Server-Sent Events stream.
    The client receives real-time notifications for the authenticated organization.
    """
    return StreamingResponse(
        _event_generator(request, organization_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
