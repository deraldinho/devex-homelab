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
    max_message_chars: int = 512
    poll_interval_s: float = 0.5
    alert_channel_id: str | None = None

    def __post_init__(self):
        if self.schema_version != 1:
            raise ValueError("discord schema_version must be 1")
        if self.max_message_chars <= 0 or self.poll_interval_s <= 0:
            raise ValueError("discord bounds must be > 0")
        alert=str(self.alert_channel_id or "").strip() or None
        if alert is not None and alert not in self.channel_ids:
            raise ValueError("discord alert_channel_id must be allowlisted")
        object.__setattr__(self,"alert_channel_id",alert)

    def accepts(self, *, guild_id: str, channel_id: str, user_id: str) -> bool:
        return bool(
            self.enabled
            and guild_id in self.guild_ids
            and channel_id in self.channel_ids
            and user_id in self.user_ids
        )


def load_discord_config(path: Path, *, env=None) -> DiscordConfig:
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    values=os.environ if env is None else env
    guilds=_env_ids(values,"ATLAS_DISCORD_GUILD_IDS") or _ids(payload.get("guild_ids"))
    channels=_env_ids(values,"ATLAS_DISCORD_CHANNEL_IDS") or _ids(payload.get("channel_ids"))
    users=_env_ids(values,"ATLAS_DISCORD_USER_IDS") or _ids(payload.get("user_ids"))
    alert_channel=str(values.get("ATLAS_DISCORD_ALERT_CHANNEL_ID") or payload.get("alert_channel_id") or "").strip() or None
    return DiscordConfig(
        schema_version=int(payload.get("schema_version",0)),
        enabled=bool(payload.get("enabled",False)),
        guild_ids=guilds,channel_ids=channels,user_ids=users,
        max_message_chars=int(payload.get("max_message_chars",512)),
        poll_interval_s=float(payload.get("poll_interval_seconds",0.5)),
        alert_channel_id=alert_channel,
    )
