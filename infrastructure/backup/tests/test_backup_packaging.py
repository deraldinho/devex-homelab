"""Offline fail-closed contract for the backup container packaging."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BackupPackagingTests(unittest.TestCase):
    def test_image_pins_restic_and_contains_runtime_dependencies(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(text, r"FROM restic/restic:0\.17\.3@sha256:[0-9a-f]{64}")
        self.assertIn("apk add --no-cache", text)
        for package in ("python3", "sqlite", "curl", "ca-certificates"):
            self.assertIn(package, text)
        for script in ("restic-backup.sh", "restic-verify.sh", "sqlite_snapshot.py", "verify_sqlite_restore.py", "github-sync.sh"):
            self.assertIn(script, text)
        self.assertNotIn("COPY secrets", text)
        self.assertNotIn("ADD secrets", text)
        self.assertNotIn("RESTIC_PASSWORD=", text)

    def test_compose_builds_local_image_and_has_no_unchecked_secret_defaults(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("build:", compose)
        self.assertIn("dockerfile: Dockerfile", compose)
        self.assertIn("image: devex/homelab-restic-backup:dr11", compose)
        self.assertNotIn("image: restic/restic:0.17.3", compose)
        for required in ("BACKUP_SOURCE_DIR", "RESTIC_PASSWORD_FILE", "RESTIC_REPOSITORY", "HOMELAB_NODE"):
            self.assertIn("${" + required + ":?", compose)
        self.assertIn("/data:ro", compose)
        self.assertIn("/run/secrets/restic_password:ro", compose)
        self.assertIn("/scripts/restic-backup.sh", compose)
        self.assertNotIn("privileged: true", compose)
        self.assertNotIn("ports:", compose)


if __name__ == "__main__":
    unittest.main()
