"""Regression guards for Atlas Pentium production backup coverage."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "tools" / "atlas-pentium-backup.sh"


class PentiumBackupContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = BACKUP.read_text(encoding="utf-8")

    def test_runtime_is_explicitly_included(self):
        self.assertIn('SOURCE_LIVE_ATLAS="$HOME_DIR/pentium-agent/atlas"', self.script)
        self.assertIn('test -d "$SOURCE_LIVE_ATLAS"', self.script)
        self.assertIn('"$SOURCE_LIVE_ATLAS" "$STAGING/sqlite-hermes" "$STAGING/sqlite-live"', self.script)

    def test_hermes_and_runtime_sqlite_are_both_transactional(self):
        self.assertIn('prepare "$SOURCE_HERMES" "$STAGING/sqlite-hermes"', self.script)
        self.assertIn('prepare "$SOURCE_LIVE_ATLAS" "$STAGING/sqlite-live"', self.script)
        for excluded in ('*.db', '*.sqlite', '*.sqlite3', '*-wal', '*-shm'):
            self.assertIn(f"--exclude '{excluded}'", self.script)

    def test_no_automatic_destructive_retention_or_unlock(self):
        for command in ('"forget"', '"prune"', '"unlock"', '"init"'):
            self.assertNotIn(command, self.script)
        self.assertIn('flock -n 9', self.script)
        self.assertIn('check --read-data-subset=2%', self.script)


if __name__ == "__main__":
    unittest.main()
