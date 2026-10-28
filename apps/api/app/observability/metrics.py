"""Bounded in-process counters and timings for Atlas operations."""

import asyncio
import functools
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class MetricStore:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    timings: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def record_timing(self, name: str, duration_ms: float) -> None:
        self.timings[name].append(duration_ms)
        if len(self.timings[name]) > 1000:
            self.timings[name] = self.timings[name][-1000:]

    def avg_timing(self, name: str) -> float:
        values = self.timings.get(name, [])
        return sum(values) / len(values) if values else 0.0

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "avg_timings_ms": {key: round(self.avg_timing(key), 2) for key in self.timings},
        }


metrics = MetricStore()


def timed(metric_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                metrics.record_timing(metric_name, (time.monotonic() - start) * 1000)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                metrics.record_timing(metric_name, (time.monotonic() - start) * 1000)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
