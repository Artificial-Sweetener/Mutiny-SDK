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

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

DEV_ENV_VALUES = {"development", "dev"}
ENV_FLAG_KEYS = ("MUTINY_ENV", "MJ_ENV")


def get_env_label() -> str | None:
    for key in ENV_FLAG_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


def is_dev_env() -> bool:
    label = get_env_label()
    return bool(label and label.lower() in DEV_ENV_VALUES)


@runtime_checkable
class TokenProvider(Protocol):
    """Provide a Discord user token for authentication."""

    def get_token(self) -> str:
        """Return the Discord user token."""


class EnvTokenProvider:
    """Load a token from environment variables (including .env)."""

    def __init__(self, env_key: str = "MJ_USER_TOKEN") -> None:
        self._env_key = env_key
        self._warned = False

    def get_token(self) -> str:
        token = os.getenv(self._env_key, "")
        if not token:
            raise RuntimeError(f"Missing {self._env_key} in environment")
        if not is_dev_env():
            label = get_env_label() or "unset"
            logger.error(
                "Env token loading is disabled unless MUTINY_ENV=development (current: %s).",
                label,
            )
            raise RuntimeError("Env token loading requires MUTINY_ENV=development")
        self._warn_once()
        return token

    def _warn_once(self) -> None:
        if self._warned:
            return
        self._warned = True
        logger.warning(
            "SECURITY WARNING: Loading Discord user token from environment/.env.\n"
            "This is intended for development only; do not use plaintext tokens in production.\n"
            "Use a secrets manager or keychain-backed TokenProvider instead."
        )


__all__ = ["TokenProvider", "EnvTokenProvider", "get_env_label", "is_dev_env"]
