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

import logging
import os
import sqlite3
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class PersistentKV:
    """Simple SQLite-backed persistent key-value store with LRU eviction by size."""

    def __init__(self, db_path: str, max_total_bytes: int = 256 * 1024 * 1024):
        self.db_path = db_path
        self.max_total_bytes = max_total_bytes
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_ts REAL NOT NULL,
                last_access_ts REAL NOT NULL,
                size_bytes INTEGER NOT NULL,
                PRIMARY KEY(namespace, key)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kv_ns_la ON kv(namespace, last_access_ts)"
        )
        self._conn.commit()

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                logger.warning(
                    "PersistentKV close failed for %s",
                    self.db_path,
                    exc_info=True,
                )

    def _total_size(self, namespace: str) -> int:
        cur = self._conn.execute(
            "SELECT COALESCE(SUM(size_bytes),0) FROM kv WHERE namespace=?", (namespace,)
        )
        (total,) = cur.fetchone()
        return int(total or 0)

    def _evict_if_needed(self, namespace: str):
        total = self._total_size(namespace)
        if total <= self.max_total_bytes:
            return
        cur = self._conn.execute(
            "SELECT key, size_bytes FROM kv WHERE namespace=? ORDER BY last_access_ts ASC",
            (namespace,),
        )
        to_free = total - self.max_total_bytes
        freed = 0
        keys = []
        for key, size in cur:
            keys.append(key)
            freed += int(size or 0)
            if freed >= to_free:
                break
        if keys:
            self._conn.executemany(
                "DELETE FROM kv WHERE namespace=? AND key=?",
                [(namespace, k) for k in keys],
            )
            self._conn.commit()

    def get(self, namespace: str, key: str) -> Optional[str]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT value FROM kv WHERE namespace=? AND key=?",
                (namespace, key),
            )
            row = cur.fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE kv SET last_access_ts=? WHERE namespace=? AND key=?",
                (time.time(), namespace, key),
            )
            self._conn.commit()
            return row[0]

    def put(self, namespace: str, key: str, value_json: str) -> None:
        with self._lock:
            now = time.time()
            size = len(value_json.encode("utf-8"))
            self._conn.execute(
                (
                    "REPLACE INTO kv(namespace, key, value, created_ts, "
                    "last_access_ts, size_bytes) VALUES(?,?,?,?,?,?)"
                ),
                (namespace, key, value_json, now, now, size),
            )
            self._conn.commit()
            self._evict_if_needed(namespace)

    def delete(self, namespace: str, key: str) -> None:
        """Delete one stored value when it exists."""

        with self._lock:
            self._conn.execute(
                "DELETE FROM kv WHERE namespace=? AND key=?",
                (namespace, key),
            )
            self._conn.commit()

    def scan(self, namespace: str, key_prefix: str = "") -> list[tuple[str, str]]:
        """Return stored key/value pairs for one namespace and optional key prefix."""

        with self._lock:
            if key_prefix:
                cur = self._conn.execute(
                    (
                        "SELECT key, value FROM kv WHERE namespace=? AND key LIKE ? "
                        "ORDER BY key ASC"
                    ),
                    (namespace, f"{key_prefix}%"),
                )
            else:
                cur = self._conn.execute(
                    "SELECT key, value FROM kv WHERE namespace=? ORDER BY key ASC",
                    (namespace,),
                )
            return [(str(key), str(value)) for key, value in cur.fetchall()]

    def apply_batch(
        self,
        namespace: str,
        *,
        puts: dict[str, str] | None = None,
        deletes: list[str] | None = None,
    ) -> None:
        """Apply multiple puts/deletes atomically within one namespace."""

        put_items = puts or {}
        delete_keys = deletes or []
        with self._lock:
            now = time.time()
            self._conn.execute("BEGIN")
            try:
                if delete_keys:
                    self._conn.executemany(
                        "DELETE FROM kv WHERE namespace=? AND key=?",
                        [(namespace, key) for key in delete_keys],
                    )
                if put_items:
                    rows = [
                        (
                            namespace,
                            key,
                            value,
                            now,
                            now,
                            len(value.encode("utf-8")),
                        )
                        for key, value in put_items.items()
                    ]
                    self._conn.executemany(
                        (
                            "REPLACE INTO kv(namespace, key, value, created_ts, "
                            "last_access_ts, size_bytes) VALUES(?,?,?,?,?,?)"
                        ),
                        rows,
                    )
                self._conn.commit()
                self._evict_if_needed(namespace)
            except Exception:
                self._conn.rollback()
                raise


__all__ = ["PersistentKV"]
