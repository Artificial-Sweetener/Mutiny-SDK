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

from dataclasses import dataclass, fields
from enum import Enum
from typing import List, Set

from ...config import Config
from ...services.token_provider import TokenProvider


class HotAction(str, Enum):
    UPDATE_RESPONSE_DUMP = "update_response_dump"
    UPDATE_CACHE = "update_cache"
    UPDATE_HTTP = "update_http"
    UPDATE_CDN = "update_cdn"
    UPDATE_WEBSOCKET = "update_websocket"
    UPDATE_EXECUTION = "update_execution"


@dataclass(frozen=True)
class ConfigDelta:
    token_changed: bool
    identity_changed: Set[str]
    api_changed: Set[str]
    http_changed: Set[str]
    websocket_changed: Set[str]
    cdn_changed: Set[str]
    cache_changed: Set[str]
    execution_changed: Set[str]
    response_dump_changed: bool


@dataclass(frozen=True)
class ChangePlan:
    requires_restart: bool
    restart_reasons: List[str]
    hot_actions: List[HotAction]
    delta: ConfigDelta


def diff_config(old: Config, new: Config) -> ConfigDelta:
    """Compute a structured diff between two Config snapshots."""

    def _diff_section(old_section, new_section) -> Set[str]:
        if old_section.__class__ is not new_section.__class__:
            return {"__class__"}
        changed: Set[str] = set()
        for field in fields(old_section):
            name = field.name
            if getattr(old_section, name) != getattr(new_section, name):
                changed.add(name)
        return changed

    def _token_value(provider: TokenProvider) -> str | None:
        try:
            return provider.get_token()
        except Exception:
            return None

    token_changed = old.token_provider is not new.token_provider
    old_token = _token_value(old.token_provider)
    new_token = _token_value(new.token_provider)
    if old_token != new_token:
        token_changed = True

    identity_changed = _diff_section(old.discord, new.discord)
    api_changed = _diff_section(old.api, new.api)
    http_changed = _diff_section(old.http, new.http)
    websocket_changed = _diff_section(old.websocket, new.websocket)
    cdn_changed = _diff_section(old.cdn, new.cdn)
    cache_changed = _diff_section(old.cache, new.cache)
    execution_changed = _diff_section(old.engine.execution, new.engine.execution)

    response_dump_changed = False
    if "capture_enabled" in websocket_changed:
        response_dump_changed = True
    if "response_dump_dir" in cache_changed:
        response_dump_changed = True

    return ConfigDelta(
        token_changed=token_changed,
        identity_changed=identity_changed,
        api_changed=api_changed,
        http_changed=http_changed,
        websocket_changed=websocket_changed,
        cdn_changed=cdn_changed,
        cache_changed=cache_changed,
        execution_changed=execution_changed,
        response_dump_changed=response_dump_changed,
    )


def plan_changes(delta: ConfigDelta) -> ChangePlan:
    """Produce a hot-apply vs. restart plan for a given config delta."""

    restart_reasons: List[str] = []
    hot_actions: List[HotAction] = []

    if delta.token_changed:
        restart_reasons.append("Token provider change requires restart")

    if delta.identity_changed:
        restart_reasons.append("Discord identity change requires restart")

    if delta.api_changed:
        restart_reasons.append("API settings change requires restart")

    http_changed = set(delta.http_changed)
    websocket_changed = set(delta.websocket_changed)
    cdn_changed = set(delta.cdn_changed)
    cache_changed = set(delta.cache_changed)

    if cache_changed:
        hot_actions.append(HotAction.UPDATE_CACHE)

    if http_changed:
        hot_actions.append(HotAction.UPDATE_HTTP)

    if cdn_changed:
        hot_actions.append(HotAction.UPDATE_CDN)

    if websocket_changed:
        hot_actions.append(HotAction.UPDATE_WEBSOCKET)

    if delta.execution_changed:
        hot_actions.append(HotAction.UPDATE_EXECUTION)

    if delta.response_dump_changed:
        hot_actions.append(HotAction.UPDATE_RESPONSE_DUMP)

    requires_restart = bool(restart_reasons)
    return ChangePlan(
        requires_restart=requires_restart,
        restart_reasons=restart_reasons,
        hot_actions=hot_actions,
        delta=delta,
    )


__all__ = ["ConfigDelta", "ChangePlan", "HotAction", "diff_config", "plan_changes"]
