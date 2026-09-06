from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .stimulus_model import StimulusSeverity

MAX_ATTRIBUTES = 16
MAX_ATTRIBUTE_KEY_CHARS = 64
MAX_ATTRIBUTE_STRING_CHARS = 128


class EntidadeSemantica(str, Enum):
    PENTIUM = "pentium"
    CORE = "core"
    X99 = "x99"
    WIFI_ZONE = "wifi_zone"


class TipoEventoSemantico(str, Enum):
    OBSERVED = "observed"
    STATE_CHANGED = "state_changed"
    RECOVERED = "recovered"
    SOURCE_ERROR = "source_error"
    PRESENCE_APPEARED = "presence_appeared"
    PRESENCE_MISSING = "presence_missing"
    PRESENCE_RECOVERED = "presence_recovered"
    PRESENCE_CHANGED = "presence_changed"


class EstadoSemantico(str, Enum):
    HEALTHY = "healthy"
    ACTIVE = "active"
    BUSY = "busy"
    DEGRADED = "degraded"
    STRESSED = "stressed"
    CRITICAL = "critical"
    RECOVERED = "recovered"
    ERROR = "error"
    PRESENT = "present"
    MISSING = "missing"


def _validar_scalar(value: object) -> None:
    if isinstance(value, str):
        if len(value) > MAX_ATTRIBUTE_STRING_CHARS:
            raise ValueError("atributo string excede bound")
        return
    if isinstance(value, bool) or isinstance(value, int) or value is None:
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise ValueError("attributes aceita somente escalares bounded")


@dataclass(frozen=True)
class EventoSemantico:
    entity: EntidadeSemantica
    event: TipoEventoSemantico
    state: EstadoSemantico
    severity: StimulusSeverity
    novelty: float
    correlation_id: str
    attributes: Mapping[str, object]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version semantico deve ser 1")
        if not 0.0 <= float(self.novelty) <= 1.0:
            raise ValueError("novelty deve estar entre 0 e 1")
        if not isinstance(self.correlation_id, str) or not self.correlation_id.strip():
            raise ValueError("correlation_id obrigatorio")
        attrs = dict(self.attributes)
        if len(attrs) > MAX_ATTRIBUTES:
            raise ValueError("attributes excede bound")
        for key, value in attrs.items():
            if not isinstance(key, str) or not key or len(key) > MAX_ATTRIBUTE_KEY_CHARS:
                raise ValueError("chave de atributo invalida")
            _validar_scalar(value)
        object.__setattr__(self, "novelty", float(self.novelty))
        object.__setattr__(self, "attributes", MappingProxyType(attrs))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "entity": self.entity.value,
            "event": self.event.value,
            "state": self.state.value,
            "severity": self.severity.value,
            "novelty": self.novelty,
            "correlation_id": self.correlation_id,
            "attributes": dict(self.attributes),
        }
