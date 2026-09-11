import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infrastructure.pentium.atlas.memory_retriever import MemoryRetriever
from infrastructure.pentium.atlas.observation_daemon import build_observation_context, run_daemon_cycle
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity
from infrastructure.pentium.atlas.tests.test_observation_daemon import (
    AGENT_CONFIG, ATLAS, EmptyScanner, FakeListener, GitHubClient, ManagedService,
)

NOW = "2026-09-11T12:00:00+00:00"
LATER = "2026-09-11T12:00:10+00:00"


class ObservationEpisodicMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config"
        self.config.mkdir()
        for path in ATLAS.glob("*.json"):
            shutil.copyfile(path, self.config / path.name)
        perception = json.loads((self.config / "config_percepcao.json").read_text())
        # Single-source replay fixture; production confirmation policy is unchanged.
        perception["politica"]["min_fontes_indisponiveis"] = 1
        perception["politica"]["max_evidencias"] = 1
        (self.config / "config_percepcao.json").write_text(json.dumps(perception))
        memory = json.loads((self.config / "config_memory.json").read_text())
        memory["episodic"] = {"idle_timeout_s": 1}
        (self.config / "config_memory.json").write_text(json.dumps(memory))

    def build(self, now=NOW):
        with patch("infrastructure.pentium.atlas.observation_daemon._utc_now", return_value=now):
            context = build_observation_context(
                config_root=self.config, state_dir=self.root / "state", agent_config_path=AGENT_CONFIG,
                wifi_interface="test0", managed_read_service=ManagedService(), github_client=GitHubClient(),
                scanner=EmptyScanner(), interaction_listener=FakeListener(),
                cognitive_interaction_listener=FakeListener(),
            )
        self.addCleanup(context.close)
        return context

    def event(self, context, sid, healthy=False, at=NOW):
        return context.composition.processar(Stimulus(
            sid, "managed.core", "recovered" if healthy else "status_changed",
            StimulusSeverity.NOTICE if healthy else StimulusSeverity.CRITICAL,
            at, {"channel_status": "healthy" if healthy else "degraded"}, 1.0, "core-health",
        ))

    def test_observation_recovery_is_retrievable_once_from_same_database(self):
        context = self.build()
        self.event(context, "down")
        self.assertEqual(1, len(context.memory_store.list_open_segments()))
        self.event(context, "up", healthy=True, at=LATER)
        self.event(context, "up", healthy=True, at=LATER)
        self.assertEqual(1, context.memory_store.count())
        memories = MemoryRetriever(context.memory_store, max_items=6, max_bytes=2048).retrieve(entity_id="core")
        self.assertEqual(1, len(memories))
        self.assertIn("recuperado", memories[0]["content"])
        self.assertTrue((self.root / "state" / "visual-state.json").is_file())

    def test_boot_recovers_previous_generation_without_duplicate_memory(self):
        first = self.build()
        self.event(first, "down")
        first.close()
        second = self.build(LATER)
        self.assertEqual(1, second.memory_store.count())
        self.assertEqual((), second.memory_store.list_open_segments())
        second.episodic_sink.recover(LATER)
        self.assertEqual(1, second.memory_store.count())
        self.assertTrue(second.composition.pipeline_percepcao.incidentes_ativos())

    def test_idle_cycle_flushes_pending_memory_and_publishes_metrics(self):
        context = self.build()
        self.event(context, "down")
        with patch.object(context.runtime, "run_scheduled_cycle", return_value=.01), patch(
            "infrastructure.pentium.atlas.observation_daemon._utc_now", return_value=LATER,
        ):
            run_daemon_cycle(context)
        self.assertEqual(1, context.memory_store.count())
        health = json.loads(context.health_path.read_text())
        self.assertEqual(1, health["episodic_memory"]["consolidation_success_total"])

    def test_close_releases_database_even_if_runtime_close_fails(self):
        context = self.build()
        with patch.object(context.runtime, "close", side_effect=RuntimeError("close")):
            with self.assertRaises(RuntimeError):
                context.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            context.memory_store.count()
