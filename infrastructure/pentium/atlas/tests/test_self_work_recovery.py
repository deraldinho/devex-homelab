"""TDD: RECOVERING state for SelfWorkRuntime - failed task recovery."""
import unittest

from infrastructure.pentium.atlas.self_work import (
    SelfWorkRuntime,
    SelfWorkState,
)


class SelfWorkRecoveryTests(unittest.TestCase):
    def runtime(self, *, ttl_s=300, max_operations=3, max_inferences=2):
        ids = iter(("sw-1", "sw-2"))
        return SelfWorkRuntime(
            ttl_s=ttl_s,
            max_operations=max_operations,
            max_inferences=max_inferences,
            id_factory=lambda: next(ids),
        )

    def test_recovery_state_transition_from_working(self):
        """SelfWorkRuntime should support transitioning to RECOVERING state from WORKING."""
        runtime = self.runtime()
        runtime.propose("revisar arquitetura", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")

        # Transition to RECOVERING state (new state for failed tasks)
        recovered = runtime.recover(now="2026-10-16T17:00:03+00:00")
        self.assertEqual(SelfWorkState.RECOVERING, recovered.state)
        self.assertIsNotNone(runtime.current)

    def test_recovery_state_is_terminal_for_retry_without_intervention(self):
        """RECOVERING state should allow transitioning back to WORKING for retry."""
        runtime = self.runtime()
        runtime.propose("revisar arquitetura", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")

        # Transition to RECOVERING
        recovered = runtime.recover(now="2026-10-16T17:00:03+00:00")
        self.assertEqual(SelfWorkState.RECOVERING, recovered.state)

        # From RECOVERING, should be able to go back to WORKING
        restarted = runtime.begin_retry(now="2026-10-16T17:00:04+00:00")
        self.assertEqual(SelfWorkState.WORKING, restarted.state)

    def test_recovery_state_preserved_in_snapshot(self):
        """Snapshot should include RECOVERING state."""
        runtime = self.runtime()
        runtime.propose("test recovery", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")

        recovered = runtime.recover(now="2026-10-16T17:00:03+00:00")
        snap = runtime.snapshot()
        self.assertIn("state", snap)
        self.assertEqual(snap["state"], "RECOVERING")

    def test_multiple_recovery_attempts(self):
        """Should allow multiple recovery attempts."""
        runtime = self.runtime()
        runtime.propose("multiple recovery test", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")

        # First recovery
        r1 = runtime.recover(now="2026-10-16T17:00:03+00:00")
        self.assertEqual(SelfWorkState.RECOVERING, r1.state)

        # Retry enters WORKING again before another recovery can begin.
        runtime.begin_retry(now="2026-10-16T17:00:04+00:00")
        r2 = runtime.recover(now="2026-10-16T17:00:05+00:00")
        self.assertEqual(SelfWorkState.RECOVERING, r2.state)

    def test_retry_without_recovery_is_denied(self):
        runtime = self.runtime()
        runtime.propose("retry guard", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        with self.assertRaises(RuntimeError):
            runtime.begin_retry(now="2026-10-16T17:00:02+00:00")
        self.assertEqual(SelfWorkState.ACTIVE, runtime.current.state)

    def test_expired_recovery_cannot_be_resumed(self):
        runtime = self.runtime(ttl_s=2)
        runtime.propose("expiring repair", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")
        runtime.recover(now="2026-10-16T17:00:02+00:00")
        done = runtime.begin_retry(now="2026-10-16T17:00:04+00:00")
        self.assertEqual(SelfWorkState.EXPIRED, done.state)
        self.assertIsNone(runtime.current)

    def test_recovery_before_working_not_allowed(self):
        """Should not allow recovery transition before beginning work."""
        runtime = self.runtime()
        runtime.propose("premature recovery", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")

        # State is ACTIVE after activate(), not WORKING - recovery not allowed
        with self.assertRaises(RuntimeError):
            runtime.recover(now="2026-10-16T17:00:02+00:00")

    def test_recovery_after_complete_not_allowed(self):
        """RECOVERING should not be possible after COMPLETED state (task is terminal)."""
        runtime = self.runtime()
        runtime.propose("test recovery after complete", "engineering", now="2026-10-16T17:00:00+00:00")
        runtime.activate(now="2026-10-16T17:00:01+00:00")
        runtime.begin_work(now="2026-10-16T17:00:02+00:00")
        runtime.review(now="2026-10-16T17:00:03+00:00")
        done = runtime.complete(now="2026-10-16T17:00:04+00:00")
        self.assertEqual(SelfWorkState.COMPLETED, done.state)
        self.assertIsNone(runtime.current)
        # After complete, recovery should not be allowed (task is terminal)
        with self.assertRaises(RuntimeError):
            runtime.recover(now="2026-10-16T17:00:05+00:00")


if __name__ == "__main__":
    unittest.main()