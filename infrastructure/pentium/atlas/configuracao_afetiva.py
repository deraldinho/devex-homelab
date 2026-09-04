from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .modelo_afetivo import PersonalidadeBase, PoliticaDecaimento


@dataclass(frozen=True)
class ConfiguracaoAfetiva:
    personalidade: PersonalidadeBase
    decaimento: PoliticaDecaimento


def carregar_configuracao_afetiva(path: Path) -> ConfiguracaoAfetiva:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("versao_esquema") != 1:
        raise ValueError("config afetiva versao_esquema deve ser 1")
    try:
        personalidade = PersonalidadeBase(**payload["personalidade_base"])
        decaimento = PoliticaDecaimento(**payload["decaimento"])
    except KeyError as exc:
        raise ValueError(f"config afetiva sem campo obrigatório: {exc.args[0]}") from exc
    return ConfiguracaoAfetiva(personalidade, decaimento)
