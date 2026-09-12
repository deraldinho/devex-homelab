import unittest

from infrastructure.pentium.atlas.self_work import (
    SelfWorkRuntime,
    SelfWorkState,
)


class SelfWorkRuntimeTests(unittest.TestCase):
    def runtime(self, *, ttl_s=300, max_operations=3, max_inferences=2):
        ids = iter(("sw-1", "sw-2"))
        return SelfWorkRuntime(
            ttl_s=ttl_s,
            max_operations=max_operations,
            max_inferences=max_inferences,
            id_factory=lambda: next(ids),
        )

    def test_one_active_item_constraint(self):
        runtime = self.runtime()
        first = runtime.propose("organizar notas", "notes", now="2026-09-12T17:00:00+00:00")
        self.assertEqual(SelfWorkState.CANDIDATE, first.state)
        with self.assertRaises(RuntimeError):
            runtime.propose("segunda tarefa", "ideas", now="2026-09-12T17:00:01+00:00")

    def test_candidate_active_working_review_completed(self):
        runtime = self.runtime()
        runtime.propose("organizar notas", "notes", now="2026-09-12T17:00:00+00:00")
        self.assertEqual(SelfWorkState.ACTIVE, runtime.activate(now="2026-09-12T17:00:01+00:00").state)
        self.assertEqual(SelfWorkState.WORKING, runtime.begin_work(now="2026-09-12T17:00:02+00:00").state)
        self.assertEqual(SelfWorkState.REVIEWING, runtime.review(now="2026-09-12T17:00:03+00:00").state)
        done = runtime.complete(now="2026-09-12T17:00:04+00:00")
        self.assertEqual(SelfWorkState.COMPLETED, done.state)
        self.assertIsNone(runtime.current)

    def test_human_preempts_and_valid_item_resumes(self):
        runtime = self.runtime()
        runtime.propose("organizar notas", "notes", now="2026-09-12T17:00:00+00:00")
        runtime.activate(now="2026-09-12T17:00:01+00:00")
        runtime.begin_work(now="2026-09-12T17:00:02+00:00")
        paused = runtime.pause_for_human(now="2026-09-12T17:00:03+00:00")
        self.assertEqual(SelfWorkState.PAUSED, paused.state)
        resumed = runtime.resume_if_valid(now="2026-09-12T17:00:04+00:00")
        self.assertEqual(SelfWorkState.WORKING, resumed.state)

    def test_expired_item_does_not_resume(self):
        runtime = self.runtime(ttl_s=2)
        runtime.propose("organizar notas", "notes", now="2026-09-12T17:00:00+00:00")
        runtime.activate(now="2026-09-12T17:00:01+00:00")
        runtime.pause_for_human(now="2026-09-12T17:00:01+00:00")
        expired = runtime.resume_if_valid(now="2026-09-12T17:00:03+00:00")
        self.assertEqual(SelfWorkState.EXPIRED, expired.state)
        self.assertIsNone(runtime.current)

    def test_operation_budget_blocks_item(self):
        runtime = self.runtime(max_operations=2)
        runtime.propose("organizar notas", "notes", now="2026-09-12T17:00:00+00:00")
        runtime.activate(now="2026-09-12T17:00:01+00:00")
        runtime.begin_work(now="2026-09-12T17:00:02+00:00")
        runtime.record_operation(now="2026-09-12T17:00:03+00:00")
        blocked = runtime.record_operation(now="2026-09-12T17:00:04+00:00")
        self.assertEqual(SelfWorkState.BLOCKED, blocked.state)
        self.assertIsNone(runtime.current)

    def test_inference_budget_blocks_item(self):
        runtime = self.runtime(max_inferences=1)
        runtime.propose("revisar ideia", "ideas", now="2026-09-12T17:00:00+00:00")
        runtime.activate(now="2026-09-12T17:00:01+00:00")
        runtime.begin_work(now="2026-09-12T17:00:02+00:00")
        blocked = runtime.record_inference(now="2026-09-12T17:00:03+00:00")
        self.assertEqual(SelfWorkState.BLOCKED, blocked.state)
        self.assertIsNone(runtime.current)

    def test_abandon_cleans_current(self):
        runtime = self.runtime()
        runtime.propose("rascunho antigo", "scratch", now="2026-09-12T17:00:00+00:00")
        abandoned = runtime.abandon(now="2026-09-12T17:00:01+00:00", reason="sem_valor")
        self.assertEqual(SelfWorkState.ABANDONED, abandoned.state)
        self.assertEqual("sem_valor", abandoned.reason)
        self.assertIsNone(runtime.current)


if __name__ == "__main__":
    unittest.main()
