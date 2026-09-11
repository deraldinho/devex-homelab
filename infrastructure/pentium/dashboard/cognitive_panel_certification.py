from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class Evidence:
    expected_sha: str
    observed_sha: str
    cognitive_expected_sha: str
    dashboard_service_state: str
    observation_service_state: str
    voice_service_state: str
    voice_service_enabled: str
    status: Mapping[str, object]
    write_methods: Mapping[str, int]

@dataclass(frozen=True)
class Result:
    physical_pass: bool
    failures: tuple[str, ...]
    marker: str | None


def certify(evidence: Evidence) -> Result:
    failures=[]
    if evidence.observed_sha != evidence.expected_sha: failures.append('sha_mismatch')
    if evidence.dashboard_service_state != 'active': failures.append('dashboard_not_active')
    if evidence.observation_service_state != 'active': failures.append('observation_not_active')
    if evidence.voice_service_state != 'inactive' or evidence.voice_service_enabled != 'disabled': failures.append('voice_not_paused')
    cognition=evidence.status.get('cognition') if isinstance(evidence.status, Mapping) else None
    if not isinstance(cognition, Mapping) or cognition.get('status') != 'available': failures.append('cognition_not_available')
    else:
        if cognition.get('observed_sha') != evidence.cognitive_expected_sha: failures.append('cognition_sha_mismatch')
        if cognition.get('entity_id') != 'x99': failures.append('cognition_entity_mismatch')
    if any(code != 405 for code in evidence.write_methods.values()): failures.append('write_method_accepted')
    passed=not failures
    return Result(passed,tuple(failures),'ATLAS_DASHBOARD_COGNITIVE_PANEL_PHYSICAL_PASS' if passed else None)
