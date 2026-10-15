import unittest
from atlas_model_discovery import build_profiles,summarize_usage
class InventoryTests(unittest.TestCase):
    def test_listing_is_not_free_entitlement(self):
        self.assertEqual(build_profiles(["nvidia/z-ai/glm-5.3-flash"],{}),[])
    def test_explicit_entitlement(self):
        meta={"mimo-v2.6-flash-free":{"verified":True,"input_price":0,"output_price":0,"capabilities":["code"]}}
        result=build_profiles(["opencode/mimo-v2.6-flash-free"],meta)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].model,"mimo-v2.6-flash-free")
    def test_paid_or_unverified_denied(self):
        meta={"x":{"verified":False,"input_price":0,"output_price":0,"capabilities":["code"]},
              "y":{"verified":True,"input_price":0,"output_price":2,"capabilities":["code"]}}
        self.assertEqual(build_profiles(["opencode/x","opencode/y"],meta),[])
    def test_usage_from_provider_only(self):
        usage=summarize_usage([{"usage":{"input_tokens":20,"output_tokens":10,"cache_read_tokens":3}},
                               {"usage":{"input_tokens":-3,"output_tokens":1,"cache_read_tokens":0}}])
        self.assertEqual(usage["samples"],1)
        self.assertEqual(usage["input_tokens"],20)
if __name__=="__main__":unittest.main()
