from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .emocao_derivada import EmocaoDerivada
from .modelo_afetivo import EstadoAfetivo
from .modelo_foco import FocoAtencao
from .modelo_percepcao import EstadoObservacao, EstadoPercepcao
from .state_model import GlobalAssessment, TechnicalState


class HumanContextProvider:
    def __init__(self, health_path: Path, *, now=lambda: datetime.now(timezone.utc)):
        self._health_path = Path(health_path)
        self._now = now

    def __call__(self) -> dict:
        now = self._now().astimezone(timezone.utc).isoformat()
        status = "unknown"
        try:
            payload = json.loads(self._health_path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "unknown")).lower()
        except (OSError, json.JSONDecodeError, ValueError):
            pass

        if status == "healthy":
            assessment = GlobalAssessment(None, TechnicalState.HEALTHY, 0, ())
            perception_state = EstadoObservacao.OBSERVADO
            confidence = 1.0
            emotion = EmocaoDerivada("calmo", ())
        else:
            assessment = GlobalAssessment(None, TechnicalState.DEGRADED, 2, ("health:unknown",))
            perception_state = EstadoObservacao.DESCONHECIDO
            confidence = 0.0
            emotion = EmocaoDerivada("vigilante", ())

        percepcao = EstadoPercepcao("pentium", perception_state, confidence, now if confidence else None, ("heartbeat",) if confidence else (), () if confidence else ("heartbeat",), False, now)
        estado = EstadoAfetivo(0.0, 0.2, 0.0 if confidence else 0.3, 0.8 if confidence else 0.3, 0.5, 0.4, now, "pentium")
        foco = FocoAtencao(None, (), now, 2)
        return {"assessment": assessment, "percepcao": percepcao, "incidente": None, "estado_afetivo": estado, "emocao": emotion, "foco": foco, "expectativa": None, "mudancas_recentes": [], "dependencias_afetadas": ()}
