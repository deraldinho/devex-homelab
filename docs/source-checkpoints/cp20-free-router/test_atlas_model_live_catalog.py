import unittest
from atlas_model_live_catalog import discover_catalog,free_fallback_order
from atlas_model_failover import FREE_MODELS

class LiveCatalogTests(unittest.TestCase):
    def test_deduplicated_catalog(self):
        self.assertEqual(discover_catalog(lambda:"opencode/x\nopencode/x\nnonsense\n"),("opencode/x",))
    def test_no_attestation_no_models(self):
        found=free_fallback_order(trusted_pricing={},task="code",allowed=FREE_MODELS,
                    catalog_run=lambda:"opencode/mimo-v2.6-flash-free\n")
        self.assertEqual(found,())
    def test_verified_zero_price_selected(self):
        pricing={"mimo-v2.6-flash-free":{"verified":True,"input_price":0,"output_price":0,"capabilities":["code"]}}
        found=free_fallback_order(trusted_pricing=pricing,task="code",allowed=FREE_MODELS,
                    catalog_run=lambda:"opencode/mimo-v2.6-flash-free\n")
        self.assertEqual(found,("mimo-v2.6-flash-free",))
    def test_provider_not_in_allowlist_denied(self):
        pricing={"x":{"verified":True,"input_price":0,"output_price":0,"capabilities":["code"]}}
        found=free_fallback_order(trusted_pricing=pricing,task="code",allowed=FREE_MODELS,
                    catalog_run=lambda:"opencode/x\n")
        self.assertEqual(found,())
if __name__=="__main__":unittest.main()
