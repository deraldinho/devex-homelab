import unittest
from atlas_native_readiness import evaluate,REQUIRED_EVIDENCE
class ReadinessTests(unittest.TestCase):
    def test_missing_blocks(self):
        report=evaluate({})
        self.assertEqual(report["status"],"BLOCKED")
        self.assertFalse(report["production_allowed"])
        self.assertEqual(len(report["missing"]),len(REQUIRED_EVIDENCE))
    def test_unverified_blocks(self):
        evidence={k:{"verified":False,"receipt":"fake"} for k in REQUIRED_EVIDENCE}
        self.assertEqual(evaluate(evidence)["status"],"BLOCKED")
    def test_claimed_receipts_not_equivalent_to_production(self):
        evidence={k:{"verified":True,"receipt":"fixture"} for k in REQUIRED_EVIDENCE}
        self.assertEqual(evaluate(evidence)["status"],"EVIDENCE_PRESENT_REQUIRES_VERIFICATION")
        self.assertFalse(evaluate(evidence)["production_allowed"])
