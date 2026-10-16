"""CP-MEM-P2: coherence enforcement at the action-authorization sink.

CP-MEM-P0/P1 made memory evidence tamper-evident and typed, but only at
ingestion, retrieval and promotion. This module moves the check to the
*authorization* decision: a capability action must not be auto-authorized
when the memory evidence that influenced the plan is untrusted or tampered.

It is deterministic and I/O-light. It never grants authority; it can only
restrict, quarantine and escalate to human approval.

Risk model (fail closed):
- READ -> LOW, CONTROL -> MEDIUM, DESTRUCTIVE -> HIGH, unknown -> HIGH.
- Tampered evidence quarantines the offending memories and blocks any
  MEDIUM/HIGH action outright (human approval cannot override tampering).
- MEDIUM/HIGH actions influenced by un-attested (no verified provenance)
  evidence are escalated to human approval instead of auto-executing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

MAX_QUARANTINE_ENTRIES = 1000
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_CORRELATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class ActionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_LEVEL_RISK = {
    "READ": ActionRisk.LOW,
    "CONTROL": ActionRisk.MEDIUM,
    "DESTRUCTIVE": ActionRisk.HIGH,
}


def classify_risk(level: object) -> ActionRisk:
    """Map a capability level to an impact risk; unknown levels fail closed."""
    if isinstance(level, str):
        risk = _LEVEL_RISK.get(level.strip().upper())
        if risk is not None:
            return risk
    return ActionRisk.HIGH


@dataclass(frozen=True)
class CoherenceDecision:
    allowed: bool
    requires_human_approval: bool
    risk: str
    correlation_id: str
    reason: str
    quarantine: tuple[str, ...] = ()


def _correlation(value: object) -> str:
    if not isinstance(value, str) or not _CORRELATION_RE.fullmatch(value):
        raise ValueError("correlation_id_invalid")
    return value


class QuarantineRegistry:
    """Durable record of memories whose evidence was detected as tampered.

    Operationally a review queue, not a cognitive memory. Bounded, atomic and
    safe to reload; a corrupt file is ignored rather than trusted.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            return
        items = raw.get("entries")
        if not isinstance(items, list):
            return
        for item in items[:MAX_QUARANTINE_ENTRIES]:
            if not isinstance(item, dict):
                continue
            memory_id = item.get("memory_id")
            if isinstance(memory_id, str) and _ID_RE.fullmatch(memory_id):
                self._entries[memory_id] = {
                    "memory_id": memory_id,
                    "reason": str(item.get("reason") or "tampered"),
                    "correlation_id": str(item.get("correlation_id") or ""),
                    "quarantined_at": str(item.get("quarantined_at") or ""),
                }

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "entries": list(self._entries.values())}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    def quarantine(self, memory_id: str, *, reason: str, correlation_id: str,
                   at: str | None = None) -> bool:
        """Record a memory for review. Idempotent; True when newly added."""
        if not isinstance(memory_id, str) or not _ID_RE.fullmatch(memory_id):
            raise ValueError("quarantine_id_invalid")
        instant = at or datetime.now(timezone.utc).isoformat()
        try:
            instant = datetime.fromisoformat(instant).astimezone(timezone.utc).isoformat()
        except ValueError as exc:
            raise ValueError("quarantine_timestamp_invalid") from exc
        if memory_id in self._entries:
            return False
        if len(self._entries) >= MAX_QUARANTINE_ENTRIES:
            oldest = min(self._entries, key=lambda key: self._entries[key]["quarantined_at"])
            del self._entries[oldest]
        self._entries[memory_id] = {
            "memory_id": memory_id,
            "reason": str(reason)[:128],
            "correlation_id": str(correlation_id)[:128],
            "quarantined_at": instant,
        }
        self._persist()
        return True

    def is_quarantined(self, memory_id: str) -> bool:
        return memory_id in self._entries

    def list(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(item) for item in self._entries.values())


@dataclass(frozen=True)
class _EvidenceSummary:
    total: int
    attested: int
    unattested: int
    tainted_ids: tuple[str, ...]
    quarantine_safe: tuple[str, ...] = field(default=())


def _summarize(memories: Any) -> _EvidenceSummary:
    total = attested = unattested = 0
    tainted: list[str] = []
    safe: list[str] = []
    for item in memories or ():
        if not isinstance(item, Mapping):
            continue
        total += 1
        integrity = item.get("integrity")
        if integrity == "tampered":
            memory_id = str(item.get("memory_id") or "")
            if _ID_RE.fullmatch(memory_id):
                tainted.append(memory_id)
            else:
                unattested += 1
        elif integrity == "attested":
            attested += 1
        else:
            unattested += 1
        memory_id = str(item.get("memory_id") or "")
        if memory_id and _ID_RE.fullmatch(memory_id):
            safe.append(memory_id)
    return _EvidenceSummary(total, attested, unattested, tuple(tainted), tuple(safe))


class MemoryCoherenceGate:
    """Enforces memory coherence at the action-authorization sink."""

    def __init__(self, *, quarantine: QuarantineRegistry | None = None,
                 escalate_at: ActionRisk = ActionRisk.MEDIUM) -> None:
        self._quarantine = quarantine or QuarantineRegistry()
        self._escalate_at = escalate_at

    def _risk_at_least(self, risk: ActionRisk) -> bool:
        order = {ActionRisk.LOW: 0, ActionRisk.MEDIUM: 1, ActionRisk.HIGH: 2}
        return order[risk] >= order[self._escalate_at]

    def evaluate(self, *, capability: str, level: object, memories: Any = (),
                 correlation_id: str, human_approval: bool = False) -> CoherenceDecision:
        correlation = _correlation(correlation_id)
        risk = classify_risk(level)
        summary = _summarize(memories)
        if summary.total == 0:
            return CoherenceDecision(True, False, risk.value, correlation,
                                     "no_memory_evidence")

        quarantined: list[str] = []
        for memory_id in summary.tainted_ids:
            try:
                if self._quarantine.quarantine(
                    memory_id, reason="tampered_memory_evidence",
                    correlation_id=correlation,
                ):
                    quarantined.append(memory_id)
            except ValueError:
                continue

        if summary.tainted_ids:
            if self._risk_at_least(risk):
                return CoherenceDecision(
                    False, True, risk.value, correlation,
                    "tampered_memory_evidence", tuple(quarantined),
                )
            return CoherenceDecision(
                True, False, risk.value, correlation,
                "tampered_low_impact_quarantined", tuple(quarantined),
            )

        if self._risk_at_least(risk) and summary.unattested > 0:
            if human_approval:
                return CoherenceDecision(True, False, risk.value, correlation,
                                         "human_approval_granted")
            return CoherenceDecision(True, True, risk.value, correlation,
                                     "unattested_evidence_requires_human_approval")

        return CoherenceDecision(True, False, risk.value, correlation,
                                 "coherent_evidence")
