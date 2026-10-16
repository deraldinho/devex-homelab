"""CP-DR12: backups transacionais restauraveis (todos os dados sao sinteticos)."""
from __future__ import annotations

import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

BACKUP = Path(__file__).resolve().parents[1]
MODULE = BACKUP / "sqlite_snapshot.py"
spec = importlib.util.spec_from_file_location("sqlite_snapshot", MODULE)
if MODULE.exists():
    sqlite_snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sqlite_snapshot)


class SqliteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cp-dr12-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "input"
        self.source.mkdir()
        self.stage = self.root / "private-stage"
        self.stage.mkdir()

    def db(self, relative="state/db with space.sqlite"):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as con:
            con.execute("CREATE TABLE IF NOT EXISTS entries(value TEXT)")
            con.execute("INSERT INTO entries VALUES('correct')")
            con.commit()
        return path

    def test_snapshot_is_sqlite_consistent_and_uses_safe_suffix(self):
        path = self.db()
        result = sqlite_snapshot.prepare(self.source, self.stage)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(len(result["databases"]), 1)
        item = result["databases"][0]
        self.assertEqual(item["source_relative"], "state/db with space.sqlite")
        safe_path = self.stage / item["backup_relative"]
        self.assertTrue(safe_path.is_file())
        self.assertTrue(safe_path.name.endswith(".sqlite-snapshot"))
        with closing(sqlite3.connect(safe_path)) as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT value FROM entries").fetchone()[0], "correct")
        self.assertEqual(json.loads((self.stage/"manifest.json").read_text())["databases"], result["databases"])
        self.assertTrue(path.is_file())

    def test_snapshot_includes_nested_db_sqlite3_and_spaces(self):
        self.db("nested dir/atlas.db")
        self.db("nested dir/events.sqlite3")
        result = sqlite_snapshot.prepare(self.source, self.stage)
        self.assertEqual({i["source_relative"] for i in result["databases"]},
                         {"nested dir/atlas.db", "nested dir/events.sqlite3"})

    def test_rejects_corrupt_database_without_partial_manifest(self):
        path = self.source / "bad.db"
        path.write_bytes(b"not a SQLite database")
        with self.assertRaises(Exception):
            sqlite_snapshot.prepare(self.source, self.stage)
        self.assertFalse((self.stage/"manifest.json").exists())

    def test_rejects_staging_inside_source(self):
        (self.source / "stage").mkdir()
        with self.assertRaises(ValueError):
            sqlite_snapshot.prepare(self.source, self.source / "stage")

    def test_restore_requires_private_target_without_overwriting(self):
        self.db("state/my.db")
        result = sqlite_snapshot.prepare(self.source, self.stage)
        recovered = self.root / "recovered"
        recovered.mkdir()
        sqlite_snapshot.restore(self.stage, recovered)
        path = recovered / "state/my.db"
        with closing(sqlite3.connect(path)) as con:
            self.assertEqual(con.execute("SELECT value FROM entries").fetchone()[0], "correct")
        with self.assertRaises(FileExistsError):
            sqlite_snapshot.restore(self.stage, recovered)

    def test_restore_rejects_traversal_manifest(self):
        self.db()
        sqlite_snapshot.prepare(self.source, self.stage)
        manifest = json.loads((self.stage/"manifest.json").read_text())
        manifest["databases"][0]["source_relative"] = "../escape.db"
        (self.stage/"manifest.json").write_text(json.dumps(manifest))
        recovered = self.root / "recovered"
        recovered.mkdir()
        with self.assertRaises(ValueError):
            sqlite_snapshot.restore(self.stage, recovered)
        self.assertFalse((self.root/"escape.db").exists())

    def test_non_sqlite_files_never_enter_stage(self):
        self.db()
        (self.source/"config.json").write_text('{"ok":true}')
        sqlite_snapshot.prepare(self.source, self.stage)
        self.assertFalse((self.stage/"config.json").exists())

    def test_empty_database_set_produces_manifest(self):
        result = sqlite_snapshot.prepare(self.source, self.stage)
        self.assertEqual(result["databases"], [])
        self.assertTrue((self.stage/"manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
