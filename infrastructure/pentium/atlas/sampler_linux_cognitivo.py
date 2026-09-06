from __future__ import annotations

from pathlib import Path

from .certificacao_cognitiva import MetricasSistema


def _ler(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _rss_kib(path: Path | None) -> int | None:
    texto = _ler(path)
    if texto is None:
        return None
    for linha in texto.splitlines():
        if linha.startswith("VmRSS:"):
            partes = linha.split()
            return int(partes[1]) if len(partes) >= 2 else None
    return None


def _swap_usada_kib(path: Path) -> int | None:
    texto = _ler(path)
    if texto is None:
        return None
    valores = {}
    for linha in texto.splitlines():
        if ":" not in linha:
            continue
        chave, resto = linha.split(":", 1)
        partes = resto.split()
        if partes and partes[0].isdigit():
            valores[chave] = int(partes[0])
    if "SwapTotal" not in valores or "SwapFree" not in valores:
        return None
    return max(0, valores["SwapTotal"] - valores["SwapFree"])


def _cpu_times(path: Path) -> tuple[int, int] | None:
    texto = _ler(path)
    if texto is None:
        return None
    linha = next((x for x in texto.splitlines() if x.startswith("cpu ")), None)
    if linha is None:
        return None
    campos = [int(x) for x in linha.split()[1:] if x.isdigit()]
    if len(campos) < 4:
        return None
    total = sum(campos)
    idle = campos[3] + (campos[4] if len(campos) > 4 else 0)
    return total, idle


def _temperatura_c(path: Path | None) -> float | None:
    texto = _ler(path)
    if texto is None:
        return None
    try:
        valor = float(texto.strip())
    except ValueError:
        return None
    return valor / 1000.0 if abs(valor) > 200.0 else valor


class LinuxCognitiveSampler:
    def __init__(self, *, meminfo_path=Path("/proc/meminfo"), proc_stat_path=Path("/proc/stat"), thermal_path=None, atlas_status_path=Path("/proc/self/status"), llm_status_path=None):
        self._meminfo = Path(meminfo_path)
        self._proc_stat = Path(proc_stat_path)
        self._thermal = Path(thermal_path) if thermal_path is not None else None
        self._atlas_status = Path(atlas_status_path)
        self._llm_status = Path(llm_status_path) if llm_status_path is not None else None
        self._cpu_anterior: tuple[int, int] | None = None

    def coletar(self) -> MetricasSistema:
        atual = _cpu_times(self._proc_stat)
        cpu_percent = None
        if atual is not None and self._cpu_anterior is not None:
            total_delta = atual[0] - self._cpu_anterior[0]
            idle_delta = atual[1] - self._cpu_anterior[1]
            if total_delta > 0:
                ocupado = max(0, total_delta - max(0, idle_delta))
                cpu_percent = round(max(0.0, min(100.0, ocupado / total_delta * 100.0)), 2)
        self._cpu_anterior = atual
        return MetricasSistema(
            rss_atlas_kib=_rss_kib(self._atlas_status),
            rss_llm_kib=_rss_kib(self._llm_status),
            swap_usada_kib=_swap_usada_kib(self._meminfo),
            cpu_percent=cpu_percent,
            temperatura_c=_temperatura_c(self._thermal),
        )
