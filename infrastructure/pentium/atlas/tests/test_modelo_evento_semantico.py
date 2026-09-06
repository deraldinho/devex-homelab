import unittest

from infrastructure.pentium.atlas.modelo_evento_semantico import (
    EntidadeSemantica,
    EstadoSemantico,
    EventoSemantico,
    TipoEventoSemantico,
)
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity


class ModeloEventoSemanticoTests(unittest.TestCase):
    def _evento(self, **changes):
        data = dict(
            entity=EntidadeSemantica.CORE,
            event=TipoEventoSemantico.STATE_CHANGED,
            state=EstadoSemantico.DEGRADED,
            severity=StimulusSeverity.WARNING,
            novelty=0.75,
            correlation_id="corr-1",
            attributes={"ssh": False, "latency_ms": 12},
        )
        data.update(changes)
        return EventoSemantico(**data)

    def test_evento_copia_atributos_e_e_imutavel(self):
        attrs = {"ssh": False}
        evento = self._evento(attributes=attrs)
        attrs["ssh"] = True
        self.assertFalse(evento.attributes["ssh"])
        with self.assertRaises(TypeError):
            evento.attributes["ssh"] = True

    def test_evento_rejeita_bounds_e_payload_composto(self):
        with self.assertRaises(ValueError):
            self._evento(novelty=1.1)
        with self.assertRaises(ValueError):
            self._evento(attributes={f"k{i}": i for i in range(17)})
        with self.assertRaises(ValueError):
            self._evento(attributes={"lista": [1, 2]})
        with self.assertRaises(ValueError):
            self._evento(attributes={"texto": "x" * 129})

    def test_evento_serializa_contrato_legivel_sem_mutar_modelo(self):
        evento = self._evento()
        data = evento.to_dict()
        self.assertEqual(1, data["schema_version"])
        self.assertEqual("core", data["entity"])
        self.assertEqual("state_changed", data["event"])
        self.assertEqual("degraded", data["state"])
        self.assertEqual("warning", data["severity"])
        self.assertEqual({"latency_ms": 12, "ssh": False}, data["attributes"])


if __name__ == "__main__":
    unittest.main()
