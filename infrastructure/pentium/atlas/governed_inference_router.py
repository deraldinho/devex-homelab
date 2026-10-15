"""Opt-in inference routing. No paid inference or ambiguous replay."""
from __future__ import annotations
from .free_model_selection import select_free_models
from .modelo_llm_gateway import ErroInferencia, ResultadoInferencia

RETRYABLE=frozenset({ErroInferencia.BACKEND_INDISPONIVEL, ErroInferencia.MODELO_INDISPONIVEL})
class GovernedInferenceRouter:
    def __init__(self, *, offers, authorized, backends, telemetry=None, adaptive_health=None):
        self.offers=tuple(offers)
        self.authorized=frozenset(authorized)
        self.backends=dict(backends)
        self.telemetry=telemetry
        self.adaptive_health=adaptive_health
    def inferir(self, request):
        order=select_free_models(self.offers,task=request.tarefa,authorized=self.authorized)
        if self.adaptive_health is not None:
            try:
                order=self.adaptive_health.rank(order,task=request.tarefa)
            except (OSError,ValueError,TypeError):
                pass  # Noncritical telemetry cannot stop safe, zero-price routing.
        if not order:
            return ResultadoInferencia(False,None,ErroInferencia.MODELO_INDISPONIVEL,0,"free-router")
        last=None
        for offer in order:
            key=(offer.provider,offer.model)
            backend=self.backends.get(key)
            if backend is None:
                continue
            # Never replay after exceptions: dispatch may have happened.
            result=backend.inferir(request)
            if self.adaptive_health is not None:
                try:
                    self.adaptive_health.observe_result(offer,result)
                except (OSError,ValueError,TypeError):
                    pass  # Preserve the inference result if the health store fails.
            if self.telemetry is not None:
                self.telemetry({"provider":offer.provider,"model":offer.model,
                    "duration_ms":result.duracao_ms,"success":result.sucesso,
                    "tokens_input":result.tokens_input,
                    "tokens_output":result.tokens_output,
                    "tokens_cache_read":result.tokens_cache_read,
                    "cost_usd":result.custo_usd,
                    "session_id":result.session_id,
                    "tokens_source":"provider" if result.tokens_input is not None else "unavailable"})
            if result.sucesso:return result
            last=result
            if result.erro not in RETRYABLE:return result
        return last or ResultadoInferencia(False,None,ErroInferencia.MODELO_INDISPONIVEL,0,"free-router")
