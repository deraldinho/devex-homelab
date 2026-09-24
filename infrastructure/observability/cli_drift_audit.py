#!/usr/bin/env python3
"""CLI de Auditoria de Drift — DevEx HomeLab

Conecta aos nós físicos (Core e Pentium) via SSH / Tailscale,
coleta o estado observado e compara contra o estado desejado versionado.
"""

from __future__ import annotations

import subprocess
import sys
from infrastructure.observability.drift_detector import DriftDetector
from infrastructure.observability.drift_model import (
    DesiredComponent,
    ObservedComponent,
    DriftReport,
    DriftSeverity,
)


def get_desired_state() -> list[DesiredComponent]:
    return [
        # Core Runners
        DesiredComponent(
            name="core-homelab-01",
            target_node="core",
            component_type="container",
            expected_state="running",
            expected_image="devex/core-homelab-runner:2.337.0",
        ),
        DesiredComponent(
            name="core-l2jtoren-01",
            target_node="core",
            component_type="container",
            expected_state="running",
            expected_image="devex/core-l2jtoren-runner:2.337.0",
        ),
        DesiredComponent(
            name="core-l2jtoren-02",
            target_node="core",
            component_type="container",
            expected_state="running",
            expected_image="devex/core-l2jtoren-runner:2.337.0",
        ),
        # Pentium Control Plane & Atlas Services
        DesiredComponent(
            name="atlas-observation.service",
            target_node="pentium",
            component_type="systemd_unit",
            expected_state="active",
        ),
        DesiredComponent(
            name="atlas-cognitive.service",
            target_node="pentium",
            component_type="systemd_unit",
            expected_state="active",
        ),
        DesiredComponent(
            name="atlas-discord.service",
            target_node="pentium",
            component_type="systemd_unit",
            expected_state="active",
        ),
        DesiredComponent(
            name="pentium-heartbeat.timer",
            target_node="pentium",
            component_type="systemd_unit",
            expected_state="active",
        ),
    ]


def collect_core_containers() -> list[ObservedComponent]:
    observed: list[ObservedComponent] = []
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "core-auto",
        "docker ps -a --format '{{.Names}}|{{.State}}|{{.Image}}'",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        for line in res.stdout.strip().splitlines():
            line = line.strip().strip("'")
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                name, state, image = parts[0], parts[1], parts[2]
                observed.append(
                    ObservedComponent(
                        name=name,
                        node="core",
                        observed_state=state,
                        observed_image=image,
                    )
                )
    except Exception as exc:
        print(f"[WARN] Falha ao coletar estado do nó core: {exc}", file=sys.stderr)
    return observed


def collect_pentium_services() -> list[ObservedComponent]:
    observed: list[ObservedComponent] = []
    units = [
        "atlas-observation.service",
        "atlas-cognitive.service",
        "atlas-discord.service",
        "pentium-heartbeat.timer",
    ]
    check_cmd = " ".join(f"systemctl --user is-active {u} 2>/dev/null || echo inactive;" for u in units)
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "deraldinho@100.107.230.78",
        f"bash -c '{check_cmd}'",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        states = [s.strip() for s in res.stdout.strip().splitlines() if s.strip()]
        for unit, state in zip(units, states):
            observed.append(
                ObservedComponent(
                    name=unit,
                    node="pentium",
                    observed_state=state,
                )
            )
    except Exception as exc:
        print(f"[WARN] Falha ao coletar estado do nó pentium: {exc}", file=sys.stderr)
    return observed


def run_audit() -> DriftReport:
    desired = get_desired_state()
    observed = collect_core_containers() + collect_pentium_services()

    detector = DriftDetector()
    report = detector.evaluate(desired, observed)
    return report


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("================================================================")
    print("[AUDIT] DevEx HomeLab - Auditoria Determinística de Drift")
    print("================================================================")
    report = run_audit()

    print(f"Timestamp: {report.timestamp}")
    print(f"Status Global: {report.overall_status.value.upper()}")
    print(f"Total de Componentes Auditados: {report.scanned_components}")
    print(f"Divergencias Encontradas: {len(report.findings)}")
    print("----------------------------------------------------------------")

    if not report.findings:
        print("[OK] CLEAN - Nenhum drift detectado. Todos os servicos e runners")
        print("     estao em perfeita consonancia com o repositorio Git!")
    else:
        for finding in report.findings:
            prefix = "[CRITICAL]" if finding.severity == DriftSeverity.CRITICAL else "[WARNING]"
            print(f"{prefix} {finding.node} -> {finding.component_name}")
            print(f"   Motivo: {finding.reason}")
            print(f"   Esperado: {finding.expected} | Observado: {finding.observed}")
            print()

    print("================================================================")
    if report.overall_status == DriftSeverity.CRITICAL:
        sys.exit(2)
    elif report.overall_status == DriftSeverity.WARNING:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
