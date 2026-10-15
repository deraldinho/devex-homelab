import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from infrastructure.pentium.atlas.operational_affective_graph import (
    OperationalAffectiveGraph,AgentAffectiveEnvelope)

A={"valencia":0.3,"ativacao":0.4,"estresse":0.1,"confianca":0.9,
   "engajamento":0.6,"curiosidade":0.8,"atualizado_em":"2026-10-15T11:00:00+00:00"}
E={"stimulus_id":"a-1","source":"pentium.self","kind":"health",
   "severity":"warning","timestamp":"2026-10-15T10:59:00+00:00",
   "correlation_id":"incident-1","payload":{"secret":"Bearer private-token"}}

class OperationalGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"graph.sqlite3"
        self.graph=OperationalAffectiveGraph(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_stimulus_affect_correlation_and_redaction(self):
        self.graph.record_stimulus(E)
        key=self.graph.record_affect("atlas",A,source_stimulus_id="a-1")
        graph=self.graph.export()
        self.assertEqual(graph["observed_events_by_severity"]["warning"],1)
        self.assertIn("OBSERVED_DURING",[e["type"] for e in graph["edges"]])
        self.assertIn("HAS_SNAPSHOT",[e["type"] for e in graph["edges"]])
        self.assertNotIn("Bearer",json.dumps(graph))
        self.assertNotIn("secret",self.path.read_bytes().decode("utf-8",errors="ignore"))
        self.assertEqual(graph["affect_series"][0]["estresse"],0.1)
    def test_exactly_once_sample(self):
        self.graph.record_stimulus(E);self.graph.record_stimulus(E)
        self.graph.record_affect("atlas",A)
        self.graph.record_affect("atlas",A)
        exported=self.graph.export()
        self.assertEqual(len(exported["affect_series"]),1)
        self.assertEqual(exported["observed_events_by_severity"]["warning"],1)
    def test_temporal_chain(self):
        self.graph.record_affect("atlas",A)
        another=dict(A,estresse=0.6,atualizado_em="2026-10-15T11:02:00+00:00")
        self.graph.record_affect("atlas",another)
        links=[e for e in self.graph.export()["edges"] if e["type"]=="PRECEDES"]
        self.assertEqual(len(links),1)
        transition=self.graph.export()["affect_transitions"][0]
        self.assertAlmostEqual(transition["delta"]["estresse"],0.5)
        self.assertEqual(transition["causality"],"unverified_temporal_association")
    def test_delegation_inherits_context_but_cannot_mutate_atlas(self):
        self.graph.record_affect("atlas",A)
        envelope=self.graph.delegate("security-auditor","task-43",
                                     time_iso="2026-10-15T11:01:00+00:00")
        self.assertEqual(envelope.parent_id,"atlas")
        self.assertAlmostEqual(envelope.metrics["estresse"],0.1)
        self.assertIn("INHERITS_CONTEXT",[e["type"] for e in self.graph.export()["edges"]])
        other=dict(A,estresse=0.7,atualizado_em="2026-10-15T11:02:00+00:00")
        self.graph.record_affect("atlas",other)
        self.assertEqual(envelope.metrics["estresse"],0.1)
        self.assertEqual(self.graph.export()["affect_series"][0]["estresse"],0.7)
        with self.assertRaises(ValueError):
            self.graph.delegate("security-auditor","task-44")
    def test_no_fake_context_for_agent_without_parent_sample(self):
        with self.assertRaises(ValueError):
            self.graph.delegate("security-auditor","task-1")
        with self.assertRaises(ValueError):
            self.graph.record_affect("unknown",A)
    def test_nan_and_invalid_payloads_fail_closed(self):
        self.graph.record_stimulus(E)
        for mutation in (dict(A,estresse=float("nan")),dict(A,valencia=-2)):
            with self.assertRaises(ValueError):self.graph.record_affect("atlas",mutation)
        with self.assertRaises(ValueError):self.graph.record_stimulus(dict(E,severity="urgent"))
        with self.assertRaises(ValueError):self.graph.record_stimulus(dict(E,source="API_KEY=super-secret"))
        with self.assertRaises(ValueError):self.graph.export(limit=10000)
    def test_cross_reopen_persistence(self):
        self.graph.record_affect("atlas",A)
        reopened=OperationalAffectiveGraph(self.path)
        self.assertEqual(len(reopened.export()["affect_series"]),1)
if __name__=="__main__":unittest.main()
