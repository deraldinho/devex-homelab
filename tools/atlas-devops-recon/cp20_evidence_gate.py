"""CP20 production evidence boundary. Never grants production authorization.

Evidence claims must be bound to the expected checkpoint and verified by a
trusted caller supplied verifier. A self-reported 'verified' flag is not proof.
"""
from collections.abc import Mapping
from atlas_native_readiness import REQUIRED_EVIDENCE

SCHEMA = "atlas.cp20.evidence.v1"


def evaluate_evidence(evidence, *, checkpoint, verifier=None):
    """Return a fail-closed, diagnostic-only evaluation.

    verifier(category, receipt, checkpoint) must return the singleton True
    after independently authenticating provenance, integrity and scope.
    """
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        raise ValueError("nonempty checkpoint required")
    if not isinstance(evidence, Mapping):
        raise TypeError("evidence must be a mapping")
    rejected = {}
    for category in REQUIRED_EVIDENCE:
        item = evidence.get(category)
        if not isinstance(item, Mapping):
            rejected[category] = "MISSING"
            continue
        if item.get("schema") != SCHEMA or item.get("checkpoint") != checkpoint:
            rejected[category] = "SCOPE_MISMATCH"
            continue
        receipt = item.get("receipt")
        if not isinstance(receipt, str) or not receipt.strip():
            rejected[category] = "INVALID_RECEIPT"
            continue
        if verifier is None:
            rejected[category] = "NO_TRUSTED_VERIFIER"
            continue
        try:
            authenticated = verifier(category, receipt, checkpoint) is True
        except Exception:
            authenticated = False
        if not authenticated:
            rejected[category] = "VERIFICATION_FAILED"
    return {
        "status": "EVIDENCE_VERIFIED_REQUIRES_AUTHORIZATION" if not rejected else "BLOCKED",
        "production_allowed": False,
        "rejected": rejected,
        "checked": len(REQUIRED_EVIDENCE),
    }
