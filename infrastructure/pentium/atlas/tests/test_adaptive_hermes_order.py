import json
from urllib import error
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.adaptive_model_health import AdaptiveModelHealth,ModelSignal
from infrastructure.pentium.atlas.adaptive_hermes_order import adaptive_order,plan,read_catalogs,read_hermes_usage

MANIFEST={"schema_version":1,"nous_free":["upstage/solar-mini4:free"],
          "nvidia_free_prototype":["google/gemma-4-31b-it"]}
CHAIN=[
  {"provider":"nous","model":"stepfun/step-5-preview:free"},
  {"provider":"nous","model":"upstage/solar-mini4:free"},
  {"provider":"nvidia","model":"nvidia/nemotron-3.5-lightning-30b-a3b","base_url":"https://integrate.api.nvidia.com/v1"},
  {"provider":"nvidia","model":"google/gemma-4-31b-it","base_url":"https://integrate.api.nvidia.com/v1"}]
def yaml_config():
    import yaml
    return yaml.safe_dump({"model":{"provider":"nous","default":"preserved"},
      "fallback_providers":CHAIN,"other":{"enabled":True}},sort_keys=False)

class AdaptiveHermesOrderTests(unittest.TestCase):
    def test_catalog_read_only_no_leak_and_reject_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"auth.json"
            p.write_text(json.dumps({"credential_pool":{"nvidia":[{"priority":0,
                "access_token":"nvapi-dummy-not-real"}]}}))
            captured=[]
            def fetch(url,headers):
                captured.append((url,headers.get("Authorization","")))
                if "nous" in url:
                    return {"freeRecommendedModels":[{"modelName":"upstage/solar-mini4:free"},{"modelName":"stepfun/step-5-preview:free"}]}
                return {"data":[{"id":"google/gemma-4-31b-it"},{"id":"nvidia/nemotron-3.5-lightning-30b-a3b"}]}
            nous,nvidia=read_catalogs(p,fetch=fetch)
            self.assertEqual(len(nous),2)
            self.assertEqual(len(nvidia),2)
            self.assertTrue(captured[1][1].startswith("Bearer "))
            with self.assertRaises(ValueError):
                read_catalogs(p,fetch=lambda url,headers:{})
    def test_catalog_falls_back_to_next_local_credential(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'auth.json'
            p.write_text(json.dumps({'credential_pool':{'nvidia':[
                {'priority':0,'access_token':'nvapi-revoked'},
                {'priority':1,'access_token':'nvapi-working'}]}}))
            attempts=[]
            def fetch(url,headers):
                if 'nous' in url:
                    return {'freeRecommendedModels':[{'id':'upstage/solar-mini4:free'}]}
                token=headers['Authorization']
                attempts.append(token.endswith('working'))
                if not attempts[-1]:
                    raise error.HTTPError(url,401,'unauthorized',{},None)
                return {'data':[{'id':'google/gemma-4-31b-it'}]}
            catalog=read_catalogs(p,fetch=fetch)
            self.assertEqual(attempts,[False,True])
            self.assertIn('google/gemma-4-31b-it',catalog[1])
    def test_missing_model_demoted_without_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            h=AdaptiveModelHealth(Path(folder)/"store.sqlite3")
            catalog=({"upstage/solar-mini4:free"},{"google/gemma-4-31b-it"})
            sorted_entries=adaptive_order(CHAIN,catalog=catalog,health=h)
            self.assertEqual(len(sorted_entries),4)
            self.assertEqual(sorted_entries[0]["model"],"upstage/solar-mini4:free")
            self.assertEqual(sorted_entries[2]["model"],"google/gemma-4-31b-it")
            self.assertEqual(sorted_entries[3]["model"],"nvidia/nemotron-3.5-lightning-30b-a3b")
            updated,entries=plan(yaml_config(),MANIFEST,catalog,h,{})
            self.assertIn("default: preserved",updated)
            self.assertEqual(plan(updated,MANIFEST,catalog,h,{})[0],updated)
    def test_quality_promotes_only_with_graded_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            h=AdaptiveModelHealth(Path(folder)/"store.sqlite3")
            catalog=({"upstage/solar-mini4:free","stepfun/step-5-preview:free"},
                     {"google/gemma-4-31b-it","nvidia/nemotron-3.5-lightning-30b-a3b"})
            for i in range(3):
                h.record_evaluation("nous","upstage/solar-mini4:free","general",f"case{i}",True)
            changed=adaptive_order(CHAIN,catalog=catalog,health=h)
            self.assertEqual(changed[0]["model"],"upstage/solar-mini4:free")
    def test_rate_limit_demotes_but_keeps_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            h=AdaptiveModelHealth(Path(folder)/"store.sqlite3")
            h.record(ModelSignal("nous","stepfun/step-5-preview:free",False,100,"rate_limit"))
            catalog=({"upstage/solar-mini4:free","stepfun/step-5-preview:free"},
                     {"google/gemma-4-31b-it","nvidia/nemotron-3.5-lightning-30b-a3b"})
            new=adaptive_order(CHAIN,catalog=catalog,health=h)
            self.assertEqual(new[0]["model"],"upstage/solar-mini4:free")
            self.assertIn(CHAIN[0],new)
    def test_refuses_unrecognized_model(self):
        with tempfile.TemporaryDirectory() as folder:
            h=AdaptiveModelHealth(Path(folder)/"store.sqlite3")
            data=yaml_config().replace("upstage/solar-mini4:free","unknown/not-reviewed")
            with self.assertRaises(ValueError):
                plan(data,MANIFEST,(set(),set()),h,{})
    def test_readonly_usage_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"state.db"
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("CREATE TABLE session_model_usage(billing_provider TEXT,model TEXT,api_call_count INTEGER,last_seen REAL)")
                db.execute("INSERT INTO session_model_usage VALUES(?,?,?,?)",
                    ("nous","stepfun/step-5-preview:free",3,1800000000.0))
            data=read_hermes_usage(p,now=1800000010)
            self.assertEqual(data[("nous","stepfun/step-5-preview:free")],3)
            self.assertEqual(read_hermes_usage(p,now=1800800000),{})
if __name__=="__main__":unittest.main()
