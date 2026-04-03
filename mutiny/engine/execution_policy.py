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

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPolicy:
    queue_size: int = 10
    core_size: int = 3
    video_core_size: int = 1
    task_timeout_minutes: int = 5


class EnginePolicy:
    """Authoritative execution limits for engine resources."""

    def __init__(self, execution: ExecutionPolicy):
        self._execution = execution
        self._queue_size = int(execution.queue_size)
        self._core_size = int(execution.core_size)
        self._video_core_size = int(execution.video_core_size)
        self._task_timeout_minutes = int(execution.task_timeout_minutes)

    @property
    def queue_size(self) -> int:
        return self._queue_size

    @property
    def core_size(self) -> int:
        return self._core_size

    @property
    def video_core_size(self) -> int:
        return self._video_core_size

    @property
    def task_timeout_minutes(self) -> int:
        return self._task_timeout_minutes

    @property
    def timeout_seconds(self) -> int:
        return self._task_timeout_minutes * 60

    def update(self, execution: ExecutionPolicy) -> None:
        """Refresh limits from a new execution snapshot."""

        self._execution = execution
        self._queue_size = int(execution.queue_size)
        self._core_size = int(execution.core_size)
        self._video_core_size = int(execution.video_core_size)
        self._task_timeout_minutes = int(execution.task_timeout_minutes)

    def as_execution(self) -> ExecutionPolicy:
        return self._execution


__all__ = ["ExecutionPolicy", "EnginePolicy"]
