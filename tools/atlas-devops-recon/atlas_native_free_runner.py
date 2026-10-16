"""Adapter to existing OpenCode FreeModelFailover, fail-closed sandbox contract.

Use an isolated non-production snapshot. This wrapper cannot enforce OS sandbox
by itself; the caller must supply independent attestation.
"""
from pathlib import Path

def make_free_runner(*, api, state_path, model_manager_type, sandbox_attestation):
    if not callable(api) or not callable(model_manager_type):
        raise TypeError("API and free-model manager required")
    if not isinstance(sandbox_attestation, dict) or (
        sandbox_attestation.get("os_enforced") is not True
        or sandbox_attestation.get("network_restricted") is not True
        or sandbox_attestation.get("secrets_excluded") is not True
        or sandbox_attestation.get("read_only_tools") is not True
    ):
        raise PermissionError("OS sandbox attestation absent")
    directory=Path(sandbox_attestation.get("snapshot_root","")).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("sandbox snapshot missing")
    from atlas_native_workflow import inspect
    missing, baseline=inspect(directory)
    if missing:
        raise PermissionError("snapshot incomplete")
    def runner(payload):
        if payload.get("read_only") is not True or payload.get("execution_authorized") is not False:
            raise PermissionError("invalid readonly request")
        if Path(payload["project_root"]).resolve(strict=True) != directory:
            raise PermissionError("snapshot location mismatch")
        if payload.get("fingerprint") != baseline or inspect(directory)[1] != baseline:
            raise PermissionError("baseline drift")
        manager=model_manager_type(api, state_path=Path(state_path), timeout_seconds=90, max_attempts=3)
        prompt=("Audit the immutable snapshot in read-only mode. Never edit files, execute scripts, "
                "request secrets, or dispatch subprocesses. Cite code filenames and concrete "
                "findings. If inspection tools are not read-only, stop. Role: "+payload["role"])
        return manager.run(directory=str(directory),title="Atlas-Review-"+payload["task_id"],
                           prompt=prompt,agent="plan")
    return runner
