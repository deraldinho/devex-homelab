from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class WorkspaceContextCache:
    def __init__(self, path: Path, *, ttl_s: float, max_entries: int, clock=None):
        if ttl_s <= 0 or max_entries <= 0:
            raise ValueError("cache_limits_invalid")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_s = float(ttl_s)
        self.max_entries = int(max_entries)
        self._clock = clock or time.monotonic
        self._db = sqlite3.connect(self.path)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache(cache_key TEXT PRIMARY KEY,created_at REAL NOT NULL,last_access REAL NOT NULL,value_json TEXT NOT NULL)")
        self._db.commit()

    @staticmethod
    def key(*, content_hash: str, query: str, intent: str, policy_version: str) -> str:
        raw = json.dumps({"content_hash": content_hash, "query": query, "intent": intent, "policy_version": policy_version}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, *, content_hash: str, query: str, intent: str, policy_version: str):
        key = self.key(content_hash=content_hash, query=query, intent=intent, policy_version=policy_version)
        row = self._db.execute("SELECT created_at,value_json FROM cache WHERE cache_key=?", (key,)).fetchone()
        if row is None:
            return None
        now = float(self._clock())
        if now - float(row[0]) > self.ttl_s:
            with self._db:
                self._db.execute("DELETE FROM cache WHERE cache_key=?", (key,))
            return None
        with self._db:
            self._db.execute("UPDATE cache SET last_access=? WHERE cache_key=?", (now, key))
        return json.loads(row[1])

    def put(self, *, content_hash: str, query: str, intent: str, policy_version: str, value) -> None:
        key = self.key(content_hash=content_hash, query=query, intent=intent, policy_version=policy_version)
        now = float(self._clock())
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._db:
            self._db.execute("INSERT INTO cache(cache_key,created_at,last_access,value_json) VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET created_at=excluded.created_at,last_access=excluded.last_access,value_json=excluded.value_json", (key, now, now, payload))
            overflow = self._db.execute("SELECT cache_key FROM cache ORDER BY last_access DESC,cache_key LIMIT -1 OFFSET ?", (self.max_entries,)).fetchall()
            for row in overflow:
                self._db.execute("DELETE FROM cache WHERE cache_key=?", (row[0],))

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0])

    def close(self) -> None:
        self._db.close()
