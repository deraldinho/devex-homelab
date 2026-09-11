from __future__ import annotations

import string
from dataclasses import dataclass


PASS_MARKER = "ATLAS_COGNITIVO_C5_PHYSICAL_PASS"
BLOCKED_MARKER = "ATLAS_COGNITIVO_C5_PHYSICAL_BLOCKED"


@dataclass(frozen=True)
class C5PhysicalBudget:
    max_rss_total_kib: int
    max_swap_usada_kib: int
    max_cpu_percent: float
    max_temperatura_c: float
    max_latencia_cold_ms: int
    max_latencia_warm_ms: int
    min_tokens_por_s: float
    min_soak_iteracoes: int

    def __post_init__(self) -> None:
        valores = (
            self.max_rss_total_kib,
            self.max_swap_usada_kib,
            self.max_cpu_percent,
            self.max_temperatura_c,
            self.max_latencia_cold_ms,
            self.max_latencia_warm_ms,
            self.min_tokens_por_s,
            self.min_soak_iteracoes,
        )
        if any(valor <= 0 for valor in valores):
            raise ValueError("budget fisico exige limites positivos")


@dataclass(frozen=True)
class C5PhysicalEvidence:
    expected_sha: str
    cold: dict[str, object]
    warm: dict[str, object]
    timeout_isolado: bool
    observation_runtime_preservado: bool
    fila_ativacao_pico: int
    fila_ativacao_limite: int
    soak_iteracoes: int
    soak_falhas: int

    def __post_init__(self) -> None:
        sha = self.expected_sha.strip().lower()
        if len(sha) != 40 or any(c not in string.hexdigits.lower() for c in sha):
            raise ValueError("expected_sha invalido")
        if min(self.fila_ativacao_pico, self.fila_ativacao_limite, self.soak_iteracoes, self.soak_falhas) < 0:
            raise ValueError("contadores fisicos devem ser >= 0")
        object.__setattr__(self, "expected_sha", sha)


@dataclass(frozen=True)
class C5PhysicalEvaluation:
    aprovado: bool
    blockers: tuple[str, ...]
    marker: str


def _numero(snapshot: dict[str, object], campo: str) -> float | None:
    valor = snapshot.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def _avaliar_snapshot(nome: str, snapshot: dict[str, object], budget: C5PhysicalBudget, blockers: list[str]) -> None:
    if snapshot.get("inferencia_sucesso") is not True:
        blockers.append(f"{nome}_inferencia_falhou")

    rss_llm = _numero(snapshot, "rss_llm_kib")
    rss_atlas = _numero(snapshot, "rss_atlas_kib")
    swap = _numero(snapshot, "swap_usada_kib")
    cpu = _numero(snapshot, "cpu_percent")
    temperatura = _numero(snapshot, "temperatura_c")
    latencia = _numero(snapshot, "latencia_total_ms")
    tokens = _numero(snapshot, "tokens_por_s")

    if rss_llm is None or rss_atlas is None:
        blockers.append(f"{nome}_rss_ausente")
    elif rss_llm + rss_atlas > budget.max_rss_total_kib:
        blockers.append(f"{nome}_rss_excedido")

    limites = (
        (swap, budget.max_swap_usada_kib, "swap"),
        (cpu, budget.max_cpu_percent, "cpu"),
        (temperatura, budget.max_temperatura_c, "temperatura"),
    )
    for valor, limite, campo in limites:
        if valor is None:
            blockers.append(f"{nome}_{campo}_ausente")
        elif valor > limite:
            blockers.append(f"{nome}_{campo}_excedido")

    latencia_max = budget.max_latencia_cold_ms if nome == "cold" else budget.max_latencia_warm_ms
    if latencia is None:
        blockers.append(f"{nome}_latencia_ausente")
    elif latencia > latencia_max:
        blockers.append(f"{nome}_latencia_excedida")

    if tokens is None:
        blockers.append(f"{nome}_tokens_por_s_ausente")
    elif tokens < budget.min_tokens_por_s:
        blockers.append(f"{nome}_tokens_por_s_abaixo_minimo")


def avaliar_c5_fisica(evidence: C5PhysicalEvidence, budget: C5PhysicalBudget | None) -> C5PhysicalEvaluation:
    blockers: list[str] = []
    if budget is None:
        blockers.append("budget_fisico_nao_aprovado")
        return C5PhysicalEvaluation(False, tuple(blockers), BLOCKED_MARKER)

    _avaliar_snapshot("cold", evidence.cold, budget, blockers)
    _avaliar_snapshot("warm", evidence.warm, budget, blockers)

    if not evidence.timeout_isolado:
        blockers.append("timeout_nao_isolado")
    if not evidence.observation_runtime_preservado:
        blockers.append("observation_runtime_nao_preservado")
    if evidence.fila_ativacao_pico > evidence.fila_ativacao_limite:
        blockers.append("fila_ativacao_excedeu_limite")
    if evidence.soak_iteracoes < budget.min_soak_iteracoes:
        blockers.append("soak_iteracoes_insuficientes")
    if evidence.soak_falhas:
        blockers.append("soak_com_falhas")

    blockers_unicos = tuple(dict.fromkeys(blockers))
    aprovado = not blockers_unicos
    return C5PhysicalEvaluation(aprovado, blockers_unicos, PASS_MARKER if aprovado else BLOCKED_MARKER)
