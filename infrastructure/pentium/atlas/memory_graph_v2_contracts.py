"""Atlas MemoryGraph v2 — versioned node/event schema contracts (CP30).

Strict, typed, versioned validation for MemoryGraph v2 nodes and events,
with mandatory provenance and bounded payloads. This module is pure
validation: it performs no I/O, opens no database, and writes no
persistent data. Existing memory_graph.py (v1) and every other module
remain untouched; migration and dual-read live in later checkpoints.

Contract rules:
- schema_version must be the exact int 2 (no bool, no str, no float).
- Top-level fields are closed: unknown or missing keys are rejected.
- Identifiers, correlation IDs and lineage IDs are bounded ASCII tokens.
- Timestamps must be timezone-aware ISO-8601 and normalize to UTC.
- Payloads are JSON-only, bounded in keys, depth, string size and bytes,
  and are deep-frozen after validation.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

SCHEMA_VERSION = 2

MAX_PAYLOAD_BYTES = 4096
MAX_PAYLOAD_KEYS = 32
MAX_PAYLOAD_DEPTH = 4
MAX_PAYLOAD_STRING_CHARS = 1024
MAX_LINEAGE_IDS = 16
MAX_EVIDENCE_REFS = 8
MAX_ID_CHARS = 128
MAX_LABEL_CHARS = 200
MAX_SOURCE_CHARS = 128
MAX_EVIDENCE_REF_CHARS = 256

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

NODE_STATUSES = frozenset({"active", "revoked"})


class ContractViolation(ValueError):
    """A raw value violated the MemoryGraph v2 contract; message is the code."""


class NodeKind(str, Enum):
    PROJECT = "project"
    NODE = "node"
    REPOSITORY = "repository"
    DECISION = "decision"
    PATTERN = "pattern"
    PREFERENCE = "preference"
    PERSON = "person"
    SERVICE = "service"
    INCIDENT = "incident"
    MEMORY = "memory"
    OPERATIONAL_EVENT = "operational_event"
    GOAL = "goal"
    ACTION = "action"
    ARTIFACT = "artifact"


class EventKind(str, Enum):
    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_REVOKED = "node_revoked"
    RELATION_ADDED = "relation_added"
    RELATION_REMOVED = "relation_removed"


# --- Strict scalar helpers -------------------------------------------------


def _require_object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ContractViolation(f"{name}_invalid")
    return value


def _exact_fields(data: Mapping, *, required: frozenset, optional: frozenset,
                  name: str) -> None:
    keys = set(data)
    if not all(isinstance(key, str) for key in keys):
        raise ContractViolation(f"{name}_fields_invalid")
    if not keys.issubset(required | optional) or not required.issubset(keys):
        raise ContractViolation(f"{name}_fields_invalid")


def _bounded_text(value: Any, name: str, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip()
            or len(value) > limit or _CONTROL_RE.search(value)):
        raise ContractViolation(f"{name}_invalid")
    return value.strip()


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_ID_CHARS or not _ID_RE.fullmatch(value):
        raise ContractViolation(f"{name}_invalid")
    return value


def _utc(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractViolation(f"{name}_invalid")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContractViolation(f"{name}_invalid") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ContractViolation(f"{name}_invalid")
    return instant.astimezone(timezone.utc).isoformat()


def _identifiers(values: Any, *, field_name: str, max_items: int) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or len(values) > max_items:
        raise ContractViolation(f"{field_name}_invalid")
    return tuple(_identifier(item, field_name) for item in values)


def _refs(values: Any, *, field_name: str, max_items: int) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or len(values) > max_items:
        raise ContractViolation(f"{field_name}_invalid")
    return tuple(_bounded_text(item, field_name, MAX_EVIDENCE_REF_CHARS) for item in values)


def _enum_value(enum_cls, value: Any, name: str):
    if not isinstance(value, str):
        raise ContractViolation(f"{name}_invalid")
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise ContractViolation(f"{name}_invalid") from exc


# --- Bounded, frozen payload ----------------------------------------------


def _freeze(value: Any, depth: int):
    if value is None or type(value) in (bool, int, str):
        if type(value) is str and len(value) > MAX_PAYLOAD_STRING_CHARS:
            raise ContractViolation("payload_value_invalid")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ContractViolation("payload_value_invalid")
        return value
    if depth > MAX_PAYLOAD_DEPTH:
        raise ContractViolation("payload_too_deep")
    if isinstance(value, dict):
        if len(value) > MAX_PAYLOAD_KEYS:
            raise ContractViolation("payload_too_many_keys")
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
                raise ContractViolation("payload_keys_invalid")
            frozen[key] = _freeze(item, depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, depth + 1) for item in value)
    raise ContractViolation("payload_value_invalid")


def _payload(raw: Any) -> Mapping[str, Any]:
    if not isinstance(raw, dict):
        raise ContractViolation("payload_invalid")
    if len(raw) > MAX_PAYLOAD_KEYS:
        raise ContractViolation("payload_too_many_keys")
    frozen = _freeze(raw, 1)
    try:
        encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:  # pragma: no cover - freeze already guards
        raise ContractViolation("payload_invalid") from exc
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ContractViolation("payload_too_large")
    return frozen


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


# --- Provenance ------------------------------------------------------------

_PROVENANCE_FIELDS = frozenset({
    "source", "producer", "captured_at", "correlation_id", "lineage", "evidence_refs",
})


@dataclass(frozen=True)
class Provenance:
    """Who produced a node/event, when, under which correlation and lineage."""
    source: str
    producer: str
    captured_at: str
    correlation_id: str
    lineage: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _bounded_text(self.source, "source", MAX_SOURCE_CHARS))
        object.__setattr__(self, "producer", _bounded_text(self.producer, "producer", MAX_SOURCE_CHARS))
        object.__setattr__(self, "captured_at", _utc(self.captured_at, "captured_at"))
        object.__setattr__(self, "correlation_id", _identifier(self.correlation_id, "correlation_id"))
        object.__setattr__(self, "lineage",
                           _identifiers(self.lineage, field_name="lineage", max_items=MAX_LINEAGE_IDS))
        object.__setattr__(self, "evidence_refs",
                           _refs(self.evidence_refs, field_name="evidence_refs", max_items=MAX_EVIDENCE_REFS))


def parse_provenance(raw: Any) -> Provenance:
    data = _require_object(raw, "provenance")
    _exact_fields(data, required=_PROVENANCE_FIELDS, optional=frozenset(), name="provenance")
    return Provenance(
        source=data["source"],
        producer=data["producer"],
        captured_at=data["captured_at"],
        correlation_id=data["correlation_id"],
        lineage=data["lineage"],
        evidence_refs=data["evidence_refs"],
    )


def provenance_to_dict(provenance: Provenance) -> dict:
    return {
        "source": provenance.source,
        "producer": provenance.producer,
        "captured_at": provenance.captured_at,
        "correlation_id": provenance.correlation_id,
        "lineage": list(provenance.lineage),
        "evidence_refs": list(provenance.evidence_refs),
    }


# --- Node ------------------------------------------------------------------

_NODE_FIELDS = frozenset({
    "schema_version", "node_id", "node_kind", "label", "status",
    "created_at", "updated_at", "provenance", "payload",
})


@dataclass(frozen=True)
class GraphNodeV2:
    """A versioned MemoryGraph v2 node with mandatory provenance."""
    schema_version: int
    node_id: str
    node_kind: NodeKind
    label: str
    status: str
    created_at: str
    updated_at: str
    provenance: Provenance
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractViolation("schema_version_invalid")
        object.__setattr__(self, "node_id", _identifier(self.node_id, "node_id"))
        if not isinstance(self.node_kind, NodeKind):
            raise ContractViolation("node_kind_invalid")
        object.__setattr__(self, "label", _bounded_text(self.label, "label", MAX_LABEL_CHARS))
        if not isinstance(self.status, str) or self.status not in NODE_STATUSES:
            raise ContractViolation("status_invalid")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if not isinstance(self.provenance, Provenance):
            raise ContractViolation("provenance_invalid")
        if not isinstance(self.payload, Mapping):
            raise ContractViolation("payload_invalid")


def parse_node(raw: Any) -> GraphNodeV2:
    data = _require_object(raw, "node")
    _exact_fields(data, required=_NODE_FIELDS, optional=frozenset(), name="node")
    return GraphNodeV2(
        schema_version=data["schema_version"],
        node_id=data["node_id"],
        node_kind=_enum_value(NodeKind, data["node_kind"], "node_kind"),
        label=data["label"],
        status=data["status"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        provenance=parse_provenance(data["provenance"]),
        payload=_payload(data["payload"]),
    )


def node_to_dict(node: GraphNodeV2) -> dict:
    return {
        "schema_version": node.schema_version,
        "node_id": node.node_id,
        "node_kind": node.node_kind.value,
        "label": node.label,
        "status": node.status,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
        "provenance": provenance_to_dict(node.provenance),
        "payload": _thaw(node.payload),
    }


# --- Event -----------------------------------------------------------------

_EVENT_REQUIRED = frozenset({
    "schema_version", "event_id", "event_kind", "subject_id",
    "occurred_at", "provenance", "payload",
})
_EVENT_OPTIONAL = frozenset({"supersedes_id"})


@dataclass(frozen=True)
class GraphEventV2:
    """A versioned, append-only MemoryGraph v2 event with mandatory provenance."""
    schema_version: int
    event_id: str
    event_kind: EventKind
    subject_id: str
    occurred_at: str
    provenance: Provenance
    payload: Mapping[str, Any]
    supersedes_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractViolation("schema_version_invalid")
        object.__setattr__(self, "event_id", _identifier(self.event_id, "event_id"))
        if not isinstance(self.event_kind, EventKind):
            raise ContractViolation("event_kind_invalid")
        object.__setattr__(self, "subject_id", _identifier(self.subject_id, "subject_id"))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        if not isinstance(self.provenance, Provenance):
            raise ContractViolation("provenance_invalid")
        if not isinstance(self.payload, Mapping):
            raise ContractViolation("payload_invalid")
        if self.supersedes_id is not None:
            object.__setattr__(self, "supersedes_id",
                               _identifier(self.supersedes_id, "supersedes_id"))


def parse_event(raw: Any) -> GraphEventV2:
    data = _require_object(raw, "event")
    _exact_fields(data, required=_EVENT_REQUIRED, optional=_EVENT_OPTIONAL, name="event")
    return GraphEventV2(
        schema_version=data["schema_version"],
        event_id=data["event_id"],
        event_kind=_enum_value(EventKind, data["event_kind"], "event_kind"),
        subject_id=data["subject_id"],
        occurred_at=data["occurred_at"],
        provenance=parse_provenance(data["provenance"]),
        payload=_payload(data["payload"]),
        supersedes_id=data.get("supersedes_id"),
    )


def event_to_dict(event: GraphEventV2) -> dict:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "event_kind": event.event_kind.value,
        "subject_id": event.subject_id,
        "occurred_at": event.occurred_at,
        "provenance": provenance_to_dict(event.provenance),
        "payload": _thaw(event.payload),
        "supersedes_id": event.supersedes_id,
    }
