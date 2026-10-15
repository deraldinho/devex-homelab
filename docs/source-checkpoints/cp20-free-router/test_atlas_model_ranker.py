import unittest
from atlas_model_ranker import ModelProfile,rank_models

class RankerTests(unittest.TestCase):
    def p(self,name,price=0,verified=True,quality=0,latency=100):
        return ModelProfile(name,price,price,verified,frozenset({'code'}),quality,latency)
    def test_zero_cost_and_quality_first(self):
        got=rank_models([self.p('slow',quality=5),self.p('fast',quality=9),self.p('paid',price=1,quality=10)],task='code')
        self.assertEqual([m.model for m in got],['fast','slow'])
    def test_unknown_price_excluded(self):
        self.assertEqual(rank_models([self.p('unknown',price=None)],task='code'),[])
    def test_unknown_entitlement_excluded(self):
        self.assertEqual(rank_models([self.p('nvidia',verified=False)],task='code'),[])
    def test_wrong_capability_excluded(self):
        self.assertEqual(rank_models([self.p('coder')],task='vision'),[])
    def test_quota_excluded(self):
        p=self.p('busy')
        self.assertEqual(rank_models([ModelProfile(**{**p.__dict__,'quota_remaining':False})],task='code'),[])
    def test_negative_token_count(self):
        with self.assertRaises(ValueError):rank_models([],task='code',input_tokens=-1)

if __name__=='__main__':unittest.main()
