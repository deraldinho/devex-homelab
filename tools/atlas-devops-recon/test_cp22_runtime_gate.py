import unittest
from cp22_runtime_gate import verify_implementation

ROOT = r"C:\Users\deral\Documents\Atlas-DevOps\CP-ATLAS-RECON-20261015"


def valid():
    return {"agent": "build", "outcome": "succeeded",
            "location": {"directory": ROOT}}


class CP22Tests(unittest.TestCase):
    def check(self, session, exists=lambda _: True):
        return verify_implementation(session, expected_project=ROOT,
                                     required_files=["feature.py"], file_exists=exists)

    def test_success_requires_build_terminal_and_artifact(self):
        result = self.check(valid())
        self.assertTrue(result["verified"])
        self.assertFalse(result["production_allowed"])

    def test_plan_agent_never_counts_as_implementation(self):
        session = valid()
        session["agent"] = "plan"
        self.assertIn("NOT_BUILD_AGENT", self.check(session)["reasons"])

    def test_accepted_prompt_does_not_equal_completion(self):
        session = valid()
        session.pop("outcome")
        self.assertFalse(self.check(session)["verified"])

    def test_wrong_project_and_absent_artifact(self):
        session = valid()
        session["location"] = {"directory": r"C:\Users\deral"}
        reasons = self.check(session, lambda _: False)["reasons"]
        self.assertIn("PROJECT_MISMATCH", reasons)
        self.assertIn("ARTIFACT_UNVERIFIED:feature.py", reasons)

    def test_errors_fail_closed(self):
        self.assertFalse(self.check(None)["verified"])
        self.assertFalse(self.check(valid(), lambda _: 1)["verified"])
        def error(_):
            raise OSError("failure")
        self.assertFalse(self.check(valid(), error)["verified"])

    def test_path_traversal_not_accepted(self):
        result = verify_implementation(valid(), expected_project=ROOT,
                                       required_files=["../other.py"], file_exists=lambda _: True)
        self.assertFalse(result["verified"])

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            verify_implementation(valid(), expected_project="", required_files=["x"], file_exists=lambda _: True)
        with self.assertRaises(ValueError):
            verify_implementation(valid(), expected_project=ROOT, required_files=[], file_exists=lambda _: True)


if __name__ == "__main__":
    unittest.main()
