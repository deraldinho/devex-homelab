"""Detector determinístico de Drift entre Desired State e Observed State no DevEx HomeLab."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Sequence

from infrastructure.observability.drift_model import (
    DesiredComponent,
    ObservedComponent,
    DriftFinding,
    DriftReport,
    DriftSeverity,
)


class DriftDetector:
    """Compara o estado desejado versionado no Git com o estado real observado nos nós."""

    def evaluate(
        self,
        desired: Sequence[DesiredComponent],
        observed: Sequence[ObservedComponent],
        *,
        now: datetime | None = None,
    ) -> DriftReport:
        current_time = now or datetime.now(timezone.utc)
        observed_map = {(c.node, c.name): c for c in observed}
        findings: list[DriftFinding] = []

        for item in desired:
            key = (item.target_node, item.name)
            observed_item = observed_map.get(key)

            # 1. Componente ausente no host
            if not observed_item:
                findings.append(
                    DriftFinding(
                        component_name=item.name,
                        node=item.target_node,
                        severity=DriftSeverity.CRITICAL,
                        reason="Componente desejado ausente no estado observado",
                        expected=item.expected_state,
                        observed="missing",
                    )
                )
                continue

            # 2. Divergência de estado de execução (ex: running vs stopped/failed)
            if observed_item.observed_state.lower() != item.expected_state.lower():
                findings.append(
                    DriftFinding(
                        component_name=item.name,
                        node=item.target_node,
                        severity=DriftSeverity.CRITICAL,
                        reason="Estado de execução divergente do versionado",
                        expected=item.expected_state,
                        observed=observed_item.observed_state,
                    )
                )

            # 3. Divergência de versão/tag de imagem
            if item.expected_image and observed_item.observed_image:
                if item.expected_image != observed_item.observed_image:
                    findings.append(
                        DriftFinding(
                            component_name=item.name,
                            node=item.target_node,
                            severity=DriftSeverity.WARNING,
                            reason="Versão da imagem divergente da tag desejada",
                            expected=item.expected_image,
                            observed=observed_item.observed_image,
                        )
                    )

        # Calcular severidade geral
        has_critical = any(f.severity == DriftSeverity.CRITICAL for f in findings)
        has_warning = any(f.severity == DriftSeverity.WARNING for f in findings)

        if has_critical:
            overall = DriftSeverity.CRITICAL
        elif has_warning:
            overall = DriftSeverity.WARNING
        else:
            overall = DriftSeverity.CLEAN

        return DriftReport(
            timestamp=current_time.isoformat(),
            overall_status=overall,
            findings=findings,
            scanned_components=len(desired),
        )
