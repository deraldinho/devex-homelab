from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HermesConfig:
    schema_version: int
    provider: str | None
    profile: str
    binary: str
    timeout_s: float
    max_context_tokens: int
    max_response_bytes: int

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version deve ser 1")
        if self.provider is not None and (not isinstance(self.provider, str) or not self.provider.strip()):
            raise ValueError("provider deve ser string nao vazia quando informado")
        for name in ("profile", "binary"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} nao pode ser vazio")
        if float(self.timeout_s) <= 0:
            raise ValueError("timeout_s deve ser > 0")
        for name in ("max_context_tokens", "max_response_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} deve ser inteiro > 0")


def load_hermes_config(path: Path) -> HermesConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"schema_version", "profile", "binary", "timeout_s", "max_context_tokens", "max_response_bytes"}
    allowed = required | {"provider"}
    if not required.issubset(payload) or not set(payload).issubset(allowed):
        raise ValueError("campos de configuracao Hermes invalidos")
    return HermesConfig(
        schema_version=payload["schema_version"],
        provider=payload.get("provider"),
        profile=payload["profile"],
        binary=payload["binary"],
        timeout_s=payload["timeout_s"],
        max_context_tokens=payload["max_context_tokens"],
        max_response_bytes=payload["max_response_bytes"],
    )
