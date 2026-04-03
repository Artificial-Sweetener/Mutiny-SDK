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

import importlib.util
import sys
import textwrap
import uuid
from pathlib import Path


def _load_checker_module():
    module_path = Path(__file__).resolve().parents[2] / "tools" / "check_consistency.py"
    module_name = f"check_consistency_tool_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load check_consistency module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_files(repo_root: Path, files: dict[str, str]) -> None:
    for rel_path, content in files.items():
        path = repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _contract_files() -> dict[str, str]:
    return {
        "mutiny/mutiny.pyi": """
            class Mutiny:
                def start(self) -> None: ...
                def imagine(self, prompt: str) -> None: ...
        """,
        "mutiny/config.pyi": """
            class Config:
                def create(self) -> None: ...
        """,
        "mutiny/public_models.pyi": """
            from .types import JobStatus

            ImageInput = bytes | str

            class JobHandle:
                id: str
        """,
        "mutiny/mutiny.py": """
            class Mutiny:
                def start(self) -> None:
                    return None
                def imagine(self, prompt: str) -> None:
                    return None
        """,
        "mutiny/config.py": """
            class Config:
                def create(self) -> None:
                    return None
        """,
        "mutiny/public_models.py": """
            from dataclasses import dataclass

            ImageInput = bytes | str

            @dataclass(frozen=True)
            class JobHandle:
                id: str
        """,
        "mutiny/__init__.py": """
            _LAZY_SYMBOLS = {
                "Mutiny": "mutiny.mutiny",
                "Config": "mutiny.config",
                "JobHandle": "mutiny.public_models",
                "JobStatus": "mutiny.public_models",
            }
            __all__ = ["Mutiny", "Config", "JobHandle", "JobStatus", "__version__"]
        """,
    }


def test_impl_drift_reports_missing_members(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "mutiny/mutiny.py"
    ] = """
        class Mutiny:
            def start(self) -> None:
                return None
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="impl")

    assert any(issue.rule_id == "IMPL_MEMBER_MISSING" for issue in issues)
    assert any(issue.symbol == "Mutiny.imagine" for issue in issues)


def test_demo_compliance_reports_internal_and_private_usage(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "examples/demo.py"
    ] = """
        from mutiny.domain.job import JobStatus
        from mutiny import Mutiny

        client = Mutiny()
        client._state
        client.stop()
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="demo")
    rules = {issue.rule_id for issue in issues}

    assert "DEMO_INTERNAL_IMPORT" in rules
    assert "DEMO_PRIVATE_ACCESS" in rules
    assert "DEMO_UNKNOWN_METHOD" in rules


def test_demo_compliance_reports_invalid_root_imports(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "examples/demo.py"
    ] = """
        from mutiny import Mutiny, GhostType

        client = Mutiny()
        client.start()
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="demo")

    assert any(
        issue.rule_id == "DEMO_ROOT_IMPORT" and issue.symbol == "GhostType" for issue in issues
    )


def test_docs_check_reports_missing_docs_dir(tmp_path: Path):
    checker = _load_checker_module()
    _write_files(tmp_path, _contract_files())

    issues = checker.run_checks(repo_root=tmp_path, section_filter="docs")
    rules = {issue.rule_id for issue in issues}

    assert "DOCS_DIR_MISSING" in rules
    assert "DOCS_API_REFERENCE_MISSING" in rules


def test_docs_check_reports_ghost_symbols_and_internal_modules(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "docs/api-reference.md"
    ] = """
        `Mutiny`
        `Config`
        `Mutiny.start()`
        `Config.create(...)`
        `Mutiny.ghost_call`
        `mutiny.types`
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="docs")

    assert any(
        issue.rule_id == "DOCS_GHOST_SYMBOL" and issue.symbol == "Mutiny.ghost_call"
        for issue in issues
    )
    assert any(
        issue.rule_id == "DOCS_INTERNAL_REFERENCE" and issue.symbol == "mutiny.types"
        for issue in issues
    )


def test_docs_check_reports_invalid_root_imports(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "docs/api-reference.md"
    ] = """
        from mutiny import Mutiny, GhostType
        `Mutiny`
        `Config`
        `Mutiny.start()`
        `Mutiny.imagine()`
        `Config.create(...)`
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="docs")

    assert any(
        issue.rule_id == "DOCS_BAD_IMPORT" and issue.symbol == "GhostType" for issue in issues
    )


def test_impl_drift_reports_missing_public_model_fields(tmp_path: Path):
    checker = _load_checker_module()
    files = _contract_files()
    files[
        "mutiny/public_models.py"
    ] = """
        from dataclasses import dataclass

        ImageInput = bytes | str

        @dataclass(frozen=True)
        class JobHandle:
            pass
    """
    _write_files(tmp_path, files)

    issues = checker.run_checks(repo_root=tmp_path, section_filter="impl")

    assert any(
        issue.rule_id == "IMPL_MEMBER_MISSING" and issue.symbol == "JobHandle.id"
        for issue in issues
    )
