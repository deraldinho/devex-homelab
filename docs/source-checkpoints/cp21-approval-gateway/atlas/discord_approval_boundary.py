"""Authenticated approval boundary for a Discord interaction payload.
The Discord adapter must verify Ed25519 signature on raw HTTP bytes upstream.
This kernel checks authenticated identity, exact plan hash and one-time claim.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from .approval_inbox import DurableApprovalInbox

@dataclass(frozen=True)
class TrustedDiscordEvent:
    actor_id: str
    channel_id: str
    interaction_id: str
    signature_verified: bool

@dataclass(frozen=True)
class ApprovalPlan:
    proposal_id: str
    content: dict
    owner_id: str
    channel_id: str
    expires_at: datetime
    def digest(self):
        return hashlib.sha256(json.dumps(self.content,sort_keys=True,
            separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()

def accept_approval(inbox: DurableApprovalInbox, *, plan: ApprovalPlan,
                    event: TrustedDiscordEvent, submitted_hash: str,
                    now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or plan.expires_at.tzinfo is None:
        return False
    if not (event.signature_verified and event.actor_id == plan.owner_id
            and event.channel_id == plan.channel_id
            and event.interaction_id and plan.proposal_id
            and now < plan.expires_at):
        return False
    if not hmac.compare_digest(submitted_hash, plan.digest()):
        return False
    return inbox.claim(nonce=event.interaction_id,
        proposal_id=plan.proposal_id, proposal_hash=plan.digest(),
        approver=event.actor_id, verified=True, unexpired=True)
