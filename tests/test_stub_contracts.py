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

import ast
from pathlib import Path


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods: set[str] = set()
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(member.name)
            return methods
    raise AssertionError(f"Class '{class_name}' not found in {path}")


def _class_fields(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields: set[str] = set()
            for member in node.body:
                if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                    fields.add(member.target.id)
            return fields
    raise AssertionError(f"Class '{class_name}' not found in {path}")


def _top_level_classes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def test_mutiny_pyi_exposes_expected_facade_methods():
    stub_path = Path("mutiny/mutiny.pyi")
    assert stub_path.exists(), "mutiny/mutiny.pyi is missing"
    methods = _class_methods(stub_path, "Mutiny")
    expected = {
        "__init__",
        "start",
        "close",
        "wait_ready",
        "events",
        "imagine",
        "describe",
        "vary_region",
        "upscale",
        "vary",
        "pan",
        "zoom",
        "animate",
        "extend",
        "blend",
        "get_job",
        "wait_for_job",
        "list_jobs",
        "resolve_image",
        "resolve_video",
        "split_image_result",
    }
    assert methods == expected


def test_config_pyi_exposes_only_config_class_and_methods():
    stub_path = Path("mutiny/config.pyi")
    assert stub_path.exists(), "mutiny/config.pyi is missing"
    assert _top_level_classes(stub_path) == {"Config"}

    methods = _class_methods(stub_path, "Config")
    expected_methods = {
        "create",
        "configure",
        "from_dict",
        "copy",
        "as_dict",
    }
    assert methods == expected_methods


def test_public_models_pyi_exposes_expected_classes_and_fields():
    stub_path = Path("mutiny/public_models.pyi")
    assert stub_path.exists(), "mutiny/public_models.pyi is missing"
    assert _top_level_classes(stub_path) == {
        "JobHandle",
        "ImageOutput",
        "VideoOutput",
        "TextOutput",
        "ProgressUpdate",
        "JobSnapshot",
        "ImageResolution",
        "VideoResolution",
        "ImageTile",
    }

    assert _class_fields(stub_path, "JobHandle") == {"id"}
    assert _class_fields(stub_path, "ImageOutput") == {"image_url", "local_file_path"}
    assert _class_fields(stub_path, "VideoOutput") == {
        "video_url",
        "local_file_path",
        "website_url",
    }
    assert _class_fields(stub_path, "TextOutput") == {"text"}
    assert _class_fields(stub_path, "ProgressUpdate") == {
        "job_id",
        "status_text",
        "preview_image_url",
    }
    assert _class_fields(stub_path, "JobSnapshot") == {
        "id",
        "kind",
        "status",
        "progress_text",
        "preview_image_url",
        "fail_reason",
        "prompt_text",
        "output",
    }
    assert _class_fields(stub_path, "ImageResolution") == {"job_id", "index"}
    assert _class_fields(stub_path, "VideoResolution") == {"job_id"}
    assert _class_fields(stub_path, "ImageTile") == {"job_id", "index", "image_bytes"}
