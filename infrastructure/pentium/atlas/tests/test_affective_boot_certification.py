import unittest

from infrastructure.pentium.atlas.affective_boot_certification import (
    AffectiveBootPhysicalEvidence,
    certify_affective_boot,
)

SHA = "1" * 40


class AffectiveBootCertificationTests(unittest.TestCase):
    def good(self, **overrides):
        data = dict(
            expected_sha=SHA,
            observed_sha=SHA,
            observation_service_state="active",
            voice_service_state="inactive",
            voice_state_accepted=True,
            health={"schema_version": 1, "status": "healthy", "expected_sha": SHA,
                    "restoration": {"a1": "estado_salvo", "a2": "estado_salvo",
                                    "a3": "estado_salvo", "a4": "estado_salvo"}},
            visual={"versao_avatar": 1},
            ipc_ok=True,
            restart_restore_ok=True,
            real_observation_ok=True,
        )
        data.update(overrides)
        return AffectiveBootPhysicalEvidence(**data)

    def test_full_evidence_emits_physical_pass(self):
        result = certify_affective_boot(self.good())
        self.assertTrue(result.physical_pass)
        self.assertEqual((), result.failures)
        self.assertEqual("ATLAS_AFFECTIVE_BOOT_PHYSICAL_PASS", result.marker)

    def test_sha_mismatch_blocks_pass(self):
        result = certify_affective_boot(self.good(observed_sha="2" * 40))
        self.assertFalse(result.physical_pass)
        self.assertIn("sha_mismatch", result.failures)

    def test_missing_ipc_or_restore_or_real_observation_blocks_pass(self):
        result = certify_affective_boot(self.good(ipc_ok=False, restart_restore_ok=False,
                                                  real_observation_ok=False))
        self.assertFalse(result.physical_pass)
        self.assertIn("ipc_not_proven", result.failures)
        self.assertIn("restart_restore_not_proven", result.failures)
        self.assertIn("real_observation_not_proven", result.failures)

    def test_bad_health_or_services_block_pass(self):
        result = certify_affective_boot(self.good(
            observation_service_state="failed",
            voice_state_accepted=False,
            health={"schema_version": 1, "status": "degraded", "expected_sha": SHA,
                    "restoration": {}},
            visual={"versao_avatar": 2},
        ))
        self.assertFalse(result.physical_pass)
        self.assertIn("observation_service_not_active", result.failures)
        self.assertIn("voice_state_not_accepted", result.failures)
        self.assertIn("health_not_healthy", result.failures)
        self.assertIn("visual_schema_invalid", result.failures)


if __name__ == "__main__":
    unittest.main()
