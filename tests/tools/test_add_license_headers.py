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

"""Regression tests for the Mutiny license-header maintenance tool."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import uuid
from pathlib import Path


def _load_tool_module():
    """Load the tool module under a unique name so tests stay isolated."""
    module_path = Path(__file__).resolve().parents[2] / "tools" / "add_license_headers.py"
    module_name = f"add_license_headers_tool_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load add_license_headers module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    """Write normalized UTF-8 test content to one temporary path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8", newline="\n")


def test_adds_header_to_plain_python_file(tmp_path: Path):
    """Add the canonical Mutiny header when one file has none."""
    tool = _load_tool_module()
    target = tmp_path / "sample.py"
    _write(
        target,
        """
        def meaning() -> int:
            return 42
        """,
    )

    tool.update_header(target)

    updated = target.read_text(encoding="utf-8")
    assert updated.startswith(tool.FULL_NEW_HEADER)
    assert "def meaning() -> int:" in updated


def test_preserves_shebang_and_encoding_lines(tmp_path: Path):
    """Keep shebang and encoding lines ahead of the inserted header."""
    tool = _load_tool_module()
    target = tmp_path / "script.py"
    _write(
        target,
        """
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        print("hello")
        """,
    )

    tool.update_header(target)

    updated = target.read_text(encoding="utf-8").splitlines()
    assert updated[0] == "#!/usr/bin/env python3"
    assert updated[1] == "# -*- coding: utf-8 -*-"
    assert updated[2] == tool.HEADER_PREFIX


def test_normalizes_known_malformed_header_block(tmp_path: Path):
    """Replace malformed known Mutiny headers with the canonical block."""
    tool = _load_tool_module()
    target = tmp_path / "malformed.py"
    _write(
        target,
        f"""
        {tool.HEADER_PREFIX}
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

        def main() -> None:
            return None
        """,
    )

    tool.update_header(target)

    updated = target.read_text(encoding="utf-8")
    assert updated.startswith(tool.FULL_NEW_HEADER)
    assert tool.COPYRIGHT_LINE in updated
    assert "#    Copyright (C) 2025  Artificial Sweetener and contributors" not in updated


def test_normalizes_legacy_mutiny_title_without_hardcoded_match_list(tmp_path: Path):
    """Normalize older Mutiny title lines as long as the header shape matches."""
    tool = _load_tool_module()
    target = tmp_path / "legacy_title.py"
    _write(
        target,
        """
        #    Mutiny - Some older product title
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

        def main() -> None:
            return None
        """,
    )

    tool.update_header(target)

    updated = target.read_text(encoding="utf-8")
    assert updated.startswith(tool.FULL_NEW_HEADER)


def test_skips_unknown_existing_agpl_header(tmp_path: Path, capsys):
    """Leave unrelated existing AGPL headers untouched."""
    tool = _load_tool_module()
    target = tmp_path / "unknown.py"
    original = textwrap.dedent(
        """
        # Custom project header
        # GNU Affero General Public License

        def main() -> None:
            return None
        """
    ).lstrip()
    target.write_text(original, encoding="utf-8", newline="\n")

    tool.update_header(target)

    assert target.read_text(encoding="utf-8") == original
    captured = capsys.readouterr()
    assert "Unknown license header already present" in captured.out
