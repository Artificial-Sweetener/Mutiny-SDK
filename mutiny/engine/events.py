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
from typing import Any

from mutiny.discord.message_interpreter import InterpretedMessage


@dataclass(frozen=True)
class ProviderMessageReceived:
    event_type: str
    message: InterpretedMessage
    context: Any
    received_at_ms: int


@dataclass(frozen=True)
class JobCompleted:
    job: Any
    finished_at_ms: int


@dataclass(frozen=True)
class SystemError:
    source: str
    error: Exception
    context: dict
    occurred_at_ms: int


__all__ = ["ProviderMessageReceived", "JobCompleted", "SystemError"]
