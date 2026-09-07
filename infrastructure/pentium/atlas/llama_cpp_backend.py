from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable

from .modelo_llm_gateway import ErroInferencia, ResultadoInferencia, SolicitacaoInferencia
from .prompt_cognitivo import construir_prompt_cognitivo

_COGNITIVE_KEYS = {"versao_schema","texto","resumo","intencao","parametros_intencao","confianca","motivo","requer_confirmacao"}
_COGNITIVE_JSON_SCHEMA = json.dumps({
    "type":"object","additionalProperties":False,
    "required":["versao_schema","texto","resumo","intencao","parametros_intencao","confianca","motivo","requer_confirmacao"],
    "properties":{
        "versao_schema":{"const":1},
        "texto":{"type":["string","null"]},"resumo":{"type":["string","null"]},
        "intencao":{"type":["string","null"]},"parametros_intencao":{"type":"object"},
        "confianca":{"type":"number","minimum":0,"maximum":1},"motivo":{"type":"string"},
        "requer_confirmacao":{"type":"boolean"}
    }
}, separators=(",", ":"))

def _extract_cognitive_json(stdout: str) -> str | None:
    decoder = json.JSONDecoder()
    matches = []
    for idx, ch in enumerate(stdout):
        if ch != "{":
            continue
        try:
            value, end = decoder.raw_decode(stdout[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and _COGNITIVE_KEYS.issubset(value.keys()):
            matches.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return matches[-1] if matches else None

class LlamaCppBackend:
    def __init__(
        self,
        binary_path: Path,
        model_path: Path,
        *,
        timeout_s: float,
        max_saida_bytes: int,
        executor: Callable[..., object] = subprocess.run,
    ):
        if timeout_s <= 0 or max_saida_bytes <= 0:
            raise ValueError("timeout e max_saida_bytes devem ser > 0")
        self._binary = Path(binary_path)
        self._model = Path(model_path)
        self._timeout_s = float(timeout_s)
        self._max_saida_bytes = int(max_saida_bytes)
        self._executor = executor

    def _falha(self, erro: ErroInferencia, inicio: float) -> ResultadoInferencia:
        return ResultadoInferencia(False, None, erro, max(0, int((time.monotonic() - inicio) * 1000)), "llama_cpp")

    def inferir(self, solicitacao: SolicitacaoInferencia) -> ResultadoInferencia:
        inicio = time.monotonic()
        if not self._binary.is_file():
            return self._falha(ErroInferencia.BACKEND_INDISPONIVEL, inicio)
        if not self._model.is_file():
            return self._falha(ErroInferencia.MODELO_INDISPONIVEL, inicio)

        prompt = construir_prompt_cognitivo(solicitacao)
        argv = [
            str(self._binary),
            "-m", str(self._model),
            "-c", str(solicitacao.max_tokens_contexto),
            "-n", "256",
            "--single-turn",
            "--simple-io",
            "--log-disable",
            "--temp", "0",
            "--json-schema", _COGNITIVE_JSON_SCHEMA,
            "--reasoning", solicitacao.reasoning_mode,
            "--no-display-prompt",
            "-p", prompt,
        ]
        try:
            proc = self._executor(
                argv,
                shell=False,
                text=True,
                capture_output=True,
                timeout=self._timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._falha(ErroInferencia.TIMEOUT, inicio)
        except OSError:
            return self._falha(ErroInferencia.BACKEND_INDISPONIVEL, inicio)

        stdout = getattr(proc, "stdout", "") or ""
        stderr = getattr(proc, "stderr", "") or ""
        if len(stdout.encode("utf-8")) > self._max_saida_bytes or len(stderr.encode("utf-8")) > self._max_saida_bytes:
            return self._falha(ErroInferencia.LIMITE_EXCEDIDO, inicio)
        if getattr(proc, "returncode", 1) != 0:
            return self._falha(ErroInferencia.BACKEND_INDISPONIVEL, inicio)
        texto = _extract_cognitive_json(stdout)
        if not texto:
            return self._falha(ErroInferencia.SAIDA_INVALIDA, inicio)
        return ResultadoInferencia(True, texto, None, max(0, int((time.monotonic() - inicio) * 1000)), "llama_cpp")
