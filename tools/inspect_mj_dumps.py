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
from collections import Counter, defaultdict

ROOT = os.path.join(".cache", "mutiny", "mj_responses")


def main():
    index_path = os.path.join(ROOT, "index.jsonl")
    if not os.path.exists(index_path):
        print(f"No dumps found at {index_path}")
        return

    label_counts = Counter()
    id_prefix_counts = Counter()
    examples = defaultdict(list)

    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            for c in obj.get("components", []) or []:
                label = c.get("label") or "<no-label>"
                cid = c.get("custom_id") or ""
                label_counts[label] += 1
                prefix = cid.split(":", 3)[:3]
                prefix_key = ":".join(prefix) if prefix else cid
                if prefix_key:
                    id_prefix_counts[prefix_key] += 1
                    if len(examples[prefix_key]) < 3:
                        examples[prefix_key].append(cid)

    print("Top button labels:")
    for label, cnt in label_counts.most_common(20):
        print(f"  {label:24} {cnt}")

    print("\nTop custom_id prefixes:")
    for key, cnt in id_prefix_counts.most_common(30):
        ex = examples.get(key) or []
        ex_s = "; ".join(ex)
        print(f"  {key:40} {cnt}  e.g. {ex_s}")


if __name__ == "__main__":
    main()
