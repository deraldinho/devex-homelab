import unittest
from atlas_opencode_session_gate import evaluate
class SessionGateTests(unittest.TestCase):
    def test_shell_is_blocked_even_if_session_cost_zero(self):
        messages=[{"type":"assistant","finish":"tool-calls","content":[{"type":"tool","name":"shell"}]}]
        self.assertEqual(evaluate({"cost":0},messages)["reason"],"UNAUTHORIZED_TOOL_USED")
    def test_tool_calls_are_not_completion(self):
        messages=[{"type":"assistant","finish":"tool-calls","content":[{"type":"tool","name":"read"}]}]
        self.assertEqual(evaluate({"cost":0},messages)["status"],"PENDING")
    def test_text_final_still_requires_independent_validation(self):
        messages=[{"type":"assistant","finish":"stop","content":[{"type":"text","text":"Review evidence with concrete findings and specific symbols that require independent verification."}]}]
        self.assertEqual(evaluate({"cost":0},messages)["status"],"REVIEW_CANDIDATE")
    def test_cost_not_proven_blocks(self):
        messages=[{"type":"assistant","finish":"stop","content":[{"type":"text","text":"Review evidence with concrete findings and specific symbols that require independent verification."}]}]
        self.assertEqual(evaluate({},messages)["status"],"BLOCKED")
