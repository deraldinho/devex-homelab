from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


def _finito(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return numero


def _limitar(valor: float, minimo: float, maximo: float, nome: str) -> float:
    return max(minimo, min(maximo, _finito(valor, nome)))


def _validar_intervalo(valor: float, minimo: float, maximo: float, nome: str) -> float:
    numero = _finito(valor, nome)
    if not minimo <= numero <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}")
    return numero


def _normalizar_instante_utc(valor: str) -> str:
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("atualizado_em deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class EstadoAfetivo:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float
    atualizado_em: str
    foco_atencao: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _limitar(self.valencia, -1.0, 1.0, "valencia"))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _limitar(getattr(self, nome), 0.0, 1.0, nome))
        object.__setattr__(self, "atualizado_em", _normalizar_instante_utc(self.atualizado_em))


@dataclass(frozen=True)
class PersonalidadeBase:
    valencia: float
    ativacao: float
    estresse: float
    confianca: float
    engajamento: float
    curiosidade: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "valencia", _validar_intervalo(self.valencia, -1.0, 1.0, "valencia"))
        for nome in ("ativacao", "estresse", "confianca", "engajamento", "curiosidade"):
            object.__setattr__(self, nome, _validar_intervalo(getattr(self, nome), 0.0, 1.0, nome))

    def criar_estado(self, atualizado_em: str) -> EstadoAfetivo:
        return EstadoAfetivo(
            self.valencia, self.ativacao, self.estresse,
            self.confianca, self.engajamento, self.curiosidade,
            atualizado_em,
        )


@dataclass(frozen=True)
class ImpulsoAfetivo:
    motivo: str
    delta_valencia: float = 0.0
    delta_ativacao: float = 0.0
    delta_estresse: float = 0.0
    delta_confianca: float = 0.0
    delta_engajamento: float = 0.0
    delta_curiosidade: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.motivo, str) or not self.motivo.strip():
            raise ValueError("motivo não pode ser vazio")
        for nome in (
            "delta_valencia", "delta_ativacao", "delta_estresse",
            "delta_confianca", "delta_engajamento", "delta_curiosidade",
        ):
            object.__setattr__(self, nome, _validar_intervalo(getattr(self, nome), -1.0, 1.0, nome))


@dataclass(frozen=True)
class PoliticaDecaimento:
    meia_vida_valencia_s: float
    meia_vida_ativacao_s: float
    meia_vida_estresse_s: float
    meia_vida_confianca_s: float
    meia_vida_engajamento_s: float
    meia_vida_curiosidade_s: float
    atenuacao_offline_maxima_s: float

    def __post_init__(self) -> None:
        for nome in (
            "meia_vida_valencia_s", "meia_vida_ativacao_s", "meia_vida_estresse_s",
            "meia_vida_confianca_s", "meia_vida_engajamento_s", "meia_vida_curiosidade_s",
        ):
            numero = _finito(getattr(self, nome), nome)
            if numero <= 0:
                raise ValueError(f"{nome} deve ser > 0")
            object.__setattr__(self, nome, numero)
        offline = _finito(self.atenuacao_offline_maxima_s, "atenuacao_offline_maxima_s")
        if offline < 0:
            raise ValueError("atenuacao_offline_maxima_s deve ser >= 0")
        object.__setattr__(self, "atenuacao_offline_maxima_s", offline)
