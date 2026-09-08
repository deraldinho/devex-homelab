from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from .configuracao_cognitiva import PoliticaContextoCognitivo
from .modelo_incidente import IncidenteTecnico
from .stimulus_model import Stimulus


def _bounded_text(value: object, limit: int) -> str:
    return str(value)[:limit]


def _perception_dict(item, limit: int) -> dict[str, Any]:
    return {
        "entidade_id": _bounded_text(item.entidade_id, limit),
        "estado": item.estado.value,
        "confianca": item.confianca,
        "ultima_observacao_valida": item.ultima_observacao_valida,
        "fontes_disponiveis": [_bounded_text(x, limit) for x in item.fontes_disponiveis],
        "fontes_indisponiveis": [_bounded_text(x, limit) for x in item.fontes_indisponiveis],
        "conflito_evidencias": item.conflito_evidencias,
        "atualizado_em": item.atualizado_em,
    }

def _incident_dict(item: IncidenteTecnico, limit: int) -> dict[str, Any]:
    return {
        "incidente_id": _bounded_text(item.incidente_id, limit),
        "entidade_principal": _bounded_text(item.entidade_principal, limit),
        "tipo": _bounded_text(item.tipo, limit),
        "gravidade": _bounded_text(item.gravidade, limit),
        "inicio_em": item.inicio_em,
        "causa_provavel": _bounded_text(item.causa_provavel, limit),
        "confianca_causal": item.confianca_causal,
        "entidades_afetadas": [_bounded_text(x, limit) for x in item.entidades_afetadas],
        "total_entidades_afetadas": item.total_entidades_afetadas,
        "eventos_correlacionados": [_bounded_text(x, limit) for x in item.eventos_correlacionados],
        "estado_recuperacao": item.estado_recuperacao.value,
        "recuperado_em": item.recuperado_em,
    }


def _affective_dict(item) -> dict[str, Any]:
    return {
        "valencia": item.valencia,
        "ativacao": item.ativacao,
        "estresse": item.estresse,
        "confianca": item.confianca,
        "engajamento": item.engajamento,
        "curiosidade": item.curiosidade,
        "atualizado_em": item.atualizado_em,
        "foco_atencao": item.foco_atencao,
    }

def _focus_item_dict(item, limit: int) -> dict[str, Any]:
    return {
        "assunto_id": _bounded_text(item.assunto_id, limit),
        "entidade_id": _bounded_text(item.entidade_id, limit),
        "gravidade": item.gravidade,
        "impacto_afetivo": item.impacto_afetivo,
        "importancia": item.importancia,
        "novidade": item.novidade,
        "urgencia": item.urgencia,
        "recencia": item.recencia,
        "critico": item.critico,
        "recuperado": item.recuperado,
    }


def _focus_dict(item, limit: int) -> dict[str, Any]:
    return {
        "principal": _focus_item_dict(item.principal, limit) if item.principal else None,
        "secundarios": [_focus_item_dict(x, limit) for x in item.secundarios],
        "atualizado_em": item.atualizado_em,
        "capacidade_secundarios": item.capacidade_secundarios,
    }


def _recent_dict(item: Stimulus, limit: int) -> dict[str, Any]:
    return {
        "stimulus_id": _bounded_text(item.stimulus_id, limit),
        "source": _bounded_text(item.source, limit),
        "kind": _bounded_text(item.kind, limit),
        "severity": item.severity.value,
        "timestamp": item.timestamp,
        "novelty": item.novelty,
        "correlation_id": _bounded_text(item.correlation_id, limit),
    }

@dataclass(frozen=True)
class CognitiveObservationSnapshot:
    schema_version: int
    generated_at: str
    expected_sha: str
    source_stimulus_id: str
    entity_id: str
    perception: Mapping[str, Any]
    incident: Mapping[str, Any] | None
    affective_state: Mapping[str, Any]
    emotion: Mapping[str, Any]
    focus: Mapping[str, Any]
    recent_changes: tuple[Mapping[str, Any], ...]
    affected_dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        for name in ("generated_at", "source_stimulus_id", "entity_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.expected_sha, str):
            raise ValueError("expected_sha must be string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "expected_sha": self.expected_sha,
            "source_stimulus_id": self.source_stimulus_id,
            "entity_id": self.entity_id,
            "perception": dict(self.perception),
            "incident": dict(self.incident) if self.incident is not None else None,
            "affective_state": dict(self.affective_state),
            "emotion": dict(self.emotion),
            "focus": dict(self.focus),
            "recent_changes": [dict(x) for x in self.recent_changes],
            "affected_dependencies": list(self.affected_dependencies),
        }

    def payload_bytes(self) -> int:
        return len(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8"))

class CognitiveObservationPublisher:
    def __init__(self, path: Path, policy: PoliticaContextoCognitivo, *, expected_sha: str = ""):
        self._path = Path(path)
        self._policy = policy
        self._expected_sha = str(expected_sha)

    def _incident(self, result, incident_id: str | None):
        if incident_id is None:
            return None
        return next((item for item in result.incidentes if item.incidente_id == incident_id), None)

    def _shrink_to_bound(self, snapshot: CognitiveObservationSnapshot) -> CognitiveObservationSnapshot:
        result = snapshot
        while result.payload_bytes() > self._policy.max_payload_bytes and result.recent_changes:
            result = replace(result, recent_changes=result.recent_changes[1:])
        while result.payload_bytes() > self._policy.max_payload_bytes and result.affected_dependencies:
            result = replace(result, affected_dependencies=result.affected_dependencies[:-1])
        while result.payload_bytes() > self._policy.max_payload_bytes and result.emotion.get("nuances"):
            emotion = dict(result.emotion)
            emotion["nuances"] = list(emotion["nuances"][:-1])
            result = replace(result, emotion=emotion)
        if result.payload_bytes() > self._policy.max_payload_bytes:
            raise ValueError("cognitive observation snapshot exceeds max_payload_bytes")
        return result

    def publish(self, stimulus: Stimulus, perception_result, impact, focus_result,
                recent_changes: Sequence[Stimulus]) -> CognitiveObservationSnapshot:
        limit = self._policy.max_string_chars
        incident = self._incident(perception_result, impact.incidente_id)
        dependencies = () if incident is None else tuple(
            _bounded_text(x, limit) for x in incident.entidades_afetadas[: self._policy.max_dependencias_afetadas])
        recent = tuple(_recent_dict(x, limit) for x in tuple(recent_changes)[-self._policy.max_mudancas_recentes:])
        nuances = tuple(focus_result.emocao.nuances[: self._policy.max_nuances])
        snapshot = CognitiveObservationSnapshot(
            1, stimulus.timestamp, self._expected_sha,
            _bounded_text(stimulus.stimulus_id, limit), _bounded_text(perception_result.percepcao.entidade_id, limit),
            _perception_dict(perception_result.percepcao, limit),
            _incident_dict(incident, limit) if incident is not None else None,
            _affective_dict(focus_result.estado_afetivo),
            {"principal": _bounded_text(focus_result.emocao.principal, limit),
             "nuances": [_bounded_text(x, limit) for x in nuances]},
            _focus_dict(focus_result.foco, limit), recent, dependencies,
        )
        snapshot = self._shrink_to_bound(snapshot)
        self._write_atomic(snapshot.to_dict())
        return snapshot

    def _write_atomic(self, payload: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_name(self._path.name + ".tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self._path)
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temp.unlink(missing_ok=True)


def load_cognitive_observation_snapshot(path: Path) -> CognitiveObservationSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "schema_version", "generated_at", "expected_sha", "source_stimulus_id", "entity_id",
        "perception", "incident", "affective_state", "emotion", "focus",
        "recent_changes", "affected_dependencies",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("invalid cognitive observation snapshot fields")
    return CognitiveObservationSnapshot(
        schema_version=payload["schema_version"],
        generated_at=payload["generated_at"],
        expected_sha=payload["expected_sha"],
        source_stimulus_id=payload["source_stimulus_id"],
        entity_id=payload["entity_id"],
        perception=dict(payload["perception"]),
        incident=dict(payload["incident"]) if payload["incident"] is not None else None,
        affective_state=dict(payload["affective_state"]),
        emotion=dict(payload["emotion"]),
        focus=dict(payload["focus"]),
        recent_changes=tuple(dict(x) for x in payload["recent_changes"]),
        affected_dependencies=tuple(payload["affected_dependencies"]),
    )
