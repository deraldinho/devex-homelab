from __future__ import annotations


class CapabilityDispatcher:
    def __init__(self, infra_executor, workspace_executor, discord_executor=None, git_executor=None, vitals_executor=None, l2j_executor=None, task_executor=None):
        self._infra_executor = infra_executor
        self._workspace_executor = workspace_executor
        self._discord_executor = discord_executor
        self._git_executor = git_executor
        self._vitals_executor = vitals_executor
        self._l2j_executor = l2j_executor
        self._task_executor = task_executor

    def __call__(self, capability: str, arguments: dict[str, object], plan=None, action=None):
        cap = str(capability)
        if cap.startswith("workspace_"):
            return self._workspace_executor(capability, arguments, plan, action)
        if cap.startswith("task_") and self._task_executor is not None:
            return self._task_executor(capability, arguments, plan, action)
        if cap.startswith("discord_") and self._discord_executor is not None:
            return self._discord_executor(capability, arguments, plan, action)
        if cap.startswith("git_") and self._git_executor is not None:
            return self._git_executor(capability, arguments, plan, action)
        if cap.startswith("l2j_") and self._l2j_executor is not None:
            return self._l2j_executor(capability, arguments)
        if cap == "get_cluster_vitals" and self._vitals_executor is not None:
            return self._vitals_executor(capability, arguments, plan, action)
        return self._infra_executor(capability, arguments, plan, action)
