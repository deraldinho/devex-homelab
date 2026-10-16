"""Strict HMAC validation for externally issued terminal agent receipts.

Test vectors use caller-provided keys only. Production custody and rotation
must be independently attested. Signed data excludes the signature field.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

FIELDS = ("task_id", "session_id", "outcome", "cost", "issued_at", "issuer")
VALID_OUTCOMES = frozenset(("succeeded", "failed", "cancelled"))

def canonical(receipt):
    return json.dumps({name:receipt[name] for name in FIELDS},
                      sort_keys=True, separators=(",",":"),ensure_ascii=False).encode()

def sign(receipt, key):
    if not isinstance(key,bytes) or len(key)<32:
        raise ValueError("minimum 32-byte key required")
    return hmac.new(key, canonical(receipt), hashlib.sha256).hexdigest()

def verifier(key, *, expected_issuer, expected_task, expected_session,
             now, max_age_seconds=120):
    if not isinstance(key,bytes) or len(key)<32:
        raise ValueError("minimum 32-byte key required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware UTC assessment time required")
    now=now.astimezone(timezone.utc)
    def verify(receipt):
        if not isinstance(receipt,dict) or set(receipt)!=set(FIELDS)|{"signature"}:
            return False
        if receipt["issuer"]!=expected_issuer or receipt["task_id"]!=expected_task:
            return False
        if receipt["session_id"]!=expected_session or receipt["outcome"] not in VALID_OUTCOMES:
            return False
        if type(receipt["cost"]) not in (int,float) or receipt["cost"]!=0:
            return False
        try:
            instant=datetime.fromisoformat(receipt["issued_at"].replace("Z","+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                return False
            age=(now-instant.astimezone(timezone.utc)).total_seconds()
            if not 0<=age<=max_age_seconds:
                return False
            supplied=receipt["signature"]
            if not isinstance(supplied,str) or len(supplied)!=64:
                return False
            return hmac.compare_digest(sign(receipt,key),supplied)
        except (TypeError,ValueError,KeyError,AttributeError):
            return False
    return verify
