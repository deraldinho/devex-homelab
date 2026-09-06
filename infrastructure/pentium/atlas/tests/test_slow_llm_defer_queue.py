import unittest

from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica, EstadoSemantico, EventoSemantico, TipoEventoSemantico,
)
from infrastructure.pentium.atlas.slow_llm_defer_queue import SlowLlmDeferQueue
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity


def evento(correlation_id: str, entity=EntidadeSemantica.CORE):
    return EventoSemantico(
        entity=entity,
        event=TipoEventoSemantico.STATE_CHANGED,
        state=EstadoSemantico.ACTIVE,
        severity=StimulusSeverity.NOTICE,
        novelty=1.0,
        correlation_id=correlation_id,
        attributes={},
    )


class SlowLlmDeferQueueTests(unittest.TestCase):
    def test_capacidade_deve_ser_positiva(self):
        with self.assertRaises(ValueError):
            SlowLlmDeferQueue(0)
    def test_fifo_e_payload_minimo_immutavel(self):
        fila = SlowLlmDeferQueue(2)
        self.assertEqual(fila.defer(evento("c1")), "slow_llm:queued")
        self.assertEqual(fila.defer(evento("c2", EntidadeSemantica.X99)), "slow_llm:queued")

        primeiro = fila.pop()
        segundo = fila.pop()
        self.assertEqual(primeiro.correlation_id, "c1")
        self.assertEqual(primeiro.entity, EntidadeSemantica.CORE)
        self.assertEqual(primeiro.event, TipoEventoSemantico.STATE_CHANGED)
        self.assertEqual(segundo.correlation_id, "c2")
        self.assertEqual(fila.pop(), None)

    def test_overflow_falha_sem_descartar_item_antigo(self):
        fila = SlowLlmDeferQueue(1)
        fila.defer(evento("c1"))
        with self.assertRaises(OverflowError):
            fila.defer(evento("c2"))
        self.assertEqual(fila.pop().correlation_id, "c1")


if __name__ == "__main__":
    unittest.main()
