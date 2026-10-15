"""Staging-only composition: trusted context required for all dispatch calls."""
from __future__ import annotations
from .capability_dispatch import CapabilityDispatcher
from .governed_dispatch import GovernedDispatcher, DispatchContext

def build_governed_dispatcher(*, trusted_context_provider, infra_executor,
                              workspace_executor, **optional_executors):
    if not callable(trusted_context_provider):
        raise TypeError("trusted context provider required")
    core = CapabilityDispatcher(infra_executor, workspace_executor, **optional_executors)
    return GovernedDispatcher(core, trusted_context_provider)
