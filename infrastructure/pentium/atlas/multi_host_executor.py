from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Callable

try:
    from agent.managed_control import (
        ControlAuthorization,
        ManagedControlOperation,
        ManagedControlService,
    )
    from agent.managed_inventory import ManagedInventory
except ImportError:
    from infrastructure.pentium.agent.managed_control import (
        ControlAuthorization,
        ManagedControlOperation,
        ManagedControlService,
    )
    from infrastructure.pentium.agent.managed_inventory import ManagedInventory

from .autonomy_executor import VerificationFailedError


_CAPABILITY_OPERATIONS = {
    "start_service": ManagedControlOperation.START_SERVICE,
    "stop_service": ManagedControlOperation.STOP_SERVICE,
    "restart_service": ManagedControlOperation.RESTART_SERVICE,
    "restart_container": ManagedControlOperation.RESTART_CONTAINER,
    "reboot_host": ManagedControlOperation.REBOOT_HOST,
}


class CanonicalHealthVerifier:
    def __init__(
        self,
        snapshot_path: Path,
        *,
        timeout_s: float = 0.0,
        poll_interval_s: float = 0.5,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    ):
        self.snapshot_path = Path(snapshot_path)
        self.timeout_s = max(0.0, float(timeout_s))
        self.poll_interval_s = max(0.01, float(poll_interval_s))
        self.monotonic = monotonic
        self.sleeper = sleeper

    @staticmethod
    def _component_id(capability: str, arguments: dict[str, object]) -> str | None:
        if capability in {"start_service", "stop_service", "restart_service"}:
            value = str(arguments.get("service") or "").strip()
            return value or None
        if capability == "restart_container":
            value = str(arguments.get("container") or "").strip()
            return f"container:{value}" if value else None
        return None

    def _check(self, host: str, component_id: str) -> bool:
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            return False
        components = payload.get("components")
        if not isinstance(components, list):
            return False
        for item in components:
            if not isinstance(item, dict):
                continue
            if (
                str(item.get("component_id") or "") == component_id
                and str(item.get("host") or "") == str(host)
            ):
                return str(item.get("state") or "").lower() == "healthy"
        return False

    def __call__(
        self,
        host: str,
        capability: str,
        arguments: dict[str, object],
        result: dict[str, object],
    ) -> bool:
        if str(result.get("status") or "").lower() != "success":
            return False
        component_id = self._component_id(str(capability), dict(arguments))
        if component_id is None:
            return False
        deadline = self.monotonic() + self.timeout_s
        while True:
            if self._check(str(host), component_id):
                return True
            if self.timeout_s <= 0.0 or self.monotonic() >= deadline:
                return False
            self.sleeper(self.poll_interval_s)


class MultiHostCapabilityExecutor:
    def __init__(
        self,
        local_executor,
        managed_control: ManagedControlService,
        inventory: ManagedInventory,
        *,
        verifier: Callable[[str, str, dict[str, object], dict[str, object]], bool],
        confirmation_checker: Callable[[str, dict[str, object], object, object], bool] = lambda *_: False,
        on_executed=None,
    ):
        self._local_executor = local_executor
        self._managed_control = managed_control
        self._inventory = inventory
        self._verifier = verifier
        self._confirmation_checker = confirmation_checker
        self._on_executed = on_executed

    @staticmethod
    def _target(capability: str, arguments: dict[str, object]) -> str | None:
        if capability in {"start_service", "stop_service", "restart_service"}:
            value = str(arguments.get("service") or "").strip()
            if not value:
                raise ValueError("service target required")
            return value
        if capability == "restart_container":
            value = str(arguments.get("container") or "").strip()
            if not value:
                raise ValueError("container target required")
            return value
        if capability == "reboot_host":
            return None
        raise PermissionError("capability_not_managed_control")

    def _verified(
        self,
        host: str,
        capability: str,
        arguments: dict[str, object],
        result: dict[str, object],
    ) -> dict[str, object]:
        if not self._verifier(host, capability, arguments, result):
            raise VerificationFailedError(
                f"closed-loop functional verification failed for {host}:{capability}"
            )
        if self._on_executed is not None:
            self._on_executed(capability, arguments)
        return result

    def __call__(
        self,
        capability: str,
        arguments: dict[str, object],
        plan=None,
        action=None,
    ) -> dict[str, object]:
        capability = str(capability)
        arguments = dict(arguments)
        host = str(arguments.get("host") or "").strip()
        if not host:
            raise ValueError("host required")

        if host == "pentium":
            if capability != "restart_service":
                raise PermissionError("local_capability_not_autonomous")
            self._local_executor(capability, arguments, plan, action)
            result = {
                "status": "success",
                "host": host,
                "operation": capability,
                "target": str(arguments.get("service") or ""),
            }
            return self._verified(host, capability, arguments, result)

        self._inventory.require_managed(host)
        try:
            operation = _CAPABILITY_OPERATIONS[capability]
        except KeyError as exc:
            raise PermissionError("capability_not_managed_control") from exc

        target = self._target(capability, arguments)
        human_confirmed = False
        if operation is ManagedControlOperation.REBOOT_HOST:
            human_confirmed = bool(
                self._confirmation_checker(capability, arguments, plan, action)
            )
            if not human_confirmed:
                raise PermissionError("human confirmation required")

        result = self._managed_control.execute(
            ControlAuthorization(
                authorized=True,
                host_id=host,
                operation=operation,
                target=target,
                human_confirmed=human_confirmed,
                reason="multi_host_executor",
            )
        )
        if str(result.get("status") or "") != "success":
            raise RuntimeError("managed_control_failed")
        return self._verified(host, capability, arguments, dict(result))
