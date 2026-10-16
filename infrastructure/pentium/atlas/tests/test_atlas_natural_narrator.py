import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.atlas_natural_narrator import (
    AtlasNaturalNarrator,NarrationUnavailable,safe_context,validate_voice)
from infrastructure.pentium.atlas.atlas_adaptive_discord_report import report

EVENT={"candidates":12,"catalog_nous":7,"catalog_nvidia":80,"changed":False}
def message():
    return 'Tenho 12 modelos acompanhados agora. O catalogo Nous mostra 7 e o da NVIDIA 80. Nada mudou na configuracao.'

class DummyNarrator:
    def narrate(self,payload):
        return message()

class NaturalNarratorTests(unittest.TestCase):
    def test_inference_on_every_new_notice_and_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);queue=root/"queue.jsonl";state=root/"state.json"
            narrator=DummyNarrator()
            self.assertTrue(report(EVENT,queue_path=queue,state_path=state,narrator=narrator,now=10000))
            self.assertFalse(report(EVENT,queue_path=queue,state_path=state,narrator=narrator,now=10100))
            self.assertTrue(report(EVENT,queue_path=queue,state_path=state,narrator=narrator,now=13610))
            rows=[json.loads(x) for x in queue.read_text().splitlines()]
            self.assertEqual(len(rows),2)
            self.assertTrue(all(x["arguments"]["narrated_by"]=="atlas_llm" for x in rows))
            self.assertEqual([x["arguments"]["message"] for x in rows],[message(),message()])
    def test_model_outage_cannot_send_raw_or_ack(self):
        class Down:
            def narrate(self,payload):
                raise NarrationUnavailable("model_unavailable")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(NarrationUnavailable):
                report(EVENT,queue_path=root/"queue.jsonl",state_path=root/"state.json",
                       narrator=Down(),now=10000)
            self.assertFalse((root/"queue.jsonl").exists())
            self.assertFalse((root/"state.json").exists())
            self.assertTrue(report(EVENT,queue_path=root/"queue.jsonl",state_path=root/"state.json",
                                   narrator=DummyNarrator(),now=10030))
    def test_llm_response_narration_and_telemetry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"affective-state.json").write_text(json.dumps({
                 "estado":{"valencia":0.3,"ativacao":0.4,"estresse":0.1,
                           "confianca":0.9,"engajamento":0.7,"curiosidade":0.6,
                           "foco_atencao":"SECRET SHOULD NOT GO TO MODEL"}}))
            (root/"cognitive-observation-context.json").write_text(json.dumps({
                "recent_changes":[{"kind":"host_warning","severity":"warning",
                  "payload":{"password":"SECRET PASSWORD"}}]}))
            called=[]
            def fake(args,**kw):
                called.append(args)
                return SimpleNamespace(returncode=0,stdout=json.dumps({"message":message()}))
            narrator=AtlasNaturalNarrator(runtime_dir=root,runner=fake)
            generated=narrator.narrate(EVENT)
            self.assertEqual(generated,message())
            prompt=called[0][-1]
            self.assertIn('"estresse": 0.1',prompt)
            self.assertNotIn("SECRET",prompt)
            self.assertIn('"catalog_nvidia": 80',prompt)
    def test_synthetic_state_influences_only_style(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"affective-state.json").write_text(json.dumps({"estado":{
              "valencia":9,"estresse":.5,"curiosidade":.5,"foco_atencao":"private"}}))
            context=safe_context(root)
            self.assertNotIn("valencia",context["affective_state"])
            self.assertEqual(context["affective_state"]["estresse"],.5)
    def test_fabricated_numbers_and_secrets_blocked(self):
        for wrong in ("São 13 modelos, 7 Nous e 80 NVIDIA. Acho que está tudo bem.",
                      "Agora tenho 12 modelos, 7 Nous e 80 NVIDIA. @everyone!",
                      "Confirmei um custo de R$ 0 e 12 modelos, 7 Nous e 80 NVIDIA.",
                      "Estou consciente do meu corpo: 12 modelos, 7 Nous e 80 NVIDIA.",
                      "Teve erro, mas não derrubou nada: 12 modelos, 7 Nous e 80 NVIDIA."):
            with self.subTest(wrong=wrong),self.assertRaises(NarrationUnavailable):
                validate_voice(wrong,EVENT)
    def test_broken_or_nonjson_llm_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            bad=AtlasNaturalNarrator(runtime_dir=folder,
                runner=lambda args,**kwargs:SimpleNamespace(returncode=0,stdout="I checked."))
            with self.assertRaises(NarrationUnavailable):bad.narrate(EVENT)
            down=AtlasNaturalNarrator(runtime_dir=folder,
                runner=lambda args,**kwargs:SimpleNamespace(returncode=1,stdout=""))
            with self.assertRaises(NarrationUnavailable):down.narrate(EVENT)
if __name__=="__main__":unittest.main()
