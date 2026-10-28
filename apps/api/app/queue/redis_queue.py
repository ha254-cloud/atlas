from collections import deque
from typing import Any


class RedisQueue:
    """Lightweight in-memory queue placeholder with Redis-like API.

    Replace with real Redis Streams / RQ / Celery integration later.
    """

    def __init__(self):
        self._queue = deque()

    def enqueue(self, item: Any):
        self._queue.append(item)

    def dequeue(self) -> Any | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def size(self) -> int:
        return len(self._queue)
