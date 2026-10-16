"""TDD for production_key_boundary.py.

Pure in-memory validation only: no OS services, keyring, network, dispatch or
file side effects.  Shadow/demo fixtures remain legal in synthetic tests; real
production integration requires an explicit independently provided 32-byte key
and provisioning metadata.
"""

from __future__ import annotations

import hashlib
import re
import unittest

import production_key_boundary as kb


def independent_key(seed: bytes = b"atlas independent production key") -> bytes:
    return hashlib.sha256(seed).digest()


def valid_metadata(environment: str = "production", **extra) -> dict:
    base = {
        "environment": environment,
        "provenance": "independently-provisioned",
        "independently_provided": True,
        "source": "vault",
        "key_id": "prod-key-0001",
    }
    base.update(extra)
    return base


class ValidProductionKeyTests(unittest.TestCase):
    def test_independent_32_byte_key_accepted(self):
        key = independent_key()
        result = kb.check_production_key(key, valid_metadata(), environment="production",
                                        expected_environment="production")
        self.assertTrue(result)
        self.assertEqual(result.reason, kb.REASON_OK if hasattr(kb, "REASON_OK") else "OK")
        self.assertEqual(result["dispatch_performed"], False)
        self.assertEqual(result["side_effects"], [])

    def test_result_unpacks_as_tuple(self):
        key = independent_key()
        ok, reason, details = kb.check_production_key(key, valid_metadata(), environment="production")
        self.assertTrue(ok)
        self.assertEqual(reason, "OK")
        self.assertIsInstance(details, dict)


class RejectedKeysTests(unittest.TestCase):
    def test_known_public_test_vector_rejected(self):
        test_key = bytes(range(32))
        result = kb.check_production_key(test_key, valid_metadata(), environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "PUBLIC_TEST_VECTOR")

    def test_empty_bytes_rejected(self):
        result = kb.check_production_key(b"", valid_metadata(), environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "EMPTY_KEY")

    def test_wrong_length_rejected(self):
        for length in (0, 1, 16, 31, 33, 64):
            key = bytes([1] * length)
            result = kb.check_production_key(key, valid_metadata(), environment="production")
            self.assertFalse(result, msg=f"length {length} should be rejected")
            self.assertIn(result.reason, ("EMPTY_KEY", "INVALID_KEY_LENGTH"))

    def test_none_not_auto_loaded(self):
        result = kb.check_production_key(None, valid_metadata(), environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "DEFAULT_KEY_FORBIDDEN")

    def test_non_bytes_rejected(self):
        result = kb.check_production_key("not bytes", valid_metadata(), environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "INVALID_KEY_TYPE")

    def test_weak_constant_key_rejected_in_production(self):
        result = kb.check_production_key(bytes([7] * 32), valid_metadata(), environment="production")
        self.assertFalse(result)


class MetadataAndEnvironmentTests(unittest.TestCase):
    def test_missing_metadata_rejected(self):
        key = independent_key()
        result = kb.check_production_key(key, None, environment="production", expected_environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "MISSING_PROVISIONING_METADATA")

    def test_environment_mismatch_rejected(self):
        key = independent_key()
        result = kb.check_production_key(key, valid_metadata("staging"), environment="production",
                                        expected_environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "ENVIRONMENT_BINDING_MISMATCH")

    def test_binding_target_expected_mismatch_rejected(self):
        key = independent_key()
        result = kb.check_production_key(key, valid_metadata(), environment="production",
                                        expected_environment="staging")
        self.assertFalse(result)
        self.assertEqual(result.reason, "ENVIRONMENT_BINDING_MISMATCH")

    def test_missing_provenance_rejected(self):
        key = independent_key()
        result = kb.check_production_key(key, {"environment": "production"}, environment="production",
                                        expected_environment="production")
        self.assertFalse(result)
        self.assertIn(result.reason, ("MISSING_PROVENANCE", "MISSING_PROVISIONING_METADATA"))

    def test_synthetic_fixture_blocked_in_production(self):
        key = independent_key()
        meta = valid_metadata(fixture=True)
        result = kb.check_production_key(key, meta, environment="production", expected_environment="production")
        self.assertFalse(result)
        self.assertEqual(result.reason, "SYNTHETIC_FIXTURE_BLOCKED")

    def test_shadow_fixture_allowed_in_synthetic_test_env(self):
        test_key = bytes(range(32))
        meta = {"environment": "test", "fixture": True, "provenance": "synthetic"}
        result = kb.check_production_key(test_key, meta, environment="test", expected_environment="test")
        self.assertTrue(result)


class RaiseAndAliasTests(unittest.TestCase):
    def test_validate_raises_on_invalid(self):
        with self.assertRaises(Exception):
            kb.validate_production_key(bytes(range(32)), valid_metadata(), environment="production")

    def test_aliases_exist(self):
        for name in ("validate_production_key", "check_production_key", "is_production_key_valid",
                     "production_key_boundary", "ProductionKeyBoundary"):
            self.assertTrue(hasattr(kb, name), name)

    def test_class_check(self):
        key = independent_key()
        result = kb.ProductionKeyBoundary.check(key, valid_metadata(), environment="production")
        self.assertTrue(result)


class FailClosedSideEffectsTests(unittest.TestCase):
    def test_no_dispatch_fields_always_false(self):
        key = independent_key()
        result = kb.check_production_key(key, valid_metadata(), environment="production")
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse(result["execution_started"])
        self.assertEqual(result["messages_sent"], 0)
        self.assertEqual(result["side_effects"], [])

    def test_no_input_mutation(self):
        key = independent_key()
        meta = valid_metadata()
        snapshot = dict(meta)
        kb.check_production_key(key, meta, environment="production")
        self.assertEqual(meta, snapshot)

    def test_no_secret_bytes_in_exception(self):
        key = independent_key()
        secret_hex = key.hex()
        try:
            kb.validate_production_key(b"", valid_metadata(), environment="production")
        except Exception as exc:  # noqa: BLE001
            self.assertNotIn(secret_hex, str(exc))
            self.assertNotIn(key.decode("latin1"), str(exc))


class StaticSafetyTests(unittest.TestCase):
    def test_no_os_or_keyring_import(self):
        import inspect
        source = inspect.getsource(kb)
        self.assertNotIn("import os", source)
        self.assertNotIn("import keyring", source)
        self.assertNotIn("keyring.", source)

    def test_no_logging_secret_bytes(self):
        import inspect
        source = inspect.getsource(kb)
        # The module must not call logging with raw key material.  We allow no
        # logging import at all, which is even stronger.
        self.assertNotIn("import logging", source)
        self.assertNotIn("logger.debug", source)
        # Avoid false positives from substrings like "_fingerprint(".
        self.assertIsNone(re.search(r"\bprint\s*\(", source))


if __name__ == "__main__":
    unittest.main()
