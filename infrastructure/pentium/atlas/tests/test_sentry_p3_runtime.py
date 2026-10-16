"""CP-SENTRY-P3 trusted-file configuration & runtime default-off contracts."""
from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.atlas_sentry_v2_keys import provision_keypair
from infrastructure.pentium.atlas.sentry_receipt_v2 import (
    Ed25519ReceiptSigner,load_signer_from_file,ReceiptV2Error,
)
from infrastructure.pentium.atlas.health_supervisor_daemon import build_owner

ROOT=Path(__file__).resolve().parents[1]


class RuntimeP3Tests(unittest.TestCase):
    def test_key_provision_is_explicit_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            private=Path(tmp)/"executor.pem"
            public=Path(tmp)/"executor.pub"
            self.assertFalse(private.exists())
            provision_keypair(private,public)
            self.assertTrue(private.is_file())
            self.assertTrue(public.is_file())
            signer=load_signer_from_file(private,role="executor",key_id="executor-k1")
            self.assertIsInstance(signer,Ed25519ReceiptSigner)
            original=private.read_bytes()
            with self.assertRaises(ValueError):
                provision_keypair(private,public)
            self.assertEqual(private.read_bytes(),original)
            if os.name != "nt":
                self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_health_owner_opt_in_fails_closed_without_independent_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            conf={
                "schema_version":1,"poll_interval_s":15,
                "features":{"health_supervisor_v1":True,"self_healing_v1":False},
                "components":{},"managed_hosts":{},
            }
            (root/"config_health_supervisor.json").write_text(json.dumps(conf))
            with patch.dict(os.environ,{"ATLAS_SENTRY_V2_HEALTH_ENABLED":"1"},clear=True):
                with self.assertRaises(ReceiptV2Error):
                    build_owner(config_root=root,state_dir=root)
            with patch.dict(os.environ,{},clear=True):
                owner=build_owner(config_root=root,state_dir=root)
                self.assertIsNone(owner.recovery_receipt_sink)
                owner.close()

    def test_health_owner_accepts_independent_keys_only_with_explicit_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            conf={
                "schema_version":1,"poll_interval_s":15,
                "features":{"health_supervisor_v1":True,"self_healing_v1":False},
                "components":{},"managed_hosts":{},
            }
            (root/"config_health_supervisor.json").write_text(json.dumps(conf))
            action_priv=root/"act.pem"; action_pub=root/"act.pub"
            health_priv=root/"health.pem"; health_pub=root/"health.pub"
            provision_keypair(action_priv,action_pub)
            provision_keypair(health_priv,health_pub)
            variables={
                "ATLAS_SENTRY_HEALTH_SHADOW":"1",
                "ATLAS_SENTRY_V2_HEALTH_ENABLED":"1",
                "ATLAS_SENTRY_V2_HEALTH_PRIVATE_KEY_FILE":str(health_priv),
                "ATLAS_SENTRY_V2_HEALTH_KEY_ID":"health-k1",
                "ATLAS_SENTRY_V2_EXECUTOR_PUBLIC_KEY_FILE":str(action_pub),
                "ATLAS_SENTRY_V2_EXECUTOR_KEY_ID":"executor-k1",
            }
            with patch.dict(os.environ,variables,clear=True):
                owner=build_owner(config_root=root,state_dir=root)
                try:
                    self.assertIsNotNone(owner.recovery_receipt_sink)
                    self.assertEqual(owner.run_once().state.value,"healthy")
                    self.assertTrue((root/"failure-memory.sqlite3").exists())
                finally:owner.close()
            (root/"failure-memory.sqlite3").unlink()

    def test_cognitive_real_factory_wires_exact_executor_sink(self):
        tree=ast.parse((ROOT/"cognitive_daemon.py").read_text(encoding="utf-8"))
        methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="build_owner"]
        self.assertEqual(len(methods),1)
        calls={n.func.id for n in ast.walk(methods[0])
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertIn("build_executor_receipt_sink",calls)
        named=[k for n in ast.walk(methods[0]) if isinstance(n,ast.Call)
               for k in n.keywords if k.arg=="on_command_succeeded"]
        self.assertEqual(len(named),1)
        self.assertIsInstance(named[0].value,ast.Name)
        self.assertEqual(named[0].value.id,"executor_receipt_sink")


if __name__=="__main__":unittest.main()
