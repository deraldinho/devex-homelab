from __future__ import annotations

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


class SamplerSistema(Protocol):
    def coletar(self) -> MetricasSistema: ...


class CertificadorCognitivo:
    def __init__(self, *, sampler: SamplerSistema, monotonic: Callable[[], float] = _monotonic):
        self._sampler = sampler
        self._monotonic = monotonic

    def executar(self, inferencia: Callable[[], dict]) -> ResultadoCertificacaoCognitiva:
        antes = self._sampler.coletar()
        inicio = self._monotonic()
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
        fim = self._monotonic()
        depois = self._sampler.coletar()
        return ResultadoCertificacaoCognitiva(
            antes=antes,
            depois=depois,
            latencia_total_ms=max(0, int(round((fim - inicio) * 1000))),
            inferencia_sucesso=sucesso,
            tokens_por_s=tokens_por_s,
            erro=erro,
        )
