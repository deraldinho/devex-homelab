from __future__ import annotations

from dataclasses import dataclass
import time

from .continuous_intent import ContinuousIntent


@dataclass(frozen=True)
class HabituationDecision:
    allow_message: bool
    tracking_visual: bool
    habituation: float


@dataclass
class _Entry:
    fingerprint: str
    repeats: int
    terminal_notified: bool
    last_seen: float


class HabituationEngine:
    def __init__(self, *, max_entries: int = 64, ttl_s: float = 300.0, clock=time.monotonic):
        if max_entries <= 0 or ttl_s <= 0:
            raise ValueError("invalid habituation bounds")
        self._max_entries = int(max_entries)
        self._ttl_s = float(ttl_s)
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    @property
    def size(self) -> int:
        return len(self._entries)

    def _key(self, intent: ContinuousIntent) -> str:
        return f"{intent.intencao_id}:{intent.assunto_id}"

    def _cleanup(self, now: float) -> None:
        stale = [key for key, item in self._entries.items() if now - item.last_seen > self._ttl_s]
        for key in stale:
            self._entries.pop(key, None)
        while len(self._entries) >= self._max_entries:
            oldest = min(self._entries.items(), key=lambda item: item[1].last_seen)[0]
            self._entries.pop(oldest, None)

    def evaluate(self, intent: ContinuousIntent, material_fingerprint: str, *, terminal: bool = False) -> HabituationDecision:
        now = float(self._clock())
        self._cleanup(now)
        key = self._key(intent)
        entry = self._entries.get(key)
        fingerprint = str(material_fingerprint)

        if entry is None:
            entry = _Entry(fingerprint=fingerprint, repeats=0, terminal_notified=False, last_seen=now)
            self._entries[key] = entry
            if terminal:
                entry.terminal_notified = True
                return HabituationDecision(True, False, 0.0)
            return HabituationDecision(True, True, 0.0)

        changed = fingerprint != entry.fingerprint
        if changed:
            entry.fingerprint = fingerprint
            entry.repeats = 0
        else:
            entry.repeats += 1
        entry.last_seen = now

        if terminal:
            if entry.terminal_notified:
                return HabituationDecision(False, False, 1.0)
            entry.terminal_notified = True
            return HabituationDecision(True, False, min(1.0, entry.repeats / 5.0))

        habituation = min(1.0, entry.repeats / 5.0)
        return HabituationDecision(changed, True, habituation)
