from __future__ import annotations

from pathlib import Path

from .config_discord import load_discord_config


class NotificationPolicy:
    def __init__(self, *, alert_channel_id: str | None):
        self._alert_channel_id=str(alert_channel_id or "").strip()

    def route_for(self, snapshot):
        if not self._alert_channel_id:
            return None
        changes=tuple(getattr(snapshot,"recent_changes",()) or ())
        should_route=False
        for change in changes:
            source=str(change.get("source","")).strip()
            kind=str(change.get("kind","")).lower()
            severity=str(change.get("severity","")).lower()
            if source.startswith("github.") and kind in {"status_changed","recovered","source_error"}:
                should_route=True; break
            if severity in {"warning","critical"} or kind in {"recovered","source_error"}:
                should_route=True; break
        if not should_route:
            return None
        return {
            "channel":"discord",
            "conversation_id":self._alert_channel_id,
            "reply_target":self._alert_channel_id,
            "actor_id":None,
        }


def load_notification_policy(config_root: Path, *, env=None) -> NotificationPolicy:
    path=Path(config_root)/"config_discord.json"
    if not path.is_file():
        return NotificationPolicy(alert_channel_id=None)
    config=load_discord_config(path,env=env)
    return NotificationPolicy(
        alert_channel_id=config.alert_channel_id if config.enabled else None,
    )
