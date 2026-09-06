from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FonteTermica:
    path: Path
    tipo: str


def status_path_para_pid(pid: int) -> Path:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("pid deve ser inteiro > 0")
    return Path(f"/proc/{pid}/status")


def descobrir_fonte_termica(root: Path = Path("/sys/class/thermal")) -> FonteTermica | None:
    candidatas: list[FonteTermica] = []
    for zone in sorted(Path(root).glob("thermal_zone*")):
        try:
            tipo = (zone / "type").read_text(encoding="utf-8").strip()
            if not (zone / "temp").is_file():
                continue
        except OSError:
            continue
        candidatas.append(FonteTermica(zone / "temp", tipo))
    preferencias = ("x86_pkg_temp", "coretemp", "cpu", "package")
    for token in preferencias:
        for fonte in candidatas:
            if token in fonte.tipo.lower():
                return fonte
    return candidatas[0] if candidatas else None
