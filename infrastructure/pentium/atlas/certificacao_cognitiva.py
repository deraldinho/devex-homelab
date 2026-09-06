from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from time import monotonic as _monotonic
from typing import Callable, Protocol


@dataclass(frozen=True)
class MetricasSistema:
    rss_atlas_kib: int | None
    rss_llm_kib: int | None
    swap_usada_kib: int | None
    cpu_percent: float | None
    temperatura_c: float | None


@dataclass(frozen=True)
class ResultadoCertificacaoCognitiva:
    antes: MetricasSistema
    depois: MetricasSistema
    latencia_total_ms: int
    inferencia_sucesso: bool
    tokens_por_s: float | None
    erro: str | None
    durante: tuple[MetricasSistema, ...] = ()


class SamplerSistema(Protocol):
    def coletar(self) -> MetricasSistema: ...

class CertificadorCognitivo:
    def __init__(self, *, sampler: SamplerSistema, monotonic: Callable[[], float] = _monotonic,
                 interval_s: float = 0.25, max_amostras_durante: int = 0,
                 sleeper: Callable[[float], None] = time.sleep):
        if interval_s <= 0 or max_amostras_durante < 0:
            raise ValueError("bounds de amostragem invalidos")
        self._sampler = sampler
        self._monotonic = monotonic
        self._interval_s = float(interval_s)
        self._max_amostras = int(max_amostras_durante)
        self._sleeper = sleeper

    def executar(self, inferencia: Callable[[], dict]) -> ResultadoCertificacaoCognitiva:
        antes = self._sampler.coletar()
        inicio = self._monotonic()
        durante: list[MetricasSistema] = []
        parar = threading.Event()

        def amostrar() -> None:
            for _ in range(self._max_amostras):
                if parar.is_set():
                    break
                durante.append(self._sampler.coletar())
                if parar.is_set():
                    break
                self._sleeper(self._interval_s)

        thread = None
        if self._max_amostras:
            thread = threading.Thread(target=amostrar, name="atlas-c5-sampler", daemon=True)
            thread.start()
        sucesso = False
        tokens_por_s = None
        erro = None
        try:
            saida = inferencia()
            sucesso = bool(saida.get("sucesso"))
            tokens = saida.get("tokens_por_s")
            tokens_por_s = float(tokens) if tokens is not None else None
        except Exception as exc:
            erro = type(exc).__name__
        finally:
            parar.set()
            if thread is not None:
                thread.join(timeout=max(0.1, self._interval_s * 2))

        fim = self._monotonic()
        depois = self._sampler.coletar()
        return ResultadoCertificacaoCognitiva(
            antes=antes,
            depois=depois,
            latencia_total_ms=max(0, int(round((fim - inicio) * 1000))),
            inferencia_sucesso=sucesso,
            tokens_por_s=tokens_por_s,
            erro=erro,
            durante=tuple(durante),
        )
