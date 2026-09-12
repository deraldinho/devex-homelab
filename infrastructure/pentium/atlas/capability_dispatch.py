from __future__ import annotations


class CapabilityDispatcher:
    def __init__(self, infra_executor, workspace_executor):
        self._infra_executor = infra_executor
        self._workspace_executor = workspace_executor

    def __call__(self, capability: str, arguments: dict[str, object], plan, action):
        if str(capability).startswith("workspace_"):
            return self._workspace_executor(capability, arguments, plan, action)
        return self._infra_executor(capability, arguments, plan, action)
