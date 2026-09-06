from __future__ import annotations

from collections.abc import Callable

from .c5_physical_evaluator import C5PhysicalEvidence


MAX_SOAK_ITERACOES = 64


def _numero(valor: object) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _pico_metricas(resultado: dict[str, object], campo: str) -> float | None:
    amostras: list[dict[str, object]] = []
    for chave in ("antes", "depois"):
        valor = resultado.get(chave)
        if isinstance(valor, dict):
            amostras.append(valor)
    durante = resultado.get("durante")
    if isinstance(durante, (list, tuple)):
        amostras.extend(item for item in durante if isinstance(item, dict))
    valores = [_numero(amostra.get(campo)) for amostra in amostras]
    presentes = [valor for valor in valores if valor is not None]
    return max(presentes) if presentes else None


def _snapshot(evidencia: dict[str, object]) -> dict[str, object]:
    resultado = evidencia.get("resultado")
    if not isinstance(resultado, dict):
        resultado = {}
    return {
        "inferencia_sucesso": resultado.get("inferencia_sucesso") is True,
        "latencia_total_ms": _numero(resultado.get("latencia_total_ms")),
        "tokens_por_s": _numero(resultado.get("tokens_por_s")),
        "rss_llm_kib": _pico_metricas(resultado, "rss_llm_kib"),
        "rss_atlas_kib": _pico_metricas(resultado, "rss_atlas_kib"),
        "swap_usada_kib": _pico_metricas(resultado, "swap_usada_kib"),
        "cpu_percent": _pico_metricas(resultado, "cpu_percent"),
        "temperatura_c": _pico_metricas(resultado, "temperatura_c"),
        "erro": resultado.get("erro"),
    }


def executar_campanha_c5(
    *,
    expected_sha: str,
    run_once: Callable[..., dict[str, object]],
    observation_probe: Callable[[], bool],
    timeout_normal_s: float,
    timeout_probe_s: float,
    soak_iteracoes: int,
) -> C5PhysicalEvidence:
    if timeout_normal_s <= 0 or timeout_probe_s <= 0:
        raise ValueError("timeouts devem ser > 0")
    if not 1 <= soak_iteracoes <= MAX_SOAK_ITERACOES:
        raise ValueError(f"soak_iteracoes deve estar entre 1 e {MAX_SOAK_ITERACOES}")

    observacao_ok = bool(observation_probe())
    cold_raw = run_once(timeout_s=timeout_normal_s, fase="cold")
    cold = _snapshot(cold_raw)
    observacao_ok = observacao_ok and bool(observation_probe())

    warm_raw = run_once(timeout_s=timeout_normal_s, fase="warm")
    warm = _snapshot(warm_raw)
    observacao_ok = observacao_ok and bool(observation_probe())

    timeout_raw = run_once(timeout_s=timeout_probe_s, fase="timeout")
    timeout_snapshot = _snapshot(timeout_raw)
    observacao_apos_timeout = bool(observation_probe())
    timeout_isolado = not bool(timeout_snapshot["inferencia_sucesso"]) and observacao_apos_timeout
    observacao_ok = observacao_ok and observacao_apos_timeout

    soak_falhas = 0
    for indice in range(1, soak_iteracoes + 1):
        raw = run_once(timeout_s=timeout_normal_s, fase=f"soak-{indice}")
        if not _snapshot(raw)["inferencia_sucesso"]:
            soak_falhas += 1
    observacao_ok = observacao_ok and bool(observation_probe())

    return C5PhysicalEvidence(
        expected_sha=expected_sha,
        cold=cold,
        warm=warm,
        timeout_isolado=timeout_isolado,
        observation_runtime_preservado=observacao_ok,
        fila_ativacao_pico=0,
        fila_ativacao_limite=0,
        soak_iteracoes=soak_iteracoes,
        soak_falhas=soak_falhas,
    )
