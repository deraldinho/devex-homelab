from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class MemoryLayer(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    RELATIONAL = "relational"


def _utc(value: str) -> str:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp deve possuir timezone")
    return instant.astimezone(timezone.utc).isoformat()


def _bounded01(value: float, name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} deve estar entre 0 e 1")
    return value

@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    layer: MemoryLayer
    created_at: str
    entity_id: str | None
    content: str
    importance: float
    confidence: float
    frequency: int
    origin: str
    criticality: float = 0.0
    pinned: bool = False
    protected: bool = False
    expires_at: str | None = None
    dedupe_key: str | None = None
    message_id: str | None = None
    reply_to_id: str | None = None
    thread_id: str | None = None
    channel_id: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.memory_id, str) or not self.memory_id.strip():
            raise ValueError("memory_id nao pode ser vazio")
        if not isinstance(self.layer, MemoryLayer):
            raise ValueError("layer invalida")
        text = str(self.content).strip()
        if not text or len(text) > 1024:
            raise ValueError("content deve possuir 1..1024 caracteres")
        if not isinstance(self.frequency, int) or self.frequency <= 0:
            raise ValueError("frequency deve ser inteiro > 0")
        if not isinstance(self.origin, str) or not self.origin.strip():
            raise ValueError("origin nao pode ser vazio")
        object.__setattr__(self, "memory_id", self.memory_id.strip())
        object.__setattr__(self, "created_at", _utc(self.created_at))
        object.__setattr__(self, "content", text)
        object.__setattr__(self, "importance", _bounded01(self.importance, "importance"))
        object.__setattr__(self, "confidence", _bounded01(self.confidence, "confidence"))
        object.__setattr__(self, "criticality", _bounded01(self.criticality, "criticality"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _utc(self.expires_at))
        if self.message_id is not None:
            object.__setattr__(self, "message_id", str(self.message_id).strip() or None)
        if self.reply_to_id is not None:
            object.__setattr__(self, "reply_to_id", str(self.reply_to_id).strip() or None)
        if self.thread_id is not None:
            object.__setattr__(self, "thread_id", str(self.thread_id).strip() or None)
        if self.channel_id is not None:
            object.__setattr__(self, "channel_id", str(self.channel_id).strip() or None)
        if self.tags:
            clean_tags = tuple(str(t).strip() for t in self.tags if str(t).strip())
            object.__setattr__(self, "tags", clean_tags)
        else:
            object.__setattr__(self, "tags", ())
