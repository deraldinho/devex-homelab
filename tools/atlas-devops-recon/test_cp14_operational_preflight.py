"""TDD for cp14_operational_preflight.py: read-only operational preflight aggregator.

All observations are caller-injected; no service, network, OS or secret access.
"""
import unittest
from datetime import datetime, timedelta, timezone

import cp14_operational_preflight as pf

T = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)


def healthy_obs(now=T):
    return {
        "x99_w32time": {"state": "running", "start_type": "automatic"},
        "pentium_ntp": {"status": "synchronized"},
        "reference_timestamps": {
            "x99_observed": now,
            "pentium_observed": now,
            "reference_instant": now,
            "capture_time": now,
        },
        "ssh_transport": {"reachable": True},
        "os_sandbox": {"available": True},
        "notification_recipient_ack": {"acked": True, "ack_id": "ack-1"},
        "lease_recovery_rollback": {"recovery_ready": True, "rollback_ready": True},
        "production_hmac_key_provisioning": {
            "provisioned": True, "environment": "production",
            "key_length": 32, "uses_test_key": False,
        },
        "cognitive_service_bridge": {"available": True},
    }


class PreflightTests(unittest.TestCase):
    def test_healthy_ready(self):
        r = pf.operational_preflight(healthy_obs(), now=T)
        self.assertEqual(r["status"], pf.STATUS_READY)
        self.assertTrue(r["ready"])
        self.assertEqual(r["blocks"], [])
        self.assertTrue(r["read_only"])
        self.assertFalse(r["execution_started"])

    def test_x99_w32time_stopped_manual_blocks(self):
        obs = healthy_obs()
        obs["x99_w32time"] = {"state": "stopped", "start_type": "manual"}
        r = pf.operational_preflight(obs, now=T)
        self.assertEqual(r["status"], pf.STATUS_BLOCKED_NOT_READY)
        self.assertFalse(r["ready"])
        self.assertIn(pf.BLOCK_CODES["x99_w32time"], r["blocks"])
        self.assertEqual(r["checks"]["x99_w32time"]["status"], "FAIL")

    def test_historic_drift_blocks(self):
        obs = healthy_obs()
        obs["reference_timestamps"]["pentium_observed"] = T + timedelta(seconds=120)
        obs["reference_timestamps"]["reference_instant"] = T + timedelta(seconds=120)
        r = pf.operational_preflight(obs, now=T + timedelta(seconds=120))
        self.assertEqual(r["status"], pf.STATUS_BLOCKED_NOT_READY)
        self.assertIn(pf.BLOCK_CODE_HISTORIC_DRIFT, r["blocks"])

    def test_missing_observation_fail_closed(self):
        r = pf.operational_preflight({}, now=T)
        self.assertEqual(r["status"], pf.STATUS_BLOCKED_NOT_READY)
        self.assertIn(pf.BLOCK_CODE_MISSING_OBSERVATION, r["blocks"])

    def test_individual_blockers(self):
        cases = [
            ("pentium_ntp", {"status": "unhealthy"}, pf.BLOCK_CODES["pentium_ntp"]),
            ("ssh_transport", {"reachable": False}, pf.BLOCK_CODES["ssh_transport"]),
            ("os_sandbox", {"available": False}, pf.BLOCK_CODES["os_sandbox"]),
            ("notification_recipient_ack", {"acked": False}, pf.BLOCK_CODES["notification_recipient_ack"]),
            ("lease_recovery_rollback", {"recovery_ready": False, "rollback_ready": True}, pf.BLOCK_CODES["lease_recovery_rollback"]),
            ("cognitive_service_bridge", {"available": False}, pf.BLOCK_CODES["cognitive_service_bridge"]),
        ]
        for key, val, code in cases:
            obs = healthy_obs()
            obs[key] = val
            r = pf.operational_preflight(obs, now=T)
            self.assertIn(code, r["blocks"], msg=key)

    def test_production_key_not_provisioned_blocks(self):
        obs = healthy_obs()
        obs["production_hmac_key_provisioning"] = {
            "provisioned": False, "environment": "production", "key_length": 32,
        }
        r = pf.operational_preflight(obs, now=T)
        self.assertIn(pf.BLOCK_CODES["production_hmac_key_provisioning"], r["blocks"])

    def testProductionKeyTestKeyBlocks(self):
        obs = healthy_obs()
        obs["production_hmac_key_provisioning"] = {
            "provisioned": True, "environment": "production",
            "key_length": 32, "uses_test_key": True,
        }
        r = pf.operational_preflight(obs, now=T)
        self.assertIn(pf.BLOCK_CODES["production_hmac_key_provisioning"], r["blocks"])

    def test_aliases_and_kwargs(self):
        obs = healthy_obs()
        r1 = pf.run_preflight(obs, now=T)
        r2 = pf.preflight(obs, now=T)
        r3 = pf.operational_preflight(observations=obs, now=T)
        self.assertTrue(r1["ready"])
        self.assertTrue(r2["ready"])
        self.assertTrue(r3["ready"])
        # kwargs flatten style
        r4 = pf.operational_preflight(**obs, now=T)
        self.assertTrue(r4["ready"])

    def test_capture_stale_blocks(self):
        obs = healthy_obs()
        obs["reference_timestamps"]["capture_time"] = T - timedelta(seconds=600)
        r = pf.operational_preflight(obs, now=T)
        self.assertIn(pf.BLOCK_CODE_CAPTURE_STALE, r["blocks"])

    def test_no_auto_remediation_fields(self):
        obs = healthy_obs()
        obs["x99_w32time"] = {"state": "stopped", "start_type": "manual"}
        r = pf.operational_preflight(obs, now=T)
        self.assertFalse(r.get("auto_remediated", False))
        self.assertFalse(r.get("service_restarted", False))
        self.assertFalse(r.get("services_restarted", False))

    def test_flat_input(self):
        obs = {
            "x99_w32time_state": "running",
            "x99_start_type": "automatic",
            "pentium_ntp_status": "synchronized",
        }
        # missing others -> blocked, but x99 check can parse flat alias? status x99 may still pass-ish
        r = pf.operational_preflight(obs, now=T)
        self.assertEqual(r["status"], pf.STATUS_BLOCKED_NOT_READY)


if __name__ == "__main__":
    unittest.main()
