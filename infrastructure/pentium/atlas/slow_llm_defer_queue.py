from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .modelo_evento_semantico import EntidadeSemantica, EventoSemantico, TipoEventoSemantico


@dataclass(frozen=True)
class IntencaoSlowLlm:
    correlation_id: str
    entity: EntidadeSemantica
    event: TipoEventoSemantico


class SlowLlmDeferQueue:
    def __init__(self, capacidade: int):
        if not isinstance(capacidade, int) or capacidade <= 0:
            raise ValueError("capacidade deve ser inteiro > 0")
        self._capacidade = capacidade
        self._fila: deque[IntencaoSlowLlm] = deque()

    @property
    def capacidade(self) -> int:
        return self._capacidade

    def defer(self, evento: EventoSemantico) -> str:
        if len(self._fila) >= self._capacidade:
            raise OverflowError("slow llm defer queue cheia")
        self._fila.append(
            IntencaoSlowLlm(
                correlation_id=evento.correlation_id,
                entity=evento.entity,
                event=evento.event,
            )
        )
        return "slow_llm:queued"

    def pop(self) -> IntencaoSlowLlm | None:
        if not self._fila:
            return None
        return self._fila.popleft()

    def __len__(self) -> int:
        return len(self._fila)
