from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FonteTermica:
    path: Path
    tipo: str


def status_path_para_pid(pid: int) -> Path:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ValueError("pid deve ser inteiro > 0")
    return Path(f"/proc/{pid}/status")


def descobrir_fonte_termica(root: Path = Path("/sys/class/thermal")) -> FonteTermica | None:
    candidatas: list[FonteTermica] = []
    try:
        zonas = sorted(Path(root).glob("thermal_zone*"))
    except OSError:
        return None
    for zona in zonas:
        try:
            tipo = (zona / "type").read_text(encoding="utf-8").strip()
            temp = zona / "temp"
            temp.read_text(encoding="utf-8")
        except OSError:
            continue
        if tipo:
            candidatas.append(FonteTermica(temp, tipo))
    if not candidatas:
        return None
    preferidas = ("x86_pkg", "coretemp", "cpu", "soc")
    for termo in preferidas:
        for fonte in candidatas:
            if termo in fonte.tipo.lower():
                return fonte
    return candidatas[0]
