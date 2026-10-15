"""Verify Discord interaction signatures before constructing trusted events.
Pure adapter; no HTTP listener, no credentials and no outbound requests.
"""
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

def verify_discord_request(*, public_key_hex: str, signature_hex: str,
                           timestamp: str, raw_body: bytes,
                           now: datetime | None = None, max_age_seconds: int = 300) -> bool:
    try:
        if not isinstance(raw_body, bytes) or not isinstance(timestamp, str):
            return False
        if len(public_key_hex) != 64 or len(signature_hex) != 128:
            return False
        if max_age_seconds <= 0 or max_age_seconds > 300:
            return False
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            return False
        submitted = int(timestamp)
        age = abs(current.timestamp() - submitted)
        if age > max_age_seconds:
            return False
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        public_key.verify(bytes.fromhex(signature_hex),timestamp.encode("utf-8")+raw_body)
        return True
    except (ValueError,TypeError,InvalidSignature,OverflowError):
        return False
