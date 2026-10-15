"""Single authenticated intake to durable proposal authorization.
The caller provides the raw HTTP request and a trusted persisted plan.
Never accepts an untrusted trusted-event or verification flag.
"""
from __future__ import annotations
from datetime import datetime
from .discord_interaction_intake import parse_verified_interaction
from .proposal_registry import ProposalRegistry
from .discord_approval_boundary import ApprovalPlan

def approve_signed_discord_interaction(*, registry: ProposalRegistry, plan: ApprovalPlan,
                                      public_key_hex: str, signature_hex: str, timestamp: str,
                                      raw_body: bytes, submitted_hash: str,
                                      now: datetime | None = None) -> bool:
    event = parse_verified_interaction(public_key_hex=public_key_hex,
        signature_hex=signature_hex,timestamp=timestamp,raw_body=raw_body,now=now)
    if event is None:
        return False
    return registry.approve(plan,event,submitted_hash=submitted_hash,now=now)
