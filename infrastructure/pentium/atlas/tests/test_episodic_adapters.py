import unittest
from dataclasses import replace

from infrastructure.pentium.atlas.episodic_adapters import (
    evidence_from_incident,
    evidence_from_perception,
)
from infrastructure.pentium.atlas.episodic_model import EpisodeCategory
from infrastructure.pentium.atlas.modelo_incidente import (
    EstadoRecuperacaoIncidente,
    IncidenteTecnico,
)
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao


NOW = "2026-09-11T12:20:00+00:00"


class EpisodicAdapterTests(unittest.TestCase):
    def setUp(self):
        self.incident = IncidenteTecnico(
            "inc-1", "core", "indisponibilidade_correlacionada", "critical",
            NOW, "core", .9, ("core", "firewall"), 2,
        )

    def test_incident_adapter_never_embeds_raw_payload(self):
        ev, category, key, terminal = evidence_from_incident(self.incident, "gen-1")
        self.assertEqual(EpisodeCategory.INCIDENT, category)
        self.assertEqual("incident:inc-1", key)
        self.assertFalse(terminal)
        self.assertNotIn("payload", ev.content_reduced.lower())
        self.assertIn("core", ev.content_reduced)
        self.assertEqual(.9, ev.reliability)
    def test_recovered_incident_is_terminal(self):
        recovered = replace(
            self.incident,
            estado_recuperacao=EstadoRecuperacaoIncidente.RECUPERADO,
            recuperado_em=NOW,
        )
        ev, _, _, terminal = evidence_from_incident(recovered, "gen-1")
        self.assertTrue(terminal)
        self.assertIn("recuperado", ev.content_reduced)

    def test_perception_adapter_uses_only_reduced_fields(self):
        perception = EstadoPercepcao(
            "core", EstadoObservacao.INACESSIVEL, .8, NOW,
            ("core.agent", "core.ping"), (), False, NOW,
        )
        ev = evidence_from_perception(perception, "gen-1")
        self.assertEqual("perception", ev.source_kind)
        self.assertEqual("core", ev.entity_id)
        self.assertEqual(.8, ev.reliability)
        self.assertIn("inacessivel", ev.content_reduced)
        self.assertNotIn("{", ev.content_reduced)


if __name__ == "__main__":
    unittest.main()
