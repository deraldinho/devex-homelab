"""CP-MEM-P1: signed ingress provenance and immutable memory typing.

This module is the trust foundation for memory ingestion. It answers two
narrow questions that retrieval and promotion must not answer by themselves:

* Was this record's *content identity* attested by a trusted ingress?
* What immutable ``kind`` did that ingress assign at ingestion time?

Guarantees and explicit limits:

- Classification is made at ingress and bound to a content address
  (SHA-256 over the immutable identity). The address is a *corruption*
  check; the HMAC signature is the only authentication element.
- HMAC-SHA256 binds a shared secret held by the trusted ingress. Keys are
  injected at runtime and are never read from, or written to, the
  repository. Production key provisioning is a separate operational gate.
- This is still **evidence only**. A valid attestation never grants action
  privileges; authorization remains with ``PolicyCapabilities`` and its
  independently authenticated operator channel.
- Operator instructions are deliberately kept in a *separate* store and
  require an independently signed operator approval. They are never
  returned by cognitive memory retrieval.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .memory_model import MemoryRecord

SCHEMA_VERSION = 1
DOMAIN_MEMORY = "atlas.memory.ingress.v1"
DOMAIN_INSTRUCTION = "atlas.operator.instruction.v1"
MIN_KEY_BYTES = 16

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9._:-]{1,64}")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_ATTESTATION_FIELDS = frozenset({
    "schema_version", "ingress", "subject_id", "kind", "content_sha256",
    "issued_at", "nonce", "signature",
})
_INSTRUCTION_FIELDS = frozenset({
    "schema_version", "instruction_id", "operator_id", "content",
    "approved_at", "created_at", "signature",
})


class IngressError(ValueError):
    """A value violated the ingress contract."""


class MemoryKind(str, Enum):
    OBSERVATION = "observation"
    FACT = "fact"
    HYPOTHESIS = "hypothesis"
    INSTRUCTION = "instruction"


@dataclass(frozen=True)
class IngressVerdict:
    allowed: bool
    reason: str
    kind: str


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _name(value: object, field: str) -> str:
    if (not isinstance(value, str) or not _NAME_RE.fullmatch(value)):
        raise IngressError(f"{field}_invalid")
    return value


def _token(value: object, field: str) -> str:
    if (not isinstance(value, str) or not _TOKEN_RE.fullmatch(value)):
        raise IngressError(f"{field}_invalid")
    return value


def _subject(value: object) -> str:
    if (not isinstance(value, str) or _CONTROL_RE.search(value)):
        raise IngressError("subject_id_invalid")
    text = value.strip()
    if not 1 <= len(text) <= 128:
        raise IngressError("subject_id_invalid")
    return text


def _hex64(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise IngressError(f"{field}_invalid")
    return value


def _utc(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise IngressError(f"{field}_invalid")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IngressError(f"{field}_invalid") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise IngressError(f"{field}_invalid")
    return instant.astimezone(timezone.utc).isoformat()


def _kind(value: object) -> str:
    try:
        return MemoryKind(value).value
    except (ValueError, TypeError) as exc:
        raise IngressError("kind_invalid") from exc


def _content_text(value: object, field: str) -> str:
    if not isinstance(value, str) or _CONTROL_RE.search(value):
        raise IngressError(f"{field}_invalid")
    text = value.strip()
    if not 1 <= len(text) <= 4096:
        raise IngressError(f"{field}_invalid")
    return text


def content_address(record: MemoryRecord, kind: str) -> str:
    """Deterministic SHA-256 over the immutable identity of a memory.

    The layer, frequency, importance, confidence, protection flags and
    tags are intentionally excluded: they legitimately evolve. Only the
    identity that the ingress vouched for is addressed.
    """
    payload = {
        "domain": DOMAIN_MEMORY,
        "schema_version": SCHEMA_VERSION,
        "memory_id": record.memory_id,
        "content": record.content,
        "origin": record.origin,
        "entity_id": record.entity_id or "",
        "created_at": record.created_at,
        "kind": _kind(kind),
    }
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def instruction_address(content: str) -> str:
    payload = {
        "domain": DOMAIN_INSTRUCTION,
        "schema_version": SCHEMA_VERSION,
        "content": _content_text(content, "content"),
    }
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


class TrustedKeyRegistry:
    """Runtime-only shared secrets for trusted ingresses and operators.

    Keys are supplied by the caller (environment/secret store) and are
    never persisted by this module. Verification uses constant-time
    comparison. An unknown principal is never trusted.
    """

    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}

    def add(self, name: str, key: bytes | str) -> None:
        _name(name, "principal")
        raw = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        if len(raw) < MIN_KEY_BYTES:
            raise IngressError("key_too_short")
        self._keys[name] = raw

    def has(self, name: str) -> bool:
        return isinstance(name, str) and name in self._keys

    def _key(self, name: str) -> bytes:
        if not self.has(name):
            raise IngressError("unknown_principal")
        return self._keys[name]

    def sign(self, name: str, message: bytes) -> str:
        return hmac.new(self._key(name), message, hashlib.sha256).hexdigest()

    def verify(self, name: str, message: bytes, signature: object) -> bool:
        if not isinstance(signature, str) or not self.has(name):
            return False
        expected = hmac.new(self._keys[name], message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class MemoryAttestation:
    """Signed, content-addressed classification of a single memory."""

    schema_version: int
    ingress: str
    subject_id: str
    kind: str
    content_sha256: str
    issued_at: str
    nonce: str
    signature: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise IngressError("attestation_schema_invalid")
        object.__setattr__(self, "ingress", _name(self.ingress, "ingress"))
        object.__setattr__(self, "subject_id", _subject(self.subject_id))
        object.__setattr__(self, "kind", _kind(self.kind))
        object.__setattr__(self, "content_sha256", _hex64(self.content_sha256, "content_sha256"))
        object.__setattr__(self, "issued_at", _utc(self.issued_at, "issued_at"))
        object.__setattr__(self, "nonce", _token(self.nonce, "nonce"))
        object.__setattr__(self, "signature", _hex64(self.signature, "signature"))

    def signed_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "ingress": self.ingress,
            "subject_id": self.subject_id,
            "kind": self.kind,
            "content_sha256": self.content_sha256,
            "issued_at": self.issued_at,
            "nonce": self.nonce,
        }

    def to_dict(self) -> dict:
        payload = self.signed_payload()
        payload["signature"] = self.signature
        return payload

    @classmethod
    def from_dict(cls, raw: object) -> "MemoryAttestation":
        if not isinstance(raw, dict) or set(raw) != _ATTESTATION_FIELDS:
            raise IngressError("attestation_fields_invalid")
        return cls(
            schema_version=raw["schema_version"],
            ingress=raw["ingress"],
            subject_id=raw["subject_id"],
            kind=raw["kind"],
            content_sha256=raw["content_sha256"],
            issued_at=raw["issued_at"],
            nonce=raw["nonce"],
            signature=raw["signature"],
        )


class MemoryIngress:
    """Trusted ingestion boundary that signs and verifies attestations."""

    def __init__(self, name: str, registry: TrustedKeyRegistry) -> None:
        _name(name, "ingress")
        if not isinstance(registry, TrustedKeyRegistry) or not registry.has(name):
            raise IngressError("unknown_ingress")
        self._name = name
        self._registry = registry

    @property
    def name(self) -> str:
        return self._name

    def attest(self, record: MemoryRecord, *, kind: str, issued_at: str,
               nonce: str | None = None) -> MemoryAttestation:
        if not isinstance(record, MemoryRecord):
            raise IngressError("record_invalid")
        kind_value = _kind(kind)
        issued = _utc(issued_at, "issued_at")
        nonce = secrets.token_hex(8) if nonce is None else _token(nonce, "nonce")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "ingress": self._name,
            "subject_id": record.memory_id,
            "kind": kind_value,
            "content_sha256": content_address(record, kind_value),
            "issued_at": issued,
            "nonce": nonce,
        }
        signature = self._registry.sign(self._name, _canonical_bytes(payload))
        return MemoryAttestation(signature=signature, **payload)

    def verify(self, record: MemoryRecord, attestation: object) -> IngressVerdict:
        if not isinstance(attestation, MemoryAttestation):
            return IngressVerdict(False, "attestation_invalid", "unknown")
        if not self._registry.has(attestation.ingress):
            return IngressVerdict(False, "attestation_ingress_untrusted", attestation.kind)
        if not self._registry.verify(
            attestation.ingress,
            _canonical_bytes(attestation.signed_payload()),
            attestation.signature,
        ):
            return IngressVerdict(False, "attestation_signature_invalid", attestation.kind)
        if not isinstance(record, MemoryRecord) or attestation.subject_id != record.memory_id:
            return IngressVerdict(False, "attestation_subject_mismatch", attestation.kind)
        kind = _kind(attestation.kind)
        if content_address(record, kind) != attestation.content_sha256:
            return IngressVerdict(False, "content_address_mismatch", kind)
        return IngressVerdict(True, "attested_evidence", kind)


@dataclass(frozen=True)
class OperatorInstruction:
    """An operator-approved instruction, kept apart from memory evidence."""

    schema_version: int
    instruction_id: str
    operator_id: str
    content: str
    approved_at: str
    created_at: str
    signature: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise IngressError("instruction_schema_invalid")
        object.__setattr__(self, "instruction_id", _name(self.instruction_id, "instruction_id"))
        object.__setattr__(self, "operator_id", _name(self.operator_id, "operator_id"))
        object.__setattr__(self, "content", _content_text(self.content, "content"))
        object.__setattr__(self, "approved_at", _utc(self.approved_at, "approved_at"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "signature", _hex64(self.signature, "signature"))

    def signed_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "instruction_id": self.instruction_id,
            "operator_id": self.operator_id,
            "content_sha256": instruction_address(self.content),
            "approved_at": self.approved_at,
        }

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "instruction_id": self.instruction_id,
            "operator_id": self.operator_id,
            "content": self.content,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "OperatorInstruction":
        if not isinstance(raw, dict) or set(raw) != _INSTRUCTION_FIELDS:
            raise IngressError("instruction_fields_invalid")
        return cls(
            schema_version=raw["schema_version"],
            instruction_id=raw["instruction_id"],
            operator_id=raw["operator_id"],
            content=raw["content"],
            approved_at=raw["approved_at"],
            created_at=raw["created_at"],
            signature=raw["signature"],
        )


class OperatorAuthority:
    """Independently signs and verifies operator instruction approvals."""

    def __init__(self, name: str, registry: TrustedKeyRegistry) -> None:
        _name(name, "operator")
        if not isinstance(registry, TrustedKeyRegistry) or not registry.has(name):
            raise IngressError("unknown_operator")
        self._name = name
        self._registry = registry

    def issue(self, *, instruction_id: str, operator_id: str, content: str,
              approved_at: str, created_at: str | None = None) -> OperatorInstruction:
        approved = _utc(approved_at, "approved_at")
        created = _utc(created_at or approved_at, "created_at")
        draft = OperatorInstruction(
            schema_version=SCHEMA_VERSION,
            instruction_id=instruction_id,
            operator_id=operator_id,
            content=content,
            approved_at=approved,
            created_at=created,
            signature="0" * 64,
        )
        signature = self._registry.sign(self._name, _canonical_bytes(draft.signed_payload()))
        return OperatorInstruction(
            schema_version=draft.schema_version,
            instruction_id=draft.instruction_id,
            operator_id=draft.operator_id,
            content=draft.content,
            approved_at=draft.approved_at,
            created_at=draft.created_at,
            signature=signature,
        )

    def verify(self, instruction: object) -> bool:
        if not isinstance(instruction, OperatorInstruction):
            return False
        return self._registry.verify(
            self._name,
            _canonical_bytes(instruction.signed_payload()),
            instruction.signature,
        )

    def persist(self, store, instruction: OperatorInstruction) -> bool:
        """Verify the approval *before* handing it to persistent storage."""
        if not self.verify(instruction):
            raise IngressError("operator_instruction_signature_invalid")
        return store.save_operator_instruction(instruction)
