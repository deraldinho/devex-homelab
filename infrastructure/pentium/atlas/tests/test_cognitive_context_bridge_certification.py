import unittest

from infrastructure.pentium.atlas.cognitive_context_bridge_certification import (
    CognitiveContextBridgePhysicalEvidence,
    certify_cognitive_context_bridge,
)

SHA = "1" * 40


class CognitiveContextBridgeCertificationTest(unittest.TestCase):
    def good(self, **overrides):
        data = dict(
            expected_sha=SHA, observed_sha=SHA,
            observation_service_state="active",
            voice_service_state="inactive", voice_service_enabled="disabled",
            health={"schema_version": 1, "status": "healthy", "expected_sha": SHA,
                    "cognitive_bridge": {"current_error": None, "last_publish_stimulus_id": "s1"}},
            snapshot={"schema_version": 1, "expected_sha": SHA, "source_stimulus_id": "s1",
                      "entity_id": "x99", "perception": {"entidade_id": "x99"}},
            snapshot_age_ok=True, state_matches=True, cli_real_context_ok=True,
            fail_safe_ok=True, restart_projection_ok=True,
        )
        data.update(overrides)
        return CognitiveContextBridgePhysicalEvidence(**data)

    def test_full_evidence_emits_physical_pass(self):
        result = certify_cognitive_context_bridge(self.good())
        self.assertTrue(result.physical_pass)
        self.assertEqual((), result.failures)
        self.assertEqual("ATLAS_COGNITIVE_CONTEXT_BRIDGE_PHYSICAL_PASS", result.marker)

    def test_sha_voice_health_snapshot_and_proofs_are_mandatory(self):
        bad_health = {"schema_version": 1, "status": "degraded", "expected_sha": SHA,
                      "cognitive_bridge": {"current_error": "publish:OSError", "last_publish_stimulus_id": "s1"}}
        result = certify_cognitive_context_bridge(self.good(
            observed_sha="2" * 40,
            observation_service_state="failed",
            voice_service_state="active", voice_service_enabled="enabled",
            health=bad_health, snapshot_age_ok=False, state_matches=False,
            cli_real_context_ok=False, fail_safe_ok=False, restart_projection_ok=False,
        ))
        for failure in (
            "sha_mismatch", "observation_service_not_active", "voice_service_not_inactive",
            "voice_service_not_disabled", "health_not_healthy", "bridge_error_present",
            "snapshot_stale", "state_mismatch", "cli_real_context_not_proven",
            "fail_safe_not_proven", "restart_projection_not_proven",
        ):
            self.assertIn(failure, result.failures)

    def test_snapshot_must_match_sha_source_and_entity_and_omit_technical_state(self):
        snapshot = {"schema_version": 1, "expected_sha": "2" * 40,
                    "source_stimulus_id": "other", "entity_id": "x99",
                    "perception": {"entidade_id": "core"}, "technical_state": "healthy"}
        result = certify_cognitive_context_bridge(self.good(snapshot=snapshot))
        self.assertIn("snapshot_sha_mismatch", result.failures)
        self.assertIn("snapshot_stimulus_mismatch", result.failures)
        self.assertIn("snapshot_entity_mismatch", result.failures)
        self.assertIn("snapshot_contains_technical_state", result.failures)


if __name__ == "__main__":
    unittest.main()


class CognitiveContextBridgeVoiceEnabledCertificationTest(unittest.TestCase):
    def test_accepts_active_enabled_voice_when_expected(self):
        base = CognitiveContextBridgeCertificationTest().good(
            voice_service_state="active",
            voice_service_enabled="enabled",
        )
        evidence = CognitiveContextBridgePhysicalEvidence(
            **{**base.__dict__, "voice_expected_active": True}
        )
        result = certify_cognitive_context_bridge(evidence)
        self.assertTrue(result.physical_pass)
        self.assertEqual((), result.failures)

    def test_rejects_inactive_voice_when_active_is_expected(self):
        base = CognitiveContextBridgeCertificationTest().good()
        evidence = CognitiveContextBridgePhysicalEvidence(
            **{**base.__dict__, "voice_expected_active": True}
        )
        result = certify_cognitive_context_bridge(evidence)
        self.assertFalse(result.physical_pass)
        self.assertIn("voice_service_not_active", result.failures)
        self.assertIn("voice_service_not_enabled", result.failures)
