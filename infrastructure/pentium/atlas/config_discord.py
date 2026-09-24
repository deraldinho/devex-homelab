from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _ids(values) -> tuple[str, ...]:
    output=[]
    for value in values or ():
        item=str(value).strip()
        if item and item not in output:
            output.append(item)
    return tuple(output)


def _env_ids(env, name: str) -> tuple[str, ...]:
    raw=str(env.get(name, "")).strip()
    return _ids(part.strip() for part in raw.split(",")) if raw else ()


@dataclass(frozen=True)
class DiscordConfig:
    schema_version: int
    enabled: bool
    guild_ids: tuple[str, ...]
    channel_ids: tuple[str, ...]
    user_ids: tuple[str, ...]
    admin_user_ids: tuple[str, ...] = ()
    max_message_chars: int = 512
    poll_interval_s: float = 0.5
    dashboard_update_interval_s: float = 30.0
    alert_channel_id: str | None = None
    memory_channel_id: str | None = None
    notes_channel_id: str | None = None
    console_channel_id: str | None = None

    def __post_init__(self):
        if self.schema_version != 1:
            raise ValueError("discord schema_version must be 1")
        if self.max_message_chars <= 0 or self.poll_interval_s <= 0 or self.dashboard_update_interval_s <= 0:
            raise ValueError("discord bounds must be > 0")
        for attr in ("alert_channel_id", "memory_channel_id", "notes_channel_id", "console_channel_id"):
            val = str(getattr(self, attr) or "").strip() or None
            if val is not None and "*" not in self.channel_ids and self.channel_ids and val not in self.channel_ids:
                raise ValueError(f"discord {attr} must be allowlisted")
            object.__setattr__(self, attr, val)

    def accepts(self, *, guild_id: str, channel_id: str, user_id: str) -> bool:
        channel_ok = "*" in self.channel_ids or not self.channel_ids or channel_id in self.channel_ids
        return bool(
            self.enabled
            and guild_id in self.guild_ids
            and channel_ok
            and ("*" in self.user_ids or user_id in self.user_ids)
        )

    def is_admin(self, user_id: str) -> bool:
        u = str(user_id or "").strip()
        if not u:
            return False
        if self.admin_user_ids:
            return u in self.admin_user_ids
        return u in self.user_ids and u != "*"


def load_discord_config(path: Path, *, env=None) -> DiscordConfig:
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    values=os.environ if env is None else env
    guilds=_env_ids(values,"ATLAS_DISCORD_GUILD_IDS") or _ids(payload.get("guild_ids"))
    channels=_env_ids(values,"ATLAS_DISCORD_CHANNEL_IDS") or _ids(payload.get("channel_ids"))
    users=_env_ids(values,"ATLAS_DISCORD_USER_IDS") or _ids(payload.get("user_ids"))
    admin_users=_env_ids(values,"ATLAS_DISCORD_ADMIN_USER_IDS") or _ids(payload.get("admin_user_ids"))
    dashboard_interval = float(values.get("ATLAS_DISCORD_DASHBOARD_INTERVAL_S") or payload.get("dashboard_update_interval_seconds", 30.0))
    alert_channel=str(values.get("ATLAS_DISCORD_ALERT_CHANNEL_ID") or payload.get("alert_channel_id") or "").strip() or None
    memory_channel=str(values.get("ATLAS_DISCORD_MEMORY_CHANNEL_ID") or payload.get("memory_channel_id") or "").strip() or None
    notes_channel=str(values.get("ATLAS_DISCORD_NOTES_CHANNEL_ID") or payload.get("notes_channel_id") or "").strip() or None
    console_channel=str(values.get("ATLAS_DISCORD_CONSOLE_CHANNEL_ID") or payload.get("console_channel_id") or "").strip() or None
    return DiscordConfig(
        schema_version=int(payload.get("schema_version",0)),
        enabled=bool(payload.get("enabled",False)),
        guild_ids=guilds,channel_ids=channels,user_ids=users,
        admin_user_ids=admin_users,
        max_message_chars=int(payload.get("max_message_chars",512)),
        poll_interval_s=float(payload.get("poll_interval_seconds",0.5)),
        dashboard_update_interval_s=dashboard_interval,
        alert_channel_id=alert_channel,
        memory_channel_id=memory_channel,
        notes_channel_id=notes_channel,
        console_channel_id=console_channel,
    )
