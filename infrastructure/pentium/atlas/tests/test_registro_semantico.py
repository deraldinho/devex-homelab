import unittest

from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from infrastructure.pentium.atlas.registro_semantico import RegistroSemantico
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity


class RegistroSemanticoTests(unittest.TestCase):
    def _evento(self, correlation_id="corr-a", state=EstadoSemantico.DEGRADED):
        return EventoSemantico(
            entity=EntidadeSemantica.CORE,
            event=TipoEventoSemantico.STATE_CHANGED,
            state=state,
            severity=StimulusSeverity.WARNING,
            novelty=0.75,
            correlation_id=correlation_id,
            attributes={"ssh": False, "latency_ms": 12},
        )

    def test_compactacao_usa_codigos_estaveis(self):
        compact = RegistroSemantico().compactar(self._evento())
        self.assertEqual(1, compact["v"])
        self.assertEqual(2, compact["e"])
        self.assertEqual(2, compact["k"])
        self.assertEqual(4, compact["s"])
        self.assertEqual(3, compact["q"])
        self.assertEqual(750, compact["n"])

    def test_fingerprint_ignora_correlacao_mas_preserva_significado(self):
        registry = RegistroSemantico()
        a = registry.fingerprint(self._evento("corr-a"))
        b = registry.fingerprint(self._evento("corr-b"))
        c = registry.fingerprint(self._evento("corr-c", EstadoSemantico.CRITICAL))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(64, len(a))

    def test_registry_nao_expoe_codigos_para_servicos_externos(self):
        registry = RegistroSemantico()
        self.assertFalse(hasattr(registry, "decode_external"))
        self.assertFalse(hasattr(registry, "service_dictionary"))


if __name__ == "__main__":
    unittest.main()
