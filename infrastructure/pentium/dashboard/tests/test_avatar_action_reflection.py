import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class AvatarActionReflectionTests(unittest.TestCase):
    def test_engine_uses_semantic_arm_side_and_posture(self):
        engine=(ROOT/'atlas-avatar-engine.js').read_text(encoding='utf-8')
        self.assertIn('lado_gesto',engine)
        self.assertIn('postura_atual',engine)
        self.assertIn('semanticPosture',engine)
        self.assertIn("side==='left'",engine)
        self.assertIn("side==='right'",engine)

    def test_visual_contract_contains_semantic_fields(self):
        model=(ROOT.parent/'atlas'/'modelo_visual_atlas.py').read_text(encoding='utf-8')
        self.assertIn('postura_atual',model)
        self.assertIn('lado_gesto',model)

if __name__=='__main__': unittest.main()
