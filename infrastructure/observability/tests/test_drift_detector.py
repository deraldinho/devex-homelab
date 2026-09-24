import json
import unittest
from datetime import datetime, timezone

from infrastructure.observability.drift_model import (
    DesiredComponent,
    ObservedComponent,
    DriftSeverity,
)
from infrastructure.observability.drift_detector import DriftDetector


class DriftDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = DriftDetector()
        self.now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)

    def test_clean_state_when_all_components_match(self):
        desired = [
            DesiredComponent(
                name="core-homelab-01",
                target_node="core",
                component_type="container",
                expected_image="devex/core-homelab-runner:2.337.0",
                expected_state="running",
            ),
            DesiredComponent(
                name="pentium-heartbeat.timer",
                target_node="pentium",
                component_type="systemd_unit",
                expected_state="active",
            ),
        ]
        observed = [
            ObservedComponent(
                name="core-homelab-01",
                node="core",
                observed_state="running",
                observed_image="devex/core-homelab-runner:2.337.0",
            ),
            ObservedComponent(
                name="pentium-heartbeat.timer",
                node="pentium",
                observed_state="active",
            ),
        ]

        report = self.detector.evaluate(desired, observed, now=self.now)
        self.assertEqual(report.overall_status, DriftSeverity.CLEAN)
        self.assertEqual(len(report.findings), 0)
        self.assertEqual(report.scanned_components, 2)

    def test_missing_component_triggers_critical_severity(self):
        desired = [
            DesiredComponent(
                name="core-l2jtoren-01",
                target_node="core",
                component_type="container",
                expected_state="running",
            )
        ]
        observed = []

        report = self.detector.evaluate(desired, observed, now=self.now)
        self.assertEqual(report.overall_status, DriftSeverity.CRITICAL)
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.severity, DriftSeverity.CRITICAL)
        self.assertEqual(finding.observed, "missing")

    def test_state_mismatch_triggers_critical_severity(self):
        desired = [
            DesiredComponent(
                name="core-l2jtoren-02",
                target_node="core",
                component_type="container",
                expected_state="running",
            )
        ]
        observed = [
            ObservedComponent(
                name="core-l2jtoren-02",
                node="core",
                observed_state="exited",
            )
        ]

        report = self.detector.evaluate(desired, observed, now=self.now)
        self.assertEqual(report.overall_status, DriftSeverity.CRITICAL)
        self.assertEqual(report.findings[0].reason, "Estado de execução divergente do versionado")

    def test_image_tag_mismatch_triggers_warning_severity(self):
        desired = [
            DesiredComponent(
                name="core-homelab-01",
                target_node="core",
                component_type="container",
                expected_image="devex/core-homelab-runner:2.337.0",
                expected_state="running",
            )
        ]
        observed = [
            ObservedComponent(
                name="core-homelab-01",
                node="core",
                observed_state="running",
                observed_image="devex/core-homelab-runner:2.336.0-drift",
            )
        ]

        report = self.detector.evaluate(desired, observed, now=self.now)
        self.assertEqual(report.overall_status, DriftSeverity.WARNING)
        self.assertEqual(report.findings[0].expected, "devex/core-homelab-runner:2.337.0")
        self.assertEqual(report.findings[0].observed, "devex/core-homelab-runner:2.336.0-drift")

    def test_report_serialization_to_dict_and_json(self):
        desired = [
            DesiredComponent(
                name="sample",
                target_node="pentium",
                component_type="container",
            )
        ]
        report = self.detector.evaluate(desired, [], now=self.now)
        payload = report.to_dict()
        serialized = json.dumps(payload)
        self.assertIn("critical", serialized)
        self.assertEqual(payload["findings_count"], 1)


if __name__ == "__main__":
    unittest.main()
