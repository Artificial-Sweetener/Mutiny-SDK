from __future__ import annotations

from typing import Any, Mapping

from .services.token_provider import TokenProvider

class Config:
    token_provider: TokenProvider
    api: Any
    discord: Any
    http: Any
    websocket: Any
    cdn: Any
    cache: Any
    engine: Any

    @classmethod
    def create(
        cls,
        *,
        token_provider: TokenProvider,
        guild_id: str,
        channel_id: str,
        user_agent: str = ...,
        api_endpoint: str = ...,
        api_secret: str = ...,
        api: Mapping[str, Any] | None = ...,
        discord: Mapping[str, Any] | None = ...,
        http: Mapping[str, Any] | None = ...,
        websocket: Mapping[str, Any] | None = ...,
        cdn: Mapping[str, Any] | None = ...,
        cache: Mapping[str, Any] | None = ...,
        engine: Mapping[str, Any] | None = ...,
        execution: Mapping[str, Any] | None = ...,
    ) -> Config: ...
    def configure(
        config_obj: Config | Mapping[str, Any],
        *,
        token_provider: TokenProvider | None = ...,
        **overrides: Any,
    ) -> Config: ...
    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, token_provider: TokenProvider | None = ...
    ) -> Config: ...
    def copy(self) -> Config: ...
    def as_dict(self) -> dict[str, Any]: ...
