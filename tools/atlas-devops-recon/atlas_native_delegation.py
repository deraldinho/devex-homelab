"""Bounded hierarchical mission delegation, no unrestricted agent spawning.

A supervisor may nominate approved specialist roles; tasks are durable,
idempotent read-only review requests. Model choices are advisory only.
"""
from atlas_native_dispatch import ALLOWED_ROLES, enqueue_readonly_review
MAX_CHILDREN=3
FREE_MODEL_PRIORITY=(
    "nemotron-3.5-lightning-free",
    "mimo-v2.6-flash-free",
    "ling-3.1-flash-free",
)

def delegate(db, mission_id, roles, *, parent_role="coordinator"):
    if parent_role!="coordinator":
        raise PermissionError("only coordinator may delegate")
    if not isinstance(roles,(tuple,list)) or not roles or len(roles)>MAX_CHILDREN:
        raise ValueError("invalid child count")
    if len(set(roles))!=len(roles) or any(role not in ALLOWED_ROLES for role in roles):
        raise ValueError("duplicate or unauthorized child roles")
    return [{"role":role, "models":FREE_MODEL_PRIORITY,
             "request":enqueue_readonly_review(db,mission_id,role)}
            for role in roles]
