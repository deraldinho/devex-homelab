from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RespostaLLMEstruturada:
    versao_schema: int
    texto: str | None
    resumo: str | None
    intencao: str | None
    parametros_intencao: dict[str, object]
    confianca: float
    motivo: str
    requer_confirmacao: bool


def _texto_opcional(valor: object, nome: str) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} invalido")
    return valor.strip()
def parse_resposta_llm(payload: str) -> RespostaLLMEstruturada:
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("saida LLM nao e JSON valido") from exc
    if not isinstance(data, dict) or data.get("versao_schema") != 1:
        raise ValueError("schema de resposta invalido")
    obrigatorios = {"versao_schema", "texto", "resumo", "intencao", "parametros_intencao", "confianca", "motivo", "requer_confirmacao"}
    if set(data) != obrigatorios:
        raise ValueError("campos de resposta invalidos")
    parametros = data["parametros_intencao"]
    if not isinstance(parametros, dict):
        raise ValueError("parametros_intencao deve ser objeto")
    intencao = _texto_opcional(data["intencao"], "intencao")
    if intencao is None and parametros:
        raise ValueError("parametros sem intencao")
    confianca = data["confianca"]
    if isinstance(confianca, bool) or not isinstance(confianca, (int, float)) or not 0.0 <= float(confianca) <= 1.0:
        raise ValueError("confianca fora do intervalo")
    if not isinstance(data["requer_confirmacao"], bool):
        raise ValueError("requer_confirmacao deve ser booleano")
    motivo = _texto_opcional(data["motivo"], "motivo")
    if motivo is None:
        raise ValueError("motivo obrigatorio")
    return RespostaLLMEstruturada(
        versao_schema=1,
        texto=_texto_opcional(data["texto"], "texto"),
        resumo=_texto_opcional(data["resumo"], "resumo"),
        intencao=intencao,
        parametros_intencao=dict(parametros),
        confianca=float(confianca),
        motivo=motivo,
        requer_confirmacao=data["requer_confirmacao"],
    )
