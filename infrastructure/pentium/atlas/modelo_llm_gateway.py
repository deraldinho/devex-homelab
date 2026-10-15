from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class ErroInferencia(str, Enum):
    TIMEOUT = "timeout"
    BACKEND_INDISPONIVEL = "backend_indisponivel"
    MODELO_INDISPONIVEL = "modelo_indisponivel"
    ENTRADA_INVALIDA = "entrada_invalida"
    SAIDA_INVALIDA = "saida_invalida"
    LIMITE_EXCEDIDO = "limite_excedido"


def _texto(valor: str, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} nao pode ser vazio")
    return valor.strip()


@dataclass(frozen=True)
class SolicitacaoInferencia:
    versao_schema: int
    tarefa: str
    contexto_json: str
    max_tokens_contexto: int
    reasoning_mode: str = "off"

    def __post_init__(self) -> None:
        if self.versao_schema != 1:
            raise ValueError("versao_schema deve ser 1")
        object.__setattr__(self, "tarefa", _texto(self.tarefa, "tarefa"))
        object.__setattr__(self, "contexto_json", _texto(self.contexto_json, "contexto_json"))
        if not isinstance(self.max_tokens_contexto, int) or self.max_tokens_contexto <= 0:
            raise ValueError("max_tokens_contexto deve ser inteiro > 0")
        if self.reasoning_mode not in {"off", "auto", "on"}:
            raise ValueError("reasoning_mode invalido")


@dataclass(frozen=True)
class ResultadoInferencia:
    sucesso: bool
    texto: str | None
    erro: ErroInferencia | None
    duracao_ms: int
    backend: str
    tokens_por_s: float | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_cache_read: int | None = None
    custo_usd: float | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.sucesso, bool):
            raise ValueError("sucesso deve ser booleano")
        if self.texto is not None and not isinstance(self.texto, str):
            raise ValueError("texto deve ser string ou None")
        if self.erro is not None and not isinstance(self.erro, ErroInferencia):
            object.__setattr__(self, "erro", ErroInferencia(self.erro))
        if not isinstance(self.duracao_ms, int) or self.duracao_ms < 0:
            raise ValueError("duracao_ms deve ser inteiro >= 0")
        object.__setattr__(self, "backend", _texto(self.backend, "backend"))
        if self.tokens_por_s is not None:
            if isinstance(self.tokens_por_s, bool) or not isinstance(self.tokens_por_s, (int, float)) or float(self.tokens_por_s) < 0:
                raise ValueError("tokens_por_s deve ser numero >= 0")
            object.__setattr__(self, "tokens_por_s", float(self.tokens_por_s))
        for field in ("tokens_input","tokens_output","tokens_cache_read"):
            value=getattr(self,field)
            if value is not None and (type(value) is not int or value<0):
                raise ValueError(f"{field} must be nonnegative integer")
        if self.custo_usd is not None:
            if type(self.custo_usd) not in (int,float) or not isfinite(self.custo_usd) or self.custo_usd<0:
                raise ValueError("invalid provider cost")
        if self.sucesso and self.erro is not None:
            raise ValueError("resultado bem sucedido nao pode conter erro")
        if not self.sucesso and self.erro is None:
            raise ValueError("resultado falho deve conter erro")
