from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PoliticaContextoCognitivo:
    max_string_chars: int
    max_mudancas_recentes: int
    max_dependencias_afetadas: int
    max_nuances: int
    max_payload_bytes: int

    def __post_init__(self) -> None:
        for nome in (
            "max_string_chars", "max_mudancas_recentes", "max_dependencias_afetadas",
            "max_nuances", "max_payload_bytes",
        ):
            valor = getattr(self, nome)
            if not isinstance(valor, int) or valor <= 0:
                raise ValueError(f"{nome} deve ser inteiro > 0")


@dataclass(frozen=True)
class PoliticaAtivacaoCognitiva:
    novidade_minima: float
    delta_afetivo_minimo: float
    cooldown_s: float
    janela_orcamento_s: float
    max_ativacoes_autonomas_janela: int

    def __post_init__(self) -> None:
        for nome in ("novidade_minima", "delta_afetivo_minimo"):
            valor = float(getattr(self, nome))
            if not 0.0 <= valor <= 1.0:
                raise ValueError(f"{nome} deve estar entre 0.0 e 1.0")
        if self.cooldown_s <= 0 or self.janela_orcamento_s <= 0:
            raise ValueError("cooldown_s e janela_orcamento_s devem ser > 0")
        if not isinstance(self.max_ativacoes_autonomas_janela, int) or self.max_ativacoes_autonomas_janela <= 0:
            raise ValueError("max_ativacoes_autonomas_janela deve ser inteiro > 0")

@dataclass(frozen=True)
class ConfiguracaoCognitiva:
    schema_version: int
    contexto: PoliticaContextoCognitivo
    ativacao: PoliticaAtivacaoCognitiva


def carregar_configuracao_cognitiva(path: str | Path) -> ConfiguracaoCognitiva:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version cognitivo deve ser 1")
    contexto = payload.get("contexto")
    ativacao = payload.get("ativacao")
    if not isinstance(contexto, dict) or not isinstance(ativacao, dict):
        raise ValueError("contexto e ativacao sao obrigatorios")
    return ConfiguracaoCognitiva(
        schema_version=1,
        contexto=PoliticaContextoCognitivo(**contexto),
        ativacao=PoliticaAtivacaoCognitiva(**ativacao),
    )
