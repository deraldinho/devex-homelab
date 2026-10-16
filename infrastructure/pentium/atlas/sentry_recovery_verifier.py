"""CP-SENTRY-P2: authenticated recovery evidence for a *separate*, trusted producer.

The action executor and independent health probe must use different 256-bit
HMAC keys, provisioned outside prompts, repositories, and Atlas memory. The
consumer only verifies their signed results. The keys and the sign helper
must not be offered to an LLM agent or exposed as an executable capability.

An authenticated receipt proves what its authorized issuer attested; it does
not itself prove the issuer's probe or executor is correct. This module never
executes commands, grants permission or generates new policy.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from .failure_memory import FailureMemory, FailureMemoryError

_RECEIPT_KEYS = frozenset({
    "version", "issuer", "key_id", "receipt_id", "incident_id",
    "component", "host", "action_id", "event_at", "operation",
    "target", "status", "authorized", "evidence_ref",
})
_SIGNED_KEYS = _RECEIPT_KEYS | {"mac"}
_IDENT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_:.\-]{0,127}\Z", re.ASCII)
_MAC = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ISSUERS = ("executor", "health_probe")
_OPERATIONS = frozenset(("restart_service", "start_service"))
_DEFAULT_WINDOW = timedelta(hours=24)


class RecoveryEvidenceError(FailureMemoryError):
    """Fail-closed rejection with no user-data in diagnostic messages."""


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")


def _event_timestamp(value):
    if not isinstance(value, str) or len(value) > 48:
        raise RecoveryEvidenceError("invalid_receipt_time")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryEvidenceError("invalid_receipt_time") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise RecoveryEvidenceError("untrusted_naive_time")
    return instant.astimezone(timezone.utc)


def _identity(value):
    return type(value) is str and bool(_IDENT.fullmatch(value))


def _validate_payload(data: dict) -> None:
    if type(data) is not dict or set(data) != _RECEIPT_KEYS:
        raise RecoveryEvidenceError("receipt_schema_invalid")
    if type(data["version"]) is not int or data["version"] != 1:
        raise RecoveryEvidenceError("receipt_version_invalid")
    issuer = data["issuer"]
    if type(issuer) is not str or issuer not in _ISSUERS:
        raise RecoveryEvidenceError("receipt_issuer_invalid")
    for name in ("key_id", "receipt_id", "incident_id", "component",
                 "host", "action_id", "target", "evidence_ref"):
        if not _identity(data[name]):
            raise RecoveryEvidenceError("receipt_identity_invalid")
    if data["component"] != data["target"]:
        raise RecoveryEvidenceError("receipt_target_mismatch")
    if type(data["authorized"]) is not bool:
        raise RecoveryEvidenceError("receipt_authorization_invalid")
    operation, status, authorized = (
        data["operation"], data["status"], data["authorized"]
    )
    if issuer == "executor":
        if operation not in _OPERATIONS or status != "success" or not authorized:
            raise RecoveryEvidenceError("action_not_authorized_and_successful")
    elif operation != "observe" or status != "healthy" or authorized:
        raise RecoveryEvidenceError("invalid_probe_attestation")
    _event_timestamp(data["event_at"])


def sign_recovery_receipt(payload: dict, key: bytes) -> dict:
    """Producer-side serialization helper; requires independently held secret.

    This function is never called from the cognitive daemon or recovery store.
    Sign only independently verified facts (not text authored by LLM agents).
    """
    _validate_payload(payload)
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("recovery_signing_key_invalid")
    signed = dict(payload)
    signed["mac"] = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    return signed


class SentryRecoveryVerifier:
    """Consumer verifier of 1 action + 2 independent probe attestations."""

    def __init__(
        self, trust_roots: Mapping, *, trusted_host: str,
        clock=None, max_age=_DEFAULT_WINDOW,
    ):
        if not _identity(trusted_host):
            raise ValueError("trusted_host_invalid")
        if not isinstance(trust_roots, Mapping) or set(trust_roots) != set(_ISSUERS):
            raise ValueError("recovery_trust_roles_invalid")
        roots = {}
        for issuer in _ISSUERS:
            keys = trust_roots[issuer]
            if not isinstance(keys, Mapping) or not 1 <= len(keys) <= 3:
                raise ValueError("recovery_trust_keyring_invalid")
            trusted = {}
            for key_id, secret in keys.items():
                if not _identity(key_id) or type(secret) is not bytes or len(secret) < 32:
                    raise ValueError("recovery_trust_key_invalid")
                trusted[key_id] = secret
            roots[issuer] = trusted
        # Separately provisioned principals must never share a signing secret.
        if set(roots["executor"].values()) & set(roots["health_probe"].values()):
            raise ValueError("shared_producer_secret_forbidden")
        if not isinstance(max_age, timedelta) or not timedelta(seconds=1) <= max_age <= timedelta(days=7):
            raise ValueError("recovery_max_age_invalid")
        if clock is None:
            clock = lambda: datetime.now(timezone.utc)
        if not callable(clock):
            raise TypeError("recovery_clock_invalid")
        self._roots = roots
        self._trusted_host = trusted_host
        self._clock = clock
        self._max_age = max_age

    def _check_signature(self, signed: dict) -> dict:
        if type(signed) is not dict or set(signed) != _SIGNED_KEYS:
            raise RecoveryEvidenceError("receipt_schema_invalid")
        try:
            if len(_canonical(signed)) > 2048:
                raise RecoveryEvidenceError("receipt_too_large")
        except (ValueError, TypeError, OverflowError) as exc:
            raise RecoveryEvidenceError("receipt_serialization_invalid") from exc
        payload = {k: signed[k] for k in _RECEIPT_KEYS}
        _validate_payload(payload)
        signature = signed["mac"]
        if type(signature) is not str or not _MAC.fullmatch(signature):
            raise RecoveryEvidenceError("receipt_mac_invalid")
        secret = self._roots[payload["issuer"]].get(payload["key_id"])
        if secret is None:
            raise RecoveryEvidenceError("receipt_key_unknown")
        expected = hmac.new(secret, _canonical(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise RecoveryEvidenceError("receipt_authentication_failed")
        return payload

    def verify(self, incident: dict, receipts: Sequence[dict]) -> tuple[str, ...]:
        if not isinstance(incident, dict) or not (
            incident.get("state") == "recovered"
            and type(incident.get("healthy_streak")) is int
            and incident["healthy_streak"] >= 2
            and _identity(incident.get("incident_id"))
            and _identity(incident.get("component"))
        ):
            raise RecoveryEvidenceError("recovery_not_confirmed")
        if not isinstance(receipts, (tuple, list)) or len(receipts) != 3:
            raise RecoveryEvidenceError("three_signed_receipts_required")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RecoveryEvidenceError("invalid_verifier_clock")
        now = now.astimezone(timezone.utc)
        opened = _event_timestamp(incident.get("opened_at"))
        recovered = _event_timestamp(incident.get("resolved_at"))
        if recovered < opened or recovered > now:
            raise RecoveryEvidenceError("untrusted_recovery_interval")
        parsed = []
        for signed in receipts:
            item = self._check_signature(signed)
            if item["incident_id"] != incident["incident_id"] or (
                item["component"] != incident["component"]
            ):
                raise RecoveryEvidenceError("receipt_incident_mismatch")
            parsed.append(item)
        if tuple(x["issuer"] for x in parsed) != (
            "executor", "health_probe", "health_probe"
        ):
            raise RecoveryEvidenceError("independent_evidence_missing")
        if len({item["receipt_id"] for item in parsed}) != 3:
            raise RecoveryEvidenceError("duplicate_receipt_id")
        if len({item["action_id"] for item in parsed}) != 1:
            raise RecoveryEvidenceError("action_correlation_mismatch")
        recorded = incident.get("recovery_evidence_refs")
        if not isinstance(recorded, (tuple, list)) or len(recorded) < 2:
            raise RecoveryEvidenceError("independent_probe_evidence_missing")
        probe_refs = (parsed[1]["evidence_ref"], parsed[2]["evidence_ref"])
        if len(set(probe_refs)) != 2 or not all(ref in recorded for ref in probe_refs):
            raise RecoveryEvidenceError("probe_evidence_mismatch")
        if {item["host"] for item in parsed} != {self._trusted_host}:
            raise RecoveryEvidenceError("host_correlation_mismatch")
        if incident["component"].startswith("inference."):
            # There is no appropriate service restart evidence for LLM model
            # inference failures. These require a separate probe policy.
            raise RecoveryEvidenceError("inference_requires_separate_evidence_policy")
        times = [_event_timestamp(item["event_at"]) for item in parsed]
        if not (
            opened <= times[0] < times[1] < times[2] <= recovered <= now
        ):
            raise RecoveryEvidenceError("invalid_recovery_evidence_order")
        if now - times[2] > self._max_age:
            raise RecoveryEvidenceError("expired_recovery_evidence")
        if times[2] - times[0] > self._max_age:
            raise RecoveryEvidenceError("recovery_window_exceeded")
        return tuple("receipt:" + item["receipt_id"] for item in parsed)


def learn_from_authenticated_recovery(
    memory: FailureMemory, *, incident_id: str, cause: str,
    correction: str, receipts: Sequence[dict],
    verifier: SentryRecoveryVerifier,
    at: str | None = None,
) -> dict:
    """One guarded entrance into existing Sentry lesson persistence.

    Without the verifier, authenticated receipts, two matching post-action
    probes and recovered incident, no lesson is persisted.
    """
    if not isinstance(memory, FailureMemory):
        raise TypeError("failure_memory_required")
    if not isinstance(verifier, SentryRecoveryVerifier):
        raise RecoveryEvidenceError("independent_verifier_required")
    incident = memory.get_incident(incident_id)
    if incident is None:
        raise RecoveryEvidenceError("incident_not_found")
    try:
        refs = verifier.verify(incident, receipts)
    except RecoveryEvidenceError:
        raise
    except Exception as exc:
        raise RecoveryEvidenceError("independent_verification_unavailable") from exc

    def independent_review(reloaded: dict, passed_refs: tuple[str, ...]) -> bool:
        # Revalidate the exact evidence against the *current* persisted incident
        # after record_verified_lesson() reloads it.
        return passed_refs == verifier.verify(reloaded, receipts)

    try:
        return memory.record_verified_lesson(
            incident_id=incident_id, cause=cause, correction=correction,
            verification_refs=refs, verifier=independent_review, at=at,
        )
    except RecoveryEvidenceError:
        raise
    except FailureMemoryError:
        raise
    except Exception as exc:
        raise RecoveryEvidenceError("authenticated_recovery_commit_failed") from exc
