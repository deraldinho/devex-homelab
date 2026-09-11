from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math


class IntentState(str, Enum):
    CANDIDATA = "CANDIDATA"
    ATIVA = "ATIVA"
    AGUARDANDO = "AGUARDANDO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"
    EXPIRADA = "EXPIRADA"


class IntentType(str, Enum):
    OBSERVAR = "OBSERVAR"
    ACOMPANHAR_RECUPERACAO = "ACOMPANHAR_RECUPERACAO"
    INTERAGIR_COM_HUMANO = "INTERAGIR_COM_HUMANO"
    ENCERRAR_ACOMPANHAMENTO = "ENCERRAR_ACOMPANHAMENTO"


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value.strip()


def _utc(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _unit(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class ContinuousIntent:
    intencao_id: str
    tipo: IntentType
    estado: IntentState
    assunto_id: str
    entidade_id: str
    motivo: str
    prioridade: float
    iniciado_em: str
    atualizado_em: str
    valido_ate: str
    notificado_usuario: bool = False
    episodio_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "intencao_id", _text(self.intencao_id, "intencao_id"))
        object.__setattr__(self, "assunto_id", _text(self.assunto_id, "assunto_id"))
        object.__setattr__(self, "entidade_id", _text(self.entidade_id, "entidade_id"))
        object.__setattr__(self, "motivo", _text(self.motivo, "motivo"))
        if not isinstance(self.tipo, IntentType) or not isinstance(self.estado, IntentState):
            raise ValueError("tipo and estado must use intent enums")
        object.__setattr__(self, "prioridade", _unit(self.prioridade, "prioridade"))
        object.__setattr__(self, "iniciado_em", _utc(self.iniciado_em, "iniciado_em"))
        object.__setattr__(self, "atualizado_em", _utc(self.atualizado_em, "atualizado_em"))
        object.__setattr__(self, "valido_ate", _utc(self.valido_ate, "valido_ate"))
        if self.episodio_id is not None:
            object.__setattr__(self, "episodio_id", _text(self.episodio_id, "episodio_id"))

    @property
    def terminal(self) -> bool:
        return self.estado in {
            IntentState.CONCLUIDA,
            IntentState.CANCELADA,
            IntentState.EXPIRADA,
        }
