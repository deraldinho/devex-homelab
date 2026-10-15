import unittest
from atlas_model_ranker import ModelProfile
from atlas_model_router_adapter import make_free_ranker
from atlas_model_failover import FREE_MODELS

class ModelRouterAdapterTests(unittest.TestCase):
    def profile(self,name,quality=0,price=0,verified=True):
        return ModelProfile(name,price,price,verified,frozenset({'code'}),quality,100)
    def test_verified_quality_order(self):
        rank=make_free_ranker([self.profile(FREE_MODELS[0],1),self.profile(FREE_MODELS[1],9)],task='code')
        self.assertEqual(rank(FREE_MODELS[:2]),(FREE_MODELS[1],FREE_MODELS[0]))
    def test_unapproved_profile_filtered(self):
        rank=make_free_ranker([self.profile('other-provider/model',10)],task='code')
        self.assertEqual(rank(FREE_MODELS),())
    def test_unknown_cost_not_selected(self):
        rank=make_free_ranker([self.profile(FREE_MODELS[0],9,price=None)],task='code')
        self.assertEqual(rank(FREE_MODELS),())
    def test_paid_not_selected(self):
        rank=make_free_ranker([self.profile(FREE_MODELS[0],10,price=1)],task='code')
        self.assertEqual(rank(FREE_MODELS),())
if __name__=='__main__':unittest.main()
