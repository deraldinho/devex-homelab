from __future__ import annotations

import json
import os
from pathlib import Path

from .presence_registry import (
    PresenceDevice,
    PresenceRegistry,
    PresenceRegistryError,
)


class PresenceStateInvalid(ValueError):
    pass


class PresenceRepository:
    def __init__(self, path: Path, *, max_devices: int = 256):
        if not isinstance(max_devices, int) or max_devices <= 0:
            raise ValueError("max_devices must be integer > 0")
        self._path = Path(path)
        self._max_devices = max_devices

    @property
    def path(self) -> Path:
        return self._path

    def save(self, registry: PresenceRegistry) -> None:
        devices = registry.devices()
        if len(devices) > self._max_devices:
            raise PresenceStateInvalid("presence registry exceeds repository bound")
        payload = {
            "schema_version": 1,
            "devices": [
                {
                    "mac": item.mac,
                    "ipv4": item.ipv4,
                    "first_seen": item.first_seen,
                    "last_seen": item.last_seen,
                    "presence": item.presence,
                    "zone": item.zone,
                    "hostname": item.hostname,
                    "vendor": item.vendor,
                }
                for item in devices
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                fd = os.open(self._path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, *, presence_window_s: float) -> PresenceRegistry | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError("presence schema_version must be 1")
            raw_devices = payload.get("devices")
            if not isinstance(raw_devices, list):
                raise ValueError("presence devices must be a list")
            if len(raw_devices) > self._max_devices:
                raise ValueError("presence saved state exceeds device bound")
            devices = tuple(_device_from_payload(item) for item in raw_devices)
            return PresenceRegistry(
                presence_window_s=presence_window_s,
                max_devices=self._max_devices,
                devices=devices,
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, PresenceRegistryError) as exc:
            raise PresenceStateInvalid(str(exc)) from exc


def _device_from_payload(item) -> PresenceDevice:
    if not isinstance(item, dict):
        raise ValueError("presence device must be an object")
    return PresenceDevice(
        mac=item["mac"],
        ipv4=item["ipv4"],
        first_seen=item["first_seen"],
        last_seen=item["last_seen"],
        presence=item["presence"],
        zone=item["zone"],
        hostname=item.get("hostname"),
        vendor=item.get("vendor"),
    )
