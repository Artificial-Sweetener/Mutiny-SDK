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

import argparse
import json
import os
import sys
import time
from pathlib import Path


def pretty_line(line: str, filters: set[str] | None = None) -> str:
    try:
        data = json.loads(line)
    except Exception:
        return line.rstrip()
    kind = data.get("kind")
    action = data.get("action")
    url = data.get("url")
    meta = data.get("meta") or {}
    if filters and kind not in filters:
        return ""
    if kind == "attachments" and isinstance(meta, dict) and meta.get("uploaded_filename"):
        return f"[{kind}] uploaded_filename={meta.get('uploaded_filename')}"
    if kind == "interaction":
        cid = meta.get("custom_id") if isinstance(meta, dict) else None
        return f"[{kind}] action={action} custom_id={cid}"
    return f"[{kind}] url={url}"


def tail_file(path: Path, filters: set[str] | None = None):
    print(f"Tailing: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            # Seek to end initially
            f.seek(0, os.SEEK_END)
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(0.25)
                    f.seek(pos)
                    continue
                out = pretty_line(line, filters)
                if out:
                    print(out)
    except KeyboardInterrupt:
        return 0
    except FileNotFoundError:
        print("File not found. Waiting for it to be created...")
        while not path.exists():
            time.sleep(0.5)
        return tail_file(path, filters)


def main():
    ap = argparse.ArgumentParser("tail-capture")
    ap.add_argument("--file", default=".cache/mutiny/dev_captures/live_capture.jsonl")
    ap.add_argument(
        "--only",
        default=None,
        help="Comma-separated kinds to show: interaction,attachments,message,other",
    )
    args = ap.parse_args()
    filters = set(args.only.split(",")) if args.only else None
    return tail_file(Path(args.file), filters)


if __name__ == "__main__":
    sys.exit(main() or 0)
