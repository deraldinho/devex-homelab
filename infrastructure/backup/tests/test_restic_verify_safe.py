"""Fail-closed, disposable Restic DR smoke. All fixtures are synthetic."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "restic-verify.sh"


class SafeResticRestoreTests(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            self.skipTest("POSIX shell fixture; run inside disposable Linux core container")
        self.temp = tempfile.TemporaryDirectory(prefix="atlas-dr-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "existing-parent"
        self.base.mkdir()
        (self.base / "must-preserve.txt").write_text("EXISTING", encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.restic = self.bin / "restic"
        self.restic.write_text(
            """#!/bin/sh
set -eu
case "$1" in
 snapshots)
    printf '%s\\n' "$FAKE_SNAPSHOTS"
    ;;
 restore)
    echo "$2" > "$FAKE_CHOSEN_ID"
    shift 2
    [ "$1" = --target ] || exit 7
    target="$2"
    mkdir -p "$target/data"
    if [ "${FAKE_RESTORE_FAIL:-0}" = 1 ]; then
      exit 17
    fi
    if [ "${FAKE_RESTORE_SYMLINK:-0}" = 1 ]; then
      ln -s /etc/passwd "$target/data/escape"
    fi
    if [ "${FAKE_RESTORE_EMPTY:-0}" != 1 ]; then
      echo restored > "$target/data/restored.txt"
    fi
    if [ "${FAKE_RESTORE_DB:-0}" = 1 ]; then
      if [ "${FAKE_SQLITE_CORRUPT:-0}" = 1 ]; then
        echo fake > "$target/data/atlas.sqlite"
      else
        python3 - "$target/data/atlas.sqlite" <<'PY_SQLITE_FIXTURE'
import sqlite3,sys
db=sqlite3.connect(sys.argv[1])
db.execute("CREATE TABLE fixture(note TEXT)")
db.execute("INSERT INTO fixture VALUES('VALID')")
db.commit()
db.close()
PY_SQLITE_FIXTURE
      fi
    fi
    ;;
  *) exit 8 ;;
esac
""", encoding="utf-8"
        )
        self.restic.chmod(0o755)
        self.sqlite = self.bin / "sqlite3"
        self.sqlite.write_text(
            """#!/bin/sh
[ "${FAKE_SQLITE_CORRUPT:-0}" = 1 ] && { echo corrupt; exit 0; }
echo ok
""", encoding="utf-8",
        )
        self.sqlite.chmod(0o755)
        self.selected = self.root / "chosen.txt"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ.get('PATH', '')}",
            "RESTIC_BIN": str(self.restic),
            "RESTIC_REPOSITORY": "synthetic-only",
            "RESTIC_PASSWORD": "synthetic-secret-not-real",
            "HOMELAB_NODE": "pentium",
            "FAKE_CHOSEN_ID": str(self.selected),
            "FAKE_SNAPSHOTS": json.dumps([
                {"id": "a" * 64, "time": "2026-10-11T00:00:00Z", "tags": ["node:pentium"]},
                {"id": "b" * 64, "time": "2026-10-12T00:00:00Z", "tags": ["node:pentium"]},
                {"id": "c" * 64, "time": "2026-10-10T00:00:00Z", "tags": ["node:pentium"]},
            ]),
        }

    def run_verify(self, *, path=None, env=None):
        return subprocess.run(
            ["/bin/sh", str(SCRIPT), str(path or self.base)],
            env=dict(self.env, **(env or {})),
            capture_output=True, text=True, timeout=12,
        )

    def assert_parent_preserved(self):
        self.assertEqual((self.base / "must-preserve.txt").read_text(), "EXISTING")
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["must-preserve.txt"])

    def test_restores_newest_by_time_and_preserves_parent(self):
        p = self.run_verify()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.selected.read_text().strip(), "b" * 64)
        self.assertIn("DEVEX_HOMELAB_BACKUP_VERIFY_PASS", p.stdout)
        self.assert_parent_preserved()

    def test_missing_snapshots_deny_and_preserve_parent(self):
        p = self.run_verify(env={"FAKE_SNAPSHOTS": "[]"})
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("BACKUP_VERIFY_PASS", p.stdout)
        self.assert_parent_preserved()

    def test_invalid_snapshots_fail_closed(self):
        for json_text in ('{invalid', '[{"id":"../../oops","tags":["node:pentium"],"time":"bad"}]'):
            with self.subTest(payload=json_text):
                p = self.run_verify(env={"FAKE_SNAPSHOTS": json_text})
                self.assertNotEqual(p.returncode, 0)
                self.assert_parent_preserved()

    def test_empty_restore_deny_and_preserve_parent(self):
        p = self.run_verify(env={"FAKE_RESTORE_EMPTY": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_corrupt_sqlite_deny_and_preserve_parent(self):
        p = self.run_verify(env={"FAKE_RESTORE_DB": "1", "FAKE_SQLITE_CORRUPT": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_valid_sqlite_passes(self):
        p = self.run_verify(env={"FAKE_RESTORE_DB": "1"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assert_parent_preserved()

    def test_restic_restore_failure_is_not_pass(self):
        p = self.run_verify(env={"FAKE_RESTORE_FAIL": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("DEVEX_HOMELAB_BACKUP_VERIFY_PASS", p.stdout)
        self.assert_parent_preserved()

    def test_restored_symlink_cannot_escape_scratch(self):
        p = self.run_verify(env={"FAKE_RESTORE_SYMLINK": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_missing_sqlite_cli_fail_closed_if_database_restored(self):
        self.sqlite.unlink()
        if shutil.which("sqlite3", path=os.environ.get("PATH", "")):
            self.skipTest("host Linux image has sqlite3; absence cannot be simulated safely")
        p = self.run_verify(env={"FAKE_RESTORE_DB": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_symlink_parent_denied_without_touching_files(self):
        link = self.root / "link"
        link.symlink_to(self.base, target_is_directory=True)
        p = self.run_verify(path=link)
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_root_as_parent_denied(self):
        p = self.run_verify(path="/")
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_missing_repository_deny(self):
        p = self.run_verify(env={"RESTIC_REPOSITORY": ""})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()

    def test_no_credentials_deny(self):
        p = self.run_verify(env={"RESTIC_PASSWORD": "", "RESTIC_PASSWORD_FILE": ""})
        self.assertNotEqual(p.returncode, 0)
        self.assert_parent_preserved()


# New transactional-manifest scenarios are covered by the standalone
# test_verify_sqlite_restore.py and the real-Restic synthetic E2E smoke.

if __name__ == "__main__":
    unittest.main()