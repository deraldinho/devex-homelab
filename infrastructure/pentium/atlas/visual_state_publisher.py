from __future__ import annotations
import json
import os
from pathlib import Path
from .modelo_visual_atlas import EstadoVisualAtlas

class VisualStatePublisher:
    def __init__(self, caminho: Path):
        self._caminho = Path(caminho)

    @property
    def caminho(self) -> Path:
        return self._caminho

    def publicar(self, estado: EstadoVisualAtlas) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho.with_name(self._caminho.name + ".tmp")
        try:
            with temporario.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    estado.para_dict(),
                    handle,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporario, self._caminho)
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._caminho.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporario.unlink(missing_ok=True)
