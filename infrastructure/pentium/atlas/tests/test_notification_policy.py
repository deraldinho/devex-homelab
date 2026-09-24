import unittest
from types import SimpleNamespace

from infrastructure.pentium.atlas.notification_policy import NotificationPolicy, load_notification_policy


class NotificationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=NotificationPolicy(alert_channel_id="channel-9")

    def route(self, *changes):
        return self.policy.route_for(SimpleNamespace(recent_changes=changes))

    def test_routes_infrastructure_warning_and_recovery(self):
        warning=self.route({"source":"core","kind":"status_changed","severity":"warning"})
        recovered=self.route({"source":"x99","kind":"recovered","severity":"info"})
        self.assertEqual("discord",warning["channel"])
        self.assertEqual("channel-9",warning["reply_target"])
        self.assertEqual("discord",recovered["channel"])

    def test_routes_github_changes_but_ignores_routine_info(self):
        github=self.route({"source":"github.deraldinho.L2jToren","kind":"status_changed","severity":"info"})
        routine=self.route({"source":"pentium.self","kind":"status_changed","severity":"info"})
        self.assertEqual("discord",github["channel"])
        self.assertIsNone(routine)

    def test_empty_alert_channel_disables_routing(self):
        policy=NotificationPolicy(alert_channel_id="")
        self.assertIsNone(policy.route_for(SimpleNamespace(recent_changes=({"source":"core","kind":"source_error","severity":"critical"},))))

    def test_loader_uses_discord_alert_channel_without_token(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import json
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"config_discord.json").write_text(json.dumps({
                "schema_version":1,"enabled":True,"guild_ids":[],"channel_ids":[],"user_ids":[],
                "alert_channel_id":None,"max_message_chars":512,"poll_interval_seconds":0.5,
            }),encoding="utf-8")
            policy=load_notification_policy(root,env={
                "ATLAS_DISCORD_CHANNEL_IDS":"channel-9",
                "ATLAS_DISCORD_ALERT_CHANNEL_ID":"channel-9",
            })
            route=policy.route_for(SimpleNamespace(recent_changes=({"source":"core","kind":"source_error","severity":"critical"},)))
            self.assertEqual("channel-9",route["reply_target"])

    def test_routes_memory_events_to_memory_channel(self):
        policy = NotificationPolicy(
            alert_channel_id="channel-alert",
            memory_channel_id="channel-memory",
            notes_channel_id="channel-notes",
        )
        memory_change = SimpleNamespace(recent_changes=({"source": "memory.episodic", "kind": "memory_consolidated", "severity": "info"},))
        route = policy.route_for(memory_change)
        self.assertIsNotNone(route)
        self.assertEqual("channel-memory", route["reply_target"])

    def test_routes_workspace_notes_to_notes_channel(self):
        policy = NotificationPolicy(
            alert_channel_id="channel-alert",
            memory_channel_id="channel-memory",
            notes_channel_id="channel-notes",
        )
        note_change = SimpleNamespace(recent_changes=({"source": "workspace.agent", "kind": "workspace_note", "severity": "info"},))
        route = policy.route_for(note_change)
        self.assertIsNotNone(route)
        self.assertEqual("channel-notes", route["reply_target"])

    def test_memory_falls_back_to_alert_channel_when_memory_channel_unset(self):
        policy = NotificationPolicy(alert_channel_id="channel-alert")
        memory_change = SimpleNamespace(recent_changes=({"source": "memory.episodic", "kind": "memory_consolidated", "severity": "info"},))
        route = policy.route_for(memory_change)
        self.assertIsNotNone(route)
        self.assertEqual("channel-alert", route["reply_target"])


if __name__ == "__main__": unittest.main()
