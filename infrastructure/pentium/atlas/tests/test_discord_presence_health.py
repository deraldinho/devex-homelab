import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

from infrastructure.pentium.atlas import discord_gateway


class DiscordPresenceHealthTests(unittest.TestCase):
    def test_health_store_records_connected_gateway_state(self):
        store_type = getattr(discord_gateway, "DiscordGatewayHealthStore", None)
        self.assertIsNotNone(store_type, "DiscordGatewayHealthStore must exist")
        with TemporaryDirectory() as tmp:
            store = store_type(Path(tmp) / "discord-gateway-health.json")
            store.write("connected", latency_s=0.123, reason="ready")
            payload = json.loads(store.path.read_text(encoding="utf-8"))
            self.assertEqual("connected", payload["state"])
            self.assertTrue(payload["connected"])
            self.assertEqual("ready", payload["reason"])
            self.assertEqual(0.123, payload["latency_s"])

    def test_ready_presence_is_published_explicitly(self):
        publish = getattr(discord_gateway, "publish_online_presence", None)
        self.assertIsNotNone(publish, "publish_online_presence must exist")

        class Status:
            online = object()
        class Game:
            def __init__(self, name): self.name = name
        Discord = type("Discord", (), {"Status": Status, "Game": Game})

        client = type("Client", (), {"change_presence": AsyncMock()})()
        asyncio.run(publish(client, Discord))
        client.change_presence.assert_awaited_once()
        kwargs = client.change_presence.await_args.kwargs
        self.assertIs(kwargs["status"], Status.online)
        self.assertIn("Atlas", kwargs["activity"].name)


if __name__ == "__main__":
    unittest.main()
