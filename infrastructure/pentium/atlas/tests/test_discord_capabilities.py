import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.capability_dispatch import CapabilityDispatcher
from infrastructure.pentium.atlas.discord_capability_executor import DiscordCapabilityExecutor
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities


class DiscordCapabilitiesTests(unittest.TestCase):
    def test_registry_contains_discord_capabilities(self):
        reg = atlas_capability_registry()
        expected = [
            "discord_create_channel",
            "discord_rename_channel",
            "discord_send_alert",
            "discord_create_note",
            "discord_create_incident",
            "discord_resolve_incident",
            "discord_purge_messages",
        ]
        for cap in expected:
            spec = reg.obter(cap)
            self.assertIsNotNone(spec)
            self.assertEqual(cap, spec.nome)

    def test_policy_governance_for_discord_capabilities(self):
        reg = atlas_capability_registry()
        policy = PolicyCapabilities(
            reg,
            auto_unscoped_control_allow=(
                "discord_create_channel",
                "discord_rename_channel",
                "discord_send_alert",
                "discord_create_note",
                "discord_create_incident",
                "discord_resolve_incident",
            )
        )

        # Control capabilities are permitted
        dec = policy.avaliar("discord_create_incident", {"slug": "disk-full", "description": "Disco a 95%"})
        self.assertTrue(dec.autorizada)
        self.assertFalse(dec.requer_confirmacao)

        # Destructive capability requires human confirmation
        dec_destr = policy.avaliar("discord_purge_messages", {"quantity": 25})
        self.assertTrue(dec_destr.requer_confirmacao)

    def test_discord_capability_executor_enqueues_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "discord-action-queue.jsonl"
            executor = DiscordCapabilityExecutor(queue_file)

            res = executor("discord_create_incident", {"slug": "backup-fail", "description": "Snapshot falhou"})
            self.assertEqual("enqueued", res["status"])

            lines = queue_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(lines))
            item = json.loads(lines[0])
            self.assertEqual("discord_create_incident", item["capability"])
            self.assertEqual("backup-fail", item["arguments"]["slug"])

    def test_capability_dispatcher_routes_to_discord_executor(self):
        from unittest.mock import MagicMock

        infra_mock = MagicMock()
        ws_mock = MagicMock()
        discord_mock = MagicMock(return_value={"status": "dispatched"})

        dispatcher = CapabilityDispatcher(infra_mock, ws_mock, discord_mock)
        res = dispatcher("discord_create_channel", {"name": "novo-canal", "topic": "topico legal"})

        discord_mock.assert_called_once()
        infra_mock.assert_not_called()
        ws_mock.assert_not_called()
        self.assertEqual({"status": "dispatched"}, res)


if __name__ == "__main__":
    unittest.main()
