from __future__ import annotations

from dataclasses import dataclass

from .modelo_afetivo import EstadoAfetivo


ROTULOS_EMOCAO = (
    "calmo", "atento", "interessado", "curioso", "preocupado",
    "estressado", "alarmado", "frustrado", "aliviado",
    "satisfeito", "confiante", "vigilante",
)


@dataclass(frozen=True)
class ContextoEmocional:
    reincidencia: float = 0.0
    criticidade_relevante: bool = False
    recuperacao_relevante: bool = False
    percepcao_insegura: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "reincidencia", max(0.0, min(1.0, float(self.reincidencia))))


@dataclass(frozen=True)
class EmocaoDerivada:
    principal: str
    nuances: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.principal not in ROTULOS_EMOCAO:
            raise ValueError("rotulo emocional principal invalido")
        if any(item not in ROTULOS_EMOCAO or item == self.principal for item in self.nuances):
            raise ValueError("nuance emocional invalida")


def _scores(estado: EstadoAfetivo, contexto: ContextoEmocional) -> dict[str, float]:
    positivo = max(0.0, estado.valencia)
    negativo = max(0.0, -estado.valencia)
    scores = {
        "calmo": (1.0 - estado.estresse) * (1.0 - estado.ativacao),
        "atento": estado.ativacao * (1.0 - estado.estresse),
        "interessado": estado.engajamento * (0.5 + 0.5 * positivo),
        "curioso": estado.curiosidade * (1.0 - 0.5 * estado.estresse),
        "preocupado": estado.estresse * (0.5 + 0.5 * negativo),
        "estressado": estado.estresse * estado.ativacao,
        "satisfeito": positivo * estado.engajamento,
        "confiante": estado.confianca * (1.0 - estado.estresse),
        "vigilante": estado.ativacao * (1.0 - estado.confianca),
    }
    scores["alarmado"] = (
        estado.estresse * estado.ativacao * 1.5
        if contexto.criticidade_relevante else 0.0
    )
    scores["frustrado"] = (
        estado.estresse * (1.0 - estado.confianca) * contexto.reincidencia * 1.6
        if contexto.reincidencia > 0.0 else 0.0
    )
    scores["aliviado"] = (
        (1.0 - estado.estresse + positivo) * 0.9
        if contexto.recuperacao_relevante else 0.0
    )
    if contexto.percepcao_insegura:
        scores["vigilante"] *= 1.25
    return scores


def derivar_emocao(
    estado: EstadoAfetivo,
    contexto: ContextoEmocional,
    *,
    capacidade_nuances: int = 2,
) -> EmocaoDerivada:
    if not isinstance(capacidade_nuances, int) or capacidade_nuances < 0:
        raise ValueError("capacidade_nuances deve ser inteiro >= 0")
    scores = _scores(estado, contexto)
    ordenados = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    principal = ordenados[0][0]
    nuances = tuple(
        rotulo for rotulo, score in ordenados[1:]
        if score > 0.0
    )[:capacidade_nuances]
    return EmocaoDerivada(principal, nuances)
