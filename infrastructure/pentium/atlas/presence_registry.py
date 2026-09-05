from __future__ import annotations

import ipaddress
import math
import re
from dataclasses import dataclass, replace
from typing import Iterable


_MAC_RE = re.compile(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
_ZONE = "WIFI_OBSERVED"
_VALID_PRESENCE = {"present", "missing"}
_VALID_EVENTS = {"appeared", "changed", "missing", "recovered"}


class PresenceRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class PresenceDevice:
    mac: str
    ipv4: str
    first_seen: float
    last_seen: float
    presence: str = "present"
    zone: str = _ZONE
    hostname: str | None = None
    vendor: str | None = None


@dataclass(frozen=True)
class PresenceEvent:
    kind: str
    mac: str
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class PresenceUpdate:
    devices: tuple[PresenceDevice, ...]
    events: tuple[PresenceEvent, ...]


def _normalize_mac(value: str) -> str:
    candidate = str(value).strip().lower()
    if not _MAC_RE.fullmatch(candidate):
        raise PresenceRegistryError("invalid MAC address")
    if int(candidate[:2], 16) & 1:
        raise PresenceRegistryError("multicast MAC is not a device identity")
    if candidate == "00:00:00:00:00:00":
        raise PresenceRegistryError("zero MAC is not a device identity")
    return candidate


def _normalize_ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ipaddress.AddressValueError as exc:
        raise PresenceRegistryError("invalid IPv4 address") from exc


def _optional_text(value) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if len(candidate) > 255:
        raise PresenceRegistryError("presence metadata exceeds 255 characters")
    return candidate


def _timestamp(value: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PresenceRegistryError("observed_at must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise PresenceRegistryError("observed_at must be finite and >= 0")
    return result


def _validate_device(device: PresenceDevice) -> PresenceDevice:
    mac = _normalize_mac(device.mac)
    ipv4 = _normalize_ipv4(device.ipv4)
    first_seen = _timestamp(device.first_seen)
    last_seen = _timestamp(device.last_seen)
    if last_seen < first_seen:
        raise PresenceRegistryError("last_seen cannot predate first_seen")
    if device.presence not in _VALID_PRESENCE or device.zone != _ZONE:
        raise PresenceRegistryError("invalid presence device state")
    return PresenceDevice(
        mac=mac,
        ipv4=ipv4,
        first_seen=first_seen,
        last_seen=last_seen,
        presence=device.presence,
        zone=_ZONE,
        hostname=_optional_text(device.hostname),
        vendor=_optional_text(device.vendor),
    )


class PresenceRegistry:
    def __init__(
        self,
        *,
        presence_window_s: float,
        max_devices: int = 256,
        devices: Iterable[PresenceDevice] = (),
    ):
        if presence_window_s <= 0:
            raise PresenceRegistryError("presence_window_s must be > 0")
        if not isinstance(max_devices, int) or max_devices <= 0:
            raise PresenceRegistryError("max_devices must be integer > 0")
        self._presence_window_s = float(presence_window_s)
        self._max_devices = max_devices
        restored = [_validate_device(item) for item in devices]
        if len(restored) > max_devices:
            raise PresenceRegistryError("presence registry exceeds device bound")
        if len({item.mac for item in restored}) != len(restored):
            raise PresenceRegistryError("duplicate MAC in presence registry")
        self._devices = {item.mac: item for item in restored}

    @property
    def presence_window_s(self) -> float:
        return self._presence_window_s

    @property
    def max_devices(self) -> int:
        return self._max_devices

    def devices(self) -> tuple[PresenceDevice, ...]:
        return tuple(sorted(self._devices.values(), key=lambda item: item.mac))

    def observe(self, neighbors, observed_at: float) -> PresenceUpdate:
        now = _timestamp(observed_at)
        observed: dict[str, tuple[str, str | None, str | None]] = {}
        for neighbor in neighbors:
            mac = _normalize_mac(getattr(neighbor, "mac"))
            ipv4 = _normalize_ipv4(getattr(neighbor, "ipv4"))
            hostname = _optional_text(getattr(neighbor, "hostname", None))
            vendor = _optional_text(getattr(neighbor, "vendor", None))
            candidate = (ipv4, hostname, vendor)
            previous = observed.get(mac)
            if previous is not None and previous != candidate:
                raise PresenceRegistryError("ambiguous duplicate MAC in one observation")
            observed[mac] = candidate

        new_count = sum(1 for mac in observed if mac not in self._devices)
        if len(self._devices) + new_count > self._max_devices:
            raise PresenceRegistryError("presence registry exceeds device bound")

        devices = dict(self._devices)
        events: list[PresenceEvent] = []
        for mac in sorted(observed):
            ipv4, hostname_hint, vendor_hint = observed[mac]
            current = devices.get(mac)
            if current is None:
                devices[mac] = PresenceDevice(
                    mac=mac,
                    ipv4=ipv4,
                    first_seen=now,
                    last_seen=now,
                    presence="present",
                    hostname=hostname_hint,
                    vendor=vendor_hint,
                )
                events.append(PresenceEvent("appeared", mac))
                continue

            hostname = hostname_hint if hostname_hint is not None else current.hostname
            vendor = vendor_hint if vendor_hint is not None else current.vendor
            changed_fields = tuple(
                field
                for field, before, after in (
                    ("ipv4", current.ipv4, ipv4),
                    ("hostname", current.hostname, hostname),
                    ("vendor", current.vendor, vendor),
                )
                if before != after
            )
            kind = None
            if current.presence == "missing":
                kind = "recovered"
            elif changed_fields:
                kind = "changed"
            devices[mac] = replace(
                current,
                ipv4=ipv4,
                last_seen=now,
                presence="present",
                hostname=hostname,
                vendor=vendor,
            )
            if kind is not None:
                events.append(PresenceEvent(kind, mac, changed_fields))

        for mac, current in tuple(devices.items()):
            if mac in observed or current.presence != "present":
                continue
            if now - current.last_seen > self._presence_window_s:
                devices[mac] = replace(current, presence="missing")
                events.append(PresenceEvent("missing", mac))

        events.sort(key=lambda event: (event.mac, event.kind))
        if len(events) > self._max_devices:
            raise PresenceRegistryError("presence event count exceeds bound")

        self._devices = devices
        return PresenceUpdate(self.devices(), tuple(events))
