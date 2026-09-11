from __future__ import annotations

from .episodic_model import EpisodeCategory, EpisodicEvidence
from .modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from .modelo_percepcao import EstadoPercepcao


def _severity_score(value: str) -> float:
    normalized = str(value).lower()
    if normalized == "critical":
        return 1.0
    if normalized in {"warning", "warn"}:
        return 0.7
    if normalized in {"notice", "info"}:
        return 0.4
    return 0.2


def evidence_from_perception(perception: EstadoPercepcao, generation_id: str) -> EpisodicEvidence:
    available = ",".join(perception.fontes_disponiveis) or "-"
    unavailable = ",".join(perception.fontes_indisponiveis) or "-"
    content = (
        f"entity={perception.entidade_id}; state={perception.estado.value}; "
        f"confidence={perception.confianca:.3f}; conflict={int(perception.conflito_evidencias)}; "
        f"sources_up={available}; sources_down={unavailable}"
    )
    event_id = f"perception:{perception.entidade_id}:{perception.atualizado_em}"
    return EpisodicEvidence(
        event_id=event_id,
        occurred_at=perception.atualizado_em,
        source="perception.pipeline",
        source_kind="perception",
        content_reduced=content,
        reliability=perception.confianca,
        verified=True,
        generation_id=generation_id,
        dedupe_key=f"perception:{perception.entidade_id}",
        importance=max(0.4, perception.confianca),
        criticality=1.0 if perception.estado.value == "inacessivel" else 0.2,
        entity_id=perception.entidade_id,
    )


def evidence_from_incident(
    incident: IncidenteTecnico,
    generation_id: str,
) -> tuple[EpisodicEvidence, EpisodeCategory, str, bool]:
    terminal = incident.estado_recuperacao is EstadoRecuperacaoIncidente.RECUPERADO
    occurred_at = incident.recuperado_em or incident.inicio_em
    content = (
        f"incident={incident.incidente_id}; entity={incident.entidade_principal}; "
        f"type={incident.tipo}; severity={incident.gravidade}; "
        f"state={incident.estado_recuperacao.value}; affected={incident.total_entidades_afetadas}; "
        f"probable_cause={incident.causa_provavel}"
    )
    key = f"incident:{incident.incidente_id}"
    event_id = f"{key}:{incident.estado_recuperacao.value}:{occurred_at}"
    evidence = EpisodicEvidence(
        event_id=event_id,
        occurred_at=occurred_at,
        source="incident.correlator",
        source_kind="incident",
        content_reduced=content,
        reliability=incident.confianca_causal,
        verified=True,
        generation_id=generation_id,
        dedupe_key=key,
        importance=max(0.5, incident.confianca_causal),
        criticality=_severity_score(incident.gravidade),
        entity_id=incident.entidade_principal,
    )
    return evidence, EpisodeCategory.INCIDENT, key, terminal
