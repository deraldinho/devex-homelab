import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.adaptador_impacto_afetivo import ImpactoAfetivoObservacional
from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaContextoCognitivo
from infrastructure.pentium.atlas.contexto_foco_emocao import ResultadoFocoEmocao
from infrastructure.pentium.atlas.emocao_derivada import ContextoEmocional, EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_incidente import EstadoRecuperacaoIncidente, IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import ResultadoPipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity

NOW = "2026-09-08T11:00:00+00:00"


class CognitiveObservationProjectionTest(unittest.TestCase):
    def policy(self, **overrides):
        values = dict(max_string_chars=64, max_mudancas_recentes=2,
                      max_dependencias_afetadas=1, max_nuances=1,
                      max_payload_bytes=4096)
        values.update(overrides)
        return PoliticaContextoCognitivo(**values)
    def stimulus(self, sid="s1", source="managed.x99"):
        return Stimulus(sid, source, "host_status", StimulusSeverity.NOTICE,
                        NOW, {"channel_status": "healthy", "secret": "do-not-copy"},
                        1.0, "corr-1")

    def result_a3(self, *, recovered=False):
        perception = EstadoPercepcao("x99", EstadoObservacao.OBSERVADO, 0.9,
                                     NOW, ("ssh",), (), False, NOW)
        incident = IncidenteTecnico(
            "inc-1", "x99", "channel", "warning", NOW, "ssh", 0.8,
            ("core", "x99"), 2, ("e1",),
            EstadoRecuperacaoIncidente.RECUPERADO if recovered else EstadoRecuperacaoIncidente.ABERTO,
            NOW if recovered else None,
        )
        return ResultadoPipelinePercepcaoCorrelacao(True, perception, (incident,))

    def focus_result(self):
        assunto = AssuntoFoco("inc-1", "x99", 0.6, 0.4, 0.7, 1.0, 0.6, 1.0)
        state = EstadoAfetivo(-0.1, 0.4, 0.3, 0.7, 0.6, 0.8, NOW, "inc-1")
        focus = FocoAtencao(assunto, (), NOW, 2)
        return ResultadoFocoEmocao(state, focus, EmocaoDerivada("curioso", ("atento", "vigilante")))

    def impact(self):
        return ImpactoAfetivoObservacional(
            ImpulsoAfetivo("incidente:inc-1"),
            AssuntoFoco("inc-1", "x99", 0.6, 0.4, 0.7, 1.0, 0.6, 1.0),
            ContextoEmocional(), "inc-1", "x99")
    def test_publish_schema_atomic_and_without_technical_state(self):
        from infrastructure.pentium.atlas.cognitive_observation_projection import (
            CognitiveObservationPublisher, load_cognitive_observation_snapshot)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cognitive-observation-context.json"
            publisher = CognitiveObservationPublisher(path, self.policy(), expected_sha="abc")
            snap = publisher.publish(self.stimulus(), self.result_a3(), self.impact(), self.focus_result(), ())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertNotIn("technical_state", payload)
            self.assertEqual(payload["expected_sha"], "abc")
            self.assertEqual(snap.entity_id, "x99")
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            self.assertEqual(load_cognitive_observation_snapshot(path).source_stimulus_id, "s1")

    def test_publish_bounds_recent_dependencies_nuances_and_filters_payload(self):
        from infrastructure.pentium.atlas.cognitive_observation_projection import CognitiveObservationPublisher
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ctx.json"
            publisher = CognitiveObservationPublisher(path, self.policy(), expected_sha="abc")
            recent = (self.stimulus("s0"), self.stimulus("s1"), self.stimulus("s2"))
            snap = publisher.publish(self.stimulus("s3"), self.result_a3(), self.impact(), self.focus_result(), recent)
            self.assertEqual(len(snap.recent_changes), 2)
            self.assertEqual(snap.affected_dependencies, ("core",))
            self.assertEqual(tuple(snap.emotion["nuances"]), ("atento",))
            self.assertNotIn("payload", snap.recent_changes[0])
            self.assertNotIn("secret", json.dumps(snap.to_dict()))
    def test_publish_preserves_recovered_incident_from_same_event(self):
        from infrastructure.pentium.atlas.cognitive_observation_projection import CognitiveObservationPublisher
        with tempfile.TemporaryDirectory() as td:
            publisher = CognitiveObservationPublisher(Path(td) / "ctx.json", self.policy(), expected_sha="abc")
            snap = publisher.publish(self.stimulus(), self.result_a3(recovered=True), self.impact(), self.focus_result(), ())
            self.assertIsNotNone(snap.incident)
            self.assertEqual(snap.incident["incidente_id"], "inc-1")
            self.assertEqual(snap.incident["estado_recuperacao"], "recuperado")

    def test_publish_rejects_when_mandatory_payload_exceeds_bound(self):
        from infrastructure.pentium.atlas.cognitive_observation_projection import CognitiveObservationPublisher
        with tempfile.TemporaryDirectory() as td:
            publisher = CognitiveObservationPublisher(
                Path(td) / "ctx.json", self.policy(max_payload_bytes=64), expected_sha="abc")
            with self.assertRaises(ValueError):
                publisher.publish(self.stimulus(), self.result_a3(), self.impact(), self.focus_result(), ())


if __name__ == "__main__":
    unittest.main()
