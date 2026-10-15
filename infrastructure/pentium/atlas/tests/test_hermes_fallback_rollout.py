import json,unittest
from infrastructure.pentium.atlas.hermes_fallback_rollout import plan
class HermesRolloutTests(unittest.TestCase):
    def test_plan_extends_both_without_changing_primary(self):
        config="""model:
  provider: nous
  default: original-free
fallback_providers:
- provider: nous
  model: poolside/laguna-s-2.1:free
- provider: nvidia
  model: nvidia/nemotron-3.5-lightning-30b-a3b
memory:
  enabled: true
"""
        manifest={"schema_version":1,"nous_free":["stepfun/step-3.7-flash:free"],
                  "nvidia_free_prototype":["google/gemma-4-31b-it"]}
        rendered,chain=plan(config,manifest)
        self.assertEqual(len(chain),4)
        self.assertIn("default: original-free",rendered)
        self.assertIn("memory:\n  enabled: true",rendered)
        self.assertEqual(plan(rendered,manifest)[1],chain)
    def test_rejects_bad_manifest(self):
        with self.assertRaises(ValueError):plan("model:\n  provider: nous\n",{})
if __name__=="__main__":unittest.main()
