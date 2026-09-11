import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.chat_inbox import ChatInbox
from infrastructure.pentium.atlas.discord_gateway import DiscordChatBridge, DiscordConfig, DiscordEventReader, DiscordReplyCursor, resolve_discord_activation
from infrastructure.pentium.atlas.config_discord import load_discord_config


def config():
    return DiscordConfig(
        schema_version=1, enabled=True,
        guild_ids=("guild-1",), channel_ids=("channel-9",), user_ids=("user-7",),
        max_message_chars=512, poll_interval_s=0.5,
    )


class DiscordGatewayTests(unittest.TestCase):
    def test_authorized_message_enters_shared_chat_inbox(self):
        with TemporaryDirectory() as tmp:
            inbox=ChatInbox(Path(tmp)/"chat-inbox.json")
            bridge=DiscordChatBridge(config(),inbox,DiscordEventReader(Path(tmp)/"events.jsonl"))
            env=bridge.accept_message("m-1","Como esta o core?",guild_id="guild-1",channel_id="channel-9",user_id="user-7")
            self.assertIsNotNone(env)
            self.assertEqual("discord",env.channel)
            self.assertEqual("channel-9",env.reply_target)
            self.assertEqual(1,inbox.pending_count())

    def test_unauthorized_or_bot_message_is_ignored(self):
        with TemporaryDirectory() as tmp:
            inbox=ChatInbox(Path(tmp)/"chat-inbox.json")
            bridge=DiscordChatBridge(config(),inbox,DiscordEventReader(Path(tmp)/"events.jsonl"))
            self.assertIsNone(bridge.accept_message("m-1","oi",guild_id="other",channel_id="channel-9",user_id="user-7"))
            self.assertIsNone(bridge.accept_message("m-2","oi",guild_id="guild-1",channel_id="channel-9",user_id="user-7",is_bot=True))
            self.assertEqual(0,inbox.pending_count())

    def test_reply_reader_filters_for_discord_atlas_messages(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"events.jsonl"
            events=[
                {"id":1,"type":"chat_message","payload":{"role":"atlas","channel":"dashboard","message":"dash"}},
                {"id":2,"type":"chat_message","payload":{"role":"user","channel":"discord","message":"user"}},
                {"id":3,"type":"chat_message","payload":{"role":"atlas","channel":"discord","reply_target":"channel-9","message":"core healthy"}},
            ]
            path.write_text("".join(json.dumps(x)+"\n" for x in events),encoding="utf-8")
            replies=DiscordEventReader(path).after(0)
            self.assertEqual(1,len(replies))
            self.assertEqual(3,replies[0].event_id)
            self.assertEqual("channel-9",replies[0].reply_target)
            self.assertEqual("core healthy",replies[0].message)

    def test_reply_cursor_is_durable(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"cursor.json"; cursor=DiscordReplyCursor(path)
            self.assertEqual(0,cursor.load())
            cursor.save(17)
            self.assertEqual(17,DiscordReplyCursor(path).load())

    def test_activation_requires_token_and_nonempty_allowlists(self):
        with self.assertRaises(RuntimeError): resolve_discord_activation(config(),{})
        blocked=DiscordConfig(1,True,(),("channel-9",),("user-7",))
        with self.assertRaises(RuntimeError): resolve_discord_activation(blocked,{"ATLAS_DISCORD_BOT_TOKEN":"secret"})
        self.assertEqual("secret",resolve_discord_activation(config(),{"ATLAS_DISCORD_BOT_TOKEN":"secret"}))

    def test_config_loads_allowlists_and_alert_channel_from_environment(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            path.write_text(json.dumps({"schema_version":1,"enabled":True,"guild_ids":[],"channel_ids":[],"user_ids":[],"max_message_chars":512,"poll_interval_seconds":0.5}),encoding="utf-8")
            cfg=load_discord_config(path,env={
                "ATLAS_DISCORD_GUILD_IDS":"guild-1",
                "ATLAS_DISCORD_CHANNEL_IDS":"channel-9,channel-10",
                "ATLAS_DISCORD_USER_IDS":"user-7",
                "ATLAS_DISCORD_ALERT_CHANNEL_ID":"channel-10",
            })
            self.assertEqual(("channel-9","channel-10"),cfg.channel_ids)
            self.assertEqual("channel-10",cfg.alert_channel_id)


if __name__ == "__main__": unittest.main()
