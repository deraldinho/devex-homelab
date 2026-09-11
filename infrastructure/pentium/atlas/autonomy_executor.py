from __future__ import annotations

import subprocess
import time


class VerificationFailedError(RuntimeError):
    """Raised when closed-loop verification fails after an autonomous action."""


class SafeLocalCapabilityExecutor:
    """Executes only explicitly allowlisted, local, reversible Atlas controls with closed-loop verification."""

    def __init__(
        self,
        *,
        host: str,
        services=(),
        runner=subprocess.run,
        timeout_s: float = 10.0,
        verifier=None,
        verify_timeout_s: float = 15.0,
        verify_poll_interval_s: float = 0.5,
        on_executed=None,
    ):
        self._host = str(host)
        self._services = frozenset(str(service) for service in services)
        self._runner = runner
        self._timeout_s = float(timeout_s)
        self._verifier = verifier
        self._verify_timeout_s = float(verify_timeout_s)
        self._verify_poll_interval_s = float(verify_poll_interval_s)
        self._on_executed = on_executed

    def _default_verify(self, service: str) -> bool:
        deadline = time.time() + self._verify_timeout_s
        while True:
            res = self._runner(
                ["systemctl", "--user", "is-active", service],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
            if res.returncode == 0 and res.stdout.strip() == "active":
                return True
            if time.time() >= deadline:
                return False
            time.sleep(self._verify_poll_interval_s)

    def __call__(self, capability: str, arguments: dict[str, object], _plan, _action) -> None:
        host = str(arguments.get("host") or "")
        service = str(arguments.get("service") or "")
        if capability != "restart_service":
            raise PermissionError("capability_not_autonomous")
        if host != self._host:
            raise PermissionError("remote_host_forbidden")
        if service not in self._services:
            raise PermissionError("service_not_allowlisted")
        self._runner(
            ["systemctl", "--user", "restart", service],
            check=True,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
        )
        verify_func = self._verifier if self._verifier is not None else self._default_verify
        if not verify_func(service):
            raise VerificationFailedError(f"closed-loop verification failed for service {service}")
        if self._on_executed is not None:
            self._on_executed(capability, arguments)
