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

"""Helpers for deterministic snapshot assertions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> str:
    """Serialize with sorted keys to provide stable byte order."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(obj: Any) -> str:
    data = canonical_json(obj).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def snapshot_hash(path: Path) -> str:
    return canonical_hash(json.loads(read_snapshot(path)))


def read_snapshot(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"Missing snapshot: {path}")
    return path.read_text(encoding="utf-8")


def assert_snapshot(obj: Any, snapshot_path: Path) -> None:
    expected = read_snapshot(snapshot_path)
    assert canonical_json(obj) == expected
