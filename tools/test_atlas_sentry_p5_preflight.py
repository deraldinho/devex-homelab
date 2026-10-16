"""Security contract for the P5 release gate. All test fixtures are synthetic."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import atlas_sentry_p5_preflight as gate


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.deployed=self.root/"pentium-agent"
        self.atlas=self.deployed/"atlas"
        self.atlas.mkdir(parents=True)
        for filename in gate.MANDATORY_CONFIG:
            (self.atlas/filename).write_text("pass",encoding="utf-8")
        (self.atlas/"config_health_supervisor.json").write_text(json.dumps({
            "schema_version":1,
            "features":{"health_supervisor_v1":True,"self_healing_v1":False},
            "components":{"atlas-observation.service":{"required":True}},
            "managed_hosts":{}
        }))
        self.units=self.root/"user-units"
        self.units.mkdir()
        (self.units/"atlas-cognitive.service").write_text("[Service]\nExecStart=/usr/bin/python3 -m atlas.cognitive_daemon\n")
        system=self.root/"system"
        system.mkdir()
        self.relay=system/"atlas-sentry-receipt-relay.service"
        self.health=system/"atlas-sentry-health.service"
        for file,command in (
            (self.relay,"tools.atlas_sentry_v2_relay"),
            (self.health,"atlas.health_supervisor_daemon")
        ):
            file.write_text(
                "[Unit]\nDescription=Health\n[Service]\n"
                "User=atlas-sentry-health\nGroup=atlas-sentry-health\n"
                "NoNewPrivileges=true\nProtectSystem=strict\n"
                "CapabilityBoundingSet=\nAmbientCapabilities=\n"
                "RestrictAddressFamilies=AF_UNIX AF_INET\n"
                "WorkingDirectory="+str(self.deployed)+"\n"
                "ExecStart=/usr/bin/python3 -m "+command+"\n")
        self.args={
            "deploy_root":self.deployed,
            "trusted_health_root":self.deployed,
            "user_unit_dir":self.units,
            "system_unit_path":self.relay,
            "system_health_unit_path":self.health,
        }
        fake_os=SimpleNamespace(name="posix",
            getgrouplist=lambda user, gid: [gid,1100])
        fake_pwd=SimpleNamespace(getpwnam=lambda name: SimpleNamespace(
            pw_uid=1000 if name=="deraldinho" else 1200,pw_gid=1000))
        fake_grp=SimpleNamespace(getgrnam=lambda name:SimpleNamespace(gr_gid=1100))
        self.mocks=[
            patch.object(gate,"os",fake_os),
            patch.object(gate,"pwd",fake_pwd),
            patch.object(gate,"grp",fake_grp),
            patch.object(gate,"_run",lambda argv:(True,"active")),
            patch.object(gate,"_immutable_root_tree",lambda path:True),
        ]
        for control in self.mocks:
            control.start()
            self.addCleanup(control.stop)

    def checks(self,**kwargs):
        items=gate.audit(**{**self.args,**kwargs})
        return {item.check:item for item in items}

    def test_complete_synthetic_configuration_is_green(self):
        findings=self.checks()
        self.assertTrue(all(item.ok for item in findings.values()),findings)
        self.assertTrue(findings["separate_unprivileged_uids"].ok)

    def test_executor_writable_health_code_cannot_pass(self):
        with patch.object(gate,"_immutable_root_tree",lambda path:False):
            check=self.checks()
        self.assertFalse(check["independent_health_code_immutable"].ok)
        self.assertFalse(check["relay_system_unit"].ok)
        self.assertFalse(check["independent_health_system_unit"].ok)

    def test_legitimate_repeated_systemd_environment_keys_are_accepted(self):
        with self.health.open("a",encoding="utf-8") as stream:
            stream.write("Environment=HOME=/var/lib/atlas-sentry-health\n")
            stream.write("Environment=PATH=/usr/bin:/bin\n")
        self.assertTrue(self.checks()["independent_health_system_unit"].ok)

    def test_missing_health_unit_cannot_pass(self):
        self.health.unlink()
        check=self.checks()
        self.assertFalse(check["independent_health_system_unit"].ok)

    def test_unit_comment_spoof_and_root_execution_are_not_accepted(self):
        self.health.write_text(
            "# User=atlas-sentry-health\n"
            "# NoNewPrivileges=true\n"
            "# ProtectSystem=strict\n"
            "# CapabilityBoundingSet=\n"
            "# AmbientCapabilities=\n"
            "# RestrictAddressFamilies=AF_UNIX\n"
            "[Service]\nUser=root\nExecStart=/usr/bin/python3 -m atlas.health_supervisor_daemon\n")
        self.assertFalse(self.checks()["independent_health_system_unit"].ok)

    def test_unsafe_self_healing_flag_fails_release(self):
        config=self.atlas/"config_health_supervisor.json"
        obj=json.loads(config.read_text())
        obj["features"]["self_healing_v1"]=True
        config.write_text(json.dumps(obj))
        self.assertFalse(self.checks()["supervisor_config"].ok)

    def test_missing_deployed_sentry_module_denies(self):
        (self.atlas/"sentry_receipt_relay.py").unlink()
        self.assertFalse(self.checks()["package_sentry_receipt_relay_py"].ok)

    def test_same_uid_cannot_pass(self):
        fake_pwd=SimpleNamespace(getpwnam=lambda name: SimpleNamespace(
            pw_uid=1000,pw_gid=1000))
        with patch.object(gate,"pwd",fake_pwd):
            self.assertFalse(self.checks()["separate_unprivileged_uids"].ok)

    def test_missing_cognitive_process_denies(self):
        with patch.object(gate,"_run",lambda argv:
                (False,"inactive") if "atlas-cognitive.service" in argv else (True,"")):
            self.assertFalse(self.checks()["cognitive_service_active"].ok)

    def test_missing_crypto_runtime_denies(self):
        with patch.object(gate,"_run",lambda argv:
                (False,"") if "python3" in argv else (True,"")):
            self.assertFalse(self.checks()["ed25519_runtime"].ok)

    def test_missing_group_denies(self):
        with patch.object(gate,"grp",SimpleNamespace(getgrnam=lambda name:
                (_ for _ in ()).throw(KeyError(name)))):
            self.assertFalse(self.checks()["socket_group_membership"].ok)

    def test_allow_inactive_never_claims_production_readiness(self):
        arguments=[
            "--deploy-root",str(self.deployed),
            "--user-unit-dir",str(self.units),
            "--system-unit-path",str(self.relay),
            "--system-health-unit-path",str(self.health),
            "--allow-inactive",
        ]
        output=io.StringIO()
        with redirect_stdout(output):
            code=gate.main(arguments)
        self.assertEqual(code,2)
        response=json.loads(output.getvalue())
        self.assertEqual(response["mode"],"staging")
        self.assertIs(response["production_ready"],False)
        self.assertIs(response["release_authorized"],False)
        self.assertIs(response["preflight_passed"],False)

    def test_green_preflight_does_not_authorize_runtime_release(self):
        arguments=[
            "--deploy-root",str(self.deployed),
            "--trusted-health-root",str(self.deployed),
            "--user-unit-dir",str(self.units),
            "--system-unit-path",str(self.relay),
            "--system-health-unit-path",str(self.health),
        ]
        output=io.StringIO()
        with redirect_stdout(output):
            code=gate.main(arguments)
        self.assertEqual(code,0)
        response=json.loads(output.getvalue())
        self.assertTrue(response["preflight_passed"])
        self.assertFalse(response["production_ready"])
        self.assertFalse(response["release_authorized"])


if __name__=="__main__":
    unittest.main()
