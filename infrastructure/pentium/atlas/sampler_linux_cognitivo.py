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


def _cpu_percent(path: Path) -> float | None:
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
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, ((total - idle) / total) * 100.0)), 2)


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
    def __init__(self, *, meminfo_path=Path("/proc/meminfo"), proc_stat_path=Path("/proc/stat"),
                 thermal_path=Path("/sys/class/thermal/thermal_zone0/temp"),
                 atlas_status_path=Path("/proc/self/status"), llm_status_path=Path("/proc/0/status")):
        self._meminfo = Path(meminfo_path)
        self._proc_stat = Path(proc_stat_path)
        self._thermal = Path(thermal_path)
        self._atlas_status = Path(atlas_status_path)
        self._llm_status = Path(llm_status_path)

    def coletar(self) -> MetricasSistema:
        return MetricasSistema(
            rss_atlas_kib=_rss_kib(self._atlas_status),
            rss_llm_kib=_rss_kib(self._llm_status),
            swap_usada_kib=_swap_usada_kib(self._meminfo),
            cpu_percent=_cpu_percent(self._proc_stat),
            temperatura_c=_temperatura_c(self._thermal),
        )
