from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass

from .modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from .modelo_llm_gateway import ResultadoInferencia


@dataclass(frozen=True)
class CognitiveCachePolicy:
    max_entries: int
    ttl_s: float
    model_id: str
    policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.max_entries, int) or self.max_entries <= 0:
            raise ValueError("max_entries deve ser inteiro > 0")
        if self.ttl_s <= 0:
            raise ValueError("ttl_s deve ser > 0")
        if not self.model_id.strip() or not self.policy_version.strip():
            raise ValueError("model_id e policy_version sao obrigatorios")


class CognitiveCache:
    def __init__(self, policy: CognitiveCachePolicy, *, clock=None):
        self.policy = policy
        self._clock = clock or time.monotonic
        self._items = OrderedDict()
        self._metrics = {"hit": 0, "miss": 0, "bypass": 0, "expired": 0, "eviction": 0}

    def allowed(self, motivo: MotivoAtivacaoCognitiva) -> bool:
        permitido = motivo is MotivoAtivacaoCognitiva.REFLEXAO_PERIODICA
        if not permitido:
            self._metrics["bypass"] += 1
        return permitido

    def key(self, contexto, tarefa: str) -> str:
        payload = contexto.to_dict()
        payload.pop("timestamp", None)
        canonical = {
            "task": tarefa,
            "model_id": self.policy.model_id,
            "policy_version": self.policy.policy_version,
            "context": payload,
        }
        raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, contexto, tarefa: str) -> ResultadoInferencia | None:
        chave = self.key(contexto, tarefa)
        item = self._items.get(chave)
        if item is None:
            self._metrics["miss"] += 1
            return None
        criado, resultado = item
        if self._clock() - criado > self.policy.ttl_s:
            del self._items[chave]
            self._metrics["expired"] += 1
            self._metrics["miss"] += 1
            return None
        self._items.move_to_end(chave)
        self._metrics["hit"] += 1
        return ResultadoInferencia(True, resultado.texto, None, 0, f"cache:{resultado.backend}")

    def put(self, contexto, tarefa: str, resultado: ResultadoInferencia) -> bool:
        if not resultado.sucesso:
            return False
        chave = self.key(contexto, tarefa)
        self._items[chave] = (self._clock(), resultado)
        self._items.move_to_end(chave)
        while len(self._items) > self.policy.max_entries:
            self._items.popitem(last=False)
            self._metrics["eviction"] += 1
        return True

    def invalidate_all(self) -> None:
        self._items.clear()

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)
