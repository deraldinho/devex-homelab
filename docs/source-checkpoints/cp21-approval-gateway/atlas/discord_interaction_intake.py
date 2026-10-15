"""Authenticated Discord interaction intake, without HTTP or network side effects."""
from __future__ import annotations
import json
from .discord_signature import verify_discord_request
from .discord_approval_boundary import TrustedDiscordEvent

def parse_verified_interaction(*, public_key_hex: str, signature_hex: str,
                               timestamp: str, raw_body: bytes, now=None) -> TrustedDiscordEvent | None:
    if not verify_discord_request(public_key_hex=public_key_hex,
            signature_hex=signature_hex,timestamp=timestamp,raw_body=raw_body,now=now):
        return None
    try:
        payload=json.loads(raw_body)
        if not isinstance(payload,dict):
            return None
        actor=payload.get("member",{}).get("user",{}).get("id")
        channel=payload.get("channel_id")
        interaction=payload.get("id")
        if not all(isinstance(x,str) and x.isdigit() and 1 <= len(x) <= 22
                   for x in (actor,channel,interaction)):
            return None
        return TrustedDiscordEvent(actor_id=actor,channel_id=channel,
                                   interaction_id=interaction,signature_verified=True)
    except (TypeError,ValueError,AttributeError):
        return None
