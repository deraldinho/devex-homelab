from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .chat_inbox import ChatInbox
from .config_discord import DiscordConfig, load_discord_config

ROOT=Path(__file__).resolve().parent
STATE_DIR=Path.home()/"pentium-agent"/"atlas"/"runtime"


@dataclass(frozen=True)
class DiscordReply:
    event_id: int
    reply_target: str
    message: str


class DiscordEventReader:
    def __init__(self,path:Path,*,max_events:int=128):
        self.path=Path(path); self.max_events=max(1,int(max_events))

    def after(self,last_event_id:int)->tuple[DiscordReply,...]:
        if not self.path.is_file(): return ()
        replies=[]
        for line in self.path.read_text(encoding="utf-8").splitlines()[-self.max_events:]:
            try: event=json.loads(line)
            except json.JSONDecodeError: continue
            if not isinstance(event,dict) or int(event.get("id",0))<=int(last_event_id): continue
            payload=event.get("payload") or {}
            if event.get("type")!="chat_message" or payload.get("role")!="atlas" or payload.get("channel")!="discord": continue
            target=str(payload.get("reply_target") or "").strip(); message=str(payload.get("message") or "").strip()
            if target and message:
                replies.append(DiscordReply(int(event["id"]),target,message))
        return tuple(replies)


class DiscordReplyCursor:
    def __init__(self,path:Path): self.path=Path(path)
    def load(self)->int:
        if not self.path.is_file(): return 0
        try: payload=json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return 0
        value=payload.get("last_event_id",0) if isinstance(payload,dict) else 0
        return max(0,int(value))
    def save(self,event_id:int)->None:
        value=max(0,int(event_id));self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        try:
            tmp.write_text(json.dumps({"schema_version":1,"last_event_id":value},sort_keys=True)+"\n",encoding="utf-8")
            os.replace(tmp,self.path)
        finally: tmp.unlink(missing_ok=True)


class DiscordChatBridge:
    def __init__(self,config:DiscordConfig,inbox:ChatInbox,event_reader:DiscordEventReader):
        self.config=config;self.inbox=inbox;self.event_reader=event_reader

    def accept_message(self,message_id:str,content:str,*,guild_id:str,channel_id:str,user_id:str,is_bot:bool=False):
        if is_bot or not self.config.accepts(guild_id=str(guild_id),channel_id=str(channel_id),user_id=str(user_id)):
            return None
        text=str(content).strip()
        if not text or len(text)>self.config.max_message_chars:
            return None
        return self.inbox.enqueue(
            text,f"discord:{message_id}",channel="discord",actor_id=str(user_id),
            conversation_id=str(channel_id),reply_target=str(channel_id),
        )

    def responses_after(self,last_event_id:int)->tuple[DiscordReply,...]:
        return self.event_reader.after(last_event_id)


def resolve_discord_activation(config: DiscordConfig, env=None) -> str:
    values=os.environ if env is None else env
    if not config.enabled:
        raise RuntimeError("discord gateway disabled")
    token=str(values.get("ATLAS_DISCORD_BOT_TOKEN","")).strip()
    if not token:
        raise RuntimeError("discord bot token unavailable")
    if not config.guild_ids or not config.channel_ids or not config.user_ids:
        raise RuntimeError("discord allowlists are incomplete")
    return token


async def _run_discord_client(config: DiscordConfig, token: str, *, state_dir: Path = STATE_DIR):
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py unavailable") from exc
    state_dir=Path(state_dir)
    inbox=ChatInbox(state_dir/"chat-inbox.json",max_items=32,max_message_chars=config.max_message_chars)
    reader=DiscordEventReader(state_dir/"dashboard-events.jsonl")
    bridge=DiscordChatBridge(config,inbox,reader)
    cursor=DiscordReplyCursor(state_dir/"discord-cursor.json")
    intents=discord.Intents.default(); intents.message_content=True
    client=discord.Client(intents=intents)
    pump_task=None

    async def pump_replies():
        while not client.is_closed():
            for reply in bridge.responses_after(cursor.load()):
                try:
                    channel=client.get_channel(int(reply.reply_target))
                    if channel is None: channel=await client.fetch_channel(int(reply.reply_target))
                    await channel.send(reply.message)
                except Exception:
                    break
                cursor.save(reply.event_id)
            await asyncio.sleep(config.poll_interval_s)

    @client.event
    async def on_ready():
        nonlocal pump_task
        if pump_task is None or pump_task.done():
            pump_task=asyncio.create_task(pump_replies())

    @client.event
    async def on_message(message):
        guild=getattr(message,"guild",None)
        author=getattr(message,"author",None)
        bridge.accept_message(
            str(getattr(message,"id","")),str(getattr(message,"content","") or ""),
            guild_id=str(getattr(guild,"id","") or ""),
            channel_id=str(getattr(getattr(message,"channel",None),"id","") or ""),
            user_id=str(getattr(author,"id","") or ""),
            is_bot=bool(getattr(author,"bot",False)),
        )

    try:
        await client.start(token)
    finally:
        if pump_task is not None:
            pump_task.cancel()
            try:
                await pump_task
            except asyncio.CancelledError:
                pass


def main() -> int:
    config=load_discord_config(ROOT/"config_discord.json")
    token=resolve_discord_activation(config)
    asyncio.run(_run_discord_client(config,token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
