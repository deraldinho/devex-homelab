import unittest
from cp20_evidence_gate import evaluate_evidence, SCHEMA
from atlas_native_readiness import REQUIRED_EVIDENCE


def all_receipts():
    return {key: {"schema": SCHEMA, "checkpoint": "CP20",
                  "receipt": "signed:" + key, "verified": True}
            for key in REQUIRED_EVIDENCE}


class CP20EvidenceGateTests(unittest.TestCase):
    def test_self_reported_evidence_cannot_authorize(self):
        result = evaluate_evidence(all_receipts(), checkpoint="CP20")
        self.assertEqual("BLOCKED", result["status"])
        self.assertFalse(result["production_allowed"])
        self.assertEqual(len(REQUIRED_EVIDENCE), len(result["rejected"]))

    def test_trusted_verifier_is_required_for_each_category(self):
        calls = []
        def verify(category, receipt, checkpoint):
            calls.append(category)
            return receipt == "signed:" + category and checkpoint == "CP20"
        result = evaluate_evidence(all_receipts(), checkpoint="CP20", verifier=verify)
        self.assertEqual("EVIDENCE_VERIFIED_REQUIRES_AUTHORIZATION", result["status"])
        self.assertFalse(result["production_allowed"])
        self.assertEqual(set(REQUIRED_EVIDENCE), set(calls))

    def test_wrong_checkpoint_rejected_without_verifier_call(self):
        result = evaluate_evidence(all_receipts(), checkpoint="CP21",
                                   verifier=lambda *_: self.fail("must not call verifier"))
        self.assertEqual(len(REQUIRED_EVIDENCE), len(result["rejected"]))

    def test_missing_and_malformed_receipts_rejected(self):
        cases = [None, {}, {"schema": SCHEMA, "checkpoint": "CP20", "receipt": ""}]
        for item in cases:
            evidence = all_receipts()
            evidence[REQUIRED_EVIDENCE[0]] = item
            with self.subTest(item=item):
                result = evaluate_evidence(evidence, checkpoint="CP20",
                                           verifier=lambda *_: True)
                self.assertEqual("BLOCKED", result["status"])

    def test_verifier_exception_and_truthy_nonboolean_fail_closed(self):
        for verifier in [lambda *_: 1, lambda *_: (_ for _ in ()).throw(RuntimeError("invalid"))]:
            with self.subTest(verifier=verifier):
                self.assertEqual("BLOCKED", evaluate_evidence(
                    all_receipts(), checkpoint="CP20", verifier=verifier)["status"])

    def test_invalid_checkpoint_and_evidence_type(self):
        with self.assertRaises(ValueError):
            evaluate_evidence({}, checkpoint="")
        with self.assertRaises(TypeError):
            evaluate_evidence([], checkpoint="CP20")


if __name__ == "__main__":
    unittest.main()
