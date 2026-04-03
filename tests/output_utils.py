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

import json
import os
import time
from urllib.parse import urlparse

import requests

OUTPUT_DIR = os.path.join("tests", "outputs")


def _ensure_dir() -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR


def _ext_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        _, _, name = path.rpartition("/")
        if "." in name:
            return name[name.rfind(".") :]
    except Exception:
        pass
    return ".bin"


def save_task_output(task: dict, label: str) -> list[str]:
    """Save task JSON and any image_url to tests/outputs. Never raises."""
    saved: list[str] = []
    try:
        _ensure_dir()
        ts = int(time.time())
        tid = task.get("id") or "unknown"
        base = f"{label}_{tid}_{ts}"

        # Save JSON summary
        json_path = os.path.join(OUTPUT_DIR, base + ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)
        saved.append(json_path)

        # Save image if present
        image_url = task.get("image_url")
        if image_url:
            ext = _ext_from_url(image_url)
            img_path = os.path.join(OUTPUT_DIR, base + ext)
            try:
                resp = requests.get(image_url, timeout=60)
                resp.raise_for_status()
                with open(img_path, "wb") as out:
                    out.write(resp.content)
                saved.append(img_path)
            except Exception:
                # best effort
                pass
    except Exception:
        # Never fail tests because of saving outputs
        return saved
    return saved


def save_bytes(content: bytes, label: str, suffix: str = ".bin") -> str | None:
    try:
        _ensure_dir()
        ts = int(time.time())
        path = os.path.join(OUTPUT_DIR, f"{label}_{ts}{suffix}")
        with open(path, "wb") as f:
            f.write(content)
        return path
    except Exception:
        return None
