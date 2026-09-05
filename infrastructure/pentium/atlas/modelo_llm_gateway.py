from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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

    def __post_init__(self) -> None:
        if self.versao_schema != 1:
            raise ValueError("versao_schema deve ser 1")
        object.__setattr__(self, "tarefa", _texto(self.tarefa, "tarefa"))
        object.__setattr__(self, "contexto_json", _texto(self.contexto_json, "contexto_json"))
        if not isinstance(self.max_tokens_contexto, int) or self.max_tokens_contexto <= 0:
            raise ValueError("max_tokens_contexto deve ser inteiro > 0")

@dataclass(frozen=True)
class ResultadoInferencia:
    sucesso: bool
    texto: str | None
    erro: ErroInferencia | None
    duracao_ms: int
    backend: str

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
        if self.sucesso and self.erro is not None:
            raise ValueError("resultado bem sucedido nao pode conter erro")
        if not self.sucesso and self.erro is None:
            raise ValueError("resultado falho deve conter erro")
