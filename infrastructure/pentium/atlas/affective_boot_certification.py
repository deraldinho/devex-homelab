from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AffectiveBootPhysicalEvidence:
    expected_sha: str
    observed_sha: str
    observation_service_state: str
    voice_service_state: str
    voice_state_accepted: bool
    health: Mapping[str, object]
    visual: Mapping[str, object]
    ipc_ok: bool
    restart_restore_ok: bool
    real_observation_ok: bool


@dataclass(frozen=True)
class AffectiveBootCertificationResult:
    physical_pass: bool
    failures: tuple[str, ...]
    marker: str | None


def certify_affective_boot(evidence: AffectiveBootPhysicalEvidence) -> AffectiveBootCertificationResult:
    failures: list[str] = []
    if evidence.observed_sha != evidence.expected_sha:
        failures.append("sha_mismatch")
    if evidence.observation_service_state != "active":
        failures.append("observation_service_not_active")
    if not evidence.voice_state_accepted:
        failures.append("voice_state_not_accepted")

    health = dict(evidence.health)
    if health.get("schema_version") != 1:
        failures.append("health_schema_invalid")
    if health.get("status") != "healthy":
        failures.append("health_not_healthy")
    if health.get("expected_sha") != evidence.expected_sha:
        failures.append("health_sha_mismatch")
    restoration = health.get("restoration")
    if not isinstance(restoration, Mapping) or set(restoration) != {"a1", "a2", "a3", "a4"}:
        failures.append("restoration_evidence_invalid")

    if evidence.visual.get("versao_avatar") != 1:
        failures.append("visual_schema_invalid")
    if not evidence.ipc_ok:
        failures.append("ipc_not_proven")
    if not evidence.restart_restore_ok:
        failures.append("restart_restore_not_proven")
    if not evidence.real_observation_ok:
        failures.append("real_observation_not_proven")

    passed = not failures
    return AffectiveBootCertificationResult(
        physical_pass=passed,
        failures=tuple(failures),
        marker="ATLAS_AFFECTIVE_BOOT_PHYSICAL_PASS" if passed else None,
    )
