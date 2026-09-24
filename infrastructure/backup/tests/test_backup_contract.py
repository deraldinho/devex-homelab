import json
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

BACKUP_DIR = Path(__file__).resolve().parent.parent
PENTIUM_DIR = BACKUP_DIR.parent / "pentium"
sys.path.insert(0, str(PENTIUM_DIR / "heartbeat"))

import heartbeat

class BackupContractTests(unittest.TestCase):
    def test_compose_file_exists_and_declares_ro_sources(self):
        compose_path = BACKUP_DIR / "compose.yaml"
        self.assertTrue(compose_path.is_file(), "compose.yaml de backup deve existir")
        content = compose_path.read_text(encoding="utf-8")
        self.assertIn("restic/restic", content)
        self.assertIn(":ro", content, "Fonte de dados deve ser montada como read-only")
        self.assertIn("RESTIC_PASSWORD_FILE", content)

    def test_scripts_exist_and_use_strict_flags(self):
        backup_sh = BACKUP_DIR / "restic-backup.sh"
        verify_sh = BACKUP_DIR / "restic-verify.sh"
        self.assertTrue(backup_sh.is_file(), "restic-backup.sh deve existir")
        self.assertTrue(verify_sh.is_file(), "restic-verify.sh deve existir")

        backup_content = backup_sh.read_text(encoding="utf-8")
        verify_content = verify_sh.read_text(encoding="utf-8")

        self.assertIn("set -eu", backup_content)
        self.assertIn("set -eu", verify_content)

    def test_backup_script_enforces_retention_policy(self):
        backup_content = (BACKUP_DIR / "restic-backup.sh").read_text(encoding="utf-8")
        self.assertIn("--keep-daily 7", backup_content)
        self.assertIn("--keep-weekly 4", backup_content)
        self.assertIn("--keep-monthly 12", backup_content)
        self.assertIn("--prune", backup_content)

    def test_backup_script_includes_transactional_sqlite_hook(self):
        backup_content = (BACKUP_DIR / "restIC-backup.sh".lower()).read_text(encoding="utf-8")
        self.assertIn(".backup", backup_content, "Deve conter pré-hook de backup transacional SQLite")
        self.assertIn("unlock", backup_content, "Deve tentar auto-unlock preventivo")
        self.assertIn("backup_status.json", backup_content, "Deve emitir status para o heartbeat")


    def test_backup_script_tags_snapshots_by_node(self):
        backup_content = (BACKUP_DIR / "restic-backup.sh").read_text(encoding="utf-8")
        self.assertIn("--tag \"homelab\"", backup_content)
        self.assertIn("--tag \"node:${NODE_NAME}\"", backup_content)

    def test_verify_script_checks_sqlite_integrity(self):
        verify_content = (BACKUP_DIR / "restic-verify.sh").read_text(encoding="utf-8")
        self.assertIn("PRAGMA integrity_check", verify_content)
        self.assertIn("DEVEX_HOMELAB_BACKUP_VERIFY_PASS", verify_content)

    def test_systemd_units_exist_and_are_valid(self):
        service_file = BACKUP_DIR / "systemd" / "homelab-backup.service"
        timer_file = BACKUP_DIR / "systemd" / "homelab-backup.timer"
        self.assertTrue(service_file.is_file())
        self.assertTrue(timer_file.is_file())

        service_content = service_file.read_text(encoding="utf-8")
        timer_content = timer_file.read_text(encoding="utf-8")

        self.assertIn("Type=oneshot", service_content)
        self.assertIn("OnCalendar=", timer_content)
        self.assertIn("RandomizedDelaySec=", timer_content)

    def test_github_sync_contract(self):
        gh_sync_sh = BACKUP_DIR / "github-sync.sh"
        self.assertTrue(gh_sync_sh.is_file(), "github-sync.sh deve existir")
        content = gh_sync_sh.read_text(encoding="utf-8")
        self.assertIn("set -eu", content)
        self.assertIn("aes-256-cbc", content, "Deve usar criptografia forte AES-256")
        self.assertIn("-pbkdf2", content, "Deve usar derivação PBKDF2")
        self.assertIn("SHA256SUMS.txt", content, "Deve gerar manifesto de integridade SHA256")
        self.assertIn("gh release create", content, "Deve publicar via gh release create")
        self.assertIn("gh release view", content, "Deve validar o asset após o upload")
        self.assertIn("gh release delete", content, "Deve expurgar releases antigas e limpar falhas")
        self.assertIn("14", content, "Deve reter as 14 releases mais recentes")
        self.assertIn("GITHUB_TOKEN", content, "Deve suportar autenticação não interativa por token")



    def test_heartbeat_check_backup_handles_states(self):
        with TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "backup_status.json"

            # 1. Ausente -> False
            missing_check = heartbeat.check_backup(status_file)
            self.assertFalse(missing_check["ok"])
            self.assertIn("missing", missing_check["detail"])

            # 2. Failed status -> False
            status_file.write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error": "network error"
            }), encoding="utf-8")
            failed_check = heartbeat.check_backup(status_file)
            self.assertFalse(failed_check["ok"])

            # 3. Healthy recente -> True
            status_file.write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "healthy",
                "snapshot_id": "abc1234"
            }), encoding="utf-8")
            healthy_check = heartbeat.check_backup(status_file)
            self.assertTrue(healthy_check["ok"])

            # 4. Stale (> 26h) -> False
            stale_time = datetime.now(timezone.utc) - timedelta(hours=28)
            status_file.write_text(json.dumps({
                "timestamp": stale_time.isoformat(),
                "status": "healthy"
            }), encoding="utf-8")
            stale_check = heartbeat.check_backup(status_file)
            self.assertFalse(stale_check["ok"])
            self.assertIn("stale", stale_check["detail"])

if __name__ == "__main__":
    unittest.main()
