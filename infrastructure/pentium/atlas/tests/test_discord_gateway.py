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

    def test_wildcard_user_id_accepts_any_guild_member_and_prefixes_name(self):
        with TemporaryDirectory() as tmp:
            inbox = ChatInbox(Path(tmp)/"chat-inbox.json")
            cfg = DiscordConfig(1, True, ("guild-1",), ("channel-9",), ("*",), admin_user_ids=("admin-1",))
            bridge = DiscordChatBridge(cfg, inbox, DiscordEventReader(Path(tmp)/"events.jsonl"))
            env = bridge.accept_message("m-10", "Ola Atlas!", guild_id="guild-1", channel_id="channel-9", user_id="random-member-99", user_name="Kaio")
            self.assertIsNotNone(env)
            self.assertEqual("Kaio: Ola Atlas!", env.message)
            self.assertEqual("discord", env.channel)
            self.assertEqual("channel-9", env.reply_target)
            self.assertEqual(1, inbox.pending_count())

    def test_admin_check_with_wildcard_users(self):
        cfg = DiscordConfig(1, True, ("guild-1",), ("channel-9",), ("*",), admin_user_ids=("admin-1",))
        self.assertTrue(cfg.is_admin("admin-1"))
        self.assertFalse(cfg.is_admin("random-member-99"))
        self.assertFalse(cfg.is_admin("*"))

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

    def test_resolve_channel_by_id_name_and_mention(self):
        from unittest.mock import MagicMock
        from infrastructure.pentium.atlas.discord_gateway import _resolve_channel
        ch1 = MagicMock(id=100)
        ch1.name = "bot-console"
        ch2 = MagicMock(id=200)
        ch2.name = "watchdog"
        guild = MagicMock(text_channels=[ch1, ch2])
        guild.get_channel = lambda cid: ch1 if cid == 100 else (ch2 if cid == 200 else None)

        self.assertEqual(ch1, _resolve_channel(guild, "100"))
        self.assertEqual(ch1, _resolve_channel(guild, "<#100>"))
        self.assertEqual(ch2, _resolve_channel(guild, "watchdog"))
        self.assertEqual(ch2, _resolve_channel(guild, "WATCHDOG"))
        self.assertIsNone(_resolve_channel(guild, "inexistente"))

    def test_control_command_blocks_unauthorized_user(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import handle_control_command

        channel = MagicMock(send=AsyncMock())
        message = MagicMock(
            content="!canal criar teste",
            author=MagicMock(id="unauthorized-user"),
            channel=channel,
        )
        handled = asyncio.run(handle_control_command(message, None, config()))
        self.assertTrue(handled)
        channel.send.assert_called_once()
        self.assertIn("Acesso negado", channel.send.call_args[0][0])

    def test_control_command_creates_channel_for_authorized_user(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import handle_control_command

        new_ch = MagicMock(id=300, mention="<#300>")
        guild = MagicMock(create_text_channel=AsyncMock(return_value=new_ch))
        channel = MagicMock(send=AsyncMock())
        message = MagicMock(
            content="!canal criar novo-canal Topico legal",
            author=MagicMock(id="user-7"),
            guild=guild,
            channel=channel,
        )
        handled = asyncio.run(handle_control_command(message, None, config()))
        self.assertTrue(handled)
        guild.create_text_channel.assert_called_once_with("novo-canal", topic="Topico legal")
        channel.send.assert_called_once()
        self.assertIn("Canal criado com sucesso", channel.send.call_args[0][0])

    def test_control_command_protects_vital_channel_from_deletion(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import handle_control_command

        vital_ch = MagicMock(id=9, delete=AsyncMock(), mention="<#9>")
        vital_ch.name = "channel-9"
        guild = MagicMock(text_channels=[vital_ch], get_channel=lambda cid: vital_ch if cid == 9 else None)
        channel = MagicMock(send=AsyncMock())
        cfg = DiscordConfig(1, True, ("guild-1",), ("9",), ("user-7",), alert_channel_id="9")

        message = MagicMock(
            content="!canal excluir 9",
            author=MagicMock(id="user-7"),
            guild=guild,
            channel=channel,
        )
        handled = asyncio.run(handle_control_command(message, None, cfg))
        self.assertTrue(handled)
        vital_ch.delete.assert_not_called()
        self.assertIn("protegido", channel.send.call_args[0][0])

    def test_confirmation_manager_lifecycle(self):
        import asyncio
        from infrastructure.pentium.atlas.discord_gateway import DiscordConfirmationManager

        called = False
        async def action():
            nonlocal called
            called = True

        mgr = DiscordConfirmationManager(timeout_s=0.1)
        prompt = mgr.request("g1", "u1", "fazer algo perigoso", action)
        self.assertIn("Confirmação Requerida", prompt)

        success, msg = asyncio.run(mgr.confirm("g1", "u1"))
        self.assertTrue(success)
        self.assertTrue(called)
        self.assertIn("sucesso", msg)

        # Confirm when nothing is pending
        success2, msg2 = asyncio.run(mgr.confirm("g1", "u1"))
        self.assertFalse(success2)
        self.assertIn("Nenhuma ação pendente", msg2)

    def test_confirmation_manager_timeout(self):
        import asyncio
        import time
        from infrastructure.pentium.atlas.discord_gateway import DiscordConfirmationManager

        called = False
        async def action():
            nonlocal called
            called = True

        mgr = DiscordConfirmationManager(timeout_s=0.05)
        mgr.request("g1", "u1", "acao demorada", action)
        time.sleep(0.06)

        success, msg = asyncio.run(mgr.confirm("g1", "u1"))
        self.assertFalse(success)
        self.assertFalse(called)
        self.assertIn("expirado", msg)

    def test_channel_deletion_requires_two_step_confirmation(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import DiscordConfirmationManager, handle_control_command

        mgr = DiscordConfirmationManager(timeout_s=15.0)
        target_ch = MagicMock(id=99, name="canal-temporario", delete=AsyncMock())
        guild = MagicMock(id="guild-1", text_channels=[target_ch], get_channel=lambda cid: target_ch if cid == 99 else None)
        channel = MagicMock(send=AsyncMock())

        # Step 1: Request delete
        msg1 = MagicMock(content="!canal excluir 99", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled1 = asyncio.run(handle_control_command(msg1, None, config(), confirmation_mgr=mgr))
        self.assertTrue(handled1)
        target_ch.delete.assert_not_called()
        self.assertIn("Confirmação Requerida", channel.send.call_args[0][0])

        # Step 2: Confirm delete
        msg2 = MagicMock(content="!confirmar", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled2 = asyncio.run(handle_control_command(msg2, None, config(), confirmation_mgr=mgr))
        self.assertTrue(handled2)
        target_ch.delete.assert_called_once()
        self.assertIn("sucesso", channel.send.call_args[0][0])

    def test_purge_above_20_requires_confirmation(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import DiscordConfirmationManager, handle_control_command

        mgr = DiscordConfirmationManager(timeout_s=15.0)
        guild = MagicMock(id="guild-1")
        channel = MagicMock(send=AsyncMock(), purge=AsyncMock(return_value=[1]*26))

        # Request purge of 25 messages
        msg1 = MagicMock(content="!limpar 25", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled1 = asyncio.run(handle_control_command(msg1, None, config(), confirmation_mgr=mgr))
        self.assertTrue(handled1)
        channel.purge.assert_not_called()
        self.assertIn("Confirmação Requerida", channel.send.call_args[0][0])

        # Confirm purge
        msg2 = MagicMock(content="!confirm", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled2 = asyncio.run(handle_control_command(msg2, None, config(), confirmation_mgr=mgr))
        self.assertTrue(handled2)
        channel.purge.assert_called_once_with(limit=26)

    def test_message_edit_blocks_editing_other_users_messages(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import handle_control_command

        bot_user = MagicMock(id=500)
        client = MagicMock(user=bot_user)
        other_user_msg = MagicMock(id=1001, author=MagicMock(id=999), edit=AsyncMock())
        channel = MagicMock(send=AsyncMock(), fetch_message=AsyncMock(return_value=other_user_msg))
        guild = MagicMock(id="guild-1")

        msg = MagicMock(content="!msg editar 1001 novo texto", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled = asyncio.run(handle_control_command(msg, client, config()))
        self.assertTrue(handled)
        other_user_msg.edit.assert_not_called()
        self.assertIn("não permite editar mensagens de outros usuários", channel.send.call_args[0][0])

    def test_message_edit_allows_editing_bot_own_message(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import handle_control_command

        bot_user = MagicMock(id=500)
        client = MagicMock(user=bot_user)
        bot_msg = MagicMock(id=1002, author=MagicMock(id=500), edit=AsyncMock())
        channel = MagicMock(send=AsyncMock(), fetch_message=AsyncMock(return_value=bot_msg))
        guild = MagicMock(id="guild-1")

        msg = MagicMock(content="!msg editar 1002 status atualizado", author=MagicMock(id="user-7"), guild=guild, channel=channel)
        handled = asyncio.run(handle_control_command(msg, client, config()))
        self.assertTrue(handled)
        bot_msg.edit.assert_called_once_with(content="status atualizado")
        self.assertIn("sucesso", channel.send.call_args[0][0])

    def test_active_engagement_vs_passive_memory_filter(self):
        from unittest.mock import MagicMock
        from infrastructure.pentium.atlas.discord_gateway import should_respond_actively

        bot_user = MagicMock(id=500)
        client = MagicMock(user=bot_user)
        cfg = DiscordConfig(1, True, ("guild-1",), ("console-ch", "chat-ch"), ("*",), console_channel_id="console-ch")

        # In console channel -> Active
        msg_console = MagicMock(channel=MagicMock(id="console-ch"), content="qualquer coisa", mentions=[])
        self.assertTrue(should_respond_actively(msg_console, client, cfg))

        # Mentioning bot in general chat -> Active
        msg_mention = MagicMock(channel=MagicMock(id="chat-ch"), content="ola", mentions=[bot_user])
        self.assertTrue(should_respond_actively(msg_mention, client, cfg))

        # Mentioning "atlas" in text -> Active
        msg_text_atlas = MagicMock(channel=MagicMock(id="chat-ch"), content="Ola Atlas tudo bem?", mentions=[])
        self.assertTrue(should_respond_actively(msg_text_atlas, client, cfg))

        # Casual message without mention in general chat -> Passive
        msg_casual = MagicMock(channel=MagicMock(id="chat-ch"), content="bom dia galera, alguem subiu o build?", mentions=[], reference=None)
        self.assertFalse(should_respond_actively(msg_casual, client, cfg))

    def test_incident_channel_lifecycle(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.pentium.atlas.discord_gateway import create_incident_channel, resolve_incident_channel

        inc_ch = MagicMock(edit=AsyncMock(), send=AsyncMock())
        inc_ch.name = "🚨-incidente-disk-full"
        guild = MagicMock(
            create_text_channel=AsyncMock(return_value=inc_ch),
            text_channels=[inc_ch],
            get_channel=lambda cid: inc_ch,
        )

        created = asyncio.run(create_incident_channel(guild, "disk-full", topic="Incidente de disco"))
        self.assertEqual(inc_ch, created)
        guild.create_text_channel.assert_called_once_with("🚨-incidente-disk-full", topic="Incidente de disco")

        resolved = asyncio.run(resolve_incident_channel(guild, "🚨-incidente-disk-full", post_mortem="Disco saneado com sucesso"))
        self.assertEqual(inc_ch, resolved)
        inc_ch.edit.assert_called_once_with(name="✅-resolvido-disk-full")
        inc_ch.send.assert_called_once()
        self.assertIn("Disco saneado", inc_ch.send.call_args[0][0])

    def test_split_discord_message_short_text(self):
        from infrastructure.pentium.atlas.discord_gateway import split_discord_message
        self.assertEqual([], split_discord_message(""))
        self.assertEqual(["ola mundo"], split_discord_message("ola mundo", max_chars=100))

    def test_split_discord_message_long_text_and_code_blocks(self):
        from infrastructure.pentium.atlas.discord_gateway import split_discord_message
        lines = [f"linha {i}" for i in range(50)]
        big_text = "\n".join(lines)
        chunks = split_discord_message(big_text, max_chars=120)
        self.assertTrue(len(chunks) > 1)
        for c in chunks:
            self.assertLessEqual(len(c), 120)

        # Bloco de código dividido preserva delimitadores
        code = "```python\n" + "\n".join([f"x = {i}" for i in range(30)]) + "\n```"
        code_chunks = split_discord_message(code, max_chars=100)
        self.assertTrue(len(code_chunks) > 1)
        self.assertTrue(code_chunks[0].endswith("```"))
        self.assertTrue(code_chunks[1].startswith("```python"))


if __name__ == "__main__": unittest.main()
