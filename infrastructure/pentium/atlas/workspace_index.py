from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class WorkspaceIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("CREATE TABLE IF NOT EXISTS docs(path TEXT PRIMARY KEY,title TEXT NOT NULL,digest TEXT NOT NULL,content TEXT NOT NULL,sha256 TEXT NOT NULL)")
        self._fts = True
        try:
            self._db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(path,title,digest,content, content='')")
        except sqlite3.OperationalError:
            self._fts = False
        self._db.commit()

    def upsert(self, path: str, *, title: str, digest: str, content: str, sha256: str) -> bool:
        row = self._db.execute("SELECT sha256 FROM docs WHERE path=?", (path,)).fetchone()
        if row is not None and row["sha256"] == sha256:
            return False
        with self._db:
            self._db.execute(
                "INSERT INTO docs(path,title,digest,content,sha256) VALUES(?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET title=excluded.title,digest=excluded.digest,content=excluded.content,sha256=excluded.sha256",
                (path, title, digest, content, sha256),
            )
            if self._fts:
                self._db.execute("DELETE FROM docs_fts WHERE path=?", (path,))
                self._db.execute("INSERT INTO docs_fts(path,title,digest,content) VALUES(?,?,?,?)", (path, title, digest, content))
        return True

    def remove(self, path: str) -> bool:
        with self._db:
            row = self._db.execute("DELETE FROM docs WHERE path=?", (path,))
            if self._fts:
                self._db.execute("DELETE FROM docs_fts WHERE path=?", (path,))
        return row.rowcount > 0

    @staticmethod
    def _terms(query: str) -> tuple[str, ...]:
        return tuple(t for t in re.findall(r"[a-z0-9_-]+", query.lower()) if len(t) > 1)

    def search(self, query: str, *, limit: int = 10) -> tuple[dict, ...]:
        terms = self._terms(query)
        if not terms:
            return ()
        rows = self._db.execute("SELECT path,title,digest,content,sha256 FROM docs").fetchall()
        ranked = []
        for row in rows:
            title = row["title"].lower()
            digest = row["digest"].lower()
            content = row["content"].lower()
            path = row["path"].lower()
            score = 0
            for term in terms:
                score += 4 * title.count(term) + 3 * path.count(term) + 2 * digest.count(term) + min(2, content.count(term))
            if score:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["path"]))
        return tuple({"path": row["path"], "title": row["title"], "digest": row["digest"], "content": row["content"], "sha256": row["sha256"]} for _, row in ranked[:limit])

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM docs").fetchone()[0])

    def fingerprint(self) -> str:
        import hashlib
        rows = self._db.execute("SELECT path,sha256 FROM docs ORDER BY path").fetchall()
        raw = "\n".join(f"{row['path']}:{row['sha256']}" for row in rows).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def close(self) -> None:
        self._db.close()
