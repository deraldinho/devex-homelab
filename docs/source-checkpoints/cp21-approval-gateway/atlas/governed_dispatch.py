"""Explicit security boundary for Atlas capability dispatch.
Designed to wrap an existing dispatcher; untrusted LLM data never creates a mandate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class DispatchContext:
    source: str
    scope: str
    allowed_capabilities: frozenset[str]
    approved_capabilities: frozenset[str] = frozenset()
    receipt_verified: bool = False

class ApprovalRequired(PermissionError):
    pass

class GovernedDispatcher:
    def __init__(self, delegate: Callable, trusted_context_provider: Callable[[], DispatchContext]):
        self._delegate=delegate
        self._provider=trusted_context_provider

    def __call__(self, capability, arguments, plan=None, action=None):
        # Context must come from a trusted session/inbox, never capability arguments.
        ctx=self._provider()
        if not isinstance(ctx,DispatchContext) or not ctx.scope:
            raise ApprovalRequired("trusted_context_missing")
        cap=str(capability)
        if cap not in ctx.allowed_capabilities:
            if cap not in ctx.approved_capabilities or not ctx.receipt_verified:
                raise ApprovalRequired("initiative_requires_verified_approval")
        # Separate operational policy remains mandatory in the underlying delegate.
        return self._delegate(capability,arguments,plan,action)
