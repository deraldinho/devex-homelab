from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .cognitive_observation_projection import load_cognitive_observation_snapshot
from .emocao_derivada import EmocaoDerivada
from .modelo_afetivo import EstadoAfetivo
from .modelo_foco import AssuntoFoco, FocoAtencao
from .modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from .modelo_percepcao import EstadoObservacao, EstadoPercepcao
from .state_model import GlobalAssessment, TechnicalState
from .stimulus_model import Stimulus, StimulusSeverity


class CognitiveContextUnavailable(RuntimeError):
    pass


def _aware_utc(value: str) -> datetime:
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return instant.astimezone(timezone.utc)


def _assunto(item: dict | None) -> AssuntoFoco | None:
    if item is None:
        return None
    return AssuntoFoco(
        assunto_id=item["assunto_id"],
        entidade_id=item["entidade_id"],
        gravidade=item["gravidade"],
        impacto_afetivo=item["impacto_afetivo"],
        importancia=item["importancia"],
        novidade=item["novidade"],
        urgencia=item["urgencia"],
        recencia=item["recencia"],
        critico=item.get("critico", False),
        recuperado=item.get("recuperado", False),
    )


def _percepcao(item: dict) -> EstadoPercepcao:
    return EstadoPercepcao(
        item["entidade_id"], EstadoObservacao(item["estado"]), item["confianca"],
        item.get("ultima_observacao_valida"), tuple(item.get("fontes_disponiveis", ())),
        tuple(item.get("fontes_indisponiveis", ())), bool(item.get("conflito_evidencias", False)),
        item["atualizado_em"],
    )


def _incidente(item: dict | None) -> IncidenteTecnico | None:
    if item is None:
        return None
    return IncidenteTecnico(
        incidente_id=item["incidente_id"], entidade_principal=item["entidade_principal"],
        tipo=item["tipo"], gravidade=item["gravidade"], inicio_em=item["inicio_em"],
        causa_provavel=item["causa_provavel"], confianca_causal=item["confianca_causal"],
        entidades_afetadas=tuple(item.get("entidades_afetadas", ())),
        total_entidades_afetadas=item["total_entidades_afetadas"],
        eventos_correlacionados=tuple(item.get("eventos_correlacionados", ())),
        estado_recuperacao=EstadoRecuperacaoIncidente(item["estado_recuperacao"]),
        recuperado_em=item.get("recuperado_em"),
    )


def _estado_afetivo(item: dict) -> EstadoAfetivo:
    return EstadoAfetivo(
        item["valencia"], item["ativacao"], item["estresse"], item["confianca"],
        item["engajamento"], item["curiosidade"], item["atualizado_em"],
        item.get("foco_atencao"),
    )


def _foco(item: dict) -> FocoAtencao:
    return FocoAtencao(
        principal=_assunto(item.get("principal")),
        secundarios=tuple(_assunto(x) for x in item.get("secundarios", ())),
        atualizado_em=item["atualizado_em"],
        capacidade_secundarios=item["capacidade_secundarios"],
    )


def _stimulus(item: dict) -> Stimulus:
    return Stimulus(
        stimulus_id=item["stimulus_id"], source=item["source"], kind=item["kind"],
        severity=StimulusSeverity(item["severity"]), timestamp=item["timestamp"],
        payload={}, novelty=item["novelty"], correlation_id=item["correlation_id"],
    )


class HumanContextProvider:
    def __init__(self, health_path: Path, observation_snapshot_path: Path,
                 *, max_snapshot_age_s: float, expected_sha: str | None = None,
                 now=lambda: datetime.now(timezone.utc)):
        if float(max_snapshot_age_s) <= 0:
            raise ValueError("max_snapshot_age_s must be > 0")
        self._health_path = Path(health_path)
        self._snapshot_path = Path(observation_snapshot_path)
        self._max_snapshot_age_s = float(max_snapshot_age_s)
        self._expected_sha = expected_sha
        self._now = now

    def _assessment(self) -> GlobalAssessment:
        status = "unknown"
        try:
            payload = json.loads(self._health_path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "unknown")).lower()
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        if status == "healthy":
            return GlobalAssessment(None, TechnicalState.HEALTHY, 0, ())
        return GlobalAssessment(None, TechnicalState.DEGRADED, 2, ("health:unknown",))

    def _snapshot(self):
        try:
            snapshot = load_cognitive_observation_snapshot(self._snapshot_path)
            generated = _aware_utc(snapshot.generated_at)
            now = self._now().astimezone(timezone.utc)
            age_s = (now - generated).total_seconds()
            if age_s < 0 or age_s > self._max_snapshot_age_s:
                raise CognitiveContextUnavailable("observation context stale")
            if self._expected_sha is not None and snapshot.expected_sha != self._expected_sha:
                raise CognitiveContextUnavailable("observation context sha mismatch")
            return snapshot
        except CognitiveContextUnavailable:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CognitiveContextUnavailable("observation context unavailable") from exc

    def __call__(self) -> dict:
        snapshot = self._snapshot()
        emotion = snapshot.emotion
        return {
            "assessment": self._assessment(),
            "percepcao": _percepcao(dict(snapshot.perception)),
            "incidente": _incidente(dict(snapshot.incident) if snapshot.incident is not None else None),
            "estado_afetivo": _estado_afetivo(dict(snapshot.affective_state)),
            "emocao": EmocaoDerivada(emotion["principal"], tuple(emotion.get("nuances", ()))),
            "foco": _foco(dict(snapshot.focus)),
            "expectativa": None,
            "mudancas_recentes": [_stimulus(dict(item)) for item in snapshot.recent_changes],
            "dependencias_afetadas": tuple(snapshot.affected_dependencies),
        }
