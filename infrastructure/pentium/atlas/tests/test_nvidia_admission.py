import unittest
from infrastructure.pentium.atlas.free_model_selection import ModelOffer
from infrastructure.pentium.atlas.nvidia_admission import eligible_nvidia_offers

class NvidiaAdmissionTests(unittest.TestCase):
    def offer(self,price=0,verified=True):
        return ModelOffer("nvidia","model-a",price,price,verified,frozenset({"code"}))
    def test_requires_rotated_credential(self):
        self.assertEqual(eligible_nvidia_offers([self.offer()],task="code",
            authorized={("nvidia","model-a")}),())
    def test_rejects_unverified_or_unknown_cost(self):
        for offer in (self.offer(verified=False),self.offer(price=None),self.offer(price=0.01)):
            self.assertEqual(eligible_nvidia_offers([offer],task="code",
                authorized={("nvidia","model-a")},credential_rotated=True),())
    def test_explicit_verified_zero_cost_admitted(self):
        self.assertEqual(len(eligible_nvidia_offers([self.offer()],task="code",
            authorized={("nvidia","model-a")},credential_rotated=True)),1)
if __name__=="__main__":unittest.main()
