from __future__ import annotations

import subprocess
import time

from .config_hermes import HermesConfig
from .modelo_llm_gateway import ErroInferencia, ResultadoInferencia, SolicitacaoInferencia


class HermesAdapter:
    def __init__(self, config: HermesConfig, *, runner=subprocess.run):
        self._config = config
        self._runner = runner

    def _prompt(self, request: SolicitacaoInferencia) -> str:
        return (
            "Responda somente JSON estrito, sem markdown, comentarios ou texto fora do JSON. "
            "O schema cognitivo Atlas v1 exige exatamente estes 8 campos, sem campos extras: "
            "versao_schema, texto, resumo, intencao, parametros_intencao, confianca, motivo, requer_confirmacao. "
            "versao_schema deve ser 1; texto, resumo e intencao devem ser string nao vazia ou null; "
            "parametros_intencao deve ser objeto e deve ser {} quando intencao for null; "
            "confianca deve ser numero entre 0 e 1; motivo deve ser string nao vazia; "
            "requer_confirmacao deve ser booleano. "
            "Para conversa sem capability use como forma: "
            '{"versao_schema":1,"texto":"resposta","resumo":"resumo","intencao":null,'
            '"parametros_intencao":{},"confianca":0.9,"motivo":"interacao_humana","requer_confirmacao":false}. '
            "Nao use ferramentas, shell, filesystem ou rede por iniciativa propria. "
            f"Tarefa: {request.tarefa}\nContexto: {request.contexto_json}"
        )

    def inferir(self, request: SolicitacaoInferencia) -> ResultadoInferencia:
        started = time.monotonic()
        command = [
            self._config.binary, "-p", self._config.profile, "-z",
            self._prompt(request),
        ]
        if self._config.provider:
            command.extend(["--provider", self._config.provider])
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=float(self._config.timeout_s),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._failure(ErroInferencia.TIMEOUT, started)
        except (OSError, UnicodeError):
            return self._failure(ErroInferencia.BACKEND_INDISPONIVEL, started)

        if completed.returncode != 0:
            return self._failure(ErroInferencia.BACKEND_INDISPONIVEL, started)
        output = completed.stdout or ""
        if len(output.encode("utf-8")) > self._config.max_response_bytes:
            return self._failure(ErroInferencia.LIMITE_EXCEDIDO, started)
        if not output.strip():
            return self._failure(ErroInferencia.SAIDA_INVALIDA, started)
        return ResultadoInferencia(
            True,
            output.strip(),
            None,
            self._duration_ms(started),
            f"hermes/{self._config.provider or 'auto'}",
        )

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((time.monotonic() - started) * 1000))

    def _failure(self, error: ErroInferencia, started: float) -> ResultadoInferencia:
        return ResultadoInferencia(
            False,
            None,
            error,
            self._duration_ms(started),
            f"hermes/{self._config.provider or 'auto'}",
        )
