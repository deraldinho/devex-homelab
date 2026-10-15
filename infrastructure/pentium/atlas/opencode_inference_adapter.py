"""OpenCode adapter, injectable transport; explicit model and zero-cost approval required."""
from __future__ import annotations
import time
import math
from .modelo_llm_gateway import ErroInferencia, ResultadoInferencia

class OpenCodeInferenceAdapter:
    def __init__(self, *, model, transport, authorized_models, clock=time.monotonic):
        if model not in frozenset(authorized_models):
            raise ValueError("OpenCode model not authorized")
        if not callable(transport):
            raise TypeError("transport must be callable")
        self.model=model
        self.transport=transport
        self.clock=clock

    def inferir(self, request):
        started=self.clock()
        try:
            response=self.transport(model=self.model, prompt=request.tarefa,
                                    context=request.contexto_json,
                                    max_tokens=request.max_tokens_contexto)
        except TimeoutError:
            return ResultadoInferencia(False,None,ErroInferencia.TIMEOUT,
                                      max(0,int((self.clock()-started)*1000)),"opencode")
        except (ConnectionError,OSError):
            # Transport uncertainty is not safe to replay on another model.
            return ResultadoInferencia(False,None,ErroInferencia.TIMEOUT,
                                      max(0,int((self.clock()-started)*1000)),"opencode")
        duration=max(0,int((self.clock()-started)*1000))
        if not isinstance(response,dict):
            return ResultadoInferencia(False,None,ErroInferencia.SAIDA_INVALIDA,duration,"opencode")
        status=response.get("status")
        usage=response.get("usage")
        usage=usage if isinstance(usage,dict) else {}
        def counter(key):
            value=usage.get(key)
            return value if type(value) is int and value>=0 else None
        price=usage.get("cost")
        price=float(price) if type(price) in (int,float) and math.isfinite(price) and price>=0 else None
        if price is not None and price>0:
            return ResultadoInferencia(False,None,ErroInferencia.LIMITE_EXCEDIDO,duration,
                                      "opencode",custo_usd=price)
        if status=="unavailable" and response.get("dispatched") is False:
            return ResultadoInferencia(False,None,ErroInferencia.MODELO_INDISPONIVEL,duration,"opencode")
        if status=="ok" and isinstance(response.get("text"),str) and response["text"].strip():
            return ResultadoInferencia(True,response["text"],None,duration,"opencode",
                tokens_input=counter("input"),tokens_output=counter("output"),
                tokens_cache_read=counter("cache_read"),custo_usd=price)
        return ResultadoInferencia(False,None,ErroInferencia.SAIDA_INVALIDA,duration,"opencode")
