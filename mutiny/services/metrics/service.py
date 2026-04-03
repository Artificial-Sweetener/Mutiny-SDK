#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


@dataclass
class _Histogram:
    buckets: List[float]
    counts: List[int] = field(default_factory=list)
    total_count: int = 0
    total_sum: float = 0.0

    def __post_init__(self) -> None:
        self.counts = [0 for _ in self.buckets]

    def observe(self, value: float) -> None:
        v = max(0.0, float(value))
        self.total_count += 1
        self.total_sum += v
        for i, bound in enumerate(self.buckets):
            if v <= bound:
                self.counts[i] += 1

    def iter_buckets(self) -> Iterable[tuple[float, int]]:
        for bound, count in zip(self.buckets, self.counts, strict=False):
            yield bound, count


class MetricsService:
    """Prometheus-style metrics without external dependencies."""

    def __init__(self) -> None:
        self._queue_size: int = 0
        self._dispatch_latency = _Histogram(
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        self._discord_errors: Dict[str, int] = {}

    def set_queue_size(self, size: int) -> None:
        self._queue_size = max(0, int(size))

    def observe_dispatch_latency_ms(self, latency_ms: float) -> None:
        self._dispatch_latency.observe(max(0.0, float(latency_ms)) / 1000.0)

    def increment_discord_error(self, component: str) -> None:
        key = str(component or "unknown")
        self._discord_errors[key] = self._discord_errors.get(key, 0) + 1

    def render(self) -> bytes:
        lines: list[str] = []
        lines.append("# TYPE mutiny_queue_size gauge")
        lines.append(f"mutiny_queue_size {self._queue_size}")

        lines.append("# TYPE mutiny_dispatch_latency_seconds histogram")
        cumulative = 0
        for bound, count in self._dispatch_latency.iter_buckets():
            cumulative += count
            lines.append(f'mutiny_dispatch_latency_seconds_bucket{{le="{bound}"}} {cumulative}')
        lines.append(
            f'mutiny_dispatch_latency_seconds_bucket{{le="+Inf"}} '
            f"{self._dispatch_latency.total_count}"
        )
        lines.append(f"mutiny_dispatch_latency_seconds_count {self._dispatch_latency.total_count}")
        lines.append(f"mutiny_dispatch_latency_seconds_sum {self._dispatch_latency.total_sum}")

        lines.append("# TYPE mutiny_discord_errors_total counter")
        if self._discord_errors:
            for component, count in sorted(self._discord_errors.items()):
                lines.append(f'mutiny_discord_errors_total{{component="{component}"}} {count}')
        else:
            lines.append('mutiny_discord_errors_total{component="none"} 0')

        return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = ["CONTENT_TYPE_LATEST", "MetricsService"]
