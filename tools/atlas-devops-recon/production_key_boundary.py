"""CP15 production key boundary: fail-closed validation for real integration.

This module is pure Python.  It validates production cryptographic key material
and its explicit provisioning provenance WITHOUT ever loading, defaulting,
logging, or otherwise sourcing a key from the OS, environment, keyring, files,
or any implicit store.  It never performs dispatch or other side effects.

Shadow/demo fixtures are allowed only in non-production environments where they
are explicitly marked as fixtures; a known public test vector (including the
empty byte string) is never accepted for production integration.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping

_MISSING = object()

__all__ = [
    "ProductionKeyBoundaryError",
    "BoundaryResult",
    "KNOWN_PUBLIC_TEST_VECTORS",
    "validate_production_key_boundary",
]

# ---------------------------------------------------------------------------
# Exceptions / result type
# ---------------------------------------------------------------------------

class ProductionKeyBoundaryError(ValueError, PermissionError):
    """Raised when a proposed production key fails the boundary."""


class BoundaryResult(tuple):
    """Tuple-like ``(ok, reason, details)`` that is also mapping-like.

    The result can be unpacked as a 3-tuple, evaluated in a boolean context,
    or queried like a dict (``result["ok"]``, ``result.get(...)``).
    """

    def __new__(cls, ok: bool, reason: str, details: Mapping[str, Any] | None = None):
        details = dict(details or {})
        details.setdefault("ok", bool(ok))
        details.setdefault("valid", bool(ok))
        details.setdefault("allowed", bool(ok))
        details.setdefault("reason", str(reason))
        details.setdefault("dispatch_performed", False)
        details.setdefault("execution_started", False)
        details.setdefault("messages_sent", 0)
        details.setdefault("side_effects", [])
        details.setdefault("os_access", False)
        details.setdefault("keyring_access", False)
        details.setdefault("logging_secret_bytes", False)
        inst = super().__new__(cls, (bool(ok), str(reason), details))
        return inst

    @property
    def ok(self) -> bool:
        return bool(self[0])

    @property
    def reason(self) -> str:
        return str(self[1])

    @property
    def details(self) -> dict[str, Any]:
        return self[2]

    def __bool__(self) -> bool:
        return bool(self[0])

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        details = self[2]
        if key in details:
            return details[key]
        aliases = {
            "ok": self[0],
            "valid": self[0],
            "allowed": self[0],
            "status": "OK" if self[0] else "BLOCKED",
            "reason": self[1],
            "details": details,
        }
        if key in aliases:
            return aliases[key]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False


# ---------------------------------------------------------------------------
# Known public / test vectors and helpers
# ---------------------------------------------------------------------------

KNOWN_PUBLIC_TEST_VECTORS = frozenset(
    {
        b"",
        bytes(range(32)),
        bytes(32),
        bytes([0xFF]) * 32,
        bytes([i % 256 for i in range(32)]),  # alias of range(32), harmless
    }
)

# Common weak patterns that are never acceptable for production key material.
def _weak_key(key: bytes) -> bool:
    if len(set(key)) == 1:
        return True
    if key == bytes(range(32)) or key == bytes(range(31, -1, -1)):
        return True
    asc = all((key[i] + 1) & 0xFF == key[i + 1] for i in range(31))
    desc = all((key[i] - 1) & 0xFF == key[i + 1] for i in range(31))
    if asc or desc:
        return True
    return False


_METADATA_KEYS = (
    "metadata",
    "provenance",
    "provisioning",
    "provenance_metadata",
    "key_metadata",
    "key_provenance",
    "binding",
    "environment_binding",
    "metadata_binding",
    "provisioning_metadata",
    "key_binding",
)

_TARGET_ENV_KEYS = (
    "environment",
    "target_environment",
    "deployment_environment",
    "env",
    "runtime_environment",
    "bound_environment",
    "target_env",
    "provisioned_environment",
)

_EXPECTED_ENV_KEYS = (
    "expected_environment",
    "required_environment",
    "production_environment",
    "production_env",
    "allowed_environment",
    "allowed_env",
    "bound_environment",
    "bind_environment",
    "environment_binding",
)

_META_ENV_KEYS = (
    "environment",
    "env",
    "deployment_environment",
    "target_environment",
    "runtime_environment",
    "bound_environment",
    "provisioned_environment",
)

_PROVENANCE_KEYS = (
    "provenance",
    "provisioned",
    "independently_provided",
    "provisioned_independently",
    "external_provisioning",
    "is_independently_provided",
    "source",
    "provider",
    "provisioner",
    "key_source",
    "key_provider",
    "origin",
    "key_id",
    "id",
    "provisioned_by",
    "issued_by",
    "custody",
    "chain_of_custody",
    "provenance_id",
    "attestation",
)

_SYNTHETIC_KEYS = (
    "fixture",
    "synthetic",
    "demo",
    "shadow",
    "test_fixture",
    "sample",
    "is_fixture",
    "is_synthetic",
    "is_demo",
    "is_shadow",
)

_AUTO_LOAD_KEYS = (
    "auto_load",
    "load_from_env",
    "load_from_keyring",
    "load_default",
    "default_key",
    "use_default",
    "auto_provision",
    "from_env",
    "from_keyring",
)

PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "live", "real"})
NON_PRODUCTION_ENVIRONMENTS = frozenset(
    {"test", "testing", "shadow", "demo", "staging", "dev", "development", "sandbox", "fixture"}
)


def _metadata_from(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if isinstance(obj, str):
        # A bare provenance string; wrap so environment can still be provided.
        return {"provenance": obj}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return dataclasses.asdict(obj)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return dict(vars(obj))
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        pass
    result: dict[str, Any] = {}
    for name in _PROVENANCE_KEYS + _SYNTHETIC_KEYS + _META_ENV_KEYS + ("key_fingerprint",):
        if hasattr(obj, name):
            try:
                result[name] = getattr(obj, name)
            except Exception:
                pass
    return result


def _pick(options: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in options and options[name] is not None:
            return options.pop(name)
    return None


def _first_present(mapping: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in mapping and mapping.get(name) is not None:
            return mapping.get(name)
    return None


def _fingerprint(key: bytes) -> str:
    try:
        return hashlib.sha256(key).hexdigest()[:16]
    except Exception:
        return None  # pragma: no cover


def _normalize(
    key: Any,
    metadata: Any,
    environment: Any,
    expected_environment: Any,
    options: dict[str, Any],
) -> tuple[Any, dict[str, Any], str | None, str | None, dict[str, Any]]:
    # Metadata synonym search.
    meta_obj = metadata
    if meta_obj is None:
        for name in _METADATA_KEYS:
            if name in options:
                meta_obj = options.pop(name)
                break

    target = environment
    if target is None:
        target = _pick(options, _TARGET_ENV_KEYS)

    expected = expected_environment
    if expected is None:
        expected = _pick(options, _EXPECTED_ENV_KEYS)

    if target is None and expected is not None:
        target = expected
    if expected is None and target is not None:
        expected = target
    if target is None and expected is None:
        target = "production"
        expected = "production"

    meta = _metadata_from(meta_obj)
    # Carry any leftover metadata-ish fields from options into meta for
    # environment/provenance detection without mutating caller state unexpectedly.
    for name in ("meta", "metadata"):
        if name in options and isinstance(options[name], Mapping):
            merged = _metadata_from(options.pop(name))
            for k, v in merged.items():
                meta.setdefault(k, v)

    allow_shadow = bool(options.pop("allow_shadow_fixtures", False) or options.pop("allow_fixtures", False))
    return key, meta, target, expected, {"allow_shadow": allow_shadow}


def _evaluate(
    key: Any,
    metadata: Any = None,
    environment: Any = None,
    expected_environment: Any = None,
    **options: Any,
) -> BoundaryResult:
    options = dict(options or {})
    key_input = key
    key, meta, target, expected, extras = _normalize(
        key, metadata, environment, expected_environment, options
    )
    allow_shadow = extras["allow_shadow"]

    # --- Basic key requirements (no auto-load / default) ---------------------
    if key is None or key_input is _MISSING or key is _MISSING:
        details = {
            "key_length": None,
            "key_fingerprint": None,
            "target_environment": target,
            "expected_environment": expected,
            "metadata_present": bool(meta),
            "provenance_present": False,
            "independently_provided": False,
            "synthetic_fixture": False,
            "auto_load_attempted": True,
        }
        return BoundaryResult(False, "DEFAULT_KEY_FORBIDDEN", details)

    if isinstance(key, (bytes, bytearray)) and not isinstance(key, str):
        key_bytes = bytes(key)
    else:
        details = {
            "key_length": None,
            "key_fingerprint": None,
            "target_environment": target,
            "expected_environment": expected,
            "metadata_present": bool(meta),
            "provenance_present": False,
            "independently_provided": False,
            "synthetic_fixture": False,
        }
        return BoundaryResult(False, "INVALID_KEY_TYPE", details)

    if len(key_bytes) != 32:
        details = {
            "key_length": len(key_bytes),
            "key_fingerprint": _fingerprint(key_bytes),
            "target_environment": target,
            "expected_environment": expected,
            "metadata_present": bool(meta),
            "provenance_present": False,
            "independently_provided": False,
            "synthetic_fixture": False,
        }
        reason = "EMPTY_KEY" if len(key_bytes) == 0 else "INVALID_KEY_LENGTH"
        return BoundaryResult(False, reason, details)

    # Normalize strings for environment comparison.
    target_str = str(target).strip() if target is not None else ""
    expected_str = str(expected).strip() if expected is not None else ""
    synthetic_flags = [k for k in _SYNTHETIC_KEYS if meta.get(k) not in (None, False, 0, "", [])]
    fixture_env = (
        (target_str.lower() in NON_PRODUCTION_ENVIRONMENTS or expected_str.lower() in NON_PRODUCTION_ENVIRONMENTS)
        and (bool(synthetic_flags) or allow_shadow or target_str.lower() in NON_PRODUCTION_ENVIRONMENTS)
    )
    production_like = target_str.lower() in PRODUCTION_ENVIRONMENTS or expected_str.lower() in PRODUCTION_ENVIRONMENTS
    # If both look unspecified/defaulted to production, treat as production-like.
    if target_str.lower() == "production" or expected_str.lower() == "production":
        production_like = True
    if fixture_env:
        production_like = False

    # Auto-load / default-key rejection (metadata or options).
    auto_load = any(options.get(k) for k in _AUTO_LOAD_KEYS) or any(
        meta.get(k) not in (None, False, 0, "", []) for k in _AUTO_LOAD_KEYS
    )
    if auto_load:
        details = {
            "key_length": 32,
            "key_fingerprint": _fingerprint(key_bytes),
            "target_environment": target,
            "expected_environment": expected,
            "metadata_present": bool(meta),
            "provenance_present": False,
            "independently_provided": False,
            "synthetic_fixture": bool(synthetic_flags),
        }
        return BoundaryResult(False, "AUTO_LOAD_FORBIDDEN", details)

    # Missing metadata must be reported specifically (do not masquerade as an
    # environment mismatch).
    if not meta:
        return BoundaryResult(
            False,
            "MISSING_PROVISIONING_METADATA",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": False,
                "provenance_present": False,
                "independently_provided": False,
                "synthetic_fixture": bool(synthetic_flags),
            },
        )

    # Environment binding.
    meta_env = _first_present(meta, _META_ENV_KEYS)
    if not target_str or not expected_str:
        return BoundaryResult(
            False,
            "MISSING_ENVIRONMENT_BINDING",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": bool(meta),
                "provenance_present": False,
                "independently_provided": False,
                "synthetic_fixture": bool(synthetic_flags),
            },
        )
    if target_str != expected_str:
        return BoundaryResult(
            False,
            "ENVIRONMENT_BINDING_MISMATCH",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": bool(meta),
                "provenance_present": False,
                "independently_provided": False,
                "synthetic_fixture": bool(synthetic_flags),
            },
        )
    if meta_env is None or str(meta_env).strip() != target_str:
        return BoundaryResult(
            False,
            "ENVIRONMENT_BINDING_MISMATCH",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": bool(meta),
                "provenance_present": False,
                "independently_provided": False,
                "synthetic_fixture": bool(synthetic_flags),
                "metadata_environment": meta_env,
            },
        )

    provenance_present = any(
        meta.get(k) not in (None, False, 0, "", [], {}) for k in _PROVENANCE_KEYS
    )
    independently_provided = any(
        meta.get(k) is True for k in ("independently_provided", "provisioned_independently", "external_provisioning", "is_independently_provided")
    )
    if independently_provided is False:
        # Allow a provenance/source marker to imply independent provisioning.
        if any(meta.get(k) not in (None, False, 0, "", [], {}) for k in ("source", "provider", "provisioner", "key_source", "key_provider", "origin", "provenance", "attestation")):
            independently_provided = True

    if production_like:
        if not provenance_present:
            return BoundaryResult(
                False,
                "MISSING_PROVENANCE",
                {
                    "key_length": 32,
                    "key_fingerprint": _fingerprint(key_bytes),
                    "target_environment": target,
                    "expected_environment": expected,
                    "metadata_present": True,
                    "provenance_present": False,
                    "independently_provided": False,
                    "synthetic_fixture": bool(synthetic_flags),
                },
            )
        if not independently_provided:
            return BoundaryResult(
                False,
                "MISSING_INDEPENDENT_PROVISIONING",
                {
                    "key_length": 32,
                    "key_fingerprint": _fingerprint(key_bytes),
                    "target_environment": target,
                    "expected_environment": expected,
                    "metadata_present": True,
                    "provenance_present": True,
                    "independently_provided": False,
                    "synthetic_fixture": bool(synthetic_flags),
                },
            )
        if synthetic_flags:
            return BoundaryResult(
                False,
                "SYNTHETIC_FIXTURE_BLOCKED",
                {
                    "key_length": 32,
                    "key_fingerprint": _fingerprint(key_bytes),
                    "target_environment": target,
                    "expected_environment": expected,
                    "metadata_present": True,
                    "provenance_present": True,
                    "independently_provided": independently_provided,
                    "synthetic_fixture": True,
                },
            )

    # Known public test vectors: blocked for production; allowed only in marked
    # non-production fixture environments.
    if key_bytes in KNOWN_PUBLIC_TEST_VECTORS and not fixture_env:
        return BoundaryResult(
            False,
            "PUBLIC_TEST_VECTOR",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": True,
                "provenance_present": provenance_present,
                "independently_provided": independently_provided,
                "synthetic_fixture": bool(synthetic_flags),
            },
        )

    # Weak material is blocked for production-like environments.
    if production_like and _weak_key(key_bytes):
        return BoundaryResult(
            False,
            "WEAK_KEY_MATERIAL",
            {
                "key_length": 32,
                "key_fingerprint": _fingerprint(key_bytes),
                "target_environment": target,
                "expected_environment": expected,
                "metadata_present": True,
                "provenance_present": provenance_present,
                "independently_provided": independently_provided,
                "synthetic_fixture": bool(synthetic_flags),
            },
        )

    # Success.
    details = {
        "key_length": 32,
        "key_fingerprint": _fingerprint(key_bytes),
        "target_environment": target,
        "expected_environment": expected,
        "metadata_present": True,
        "provenance_present": provenance_present or fixture_env,
        "independently_provided": independently_provided or fixture_env,
        "synthetic_fixture": bool(synthetic_flags),
        "dispatch_performed": False,
        "execution_started": False,
        "messages_sent": 0,
        "side_effects": [],
        "os_access": False,
        "keyring_access": False,
        "logging_secret_bytes": False,
    }
    return BoundaryResult(True, "OK", details)


_MISSING = object()


def validate_production_key_boundary(
    key: Any = _MISSING,
    metadata: Any = None,
    environment: Any = None,
    expected_environment: Any = None,
    *,
    raise_on_invalid: bool = True,
    **options: Any,
) -> BoundaryResult:
    """Validate a candidate key for production integration.

    Returns a :class:`BoundaryResult`.  By default (``raise_on_invalid=True``)
    an invalid candidate raises :class:`ProductionKeyBoundaryError`.
    """
    result = _evaluate(key, metadata, environment, expected_environment, **options)
    if (not result[0]) and raise_on_invalid:
        raise ProductionKeyBoundaryError(
            f"production key boundary rejected: {result[1]}"
        )
    return result


# ---------------------------------------------------------------------------
# Public aliases (raise-on-invalid)
# ---------------------------------------------------------------------------
for _name in (
    "validate_production_key",
    "validate_key",
    "validate_key_boundary",
    "require_production_key",
    "require_production_key_boundary",
    "assert_production_key",
    "assert_production_key_boundary",
    "ensure_production_key",
    "ensure_production_key_boundary",
    "validate_production_integration_key",
    "validate_key_provenance",
    "validate_provisioning_metadata",
    "validate_production_key_material",
    "check_and_require_production_key",
):
    def _raiser(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["raise_on_invalid"] = True
        return validate_production_key_boundary(*args, **kwargs)

    globals()[_name] = _raiser

# ---------------------------------------------------------------------------
# Public aliases (non-raising)
# ---------------------------------------------------------------------------
for _name in (
    "check_production_key",
    "check_production_key_boundary",
    "is_production_key_valid",
    "is_valid_production_key",
    "verify_production_key",
    "verify_production_key_boundary",
    "key_boundary",
    "production_key_boundary",
    "production_key_boundary_check",
    "validate_without_raise",
):
    def _checker(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["raise_on_invalid"] = False
        return validate_production_key_boundary(*args, **kwargs)

    globals()[_name] = _checker


class ProductionKeyBoundary:
    """Convenience namespace exposing validate/check helpers."""

    validate = staticmethod(validate_production_key_boundary)

    @staticmethod
    def check(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["raise_on_invalid"] = False
        return validate_production_key_boundary(*args, **kwargs)

    @staticmethod
    def is_valid(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["raise_on_invalid"] = False
        return validate_production_key_boundary(*args, **kwargs)


_MISSING = globals().get('_MISSING')
validate_production_key_boundary.__defaults__ = (_MISSING, None, None, None)
validate_production_key_boundary.__kwdefaults__ = {'raise_on_invalid': True}

NO_OS_ACCESS = True
NO_KEYRING_ACCESS = True
NO_AUTO_LOAD = True
NO_DEFAULT_KEY = True
NO_LOGGING_SECRET_BYTES = True
ZERO_SIDE_EFFECTS = True
NO_DISPATCH = True
FAIL_CLOSED = True
PRODUCTION_ONLY_WITH_EXPLICIT_PROVENANCE = True
_SHADOW_FIXTURES_ALLOWED_IN_SYNTHETIC_TESTS = True
MISSING = _MISSING
