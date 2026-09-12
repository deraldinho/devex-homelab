import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from infrastructure.pentium.atlas.cognitive_observability import CognitiveObservablePublisher


class CognitiveObservablePublisherTests(unittest.TestCase):
    def snapshot(self):
        return SimpleNamespace(source_stimulus_id="s1", entity_id="x99")

    def response(self):
        return SimpleNamespace(
            ativado=True, razao=None, motivo="mudanca_estado",
            texto="Vou verificar o estado observado.", resumo="Mudanca detectada no x99.",
            intencao="get_host_status", parametros_intencao={"host": "x99", "secret": "no"},
            confianca=.82, backend="llama_cpp", duracao_ms=321,
            requer_confirmacao=False, intencao_autorizada=True,
        )

    def test_phase_and_result_publish_safe_state_and_timeline(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            publisher = CognitiveObservablePublisher(root / "runtime.json", root / "activity.jsonl", max_events=8)
            publisher.publish_phase(self.snapshot(), state="INFERINDO", activity="executando_qwen", task="formular_resposta_cognitiva", motivo="mudanca_estado")
            publisher.publish_result(self.snapshot(), self.response(), task="formular_resposta_cognitiva")
            state = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
            events = [json.loads(line) for line in (root / "activity.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(2, state["schema_version"])
        self.assertEqual("OBSERVANDO", state["state"])
        self.assertEqual("Mudanca detectada no x99.", state["last_result"]["summary"])
        self.assertEqual("Vou verificar o estado observado.", state["last_result"]["response_preview"])
        self.assertEqual("get_host_status", state["last_result"]["intention"])
        self.assertNotIn("parameters", state["last_result"])
        self.assertEqual("resultado_concluido", events[-1]["activity"])
        self.assertNotIn("prompt", json.dumps(state).lower())

    def test_timeline_coalesces_identical_consecutive_phase_for_same_stimulus(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            publisher=CognitiveObservablePublisher(root/"runtime.json",root/"activity.jsonl",max_events=8)
            publisher.publish_phase(self.snapshot(),state="ANALISANDO",activity="avaliando_estimulo")
            publisher.publish_phase(self.snapshot(),state="ANALISANDO",activity="avaliando_estimulo")
            events=(root/"activity.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(1,len(events))

    def test_policy_suppression_reasons_are_not_reported_as_degraded(self):
        for reason in ("sem_motivo", "cooldown", "orcamento"):
            with self.subTest(reason=reason), TemporaryDirectory() as tmp:
                root = Path(tmp)
                publisher = CognitiveObservablePublisher(root / "runtime.json", root / "activity.jsonl", max_events=8)
                response = self.response()
                response.ativado = False
                response.razao = reason
                response.resumo = None
                publisher.publish_result(self.snapshot(), response)
                state = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
                self.assertEqual("OBSERVANDO", state["state"])
                self.assertEqual(reason, state["last_result"]["reason"])

    def test_unexpected_reason_remains_degraded(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            publisher = CognitiveObservablePublisher(root / "runtime.json", root / "activity.jsonl", max_events=8)
            response = self.response()
            response.ativado = False
            response.razao = "backend_unavailable"
            publisher.publish_result(self.snapshot(), response)
            state = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual("DEGRADADA", state["state"])
