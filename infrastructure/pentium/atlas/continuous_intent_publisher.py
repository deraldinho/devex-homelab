from __future__ import annotations

import json
import os
from pathlib import Path


class ContinuousIntentPublisher:
    def __init__(self, path: Path):
        self._path = Path(path)

    def publish(self, intent, *, communication_mode: str, material_fingerprint: str) -> None:
        payload = {
            "schema_version": 1,
            "communication_mode": str(communication_mode),
            "material_fingerprint": str(material_fingerprint)[:256],
            "intent": None if intent is None else {
                "intencao_id": intent.intencao_id,
                "tipo": intent.tipo.value,
                "estado": intent.estado.value,
                "assunto_id": intent.assunto_id,
                "entidade_id": intent.entidade_id,
                "motivo": intent.motivo,
                "prioridade": intent.prioridade,
                "iniciado_em": intent.iniciado_em,
                "atualizado_em": intent.atualizado_em,
                "valido_ate": intent.valido_ate,
                "notificado_usuario": intent.notificado_usuario,
                "episodio_id": intent.episodio_id,
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_name(self._path.name + ".tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self._path)
        finally:
            temp.unlink(missing_ok=True)
