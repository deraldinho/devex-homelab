#!/usr/bin/env python3
"""Technical certification harness for dual-zone observation I1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class I1CertificationResult:
    passed: bool
    wifi_observed: bool
    managed_observed: tuple[str, ...]
    control_default_deny: bool
    physical_certified: bool = False

    @property
    def marker(self) -> str | None:
        if not self.passed:
            return None
        return "ATLAS_I1_OBSERVATION_INTEGRATION_PASS"


def _valid_zone(stimulus, expected_zone: str) -> bool:
    if stimulus is None or getattr(stimulus, "kind", None) == "source_error":
        return False
    payload = getattr(stimulus, "payload", {})
    return payload.get("zone") == expected_zone


def certify_dual_zone(
    runtime,
    *,
    managed_sources: tuple[str, ...],
    control_default_deny: Callable[[], bool],
) -> I1CertificationResult:
    if not managed_sources:
        raise ValueError("managed_sources must be non-empty")

    wifi = runtime.run_once("wifi.presence")
    wifi_ok = _valid_zone(wifi, "WIFI_OBSERVED")
    managed_ok = []
    for source_name in managed_sources:
        stimulus = runtime.run_once(source_name)
        if _valid_zone(stimulus, "MANAGED"):
            managed_ok.append(source_name)

    control_ok = bool(control_default_deny())
    passed = wifi_ok and len(managed_ok) == len(managed_sources) and control_ok
    return I1CertificationResult(
        passed=passed,
        wifi_observed=wifi_ok,
        managed_observed=tuple(managed_ok),
        control_default_deny=control_ok,
        physical_certified=False,
    )
