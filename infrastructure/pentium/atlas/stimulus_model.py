from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class StimulusSeverity(str, Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


def stable_fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compute_novelty(previous_seen_count: int) -> float:
    if previous_seen_count < 0:
        raise ValueError("previous_seen_count must be >= 0")
    return max(0.1, 1.0 / (previous_seen_count + 1))


@dataclass(frozen=True)
class Stimulus:
    stimulus_id: str
    source: str
    kind: str
    severity: StimulusSeverity
    timestamp: str
    payload: Mapping[str, Any]
    novelty: float
    correlation_id: str
    previous_fingerprint: str | None = None
    current_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stimulus_id": self.stimulus_id,
            "source": self.source,
            "kind": self.kind,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "novelty": self.novelty,
            "correlation_id": self.correlation_id,
            "previous_fingerprint": self.previous_fingerprint,
            "current_fingerprint": self.current_fingerprint,
        }
