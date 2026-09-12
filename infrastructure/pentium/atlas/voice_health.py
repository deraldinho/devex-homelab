from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class VoiceHealthPublisher:
    def __init__(self, path: Path, *, max_reason_chars: int = 256, now=None):
        if max_reason_chars <= 0:
            raise ValueError("max_reason_chars deve ser > 0")
        self._path = Path(path)
        self._max_reason_chars = int(max_reason_chars)
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat())

    def publish(self, *, status: str, state: str,
                reason: str | None, expected_sha: str | None) -> None:
        payload = {
            "schema_version": 1,
            "status": str(status),
            "state": str(state)[:64],
            "reason": None if reason is None else str(reason)[:self._max_reason_chars],
            "expected_sha": None if expected_sha is None else str(expected_sha).strip().lower(),
            "generated_at": str(self._now()),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_name(self._path.name + ".tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, self._path)
        finally:
            temp.unlink(missing_ok=True)
