from __future__ import annotations

import json
import time
from pathlib import Path


class DiscordCapabilityExecutor:
    """Enfileira ações de controle do Discord formuladas pelas capabilities cognitivas do Hermes."""

    def __init__(self, queue_path: Path):
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, capability: str, arguments: dict[str, object], _plan=None, _action=None):
        cap = str(capability).strip()
        args = dict(arguments or {})

        if cap == "discord_purge_messages":
            qty = int(args.get("quantity") or 10)
            if qty > 20:
                raise PermissionError("expurgo > 20 mensagens requer confirmacao humana")

        action_item = {
            "id": f"act-{int(time.time() * 1000)}",
            "capability": cap,
            "arguments": args,
            "enqueued_at": time.time(),
        }
        with self.queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(action_item, ensure_ascii=False) + "\n")
        return {"status": "enqueued", "capability": cap, "arguments": args}
