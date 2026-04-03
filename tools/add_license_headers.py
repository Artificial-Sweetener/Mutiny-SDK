#!/usr/bin/env python3
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
"""Add or update license headers in tracked Mutiny Python files.

Scans the git repository for tracked ``.py`` and ``.pyi`` files and ensures
they start with Mutiny's canonical AGPL header. The tool preserves shebang and
encoding lines, normalizes malformed known headers, and skips unknown existing
AGPL/GPL headers rather than overwriting them blindly.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

HEADER_PREFIX = "#    Mutiny - Unofficial Midjourney integration SDK"
HEADER_PREFIX_PATTERN = re.compile(r"#\s+Mutiny\s+-\s+.+")
COPYRIGHT_LINE = "#    Copyright (C) 2026  Artificial Sweetener and contributors"
LICENSE_BODY = """#
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
"""
COPYRIGHT_VARIANT_PATTERN = re.compile(
    r"#\s+Copyright \(C\)\s+\d{4}\s+Artificial Sweetener(?:\s+and\s+contributors)*"
)
NEW_HEADER_START = f"{HEADER_PREFIX}\n{COPYRIGHT_LINE}"
FULL_NEW_HEADER = f"{NEW_HEADER_START}\n{LICENSE_BODY}"
HEADER_END_MARKER = "#    along with this program.  If not, see <https://www.gnu.org/licenses/>."


def _normalize_header_block(lines: list[str]) -> list[str] | None:
    """Return lines with one malformed known header block replaced.

    Args:
        lines: File content split with ``keepends=True``.

    Returns:
        Updated lines when the file contains one recognizable Mutiny header that
        should be normalized, otherwise ``None``.
    """
    header_start = None
    header_end = None
    for idx, line in enumerate(lines):
        if HEADER_PREFIX_PATTERN.fullmatch(line.rstrip("\n")):
            header_start = idx
            break
    if header_start is None:
        return None

    for idx in range(header_start, len(lines)):
        candidate = lines[idx].rstrip("\n")
        if candidate == HEADER_END_MARKER:
            header_end = idx
            continue
        if candidate and not candidate.startswith("#"):
            break

    if header_end is None or header_end < header_start:
        return None

    existing_block = "".join(lines[header_start : header_end + 1]).rstrip("\n")
    canonical_block = FULL_NEW_HEADER.rstrip("\n")
    if existing_block == canonical_block:
        return None

    normalized_lines = [line + "\n" for line in FULL_NEW_HEADER.splitlines()]
    return lines[:header_start] + normalized_lines + lines[header_end + 1 :]


def get_tracked_python_files(repo_root: Path | None = None) -> list[Path]:
    """Return tracked Python source and stub files relative to the repo root."""
    root = repo_root or Path.cwd()
    try:
        result_py = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        result_pyi = subprocess.run(
            ["git", "ls-files", "*.pyi"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Error running git ls-files: {exc}")
        raise SystemExit(1) from exc

    files: set[Path] = set()
    if result_py.stdout:
        files.update(Path(path) for path in result_py.stdout.splitlines())
    if result_pyi.stdout:
        files.update(Path(path) for path in result_pyi.stdout.splitlines())
    return sorted(files)


def update_header(file_path: Path) -> None:
    """Add or normalize the Mutiny license header for one file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Skipping {file_path}: Unable to read (encoding issue)")
        return

    match = COPYRIGHT_VARIANT_PATTERN.search(content)
    if match and match.group(0) != COPYRIGHT_LINE:
        updated_content = f"{content[: match.start()]}{COPYRIGHT_LINE}{content[match.end() :]}"
        file_path.write_text(updated_content, encoding="utf-8", newline="\n")
        print(f"Updated header in {file_path}")
        return

    lines = content.splitlines(keepends=True)
    normalized_lines = _normalize_header_block(lines)
    if normalized_lines is not None:
        file_path.write_text("".join(normalized_lines), encoding="utf-8", newline="\n")
        print(f"Normalized header in {file_path}")
        return

    if NEW_HEADER_START in content:
        return

    if (
        "GNU Affero General Public License" in content[:1000]
        or "GNU General Public License" in content[:1000]
    ):
        print(f"Skipping {file_path}: Unknown license header already present")
        return

    insert_idx = 0
    if lines and lines[0].startswith("#!"):
        insert_idx += 1
    if (
        len(lines) > insert_idx
        and lines[insert_idx].startswith("#")
        and "coding" in lines[insert_idx]
    ):
        insert_idx += 1

    new_lines = lines[:insert_idx] + [FULL_NEW_HEADER + "\n"] + lines[insert_idx:]
    file_path.write_text("".join(new_lines), encoding="utf-8", newline="\n")
    print(f"Added header to {file_path}")


def main() -> int:
    """Update license headers in all tracked Python files."""
    files = get_tracked_python_files()
    print(f"Found {len(files)} tracked Python files.")
    for relative_path in files:
        file_path = Path(relative_path)
        if file_path.exists():
            update_header(file_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
