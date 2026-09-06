from __future__ import annotations

import time
from pathlib import Path

from .modelo_llm_gateway import ErroInferencia, ResultadoInferencia, SolicitacaoInferencia
from .prompt_cognitivo import construir_prompt_cognitivo
from .unix_http import post_json_unix


class LlamaCppResidentBackend:
    def __init__(self, socket_path: Path, *, cache_reuse: int, timeout_s: float, max_response_bytes: int = 8192, requester=post_json_unix, fallback=None):
        if cache_reuse < 0 or timeout_s <= 0 or max_response_bytes <= 0:
            raise ValueError("bounds invalidos")
        self._socket = Path(socket_path)
        self._cache_reuse = int(cache_reuse)
        self._timeout_s = float(timeout_s)
        self._max_response_bytes = int(max_response_bytes)
        self._requester = requester
        self._fallback = fallback

    def inferir(self, solicitacao: SolicitacaoInferencia) -> ResultadoInferencia:
        inicio = time.monotonic()
        prompt = construir_prompt_cognitivo(solicitacao)
        payload = {"prompt": prompt, "n_predict": 256, "cache_prompt": True, "n_cache_reuse": self._cache_reuse, "stream": False}
        try:
            status, data = self._requester(self._socket, "/completion", payload, self._timeout_s, self._max_response_bytes)
            if status != 200:
                raise OSError("llama-server indisponivel")
            texto = data.get("content")
            if not isinstance(texto, str) or not texto.strip():
                return ResultadoInferencia(False, None, ErroInferencia.SAIDA_INVALIDA, max(0, int((time.monotonic()-inicio)*1000)), "llama_server")
            timings = data.get("timings") if isinstance(data.get("timings"), dict) else {}
            tps = timings.get("predicted_per_second")
            tps = float(tps) if isinstance(tps, (int, float)) and tps >= 0 else None
            return ResultadoInferencia(True, texto.strip(), None, max(0, int((time.monotonic()-inicio)*1000)), "llama_server", tps)
        except Exception:
            if self._fallback is not None:
                return self._fallback.inferir(solicitacao)
            return ResultadoInferencia(False, None, ErroInferencia.BACKEND_INDISPONIVEL, max(0, int((time.monotonic()-inicio)*1000)), "llama_server")
