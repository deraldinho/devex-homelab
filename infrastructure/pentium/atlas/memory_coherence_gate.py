"""CP-MEM-P0: conservative gate against self-propagating memory instructions.

This is a *data quality* boundary for automatic EPISODIC -> SEMANTIC
promotion, NOT an authorization system. The origin and tags stored in
MemoryRecord are untrusted claims; they can restrict eligibility but cannot
grant action privileges. Authorization belongs to the capability policy and
its separately authenticated operator channel.

Deterministic prompt-injection indicators are defense in depth only. They
cannot classify all natural-language instructions. All retrieved memories
remain untrusted evidence, including promoted SEMANTIC records.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .memory_ingress import MemoryKind
from .memory_model import MemoryLayer, MemoryRecord

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .memory_ingress import IngressVerdict


__all__ = [
    "MemoryKind",
    "PromotionReview",
    "declared_kind",
    "memory_kind",
    "review_promotion",
    "same_evidence_claim",
]

@dataclass(frozen=True)
class PromotionReview:
    allowed: bool
    reason: str
    memory_kind: str
    authority: str = "evidence_only"
    kind_source: str = "tags"
    attested: bool = False



# Anchored role claims and short imperative sequences are intentionally
# conservative. This is NOT a general prompt-injection detector.
_INJECTION = (
    re.compile(r"(?i)(?:\[system\]|<\s*system\s*>|role\s*[:=]\s*system)"),
    re.compile(r"(?i)\b(?:ignore|disregard|forget)\b.{0,70}\b(?:previous|prior|system|instructions|policy)\b"),
    re.compile(r"(?i)\b(?:override|bypass|disable)\b.{0,48}\b(?:policy|safeguards|guardrails|approval|permissions)\b"),
    re.compile(r"(?i)\b(?:ignore|desconsidere|ignorem)\b.{0,64}\b(?:instru[cç][oõ]es|pol[ií]tica|regras anteriores)\b"),
)

_FORBIDDEN_ORIGIN_PREFIXES = (
    "agent", "assistant", "llm", "model", "tool", "workspace",
    "file", "document", "retrieved", "discord", "web", "prompt",
)


def declared_kind(record: MemoryRecord) -> str | None:
    """Kind explicitly asserted by tags, or None when no `kind:` tag exists.

    A tag is never proof of authorization, but multiple or unknown kinds are
    reported as ``"invalid"`` so callers can fail closed.
    """
    markers = [x[5:] for x in record.tags if x.startswith("kind:")]
    if not markers:
        return None
    if len(markers) != 1:
        return "invalid"
    try:
        return MemoryKind(markers[0]).value
    except ValueError:
        return "invalid"


def memory_kind(record: MemoryRecord) -> str:
    """Restrictive, tag-derived classification (P0 compatibility path)."""
    declared = declared_kind(record)
    return MemoryKind.OBSERVATION.value if declared is None else declared


def same_evidence_claim(left: MemoryRecord, right: MemoryRecord) -> bool:
    """Dedupe identity is not proof of equivalent facts or provenance."""
    return (
        left.dedupe_key is not None
        and left.dedupe_key == right.dedupe_key
        and left.origin == right.origin
        and left.content == right.content
        and left.entity_id == right.entity_id
        and left.layer is right.layer
        and left.tags == right.tags
        and left.pinned is right.pinned
        and left.protected is right.protected
    )


def review_promotion(record: MemoryRecord, *,
                     verdict: "IngressVerdict | None" = None) -> PromotionReview:
    """Whether recurrence may *index* information as semantic evidence.

    This decision never grants execution rights or upgrades source authority.
    Unknown types, self-generated claims and suspicious directives stay in
    EPISODIC memory for review; records are not deleted.

    When a verified ingress ``verdict`` is supplied, the immutable attested
    ``kind`` is authoritative and a conflicting tag claim is rejected. Without
    a verdict the tag-derived classification (P0 behaviour) is used.
    """
    if not isinstance(record, MemoryRecord):
        return PromotionReview(False, "not_record", "unknown")
    kind = memory_kind(record)
    kind_source = "tags"
    attested = False
    if verdict is not None:
        kind_source = "attestation"
        if not getattr(verdict, "allowed", False):
            reason = str(getattr(verdict, "reason", "attestation_invalid"))
            return PromotionReview(False, reason, kind, kind_source=kind_source)
        declared = declared_kind(record)
        if declared == "invalid":
            return PromotionReview(False, "kind_invalid", getattr(verdict, "kind", kind),
                                   kind_source=kind_source, attested=True)
        if declared is not None and declared != getattr(verdict, "kind", declared):
            return PromotionReview(False, "kind_conflict", getattr(verdict, "kind", kind),
                                   kind_source=kind_source, attested=True)
        kind = getattr(verdict, "kind", kind)
        attested = True
    if record.layer is not MemoryLayer.EPISODIC:
        return PromotionReview(False, "not_episodic", kind, kind_source=kind_source, attested=attested)
    if kind == "invalid":
        return PromotionReview(False, "kind_invalid", kind, kind_source=kind_source, attested=attested)
    if kind in (MemoryKind.INSTRUCTION.value, MemoryKind.HYPOTHESIS.value):
        return PromotionReview(False, "non_factual_kind", kind, kind_source=kind_source, attested=attested)
    source = record.origin.strip().lower()
    if (source.startswith(_FORBIDDEN_ORIGIN_PREFIXES)
            or source not in ("observation", "human")
            and not source.startswith("episodic:")):
        return PromotionReview(False, "untrusted_origin", kind, kind_source=kind_source, attested=attested)
    if any(pattern.search(record.content) for pattern in _INJECTION):
        return PromotionReview(False, "instruction_indicator", kind, kind_source=kind_source, attested=attested)
    return PromotionReview(True, "evidence_only_promotion", kind,
                           kind_source=kind_source, attested=attested)
