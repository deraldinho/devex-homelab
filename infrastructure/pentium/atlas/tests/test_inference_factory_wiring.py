"""Contract tests: production keeps Hermes default and supports explicit opt-in."""
import inspect
import unittest
from pathlib import Path
from infrastructure.pentium.atlas import cognitive_daemon

class InferenceFactoryWiringTests(unittest.TestCase):
    def test_factory_opt_in_defaults_to_hermes(self):
        signature=inspect.signature(cognitive_daemon.build_owner)
        self.assertIsNone(signature.parameters["inference_backend_factory"].default)
    def test_factory_selection_is_explicit_and_validated(self):
        source=inspect.getsource(cognitive_daemon.build_owner)
        self.assertIn("HermesAdapter(hermes) if inference_backend_factory is None",source)
        self.assertIn("inference_backend_factory(hermes)",source)
        self.assertIn("callable(getattr(backend, 'inferir', None))",source)
    def test_no_automatic_paid_fallback(self):
        from infrastructure.pentium.atlas.free_model_selection import ModelOffer,select_free_models
        paid=ModelOffer("nvidia","unpriced",None,None,False,frozenset({"code"}))
        self.assertEqual(select_free_models([paid],task="code",
                         authorized=frozenset({("nvidia","unpriced")})),())
if __name__=="__main__":unittest.main()
