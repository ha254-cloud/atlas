"""
In-process metrics collection.
Tracks counters and timings for key Atlas operations.
For production, export these to Prometheus, Datadog, or CloudWatch.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable
import functools


@dataclass
class MetricStore:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    timings: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def record_timing(self, name: str, duration_ms: float) -> None:
        self.timings[name].append(duration_ms)
        # Keep only last 1000 samples to bound memory
        if len(self.timings[name]) > 1000:
            self.timings[name] = self.timings[name][-1000:]

    def avg_timing(self, name: str) -> float:
        values = self.timings.get(name, [])
        return sum(values) / len(values) if values else 0.0

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "avg_timings_ms": {k: round(self.avg_timing(k), 2) for k in self.timings},
        }


# Module-level singleton
metrics = MetricStore()


def timed(metric_name: str) -> Callable:
    """Decorator that records function execution time."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                ms = (time.monotonic() - start) * 1000
                metrics.record_timing(metric_name, ms)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                ms = (time.monotonic() - start) * 1000
                metrics.record_timing(metric_name, ms)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
