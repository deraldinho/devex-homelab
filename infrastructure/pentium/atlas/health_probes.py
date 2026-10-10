from __future__ import annotations

import json
import subprocess
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .health_supervisor_model import ComponentHealthState


def _now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    instant = datetime.fromisoformat(str(value))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return instant.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    state: ComponentHealthState
    observed_at: str
    reason: str
    evidence_refs: tuple[str, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)


class SystemdUserProbe:
    def __init__(
        self,
        unit: str,
        *,
        expected_state: str = "running",
        runner=subprocess.run,
        clock=lambda: datetime.now(timezone.utc),
        timeout_s: float = 5.0,
    ):
        self.unit = str(unit).strip()
        self.expected_state = str(expected_state).strip().lower()
        self.runner = runner
        self.clock = clock
        self.timeout_s = float(timeout_s)

    def probe(self) -> ProbeResult:
        now = _now(self.clock)
        if self.expected_state == "paused":
            return ProbeResult(
                True,
                ComponentHealthState.PAUSED_INTENTIONALLY,
                _utc_text(now),
                "expected_paused",
                (f"systemd-user:{self.unit}",),
                {"dimension": "process", "unit": self.unit},
            )
        command = ["systemctl", "--user", "is-active", self.unit]
        try:
            result = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProbeResult(
                False,
                ComponentHealthState.DISCONNECTED,
                _utc_text(now),
                type(exc).__name__,
                (f"systemd-user:{self.unit}",),
                {"dimension": "process", "unit": self.unit},
            )
        active = result.returncode == 0 and str(result.stdout).strip() == "active"
        return ProbeResult(
            active,
            ComponentHealthState.HEALTHY if active else ComponentHealthState.FAILED,
            _utc_text(now),
            "systemd_active" if active else "systemd_not_active",
            (f"systemd-user:{self.unit}",),
            {"dimension": "process", "unit": self.unit},
        )


class _JsonFreshnessProbe:
    timestamp_field = "generated_at"

    def __init__(
        self,
        path: Path,
        *,
        max_age_s: float,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self.path = Path(path)
        self.max_age_s = float(max_age_s)
        self.clock = clock

    def _read(self) -> tuple[dict | None, ProbeResult | None]:
        now = _now(self.clock)
        if not self.path.is_file():
            return None, ProbeResult(
                False,
                ComponentHealthState.FAILED,
                _utc_text(now),
                "missing_health_file",
                (f"file:{self.path}",),
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload_not_object")
            observed = _parse_utc(str(payload[self.timestamp_field]))
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            return None, ProbeResult(
                False,
                ComponentHealthState.DEGRADED,
                _utc_text(now),
                f"invalid_health_payload:{type(exc).__name__}",
                (f"file:{self.path}",),
            )
        age_s = max(0.0, (now - observed).total_seconds())
        if age_s > self.max_age_s:
            return payload, ProbeResult(
                False,
                ComponentHealthState.STALE,
                _utc_text(now),
                "health_snapshot_stale",
                (f"file:{self.path}",),
                {"age_s": age_s, "max_age_s": self.max_age_s},
            )
        return payload, None


class DiscordGatewayProbe(_JsonFreshnessProbe):
    timestamp_field = "updated_at"

    def probe(self) -> ProbeResult:
        now = _now(self.clock)
        payload, error = self._read()
        if error is not None:
            return error
        connected = bool(payload.get("connected")) and str(payload.get("state", "")).lower() == "connected"
        return ProbeResult(
            connected,
            ComponentHealthState.HEALTHY if connected else ComponentHealthState.DISCONNECTED,
            _utc_text(now),
            str(payload.get("reason") or ("gateway_connected" if connected else "gateway_disconnected")),
            (f"file:{self.path}",),
            {"dimension": "functional", "connected": connected},
        )


class CognitiveSnapshotProbe(_JsonFreshnessProbe):
    timestamp_field = "generated_at"

    def probe(self) -> ProbeResult:
        now = _now(self.clock)
        payload, error = self._read()
        if error is not None:
            return error
        return ProbeResult(
            True,
            ComponentHealthState.HEALTHY,
            _utc_text(now),
            "cognitive_snapshot_fresh",
            (f"file:{self.path}",),
            {"dimension": "freshness"},
        )


class ObservationJournalProbe:
    def __init__(
        self,
        path: Path,
        *,
        max_age_s: float,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self.path = Path(path)
        self.max_age_s = float(max_age_s)
        self.clock = clock

    def probe(self) -> ProbeResult:
        now = _now(self.clock)
        if not self.path.is_file():
            return ProbeResult(
                False,
                ComponentHealthState.FAILED,
                _utc_text(now),
                "observation_journal_missing",
                (f"file:{self.path}",),
            )
        try:
            age_s = max(0.0, now.timestamp() - self.path.stat().st_mtime)
        except OSError as exc:
            return ProbeResult(
                False,
                ComponentHealthState.DEGRADED,
                _utc_text(now),
                type(exc).__name__,
                (f"file:{self.path}",),
            )
        fresh = age_s <= self.max_age_s
        return ProbeResult(
            fresh,
            ComponentHealthState.HEALTHY if fresh else ComponentHealthState.STALE,
            _utc_text(now),
            "observation_journal_progressing" if fresh else "observation_journal_stale",
            (f"file:{self.path}",),
            {"dimension": "freshness", "age_s": age_s, "max_age_s": self.max_age_s},
        )


def _default_http_getter(url: str, timeout_s: float) -> tuple[int, object]:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        raw = response.read()
        return int(response.status), json.loads(raw.decode("utf-8"))


class DashboardHttpProbe:
    def __init__(
        self,
        url: str,
        *,
        getter=_default_http_getter,
        clock=lambda: datetime.now(timezone.utc),
        timeout_s: float = 5.0,
    ):
        self.url = str(url)
        self.getter = getter
        self.clock = clock
        self.timeout_s = float(timeout_s)

    def probe(self) -> ProbeResult:
        now = _now(self.clock)
        try:
            status, payload = self.getter(self.url, self.timeout_s)
        except Exception as exc:
            return ProbeResult(
                False,
                ComponentHealthState.DISCONNECTED,
                _utc_text(now),
                f"dashboard_request_failed:{type(exc).__name__}",
                (f"url:{self.url}",),
                {"dimension": "functional"},
            )
        valid = 200 <= int(status) < 300 and isinstance(payload, dict)
        return ProbeResult(
            valid,
            ComponentHealthState.HEALTHY if valid else ComponentHealthState.DEGRADED,
            _utc_text(now),
            "dashboard_http_ok" if valid else "dashboard_http_invalid",
            (f"url:{self.url}",),
            {"dimension": "functional", "status_code": int(status)},
        )
