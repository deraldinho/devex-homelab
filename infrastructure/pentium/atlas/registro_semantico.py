from __future__ import annotations

import hashlib
import json

from .modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from .stimulus_model import StimulusSeverity


_ENTITY_CODES = {
    EntidadeSemantica.PENTIUM: 1,
    EntidadeSemantica.CORE: 2,
    EntidadeSemantica.X99: 3,
    EntidadeSemantica.WIFI_ZONE: 4,
}
_EVENT_CODES = {
    TipoEventoSemantico.OBSERVED: 1,
    TipoEventoSemantico.STATE_CHANGED: 2,
    TipoEventoSemantico.RECOVERED: 3,
    TipoEventoSemantico.SOURCE_ERROR: 4,
    TipoEventoSemantico.PRESENCE_APPEARED: 5,
    TipoEventoSemantico.PRESENCE_MISSING: 6,
    TipoEventoSemantico.PRESENCE_RECOVERED: 7,
    TipoEventoSemantico.PRESENCE_CHANGED: 8,
}
_STATE_CODES = {
    EstadoSemantico.HEALTHY: 1,
    EstadoSemantico.ACTIVE: 2,
    EstadoSemantico.BUSY: 3,
    EstadoSemantico.DEGRADED: 4,
    EstadoSemantico.STRESSED: 5,
    EstadoSemantico.CRITICAL: 6,
    EstadoSemantico.RECOVERED: 7,
    EstadoSemantico.ERROR: 8,
    EstadoSemantico.PRESENT: 9,
    EstadoSemantico.MISSING: 10,
}
_SEVERITY_CODES = {
    StimulusSeverity.INFO: 1,
    StimulusSeverity.NOTICE: 2,
    StimulusSeverity.WARNING: 3,
    StimulusSeverity.CRITICAL: 4,
}


class RegistroSemantico:
    schema_version = 1

    def compactar(self, evento: EventoSemantico) -> dict[str, object]:
        return {
            "v": self.schema_version,
            "e": _ENTITY_CODES[evento.entity],
            "k": _EVENT_CODES[evento.event],
            "s": _STATE_CODES[evento.state],
            "q": _SEVERITY_CODES[evento.severity],
            "n": int(round(evento.novelty * 1000)),
            "c": evento.correlation_id,
            "a": dict(evento.attributes),
        }

    def fingerprint(self, evento: EventoSemantico) -> str:
        compact = self.compactar(evento)
        compact.pop("c", None)
        canonical = json.dumps(
            compact,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
