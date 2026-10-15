from __future__ import annotations

import json
from typing import Protocol

from .modelo_contexto_cognitivo import ContextoCognitivo
from .modelo_llm_gateway import ResultadoInferencia, SolicitacaoInferencia


class LLMBackend(Protocol):
    def inferir(self, solicitacao: SolicitacaoInferencia) -> ResultadoInferencia: ...


class LLMGateway:
    def __init__(self, backend: LLMBackend, *, max_payload_bytes: int, max_tokens_contexto: int, reasoning_policy=None, token_recorder=None):
        if max_payload_bytes <= 0 or max_tokens_contexto <= 0:
            raise ValueError("bounds do gateway devem ser > 0")
        self._backend = backend
        self._max_payload_bytes = int(max_payload_bytes)
        self._max_tokens_contexto = int(max_tokens_contexto)
        self._reasoning_policy = reasoning_policy
        self._token_recorder = token_recorder

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, (len(text.encode("utf-8")) + 3) // 4)

    def inferir(self, contexto: ContextoCognitivo, tarefa: str) -> ResultadoInferencia:
        if not isinstance(contexto, ContextoCognitivo):
            raise TypeError("contexto deve ser ContextoCognitivo")
        if not isinstance(tarefa, str) or not tarefa.strip():
            raise ValueError("tarefa nao pode ser vazia")
        payload = json.dumps(contexto.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(payload.encode("utf-8")) > self._max_payload_bytes:
            raise ValueError("contexto excede max_payload_bytes")
        mode = self._reasoning_policy.select(contexto, tarefa) if self._reasoning_policy is not None else "off"
        solicitacao = SolicitacaoInferencia(1, tarefa.strip(), payload, self._max_tokens_contexto, mode)
        resultado = self._backend.inferir(solicitacao)
        if self._token_recorder is not None:
            output = resultado.texto or ""
            if resultado.tokens_input is not None and resultado.tokens_output is not None:
                total=resultado.tokens_input+resultado.tokens_output+(resultado.tokens_cache_read or 0)
            else:
                total=self._estimate_tokens(payload)+self._estimate_tokens(output)
            self._token_recorder(total)
        return resultado
