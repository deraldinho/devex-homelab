from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CognitiveContextBridgePhysicalEvidence:
    expected_sha: str
    observed_sha: str
    observation_service_state: str
    voice_service_state: str
    voice_service_enabled: str
    health: Mapping[str, object]
    snapshot: Mapping[str, object]
    snapshot_age_ok: bool
    state_matches: bool
    cli_real_context_ok: bool
    fail_safe_ok: bool
    restart_projection_ok: bool
    voice_expected_active: bool = False


@dataclass(frozen=True)
class CognitiveContextBridgeCertificationResult:
    physical_pass: bool
    failures: tuple[str, ...]
    marker: str | None


def certify_cognitive_context_bridge(
    evidence: CognitiveContextBridgePhysicalEvidence,
) -> CognitiveContextBridgeCertificationResult:
    failures: list[str] = []
    if evidence.observed_sha != evidence.expected_sha:
        failures.append("sha_mismatch")
    if evidence.observation_service_state != "active":
        failures.append("observation_service_not_active")
    if evidence.voice_expected_active:
        if evidence.voice_service_state != "active":
            failures.append("voice_service_not_active")
        if evidence.voice_service_enabled != "enabled":
            failures.append("voice_service_not_enabled")
    else:
        if evidence.voice_service_state != "inactive":
            failures.append("voice_service_not_inactive")
        if evidence.voice_service_enabled != "disabled":
            failures.append("voice_service_not_disabled")

    health = dict(evidence.health)
    if health.get("schema_version") != 1:
        failures.append("health_schema_invalid")
    if health.get("status") != "healthy":
        failures.append("health_not_healthy")
    if health.get("expected_sha") != evidence.expected_sha:
        failures.append("health_sha_mismatch")
    bridge = health.get("cognitive_bridge")
    if not isinstance(bridge, Mapping):
        failures.append("bridge_health_invalid")
        bridge = {}
    if bridge.get("current_error") is not None:
        failures.append("bridge_error_present")

    snapshot = dict(evidence.snapshot)
    if snapshot.get("schema_version") != 1:
        failures.append("snapshot_schema_invalid")
    if snapshot.get("expected_sha") != evidence.expected_sha:
        failures.append("snapshot_sha_mismatch")
    if snapshot.get("source_stimulus_id") != bridge.get("last_publish_stimulus_id"):
        failures.append("snapshot_stimulus_mismatch")
    perception = snapshot.get("perception")
    perception_entity = perception.get("entidade_id") if isinstance(perception, Mapping) else None
    if snapshot.get("entity_id") != perception_entity:
        failures.append("snapshot_entity_mismatch")
    if "technical_state" in snapshot:
        failures.append("snapshot_contains_technical_state")
    if not evidence.snapshot_age_ok:
        failures.append("snapshot_stale")
    if not evidence.state_matches:
        failures.append("state_mismatch")
    if not evidence.cli_real_context_ok:
        failures.append("cli_real_context_not_proven")
    if not evidence.fail_safe_ok:
        failures.append("fail_safe_not_proven")
    if not evidence.restart_projection_ok:
        failures.append("restart_projection_not_proven")

    passed = not failures
    return CognitiveContextBridgeCertificationResult(
        physical_pass=passed,
        failures=tuple(failures),
        marker="ATLAS_COGNITIVE_CONTEXT_BRIDGE_PHYSICAL_PASS" if passed else None,
    )
