import unittest
import tempfile
from pathlib import Path
from infrastructure.pentium.atlas.hermes_fallback_expansion import extend_fallbacks,replace_fallback_yaml,atomic_backup_and_write

OLD=[{"provider":"nous","model":"stepfun/step-5-preview:free"},
     {"provider":"nous","model":"poolside/laguna-s-2.1:free"},
     {"provider":"nvidia","model":"nvidia/nemotron-3.5-lightning-30b-a3b",
      "base_url":"https://integrate.api.nvidia.com/v1"}]
YAML="""model:
  provider: nous
  default: original-free
other_setting:
  enabled: true
fallback_providers:
  - provider: nous
    model: stepfun/step-5-preview:free
  - provider: nous
    model: poolside/laguna-s-2.1:free
  - provider: nvidia
    model: nvidia/nemotron-3.5-lightning-30b-a3b
    base_url: https://integrate.api.nvidia.com/v1
memory:
  summary: on
"""

class FallbackExpansionTests(unittest.TestCase):
    def test_keeps_primary_and_existing_and_adds_models_in_order(self):
        new=extend_fallbacks(OLD,["upstage/solar-mini4:free"],
              ["google/gemma-4-31b-it"])
        self.assertEqual([x["provider"] for x in new],["nous","nous","nous","nvidia","nvidia"])
        self.assertEqual(new[3],OLD[2])
        self.assertEqual(new[-1]["base_url"],"https://integrate.api.nvidia.com/v1")
        transformed=replace_fallback_yaml(YAML,new)
        self.assertIn("default: original-free",transformed)
        self.assertIn("memory:\n  summary: on",transformed)
    def test_idempotent(self):
        first=extend_fallbacks(OLD,["upstage/solar-mini4:free"],["google/gemma-4-31b-it"])
        second=extend_fallbacks(first,["upstage/solar-mini4:free"],["google/gemma-4-31b-it"])
        self.assertEqual(first,second)
    def test_rejects_paid_or_unsafe_models(self):
        with self.assertRaises(ValueError):extend_fallbacks(OLD,["openai/gpt-6"],[])
        with self.assertRaises(ValueError):extend_fallbacks(OLD,[],["thing;rm -rf /"])
    def test_rejects_modified_primary(self):
        with self.assertRaises(ValueError):replace_fallback_yaml(YAML.replace("provider: nous\n  default","provider: nvidia\n  default"),OLD)
    def test_rejects_duplicate(self):
        with self.assertRaises(ValueError):extend_fallbacks(OLD+OLD,[],[])
    def test_backup_is_preserved_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.yaml'
            config.write_text(YAML,encoding='utf-8')
            backup=atomic_backup_and_write(config,YAML+'\n# extra\n')
            self.assertEqual(backup.read_text(encoding='utf-8'),YAML)
            self.assertIn('# extra',config.read_text(encoding='utf-8'))
            self.assertNotEqual(config,backup)
    def test_does_not_modify_unrelated_top_level(self):
        new=extend_fallbacks(OLD,["upstage/solar-mini4:free"],[])
        t=replace_fallback_yaml(YAML,new)
        self.assertIn("other_setting:\n  enabled: true",t)
        self.assertIn("fallback_providers:",t)
if __name__=="__main__":unittest.main()
