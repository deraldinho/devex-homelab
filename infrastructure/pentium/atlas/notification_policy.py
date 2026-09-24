from __future__ import annotations

from pathlib import Path

from .config_discord import load_discord_config


class NotificationPolicy:
    def __init__(
        self,
        *,
        alert_channel_id: str | None,
        memory_channel_id: str | None = None,
        notes_channel_id: str | None = None,
    ):
        self._alert_channel_id = str(alert_channel_id or "").strip()
        self._memory_channel_id = str(memory_channel_id or "").strip()
        self._notes_channel_id = str(notes_channel_id or "").strip()

    def route_for(self, snapshot):
        changes = tuple(getattr(snapshot, "recent_changes", ()) or ())
        target_channel = None

        for change in changes:
            source = str(change.get("source", "")).strip()
            kind = str(change.get("kind", "")).lower()
            severity = str(change.get("severity", "")).lower()

            # 1. Memorias episodicas e consolidacao
            if kind in {"memory_consolidated", "episodic_reflection", "memory_stored"} or source.startswith("memory."):
                target_channel = self._memory_channel_id or self._notes_channel_id or self._alert_channel_id
                if target_channel:
                    break

            # 2. Anotacoes do workspace e diario
            if kind in {"workspace_note", "action_completed", "note_created"} or source.startswith("workspace."):
                target_channel = self._notes_channel_id or self._alert_channel_id
                if target_channel:
                    break

            # 3. Alertas do GitHub e infraestrutura
            if source.startswith("github.") and kind in {"status_changed", "recovered", "source_error"}:
                target_channel = self._alert_channel_id
                break
            if severity in {"warning", "critical"} or kind in {"recovered", "source_error"}:
                target_channel = self._alert_channel_id
                break

        if not target_channel:
            return None

        return {
            "channel": "discord",
            "conversation_id": target_channel,
            "reply_target": target_channel,
            "actor_id": None,
        }


def load_notification_policy(config_root: Path, *, env=None) -> NotificationPolicy:
    path = Path(config_root) / "config_discord.json"
    if not path.is_file():
        return NotificationPolicy(alert_channel_id=None)
    config = load_discord_config(path, env=env)
    return NotificationPolicy(
        alert_channel_id=config.alert_channel_id if config.enabled else None,
        memory_channel_id=config.memory_channel_id if config.enabled else None,
        notes_channel_id=config.notes_channel_id if config.enabled else None,
    )
