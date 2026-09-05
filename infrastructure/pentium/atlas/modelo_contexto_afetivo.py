from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum


class TipoEntidadeAfetiva(str, Enum):
    CEREBRO = "cerebro"
    MEMBRO = "membro"
    ORGAO_VITAL = "orgao_vital"
    DEPENDENCIA_EXTERNA = "dependencia_externa"
    RECURSO_EXTERNO = "recurso_externo"
    PROJETO = "projeto"
    SERVICO = "servico"


def _texto_obrigatorio(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()


def _finito(valor: float, nome: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{nome} deve ser finito")
    return numero

def _limitar_01(valor: float, nome: str) -> float:
    return max(0.0, min(1.0, _finito(valor, nome)))


def _delta_experiencial(valor: float, nome: str) -> float:
    numero = _finito(valor, nome)
    if not -1.0 <= numero <= 1.0:
        raise ValueError(f"{nome} deve estar entre -1.0 e 1.0")
    return numero


@dataclass(frozen=True)
class EntidadeAfetiva:
    entidade_id: str
    nome: str
    tipo: TipoEntidadeAfetiva
    incorporada: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        object.__setattr__(self, "nome", _texto_obrigatorio(self.nome, "nome"))
        if not isinstance(self.tipo, TipoEntidadeAfetiva):
            object.__setattr__(self, "tipo", TipoEntidadeAfetiva(self.tipo))
        if not isinstance(self.incorporada, bool):
            raise ValueError("incorporada deve ser booleana")

    def incorporar(self) -> "EntidadeAfetiva":
        if self.tipo is not TipoEntidadeAfetiva.MEMBRO:
            raise ValueError("somente entidades MEMBRO possuem incorporacao explicita")
        return replace(self, incorporada=True)

@dataclass(frozen=True)
class VinculoAfetivo:
    entidade_id: str
    importancia: float
    proximidade: float
    responsabilidade: float
    dependencia_operacional: float
    familiaridade: float
    confianca_operacional: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        for nome in (
            "importancia", "proximidade", "responsabilidade",
            "dependencia_operacional", "familiaridade", "confianca_operacional",
        ):
            object.__setattr__(self, nome, _limitar_01(getattr(self, nome), nome))

    def evoluir_experiencia(
        self,
        delta_familiaridade: float,
        delta_confianca_operacional: float,
    ) -> "VinculoAfetivo":
        df = _delta_experiencial(delta_familiaridade, "delta_familiaridade")
        dc = _delta_experiencial(delta_confianca_operacional, "delta_confianca_operacional")
        return replace(
            self,
            familiaridade=_limitar_01(self.familiaridade + df, "familiaridade"),
            confianca_operacional=_limitar_01(self.confianca_operacional + dc, "confianca_operacional"),
        )


def _normalizar_instante_utc(valor: str, nome: str) -> str:
    texto = _texto_obrigatorio(valor, nome)
    instante = datetime.fromisoformat(texto)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError(f"{nome} deve possuir timezone")
    return instante.astimezone(timezone.utc).isoformat()


def _instante(valor: str, nome: str) -> datetime:
    return datetime.fromisoformat(_normalizar_instante_utc(valor, nome))


class TipoExpectativa(str, Enum):
    MANUTENCAO_PLANEJADA = "manutencao_planejada"
    RETORNO_ESPERADO = "retorno_esperado"


class EstadoExpectativa(str, Enum):
    EM_CURSO = "em_curso"
    ATRASADA = "atrasada"
    CUMPRIDA = "cumprida"
    CANCELADA = "cancelada"


class TipoExperienciaOperacional(str, Enum):
    INCIDENTE = "incidente"
    RECUPERACAO = "recuperacao"
    INTERACAO_SUCESSO = "interacao_sucesso"


@dataclass(frozen=True)
class Expectativa:
    expectativa_id: str
    entidade_id: str
    tipo: TipoExpectativa
    criada_em: str
    inicio_previsto_em: str
    limite_em: str
    encerrada_com: EstadoExpectativa | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "expectativa_id", _texto_obrigatorio(self.expectativa_id, "expectativa_id"))
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        if not isinstance(self.tipo, TipoExpectativa):
            object.__setattr__(self, "tipo", TipoExpectativa(self.tipo))
        for nome in ("criada_em", "inicio_previsto_em", "limite_em"):
            object.__setattr__(self, nome, _normalizar_instante_utc(getattr(self, nome), nome))
        if _instante(self.inicio_previsto_em, "inicio_previsto_em") > _instante(self.limite_em, "limite_em"):
            raise ValueError("inicio_previsto_em nao pode ser posterior a limite_em")
        if self.encerrada_com not in (None, EstadoExpectativa.CUMPRIDA, EstadoExpectativa.CANCELADA):
            raise ValueError("encerrada_com deve ser CUMPRIDA, CANCELADA ou None")

    def estado_em(self, agora: str) -> EstadoExpectativa:
        if self.encerrada_com is not None:
            return self.encerrada_com
        return EstadoExpectativa.ATRASADA if _instante(agora, "agora") > _instante(self.limite_em, "limite_em") else EstadoExpectativa.EM_CURSO

    def concluir(self) -> "Expectativa":
        return replace(self, encerrada_com=EstadoExpectativa.CUMPRIDA)

    def cancelar(self) -> "Expectativa":
        return replace(self, encerrada_com=EstadoExpectativa.CANCELADA)


@dataclass(frozen=True)
class ExperienciaOperacional:
    experiencia_id: str
    entidade_id: str
    tipo: TipoExperienciaOperacional
    ocorrido_em: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "experiencia_id", _texto_obrigatorio(self.experiencia_id, "experiencia_id"))
        object.__setattr__(self, "entidade_id", _texto_obrigatorio(self.entidade_id, "entidade_id"))
        if not isinstance(self.tipo, TipoExperienciaOperacional):
            object.__setattr__(self, "tipo", TipoExperienciaOperacional(self.tipo))
        object.__setattr__(self, "ocorrido_em", _normalizar_instante_utc(self.ocorrido_em, "ocorrido_em"))
