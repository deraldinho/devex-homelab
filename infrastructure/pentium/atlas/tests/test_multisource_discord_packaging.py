import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
ATLAS=ROOT/"infrastructure"/"pentium"/"atlas"


class MultisourceDiscordPackagingTests(unittest.TestCase):
    def test_installer_packages_new_runtime_without_secret_or_auto_enable(self):
        text=(ATLAS/"install-user.sh").read_text(encoding="utf-8")
        for name in (
            "local_health.py","github_observation.py","config_github.json",
            "notification_policy.py","config_discord.py","config_discord.json",
            "discord_gateway.py","requirements-discord.txt","prepare-discord-atlas.sh",
            "atlas-discord.service",
        ):
            self.assertIn(name,text)
        self.assertNotIn("ATLAS_DISCORD_BOT_TOKEN=",text)
        self.assertNotIn("enable atlas-discord.service",text)
        self.assertNotIn("restart atlas-discord.service",text)
        self.assertIn("DEVEX_HOMELAB_ATLAS_MULTISOURCE_CHAT_INSTALL_PASS",text)
        service=(ATLAS/"atlas-discord.service").read_text(encoding="utf-8")
        self.assertIn(".venv-discord/bin/python -m atlas.discord_gateway",service)

    def test_ci_contains_multisource_gate_and_emotional_regression_tests(self):
        text=(ROOT/".github"/"workflows"/"foundation-ci.yml").read_text(encoding="utf-8")
        for name in (
            "tests.test_affective_composition","tests.test_github_observation",
            "tests.test_notification_policy","tests.test_discord_gateway",
            "DEVEX_HOMELAB_ATLAS_MULTISOURCE_CHAT_PASS",
        ):
            self.assertIn(name,text)


if __name__=="__main__": unittest.main()
