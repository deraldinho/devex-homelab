from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .self_work import SelfWorkItem, SelfWorkState, _utc


def _item_to_dict(item: SelfWorkItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "objective": item.objective,
        "area": item.area,
        "state": item.state.value,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "valid_until": item.valid_until,
        "operations_used": item.operations_used,
        "inferences_used": item.inferences_used,
        "reason": item.reason,
    }


def _item_from_dict(data: dict[str, Any]) -> SelfWorkItem:
    return SelfWorkItem(
        item_id=str(data["item_id"]),
        objective=str(data["objective"]),
        area=str(data["area"]),
        state=SelfWorkState(data["state"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        valid_until=str(data["valid_until"]),
        operations_used=int(data.get("operations_used", 0)),
        inferences_used=int(data.get("inferences_used", 0)),
        reason=str(data.get("reason", "")),
    )


class SelfWorkStore:
    def __init__(
        self,
        current_path: Path,
        history_path: Optional[Path] = None,
        max_history_lines: int = 128,
    ):
        self.current_path = Path(current_path)
        self.history_path = Path(history_path) if history_path else None
        self.max_history_lines = int(max_history_lines)
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        if self.history_path:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def save_current(self, item: Optional[SelfWorkItem]) -> None:
        tmp_path = self.current_path.with_suffix(".tmp")
        if item is None:
            if self.current_path.exists():
                try:
                    self.current_path.unlink()
                except OSError:
                    pass
            return

        payload = {
            "schema_version": 1,
            "task": _item_to_dict(item),
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, self.current_path)

    def load_active(self, now: str) -> Optional[SelfWorkItem]:
        if not self.current_path.is_file():
            return None
        try:
            with open(self.current_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            task_dict = data.get("task")
            if not isinstance(task_dict, dict):
                return None
            item = _item_from_dict(task_dict)
            if item.terminal:
                self.save_current(None)
                return None
            # Verifica se o TTL ainda é válido
            instant = _utc(now)
            valid_until = _utc(item.valid_until)
            if instant > valid_until:
                # Expirado: registra término no histórico e limpa current
                expired_item = SelfWorkItem(
                    item_id=item.item_id,
                    objective=item.objective,
                    area=item.area,
                    state=SelfWorkState.EXPIRED,
                    created_at=item.created_at,
                    updated_at=instant.isoformat(),
                    valid_until=item.valid_until,
                    operations_used=item.operations_used,
                    inferences_used=item.inferences_used,
                    reason="ttl_expired",
                )
                self.record_history(expired_item)
                self.save_current(None)
                return None
            return item
        except Exception:
            return None

    def record_history(self, item: SelfWorkItem) -> None:
        if not self.history_path:
            return
        line = json.dumps(_item_to_dict(item), ensure_ascii=False)
        try:
            lines = []
            if self.history_path.is_file():
                lines = [l for l in self.history_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            lines.append(line)
            lines = lines[-self.max_history_lines:]
            tmp_history = self.history_path.with_suffix(".tmp")
            with open(tmp_history, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(l + "\n")
            os.replace(tmp_history, self.history_path)
        except OSError:
            pass
