"""CP30 BUILD: MemoryGraph v2 node/event schema contract tests.

Strictly typed, versioned contract validation only: no persistence,
no network, no migration. Rejection behaviour is first-class.
"""
from __future__ import annotations

import ast
import dataclasses
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.memory_graph_v2_contracts import (
    MAX_EVIDENCE_REFS,
    MAX_LINEAGE_IDS,
    MAX_PAYLOAD_DEPTH,
    MAX_PAYLOAD_KEYS,
    MAX_PAYLOAD_STRING_CHARS,
    SCHEMA_VERSION,
    ContractViolation,
    EventKind,
    GraphEventV2,
    GraphNodeV2,
    NodeKind,
    Provenance,
    event_to_dict,
    node_to_dict,
    parse_event,
    parse_node,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "memory_graph_v2_contracts.py"


def valid_provenance(**overrides):
    data = {
        "source": "atlas.cognitive_daemon",
        "producer": "cp30-builder",
        "captured_at": "2026-10-15T12:00:00+00:00",
        "correlation_id": "corr:20261015-cp30-0001",
        "lineage": ["event:20261014-0007"],
        "evidence_refs": ["docs/implementation/2026-10-15-atlas-cp26-cp31-master-plan.md"],
    }
    data.update(overrides)
    return data


def valid_node(**overrides):
    data = {
        "schema_version": SCHEMA_VERSION,
        "node_id": "node:goal:cp30",
        "node_kind": "goal",
        "label": "CP30 MemoryGraph v2 contracts",
        "status": "active",
        "created_at": "2026-10-15T12:00:00+00:00",
        "updated_at": "2026-10-15T12:05:00+00:00",
        "provenance": valid_provenance(),
        "payload": {"objective": "context recovery", "priority": 1},
    }
    data.update(overrides)
    return data


def valid_event(**overrides):
    data = {
        "schema_version": SCHEMA_VERSION,
        "event_id": "event:20261015-0001",
        "event_kind": "node_created",
        "subject_id": "node:goal:cp30",
        "occurred_at": "2026-10-15T12:00:05+00:00",
        "provenance": valid_provenance(),
        "payload": {"origin": "cognitive_daemon"},
    }
    data.update(overrides)
    return data


class NodeContractTests(unittest.TestCase):
    def test_accepts_valid_node_and_normalizes(self):
        node = parse_node(valid_node())
        self.assertIsInstance(node, GraphNodeV2)
        self.assertEqual(node.node_kind, NodeKind.GOAL)
        self.assertEqual(node.schema_version, 2)
        self.assertEqual(node.payload["objective"], "context recovery")
        self.assertEqual(node.payload["priority"], 1)

    def test_normalizes_timestamps_to_utc(self):
        node = parse_node(valid_node(
            created_at="2026-10-15T14:00:00+02:00",
            updated_at="2026-10-15T14:05:00+02:00",
        ))
        self.assertEqual(node.created_at, "2026-10-15T12:00:00+00:00")
        self.assertEqual(node.updated_at, "2026-10-15T12:05:00+00:00")

    def test_rejects_schema_version_matrix(self):
        for bad in (1, 3, "2", 2.0, True, None):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(schema_version=bad))
            self.assertEqual(str(ctx.exception), "schema_version_invalid")

    def test_rejects_missing_schema_version(self):
        raw = valid_node()
        del raw["schema_version"]
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(raw)
        self.assertEqual(str(ctx.exception), "node_fields_invalid")

    def test_rejects_unknown_top_level_field(self):
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(extra="surprise"))
        self.assertEqual(str(ctx.exception), "node_fields_invalid")

    def test_rejects_non_string_field_name(self):
        raw = valid_node()
        raw[b"bytes_key"] = 1
        with self.assertRaises(ContractViolation):
            parse_node(raw)

    def test_rejects_each_missing_field(self):
        for field_name in ("node_id", "node_kind", "label", "status",
                           "created_at", "updated_at", "provenance", "payload"):
            raw = valid_node()
            del raw[field_name]
            with self.subTest(field=field_name), self.assertRaises(ContractViolation) as ctx:
                parse_node(raw)
            self.assertEqual(str(ctx.exception), "node_fields_invalid")

    def test_rejects_unknown_node_kind(self):
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(node_kind="wormhole"))
        self.assertEqual(str(ctx.exception), "node_kind_invalid")

    def test_rejects_non_string_node_kind(self):
        with self.assertRaises(ContractViolation):
            parse_node(valid_node(node_kind=7))

    def test_rejects_unknown_status(self):
        for status in ("zombie", "", 1, True):
            with self.subTest(status=status), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(status=status))
            self.assertEqual(str(ctx.exception), "status_invalid")

    def test_rejects_invalid_node_id(self):
        for node_id in ("", "node goal", "node:\x00x", " node:lead", 42, "n" * 200):
            with self.subTest(node_id=node_id), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(node_id=node_id))
            self.assertEqual(str(ctx.exception), "node_id_invalid")

    def test_rejects_invalid_label(self):
        for label in ("", "   ", "bad\x07label", 3, "x" * 500):
            with self.subTest(label=repr(label)), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(label=label))
            self.assertEqual(str(ctx.exception), "label_invalid")

    def test_rejects_non_object_node(self):
        for raw in (None, [], "node", 5):
            with self.subTest(raw=raw), self.assertRaises(ContractViolation) as ctx:
                parse_node(raw)
            self.assertEqual(str(ctx.exception), "node_invalid")

    def test_rejects_bad_timestamps(self):
        for ts in ("2026-10-15T12:00:00", "not-a-time", "", 12, None):
            with self.subTest(ts=ts), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(created_at=ts))
            self.assertEqual(str(ctx.exception), "created_at_invalid")


class EventContractTests(unittest.TestCase):
    def test_accepts_valid_event_without_supersedes(self):
        event = parse_event(valid_event())
        self.assertIsInstance(event, GraphEventV2)
        self.assertEqual(event.event_kind, EventKind.NODE_CREATED)
        self.assertIsNone(event.supersedes_id)
        self.assertEqual(event.subject_id, "node:goal:cp30")

    def test_accepts_event_with_supersedes_id(self):
        event = parse_event(valid_event(supersedes_id="event:20261014-0007"))
        self.assertEqual(event.supersedes_id, "event:20261014-0007")

    def test_rejects_invalid_supersedes_id(self):
        for bad in ("", "bad id", 42, "x" * 200):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_event(valid_event(supersedes_id=bad))
            self.assertEqual(str(ctx.exception), "supersedes_id_invalid")

    def test_rejects_unknown_event_kind(self):
        with self.assertRaises(ContractViolation) as ctx:
            parse_event(valid_event(event_kind="wormhole"))
        self.assertEqual(str(ctx.exception), "event_kind_invalid")

    def test_rejects_schema_version_matrix(self):
        for bad in (0, 1, 3, "2", True):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_event(valid_event(schema_version=bad))
            self.assertEqual(str(ctx.exception), "schema_version_invalid")

    def test_rejects_missing_and_extra_fields(self):
        for mutate in (lambda d: d.pop("occurred_at"), lambda d: d.pop("provenance"),
                       lambda d: d.update(unknown=1)):
            raw = valid_event()
            mutate(raw)
            with self.subTest(mutate=mutate), self.assertRaises(ContractViolation) as ctx:
                parse_event(raw)
            self.assertEqual(str(ctx.exception), "event_fields_invalid")

    def test_rejects_invalid_event_and_subject_ids(self):
        for field_name in ("event_id", "subject_id"):
            with self.subTest(field=field_name), self.assertRaises(ContractViolation) as ctx:
                parse_event(valid_event(**{field_name: "not valid"}))
            self.assertEqual(str(ctx.exception), field_name + "_invalid")


class ProvenanceContractTests(unittest.TestCase):
    def test_accepts_empty_lineage_and_evidence(self):
        prov = parse_node(valid_node(provenance=valid_provenance(
            lineage=[], evidence_refs=[]))).provenance
        self.assertEqual(prov.lineage, ())
        self.assertEqual(prov.evidence_refs, ())

    def test_rejects_missing_or_non_dict_provenance(self):
        for bad in (None, [], "prov", 3):
            raw = valid_node()
            raw["provenance"] = bad
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_node(raw)
            self.assertEqual(str(ctx.exception), "provenance_invalid")

    def test_rejects_each_missing_field(self):
        for field_name in ("source", "producer", "captured_at",
                           "correlation_id", "lineage", "evidence_refs"):
            prov = valid_provenance()
            del prov[field_name]
            with self.subTest(field=field_name), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(provenance=prov))
            self.assertEqual(str(ctx.exception), "provenance_fields_invalid")

    def test_rejects_unknown_provenance_field(self):
        prov = valid_provenance(hacker="x")
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(provenance=prov))
        self.assertEqual(str(ctx.exception), "provenance_fields_invalid")

    def test_rejects_naive_or_bad_captured_at(self):
        for ts in ("2026-10-15T12:00:00", "yesterday", "", 5):
            prov = valid_provenance(captured_at=ts)
            with self.subTest(ts=ts), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(provenance=prov))
            self.assertEqual(str(ctx.exception), "captured_at_invalid")

    def test_rejects_bad_correlation_id(self):
        for cid in ("", "corr id", "corr:\x00", 9, "c" * 300):
            prov = valid_provenance(correlation_id=cid)
            with self.subTest(cid=cid), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(provenance=prov))
            self.assertEqual(str(ctx.exception), "correlation_id_invalid")

    def test_rejects_oversized_lineage(self):
        lineage = ["event:%04d" % i for i in range(MAX_LINEAGE_IDS + 1)]
        prov = valid_provenance(lineage=lineage)
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(provenance=prov))
        self.assertEqual(str(ctx.exception), "lineage_invalid")

    def test_rejects_non_identifier_lineage_item(self):
        prov = valid_provenance(lineage=["event ok"])
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(provenance=prov))
        self.assertEqual(str(ctx.exception), "lineage_invalid")

    def test_rejects_too_many_evidence_refs(self):
        refs = ["ref:%04d" % i for i in range(MAX_EVIDENCE_REFS + 1)]
        prov = valid_provenance(evidence_refs=refs)
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(provenance=prov))
        self.assertEqual(str(ctx.exception), "evidence_refs_invalid")

    def test_rejects_non_list_collections(self):
        for field_name in ("lineage", "evidence_refs"):
            prov = valid_provenance(**{field_name: "not-a-list"})
            with self.subTest(field=field_name), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(provenance=prov))
            self.assertEqual(str(ctx.exception), field_name + "_invalid")


class PayloadBoundsTests(unittest.TestCase):
    def test_accepts_empty_payload(self):
        node = parse_node(valid_node(payload={}))
        self.assertEqual(dict(node.payload), {})

    def test_accepts_boundary_values(self):
        payload = {"k%02d" % i: "v" for i in range(MAX_PAYLOAD_KEYS - 5)}
        payload["long"] = "x" * MAX_PAYLOAD_STRING_CHARS
        payload["nested"] = {"a": {"b": {"c": "leaf"}}}
        payload["flag"] = True
        payload["ratio"] = 0.5
        payload["nothing"] = None
        node = parse_node(valid_node(payload=payload))
        self.assertEqual(node.payload["long"], "x" * MAX_PAYLOAD_STRING_CHARS)

    def test_rejects_payload_not_dict(self):
        for bad in (None, [], "payload", 5, ("a",)):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(payload=bad))
            self.assertEqual(str(ctx.exception), "payload_invalid")

    def test_rejects_too_many_keys(self):
        payload = {"k%03d" % i: i for i in range(MAX_PAYLOAD_KEYS + 1)}
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(payload=payload))
        self.assertEqual(str(ctx.exception), "payload_too_many_keys")

    def test_rejects_deeply_nested_payload(self):
        deep = {"l1": {"l2": {"l3": {"l4": {"l5": "too deep"}}}}}
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(payload=deep))
        self.assertEqual(str(ctx.exception), "payload_too_deep")

    def test_rejects_long_string_value(self):
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(payload={"blob": "x" * (MAX_PAYLOAD_STRING_CHARS + 1)}))
        self.assertEqual(str(ctx.exception), "payload_value_invalid")

    def test_rejects_non_finite_float(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(payload={"score": bad}))
            self.assertEqual(str(ctx.exception), "payload_value_invalid")

    def test_rejects_non_string_key(self):
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(payload={1: "x"}))
        self.assertEqual(str(ctx.exception), "payload_keys_invalid")

    def test_rejects_invalid_key_format(self):
        for key in ("with space", "with:colon", "", "with\x00null"):
            with self.subTest(key=repr(key)), self.assertRaises(ContractViolation) as ctx:
                parse_node(valid_node(payload={key: "x"}))
            self.assertEqual(str(ctx.exception), "payload_keys_invalid")

    def test_rejects_non_json_value_types(self):
        for bad in (b"bytes", {1, 2}, complex(1, 2)):
            with self.subTest(bad=bad), self.assertRaises(ContractViolation):
                parse_node(valid_node(payload={"thing": bad}))

    def test_rejects_payload_over_byte_budget(self):
        payload = {"k%02d" % i: "v" * 200 for i in range(MAX_PAYLOAD_KEYS)}
        with self.assertRaises(ContractViolation) as ctx:
            parse_node(valid_node(payload=payload))
        self.assertEqual(str(ctx.exception), "payload_too_large")


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    def test_node_is_frozen(self):
        node = parse_node(valid_node())
        with self.assertRaises(AttributeError):
            node.label = "changed"

    def test_payload_is_deeply_frozen(self):
        node = parse_node(valid_node(payload={"nested": {"a": 1}, "items": [1, 2]}))
        with self.assertRaises(TypeError):
            node.payload["nested"] = {}
        with self.assertRaises(TypeError):
            node.payload["nested"]["a"] = 2
        self.assertEqual(node.payload["items"], (1, 2))

    def test_input_mutation_does_not_affect_validated_node(self):
        raw = valid_node()
        node = parse_node(raw)
        raw["payload"]["objective"] = "tampered"
        raw["label"] = "tampered"
        self.assertEqual(node.payload["objective"], "context recovery")
        self.assertEqual(node.label, "CP30 MemoryGraph v2 contracts")

    def test_provenance_is_frozen_and_isolated(self):
        prov_raw = valid_provenance()
        node = parse_node(valid_node(provenance=prov_raw))
        prov_raw["lineage"].append("event:injected")
        self.assertEqual(node.provenance.lineage, ("event:20261014-0007",))
        with self.assertRaises(AttributeError):
            node.provenance.source = "changed"

    def test_node_round_trip_through_dict(self):
        node = parse_node(valid_node())
        self.assertEqual(parse_node(node_to_dict(node)), node)

    def test_event_round_trip_through_dict(self):
        event = parse_event(valid_event(supersedes_id="event:20261014-0007"))
        self.assertEqual(parse_event(event_to_dict(event)), event)

    def test_round_trip_output_is_json_friendly(self):
        import json
        encoded = json.dumps(node_to_dict(parse_node(valid_node())), sort_keys=True)
        self.assertIn("schema_version", encoded)


class ContractPurityTests(unittest.TestCase):
    def test_module_has_no_persistent_io_imports(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.issubset({"__future__", "dataclasses", "datetime",
                               "enum", "json", "math", "re", "types", "typing"}),
            "unexpected imports: %s" % sorted(imported),
        )
        for forbidden in ("sqlite3", "os", "subprocess", "pathlib", "socket"):
            self.assertNotIn(forbidden, imported)

    def test_module_does_not_call_open(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", called)

    def test_version_is_strictly_typed_int(self):
        self.assertIs(type(SCHEMA_VERSION), int)
        self.assertEqual(SCHEMA_VERSION, 2)


if __name__ == "__main__":
    unittest.main()
