from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceEconomyPublisher:
    def __init__(self, path: Path):
        self.path = Path(path)

    def publish(self, *, broker, governor, router, self_work, expected_sha: str | None = None) -> dict:
        current = self_work.current if self_work is not None else None
        economy = dict(governor.metrics())
        economy["routes"] = router.metrics()
        payload = {
            "schema_version": 1,
            "generated_at": _utc_now(),
            "status": "healthy",
            "expected_sha": expected_sha,
            "workspace": broker.status(),
            "self_work": {
                "active": current is not None,
                "item_id": None if current is None else current.item_id,
                "objective": None if current is None else current.objective,
                "area": None if current is None else current.area,
                "state": None if current is None else current.state.value,
                "operations_used": 0 if current is None else current.operations_used,
                "inferences_used": 0 if current is None else current.inferences_used,
            },
            "economy": economy,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)
        return payload
