"""DR-13 verifier regression: synthetic files only, no Restic host access."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

BACKUP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKUP_DIR))
from sqlite_snapshot import prepare
from verify_sqlite_restore import RestoreVerificationError, verify, VERIFIED_DIR


class VerifyResticSqliteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dr13-verifier-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.restored = self.root / "restore"
        self.restored.mkdir()
        self.stage = self.restored / "tmp" / "staging" / ".restic-backup.ABCDEFGH" / "sqlite"
        self.stage.mkdir(parents=True)

    def make_db(self, relative="nested dir/liveness.sqlite"):
        db = self.source / relative
        db.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(db)) as con:
            con.execute("CREATE TABLE IF NOT EXISTS sample(value TEXT)")
            con.execute("INSERT INTO sample VALUES('RECONSTRUCTED')")
            con.commit()
        return db

    def stage_db(self):
        self.make_db()
        prepare(self.source, self.stage)

    def test_transactional_images_recreated_inside_private_restore_tree(self):
        self.stage_db()
        out = verify(self.restored)
        self.assertEqual(out, {"status":"verified","mode":"transactional","sqlite_databases":1})
        db = self.restored / VERIFIED_DIR / "nested dir" / "liveness.sqlite"
        self.assertTrue(db.is_file())
        with closing(sqlite3.connect(db)) as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT value FROM sample").fetchone()[0], "RECONSTRUCTED")
        self.assertTrue((self.stage/"manifest.json").is_file())

    def test_manifest_traversal_denied(self):
        self.stage_db()
        path = self.stage / "manifest.json"
        data = json.loads(path.read_text())
        data["databases"][0]["source_relative"] = "../escape.sqlite"
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            verify(self.restored)
        self.assertFalse((self.root/"escape.sqlite").exists())

    def test_corrupted_image_does_not_pass(self):
        self.stage_db()
        images = list(self.stage.rglob("*.sqlite-snapshot"))
        self.assertEqual(len(images), 1)
        images[0].write_bytes(b"invalid image")
        with self.assertRaises(Exception):
            verify(self.restored)

    def test_staging_without_manifest_is_denied(self):
        (self.stage/"broken.sqlite-snapshot").write_bytes(b"not a snapshot")
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_raw_database_present_with_transactional_manifest_is_denied(self):
        self.stage_db()
        shutil.copyfile(self.source/"nested dir/liveness.sqlite", self.restored/"raw.sqlite")
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_multiple_manifests_denied(self):
        self.stage_db()
        another = self.restored/"tmp"/"other"/".restic-backup.87654321"/"sqlite"
        another.mkdir(parents=True)
        shutil.copyfile(self.stage/"manifest.json", another/"manifest.json")
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_dual_stage_atlas_and_hermes_reconstructed(self):
        # Pentium now backs up the live Atlas DB and Hermes as independent
        # transactional roots inside one Restic snapshot.
        self.stage.rmdir()
        live = self.stage.parent / "sqlite-live"
        hermes = self.stage.parent / "sqlite-hermes"
        live.mkdir()
        hermes.mkdir()
        self.make_db("runtime/memory.sqlite3")
        prepare(self.source, live)
        other = self.root / "hermes-source"
        other.mkdir()
        with closing(sqlite3.connect(other / "state.db")) as con:
            con.execute("create table sample(value text)")
            con.execute("insert into sample values ('HERMES')")
            con.commit()
        prepare(other, hermes)
        outcome = verify(self.restored)
        self.assertEqual(outcome["mode"], "transactional")
        self.assertEqual(outcome["sqlite_databases"], 2)
        atlas_db = self.restored / VERIFIED_DIR / "sqlite-live/runtime/memory.sqlite3"
        hermes_db = self.restored / VERIFIED_DIR / "sqlite-hermes/state.db"
        self.assertTrue(atlas_db.is_file())
        self.assertTrue(hermes_db.is_file())
        with closing(sqlite3.connect(hermes_db)) as con:
            self.assertEqual(con.execute("select value from sample").fetchone()[0], "HERMES")

    def test_partial_dual_stage_denied(self):
        self.stage.rmdir()
        lone = self.stage.parent / "sqlite-live"
        lone.mkdir()
        self.make_db()
        prepare(self.source, lone)
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_mixed_legacy_and_dual_stage_denied(self):
        self.stage_db()
        newer = self.stage.parent / "sqlite-live"
        newer.mkdir()
        source = self.root / "newer-source"
        source.mkdir()
        with closing(sqlite3.connect(source / "state.db")) as con:
            con.execute("create table x(id int)")
        prepare(source, newer)
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_dual_stages_with_different_restic_root_denied(self):
        self.stage.rmdir()
        live = self.stage.parent / "sqlite-live"
        live.mkdir()
        self.make_db()
        prepare(self.source, live)
        foreign = self.restored / "other" / ".restic-backup.87654321" / "sqlite-hermes"
        foreign.mkdir(parents=True)
        source = self.root / "other-source"
        source.mkdir()
        with closing(sqlite3.connect(source / "state.db")) as con:
            con.execute("create table x(id int)")
        prepare(source, foreign)
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_symlink_denied(self):
        self.stage_db()
        try:
            (self.restored/"bad-link").symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink privilege")
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)

    def test_legacy_raw_sqlite_verified(self):
        path = self.make_db("data.db")
        shutil.copyfile(path, self.restored/"data.db")
        result = verify(self.restored)
        self.assertEqual(result["mode"], "legacy")
        self.assertEqual(result["sqlite_databases"], 1)

    def test_invalid_legacy_sqlite_denied(self):
        (self.restored/"invalid.db").write_bytes(b"bad")
        with self.assertRaises(sqlite3.DatabaseError):
            verify(self.restored)

    def test_plain_files_legacy_restore_is_supported(self):
        (self.restored/"note.txt").write_text("only text")
        self.assertEqual(verify(self.restored)["sqlite_databases"], 0)

    def test_verifier_does_not_overwrite_existing_private_destination(self):
        self.stage_db()
        (self.restored/VERIFIED_DIR).mkdir()
        sentinel=self.restored/VERIFIED_DIR/"dont-touch.txt"
        sentinel.write_text("PRESERVE")
        with self.assertRaises(RestoreVerificationError):
            verify(self.restored)
        self.assertEqual(sentinel.read_text(), "PRESERVE")


if __name__ == "__main__":
    unittest.main()
