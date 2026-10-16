"""Explicit production gate: tests are not evidence of live capability."""
from pathlib import Path
import json

REQUIRED_EVIDENCE = (
    "os_sandbox_external_attestation",
    "trusted_signed_receipt_verification",
    "real_cross_host_ntp_attestation",
    "hmac_key_custody",
    "discord_delivery_ack",
    "sqlite_rollback_drill",
    "linux_symlink_toctou_test",
    "independent_security_review",
    "production_approval",
)

def evaluate(evidence):
    if not isinstance(evidence, dict):
        raise TypeError("evidence must be keyed mapping")
    missing = [key for key in REQUIRED_EVIDENCE
               if not isinstance(evidence.get(key), dict)
               or evidence[key].get("verified") is not True
               or not isinstance(evidence[key].get("receipt"), str)
               or not evidence[key]["receipt"].strip()]
    return {"status": "BLOCKED" if missing else "EVIDENCE_PRESENT_REQUIRES_VERIFICATION",
            "production_allowed": False, "missing": missing,
            "required": len(REQUIRED_EVIDENCE)}

def save_report(path, evidence):
    result = evaluate(evidence)
    Path(path).write_text(json.dumps(result, indent=2),encoding="utf-8")
    return result
