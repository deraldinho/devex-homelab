from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracaoLlamaServer:
    schema_version: int
    socket_path: str
    context_size: int
    cache_reuse: int
    max_response_bytes: int
    persist_kv_cache: bool

    def __post_init__(self):
        if self.schema_version != 1:
            raise ValueError('schema_version deve ser 1')
        if not isinstance(self.socket_path, str) or not self.socket_path.endswith('.sock'):
            raise ValueError('socket_path deve ser Unix socket .sock')
        if self.context_size <= 0 or self.cache_reuse < 0 or self.max_response_bytes <= 0:
            raise ValueError('bounds invalidos')
        if self.persist_kv_cache is not False:
            raise ValueError('persistencia KV nao permitida no K2')


def carregar_configuracao_llama_server(path: Path) -> ConfiguracaoLlamaServer:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return ConfiguracaoLlamaServer(**data)
