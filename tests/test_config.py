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

import pytest

from mutiny.config import Config, _load_env_config
from mutiny.engine.runtime.state import State
from mutiny.services.token_provider import EnvTokenProvider


def test_config_env_and_overrides(monkeypatch):
    monkeypatch.setenv("MUTINY_ENV", "development")
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "g1")
    monkeypatch.setenv("MJ_CHANNEL_ID", "c1")

    cfg = _load_env_config()
    assert cfg.token_provider.get_token() == "tok"
    assert cfg.discord.guild_id == "g1"
    assert cfg.discord.channel_id == "c1"

    updated = cfg.configure(discord={"guild_id": "g2"})
    assert updated.discord.guild_id == "g2"
    assert updated.discord.channel_id == "c1"
    assert updated.token_provider.get_token() == "tok"


def test_config_from_env_requires_dev_flag(monkeypatch, caplog):
    monkeypatch.delenv("MUTINY_ENV", raising=False)
    monkeypatch.delenv("MJ_ENV", raising=False)
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "g1")
    monkeypatch.setenv("MJ_CHANNEL_ID", "c1")

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            _load_env_config()
    assert "Env config loading is disabled" in caplog.text


def test_env_token_provider_warns(monkeypatch, caplog):
    monkeypatch.setenv("MUTINY_ENV", "development")
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "g1")
    monkeypatch.setenv("MJ_CHANNEL_ID", "c1")

    cfg = _load_env_config()
    with caplog.at_level("WARNING"):
        assert cfg.token_provider.get_token() == "tok"
    assert "SECURITY WARNING" in caplog.text


def test_env_token_provider_requires_dev_flag(monkeypatch, caplog):
    monkeypatch.delenv("MUTINY_ENV", raising=False)
    monkeypatch.delenv("MJ_ENV", raising=False)
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")

    provider = EnvTokenProvider()
    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            provider.get_token()
    assert "Env token loading is disabled" in caplog.text


def _set_dev_env(monkeypatch):
    monkeypatch.setenv("MUTINY_ENV", "development")
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "g1")
    monkeypatch.setenv("MJ_CHANNEL_ID", "c1")


def test_config_as_dict_round_trip(monkeypatch):
    _set_dev_env(monkeypatch)
    cfg = _load_env_config()
    assert not hasattr(cfg, "features")
    snapshot = cfg.as_dict()
    assert "token_provider" not in snapshot
    assert "features" not in snapshot
    rebuilt = Config.from_dict(snapshot, token_provider=cfg.token_provider)
    assert rebuilt == cfg
    assert rebuilt.as_dict() == snapshot


def test_env_token_provider_warns_once(monkeypatch, caplog):
    _set_dev_env(monkeypatch)
    provider = EnvTokenProvider()
    with caplog.at_level("WARNING"):
        assert provider.get_token() == "tok"
        assert provider.get_token() == "tok"
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warnings) == 1


def test_env_label_in_error_message(monkeypatch, caplog):
    monkeypatch.delenv("MUTINY_ENV", raising=False)
    monkeypatch.setenv("MJ_ENV", "production")
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "g1")
    monkeypatch.setenv("MJ_CHANNEL_ID", "c1")
    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            _load_env_config()
    assert "production" in caplog.text


def test_config_has_no_public_from_env():
    assert not hasattr(Config, "from_env")


def test_state_rejects_multiple_identities(test_config):
    cfg = test_config.configure(discord={"guild_id": ["g1", "g2"]})
    with pytest.raises(ValueError):
        State(config=cfg)


class _DummyTokenProvider:
    def get_token(self):
        return "tok"


def test_config_create_defaults():
    provider = _DummyTokenProvider()
    cfg = Config.create(token_provider=provider, guild_id="g1", channel_id="c1")

    assert cfg.token_provider is provider
    assert cfg.discord.guild_id == "g1"
    assert cfg.discord.channel_id == "c1"
    assert cfg.http.read_timeout == 20.0
    assert cfg.websocket.backoff_max == 30.0
    assert cfg.engine.execution.queue_size == 10


def test_config_configure_classmethod_with_snapshot():
    provider = _DummyTokenProvider()
    base = Config.create(token_provider=provider, guild_id="g1", channel_id="c1")

    updated = Config.configure(base, http={"read_timeout": 10.5})
    assert updated.http.read_timeout == 10.5
    assert updated.discord.guild_id == base.discord.guild_id
    assert updated.token_provider is provider

    snap = base.as_dict()
    rebuilt = Config.configure(snap, token_provider=provider, http={"max_retries": 7})
    assert rebuilt.http.max_retries == 7
    assert rebuilt.discord.channel_id == "c1"


def test_config_from_dict_requires_token(monkeypatch):
    _set_dev_env(monkeypatch)
    cfg = _load_env_config()
    with pytest.raises(ValueError):
        Config.from_dict(cfg.as_dict())
