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

from dataclasses import fields
from pathlib import Path

import tomllib

import mutiny
from mutiny import (
    Config,
    ImageOutput,
    ImageResolution,
    ImageTile,
    JobHandle,
    JobSnapshot,
    JobStatus,
    Mutiny,
    ProgressUpdate,
    TextOutput,
    VideoOutput,
    VideoResolution,
)


def test_public_facade_contract():
    expected = [
        "Mutiny",
        "Config",
        "JobHandle",
        "JobSnapshot",
        "ProgressUpdate",
        "JobStatus",
        "ImageResolution",
        "VideoResolution",
        "ImageTile",
        "ImageOutput",
        "VideoOutput",
        "TextOutput",
        "__version__",
    ]
    assert mutiny.__all__ == expected
    assert dir(mutiny) == sorted(expected)


def test_public_imports_resolve_expected_modules():
    assert Mutiny.__module__ == "mutiny.mutiny"
    assert Config.__module__ == "mutiny.config"
    assert JobHandle.__module__ == "mutiny.public_models"
    assert JobSnapshot.__module__ == "mutiny.public_models"
    assert ProgressUpdate.__module__ == "mutiny.public_models"
    assert ImageResolution.__module__ == "mutiny.public_models"
    assert VideoResolution.__module__ == "mutiny.public_models"
    assert ImageTile.__module__ == "mutiny.public_models"
    assert ImageOutput.__module__ == "mutiny.public_models"
    assert VideoOutput.__module__ == "mutiny.public_models"
    assert TextOutput.__module__ == "mutiny.public_models"


def test_job_status_is_exported_from_public_models():
    assert JobStatus.__module__ == "mutiny.domain.job"
    assert JobStatus.SUCCEEDED.value == "SUCCEEDED"


def test_public_model_runtime_fields_match_contract():
    assert {field.name for field in fields(JobHandle)} == {"id"}
    assert {field.name for field in fields(ImageOutput)} == {"image_url", "local_file_path"}
    assert {field.name for field in fields(VideoOutput)} == {
        "video_url",
        "local_file_path",
        "website_url",
    }
    assert {field.name for field in fields(TextOutput)} == {"text"}
    assert {field.name for field in fields(ProgressUpdate)} == {
        "job_id",
        "status_text",
        "preview_image_url",
    }
    assert {field.name for field in fields(JobSnapshot)} == {
        "id",
        "kind",
        "status",
        "progress_text",
        "preview_image_url",
        "fail_reason",
        "prompt_text",
        "output",
    }
    assert {field.name for field in fields(ImageResolution)} == {"job_id", "index"}
    assert {field.name for field in fields(VideoResolution)} == {"job_id"}
    assert {field.name for field in fields(ImageTile)} == {"job_id", "index", "image_bytes"}


def test_public_version_matches_pyproject_version():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert mutiny.__version__ == pyproject["project"]["version"]


def test_public_version_metadata_lookup_uses_distribution_name(monkeypatch):
    class MissingPyprojectPath:
        def __init__(self, *_args, **_kwargs):
            pass

        def resolve(self):
            return self

        @property
        def parents(self):
            return [self, self]

        def __truediv__(self, _other):
            return self

        def exists(self):
            return False

    requested_names = []

    def fake_version(name: str) -> str:
        requested_names.append(name)
        return "9.9.9"

    monkeypatch.setattr(mutiny, "Path", MissingPyprojectPath)
    monkeypatch.setattr(mutiny.metadata, "version", fake_version)

    assert mutiny._load_package_version() == "9.9.9"
    assert requested_names == ["mutiny-sdk"]


def test_core_docs_keep_mutiny_import_namespace():
    for path in [
        Path("README.md"),
        Path("docs/getting-started.md"),
        Path("docs/api-reference.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "mutiny_sdk" not in text
