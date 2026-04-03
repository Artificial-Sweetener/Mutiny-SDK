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

import base64

import pytest

from mutiny.config import _load_env_config
from mutiny.services.image_processor import OpenCVImageProcessor


@pytest.fixture
def test_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MUTINY_ENV", "development")
    monkeypatch.setenv("MJ_USER_TOKEN", "tok")
    monkeypatch.setenv("MJ_GUILD_ID", "guild")
    monkeypatch.setenv("MJ_CHANNEL_ID", "chan")
    return _load_env_config()


@pytest.fixture(scope="session")
def sample_png_bytes() -> bytes:
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAM0lEQVR4nEWLsQ3AMBCE"
        "iOTq6tQ/q3+73wrLaSIEHQh+oIoLbIB90/DkLap+mcRMTOY+Ht9YFlVseLlZAAAAAElF"
        "TkSuQmCC"
    )
    return base64.b64decode(png_b64)


@pytest.fixture
def image_processor():
    return OpenCVImageProcessor()
