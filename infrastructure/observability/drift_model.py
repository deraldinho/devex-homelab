"""Modelos de dados para detecção de Drift entre Desired State (Git) e Observed State (Hosts)."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DriftSeverity(str, Enum):
    CLEAN = "clean"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DesiredComponent:
    name: str
    target_node: str
    component_type: str  # "container", "systemd_unit", "config"
    expected_image: str | None = None
    expected_state: str = "running"
    ports: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservedComponent:
    name: str
    node: str
    observed_state: str
    observed_image: str | None = None
    uptime: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftFinding:
    component_name: str
    node: str
    severity: DriftSeverity
    reason: str
    expected: Any
    observed: Any


@dataclass(frozen=True)
class DriftReport:
    timestamp: str
    overall_status: DriftSeverity
    findings: list[DriftFinding] = field(default_factory=list)
    scanned_components: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "scanned_components": self.scanned_components,
            "findings_count": len(self.findings),
            "findings": [
                {
                    "component": f.component_name,
                    "node": f.node,
                    "severity": f.severity.value,
                    "reason": f.reason,
                    "expected": f.expected,
                    "observed": f.observed,
                }
                for f in self.findings
            ],
        }
