"""CP-DR12: fail-closed shell integration; POSIX, fake Restic, synthetic DB only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "restic-backup.sh"


class SafeResticBackupTests(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.skipTest("Run POSIX integration in disposable Core Linux container")
        self.temp = tempfile.TemporaryDirectory(prefix="cp-dr12-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/"source"
        self.source.mkdir()
        self.state = self.root/"state"
        self.state.mkdir()
        self.stage = self.root/"staging"
        self.stage.mkdir()
        self.bin = self.root/"bin"
        self.bin.mkdir()
        self.log = self.root/"commands.log"
        self.inspect = self.root/"snapshot-check.json"
        fake = self.bin/"restic"
        fake.write_text("""#!/bin/sh
set -eu
printf '%s\\n' "$1" >> "$FAKE_RESTIC_CALLS"
op="$1"
shift
case "$op" in
  snapshots) [ "${FAKE_SNAPSHOTS_FAIL:-0}" != 1 ] || exit 10; printf '[]\\n';;
  backup)
    [ "${FAKE_BACKUP_FAIL:-0}" != 1 ] || exit 3
    for a do
      case "$a" in
        */sqlite)
          python3 -c '
import json,pathlib,sqlite3,sys
base=pathlib.Path(sys.argv[1])
manifest=json.loads((base/"manifest.json").read_text())
data=[]
for db in manifest["databases"]:
    path=base/db["backup_relative"]
    con=sqlite3.connect(path)
    data.append({"integrity":con.execute("PRAGMA integrity_check").fetchone()[0],
                 "rows":con.execute("SELECT value FROM entries").fetchall()})
    con.close()
pathlib.Path(sys.argv[2]).write_text(json.dumps(data))
' "$a" "$FAKE_STAGE_CHECK"
          ;;
      esac
    done
    echo '{"message_type":"summary","snapshot_id":"aaaaaaaaaaaaaaaa"}';;
  forget) [ "${FAKE_FORGET_FAIL:-0}" != 1 ];;
  check) [ "${FAKE_CHECK_FAIL:-0}" != 1 ];;
  *) exit 66;;
esac
""", encoding="utf-8")
        fake.chmod(0o755)
        self.restic = fake
        self.env = {
            **os.environ, "RESTIC_BIN": str(fake),
            "RESTIC_REPOSITORY": "synthetic-local-only",
            "RESTIC_PASSWORD": "synthetic-test-password",
            "RESTIC_PASSWORD_FILE": "",
            "HOMELAB_NODE": "pentium",
            "HOMELAB_STATE_DIR": str(self.state),
            "BACKUP_STAGING_PARENT": str(self.stage),
            "FAKE_RESTIC_CALLS": str(self.log),
            "FAKE_STAGE_CHECK": str(self.inspect),
        }

    def db(self, name="nested dir/database.sqlite"):
        path = self.source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE entries(value TEXT)")
        con.execute("INSERT INTO entries VALUES('synthetic')")
        con.commit()
        con.close()
        return path

    def run_backup(self, *, env=None):
        return subprocess.run(
            ["/bin/sh", str(SCRIPT), str(self.source)],
            env=dict(self.env, **(env or {})),
            capture_output=True, text=True, timeout=20,
        )

    def status(self):
        return json.loads((self.state/"backup_status.json").read_text())

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def assert_clean_stage(self):
        self.assertEqual(list(self.stage.iterdir()), [])

    def test_success_transactional_images_and_cleanup(self):
        self.db()
        proc = self.run_backup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DEVEX_HOMELAB_BACKUP_PASS", proc.stdout)
        self.assertEqual(self.calls(), ["snapshots", "backup", "forget", "check"])
        self.assertEqual(self.status()["status"], "healthy")
        self.assertEqual(self.status()["snapshot_id"], "a"*16)
        data = json.loads(self.inspect.read_text())
        self.assertEqual(data, [{"integrity":"ok", "rows":[["synthetic"]]}])
        self.assert_clean_stage()

    def test_missing_repository_is_not_initialized(self):
        self.db()
        proc = self.run_backup(env={"FAKE_SNAPSHOTS_FAIL": "1"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.calls(), ["snapshots"])
        self.assertEqual(self.status()["status"], "failed")
        self.assertNotIn("BACKUP_PASS", proc.stdout)
        self.assert_clean_stage()

    def test_corrupt_sqlite_does_not_fallback_to_copy(self):
        (self.source/"bad.sqlite").write_text("not a database")
        proc = self.run_backup()
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.calls(), ["snapshots"])
        self.assertEqual(self.status()["status"], "failed")
        self.assert_clean_stage()

    def test_backup_partial_failure_not_healthy(self):
        self.db()
        proc = self.run_backup(env={"FAKE_BACKUP_FAIL": "1"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.calls(), ["snapshots", "backup"])
        self.assertEqual(self.status()["status"], "failed")
        self.assert_clean_stage()

    def test_check_failure_marks_failed(self):
        self.db()
        proc = self.run_backup(env={"FAKE_CHECK_FAIL": "1"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.calls(), ["snapshots", "backup", "forget", "check"])
        self.assertEqual(self.status()["status"], "failed")
        self.assert_clean_stage()

    def test_missing_credentials_denies_without_restic(self):
        proc = self.run_backup(env={"RESTIC_PASSWORD": ""})
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.status()["status"], "failed")

    def test_no_sqlite_still_creates_normal_snapshot(self):
        (self.source/"plain.txt").write_text("test")
        proc = self.run_backup()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.calls(), ["snapshots", "backup", "forget", "check"])
        self.assertFalse(self.inspect.exists())
        self.assert_clean_stage()


if __name__ == "__main__":
    unittest.main()
