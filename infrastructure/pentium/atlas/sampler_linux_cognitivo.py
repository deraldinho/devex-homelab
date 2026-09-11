from __future__ import annotations

from pathlib import Path

from .certificacao_cognitiva import MetricasSistema


def _ler(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _rss_kib(path: Path) -> int | None:
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


def _cpu_snapshot(path: Path) -> tuple[int, int] | None:
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


def _cpu_percent(anterior: tuple[int, int] | None, atual: tuple[int, int] | None) -> float | None:
    if anterior is None or atual is None:
        return None
    delta_total = atual[0] - anterior[0]
    delta_idle = atual[1] - anterior[1]
    if delta_total <= 0:
        return None
    ocupado = delta_total - max(0, delta_idle)
    return round(max(0.0, min(100.0, ocupado / delta_total * 100.0)), 2)


def _temperatura_c(path: Path) -> float | None:
    texto = _ler(path)
    if texto is None:
        return None
    try:
        valor = float(texto.strip())
    except ValueError:
        return None
    return valor / 1000.0 if abs(valor) > 200.0 else valor


class LinuxCognitiveSampler:
    def __init__(self, *, thermal_path: Path, meminfo_path=Path("/proc/meminfo"),
                 proc_stat_path=Path("/proc/stat"), atlas_status_path=Path("/proc/self/status")):
        self._meminfo = Path(meminfo_path)
        self._proc_stat = Path(proc_stat_path)
        self._thermal = Path(thermal_path)
        self._atlas_status = Path(atlas_status_path)
        self._cpu_anterior = None

    def coletar(self) -> MetricasSistema:
        cpu_atual = _cpu_snapshot(self._proc_stat)
        cpu_percent = _cpu_percent(self._cpu_anterior, cpu_atual)
        self._cpu_anterior = cpu_atual
        return MetricasSistema(
            rss_atlas_kib=_rss_kib(self._atlas_status),
            rss_llm_kib=None,
            swap_usada_kib=_swap_usada_kib(self._meminfo),
            cpu_percent=cpu_percent,
            temperatura_c=_temperatura_c(self._thermal),
        )
