"""CP-MEM-P2: coherence enforcement at the action-authorization sink."""
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.action_plan import (
    ActionStatus,
    ActionType,
    AtlasAction,
    PlanoAcaoAtlas,
)
from infrastructure.pentium.atlas.action_policy import ActionPolicy
from infrastructure.pentium.atlas.capability_registry import atlas_capability_registry
from infrastructure.pentium.atlas.memory_action_gate import (
    ActionRisk,
    CoherenceDecision,
    MemoryCoherenceGate,
    QuarantineRegistry,
    classify_risk,
)
from infrastructure.pentium.atlas.policy_capabilities import PolicyCapabilities

CORRELATION = "stim-1"


def evidence(*, memory_id="m1", integrity="attested"):
    return {"memory_id": memory_id, "integrity": integrity,
            "authority": "evidence_only"}


def plan_with(capability, arguments):
    return PlanoAcaoAtlas.create(
        stimulus_id="s1", objective="agir", confidence=0.9, response_text=None,
        actions=[AtlasAction.create(ActionType.CAPABILITY_REQUEST, target="core",
                                    parameters={"capability": capability,
                                                "arguments": arguments})],
    )


class RiskClassificationTests(unittest.TestCase):
    def test_levels_map_to_risk_and_unknown_fails_closed(self):
        self.assertEqual(ActionRisk.LOW, classify_risk("READ"))
        self.assertEqual(ActionRisk.MEDIUM, classify_risk("control"))
        self.assertEqual(ActionRisk.HIGH, classify_risk("DESTRUCTIVE"))
        self.assertEqual(ActionRisk.HIGH, classify_risk("mystery"))
        self.assertEqual(ActionRisk.HIGH, classify_risk(None))


class GateDecisionTests(unittest.TestCase):
    def setUp(self):
        self.gate = MemoryCoherenceGate()

    def test_no_memory_evidence_allows_and_traces_correlation(self):
        decision = self.gate.evaluate(capability="restart_service", level="CONTROL",
                                      memories=(), correlation_id=CORRELATION)
        self.assertTrue(decision.allowed)
        self.assertEqual("no_memory_evidence", decision.reason)
        self.assertEqual(CORRELATION, decision.correlation_id)

    def test_tampered_evidence_blocks_medium_action_and_quarantines(self):
        decision = self.gate.evaluate(capability="restart_service", level="CONTROL",
                                      memories=(evidence(integrity="tampered"),),
                                      correlation_id=CORRELATION)
        self.assertFalse(decision.allowed)
        self.assertEqual("tampered_memory_evidence", decision.reason)
        self.assertIn("m1", decision.quarantine)
        self.assertTrue(self.gate._quarantine.is_quarantined("m1"))

    def test_human_approval_cannot_override_tampering(self):
        decision = self.gate.evaluate(capability="restart_service", level="CONTROL",
                                      memories=(evidence(integrity="tampered"),),
                                      correlation_id=CORRELATION, human_approval=True)
        self.assertFalse(decision.allowed)

    def test_tampered_low_impact_is_quarantined_but_allowed(self):
        decision = self.gate.evaluate(capability="get_host_status", level="READ",
                                      memories=(evidence(integrity="tampered"),),
                                      correlation_id=CORRELATION)
        self.assertTrue(decision.allowed)
        self.assertEqual("tampered_low_impact_quarantined", decision.reason)
        self.assertTrue(self.gate._quarantine.is_quarantined("m1"))

    def test_unattested_evidence_escalates_medium_action(self):
        decision = self.gate.evaluate(capability="restart_service", level="CONTROL",
                                      memories=({"memory_id": "m2"},),
                                      correlation_id=CORRELATION)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.requires_human_approval)
        self.assertEqual("unattested_evidence_requires_human_approval", decision.reason)

    def test_human_approval_resolves_unattested_escalation(self):
        decision = self.gate.evaluate(capability="restart_service", level="CONTROL",
                                      memories=({"memory_id": "m2"},),
                                      correlation_id=CORRELATION, human_approval=True)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_human_approval)
        self.assertEqual("human_approval_granted", decision.reason)

    def test_fully_attested_evidence_allows_destructive(self):
        decision = self.gate.evaluate(capability="reboot_host", level="DESTRUCTIVE",
                                      memories=(evidence(memory_id="m3"),),
                                      correlation_id=CORRELATION)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_human_approval)
        self.assertEqual("coherent_evidence", decision.reason)

    def test_missing_correlation_is_rejected(self):
        with self.assertRaises(ValueError):
            self.gate.evaluate(capability="x", level="READ", memories=(),
                               correlation_id="")


class QuarantineRegistryTests(unittest.TestCase):
    def test_quarantine_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.json"
            first = QuarantineRegistry(path)
            self.assertTrue(first.quarantine("m1", reason="tampered",
                                             correlation_id=CORRELATION))
            self.assertFalse(first.quarantine("m1", reason="tampered",
                                              correlation_id=CORRELATION))
            second = QuarantineRegistry(path)
            self.assertTrue(second.is_quarantined("m1"))
            entries = second.list()
            self.assertEqual(1, len(entries))
            self.assertEqual(CORRELATION, entries[0]["correlation_id"])

    def test_invalid_memory_id_rejected(self):
        with self.assertRaises(ValueError):
            QuarantineRegistry().quarantine("bad id!", reason="x", correlation_id="c")

    def test_corrupt_file_is_ignored_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.json"
            path.write_text("{not json", encoding="utf-8")
            registry = QuarantineRegistry(path)
            self.assertEqual((), registry.list())


class ActionPolicySinkTests(unittest.TestCase):
    def _caps(self):
        return PolicyCapabilities(atlas_capability_registry(),
                                  read_auto_allow=("get_host_status",),
                                  control_allow=("restart_service",))

    def _policy(self, gate):
        return ActionPolicy(self._caps(), coherence_gate=gate)

    def test_tampered_evidence_blocks_control_action_at_sink(self):
        gate = MemoryCoherenceGate()
        authorized = self._policy(gate).authorize(
            plan_with("restart_service", {"host": "core", "service": "web"}),
            evidence=(evidence(integrity="tampered"),),
        )
        action = authorized.actions[0]
        self.assertEqual(ActionStatus.BLOCKED, action.status)
        self.assertTrue(action.reason.startswith("memory_coherence:"))
        # correlation defaults to the plan id, not the stimulus id
        entries = gate._quarantine.list()
        self.assertEqual(1, len(entries))
        self.assertEqual(authorized.plan_id, entries[0]["correlation_id"])
        self.assertNotEqual("s1", entries[0]["correlation_id"])

    def test_unattested_evidence_escalates_control_to_confirmation(self):
        gate = MemoryCoherenceGate()
        authorized = self._policy(gate).authorize(
            plan_with("restart_service", {"host": "core", "service": "web"}),
            evidence=({"memory_id": "m2"},),
        )
        self.assertEqual(ActionStatus.AUTHORIZED, authorized.actions[0].status)
        self.assertTrue(authorized.requires_confirmation)
        self.assertTrue(authorized.actions[0].reason.startswith("memory_coherence:"))

    def test_attested_evidence_keeps_auto_authorization(self):
        gate = MemoryCoherenceGate()
        authorized = self._policy(gate).authorize(
            plan_with("restart_service", {"host": "core", "service": "web"}),
            evidence=(evidence(),),
        )
        self.assertEqual(ActionStatus.AUTHORIZED, authorized.actions[0].status)
        self.assertFalse(authorized.requires_confirmation)

    def test_without_gate_behaviour_is_unchanged(self):
        authorized = ActionPolicy(self._caps()).authorize(
            plan_with("restart_service", {"host": "core", "service": "web"}),
        )
        self.assertEqual(ActionStatus.AUTHORIZED, authorized.actions[0].status)
        self.assertFalse(authorized.requires_confirmation)

    def test_explicit_correlation_id_is_used(self):
        gate = MemoryCoherenceGate()
        self._policy(gate).authorize(
            plan_with("restart_service", {"host": "core", "service": "web"}),
            evidence=(evidence(integrity="tampered"),),
            correlation_id="stim-42",
        )
        self.assertEqual("stim-42", gate._quarantine.list()[0]["correlation_id"])


if __name__ == "__main__":
    unittest.main()
