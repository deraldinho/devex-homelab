from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class EpisodeCategory(str, Enum):
    INCIDENT = "incident"
    DEPLOYMENT = "deployment"
    DEVELOPMENT_SESSION = "development_session"
    HUMAN_INTERACTION = "human_interaction"
    GENERIC = "generic"


class SegmentStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CONSOLIDATED = "consolidated"


class ClosureReason(str, Enum):
    TERMINAL_EVENT = "terminal_event"
    SEMANTIC_CHANGE = "semantic_change"
    IDLE_TIMEOUT = "idle_timeout"
    MAX_EVENTS = "max_events"
    MAX_BYTES = "max_bytes"
    GENERATION_FENCE = "generation_fence"
    RESTART_RECOVERY = "restart_recovery"


def _utc(value: str) -> str:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp deve possuir timezone")
    return instant.astimezone(timezone.utc).isoformat()


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} nao pode ser vazio")
    return value.strip()


def _bounded01(value: float, name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} deve estar entre 0 e 1")
    return value


@dataclass(frozen=True)
class EpisodicEvidence:
    event_id: str
    occurred_at: str
    source: str
    source_kind: str
    content_reduced: str
    reliability: float
    verified: bool
    generation_id: str
    dedupe_key: str | None = None
    importance: float = 0.5
    criticality: float = 0.0
    entity_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _text(self.event_id, "event_id"))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "source_kind", _text(self.source_kind, "source_kind"))
        content = _text(self.content_reduced, "content_reduced")
        if len(content) > 512:
            raise ValueError("content_reduced deve possuir no maximo 512 caracteres")
        object.__setattr__(self, "content_reduced", content)
        object.__setattr__(self, "reliability", _bounded01(self.reliability, "reliability"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified deve ser booleano")
        object.__setattr__(self, "generation_id", _text(self.generation_id, "generation_id"))
        object.__setattr__(self, "importance", _bounded01(self.importance, "importance"))
        object.__setattr__(self, "criticality", _bounded01(self.criticality, "criticality"))
        if self.entity_id is not None:
            object.__setattr__(self, "entity_id", _text(self.entity_id, "entity_id"))


@dataclass(frozen=True)
class EpisodicSegment:
    segment_id: str
    generation_id: str
    category: EpisodeCategory
    entity_id: str | None
    semantic_key: str
    opened_at: str
    updated_at: str
    status: SegmentStatus = SegmentStatus.OPEN
    closure_reason: ClosureReason | None = None
    event_count: int = 0
    byte_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "segment_id", _text(self.segment_id, "segment_id"))
        object.__setattr__(self, "generation_id", _text(self.generation_id, "generation_id"))
        if not isinstance(self.category, EpisodeCategory):
            object.__setattr__(self, "category", EpisodeCategory(self.category))
        if self.entity_id is not None:
            object.__setattr__(self, "entity_id", _text(self.entity_id, "entity_id"))
        object.__setattr__(self, "semantic_key", _text(self.semantic_key, "semantic_key"))
        object.__setattr__(self, "opened_at", _utc(self.opened_at))
        object.__setattr__(self, "updated_at", _utc(self.updated_at))
        if not isinstance(self.status, SegmentStatus):
            object.__setattr__(self, "status", SegmentStatus(self.status))
        if self.closure_reason is not None and not isinstance(self.closure_reason, ClosureReason):
            object.__setattr__(self, "closure_reason", ClosureReason(self.closure_reason))
        if self.status is not SegmentStatus.OPEN and self.closure_reason is None:
            raise ValueError("segmento fechado deve possuir closure_reason")
        if self.event_count < 0 or self.byte_count < 0:
            raise ValueError("contadores do segmento nao podem ser negativos")


@dataclass(frozen=True)
class MemoryProvenance:
    segment_id: str
    memory_id: str
    generation_id: str
    sources: tuple[str, ...]
    started_at: str
    ended_at: str
    evidence_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "segment_id", _text(self.segment_id, "segment_id"))
        object.__setattr__(self, "memory_id", _text(self.memory_id, "memory_id"))
        object.__setattr__(self, "generation_id", _text(self.generation_id, "generation_id"))
        sources = tuple(sorted({_text(item, "source") for item in self.sources}))
        if not sources:
            raise ValueError("provenance deve possuir ao menos uma source")
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "started_at", _utc(self.started_at))
        object.__setattr__(self, "ended_at", _utc(self.ended_at))
        if self.evidence_count <= 0:
            raise ValueError("evidence_count deve ser > 0")
