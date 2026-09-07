from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracaoLlm:
    schema_version: int
    backend: str
    modelo_nome: str
    modelo_path: str
    timeout_s: float
    max_tokens_contexto: int
    max_saida_bytes: int

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version deve ser 1")
        if self.backend != "llama_cpp":
            raise ValueError("backend deve ser llama_cpp")
        for nome in ("modelo_nome", "modelo_path"):
            valor = getattr(self, nome)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError(f"{nome} nao pode ser vazio")
        if float(self.timeout_s) <= 0:
            raise ValueError("timeout_s deve ser > 0")
        for nome in ("max_tokens_contexto", "max_saida_bytes"):
            valor = getattr(self, nome)
            if not isinstance(valor, int) or valor <= 0:
                raise ValueError(f"{nome} deve ser inteiro > 0")

def carregar_configuracao_llm(path: Path) -> ConfiguracaoLlm:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ConfiguracaoLlm(
        schema_version=payload["schema_version"],
        backend=payload["backend"],
        modelo_nome=payload["modelo_nome"],
        modelo_path=payload["modelo_path"],
        timeout_s=payload["timeout_s"],
        max_tokens_contexto=payload["max_tokens_contexto"],
        max_saida_bytes=payload["max_saida_bytes"],
    )
