#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: float) -> CommandResult:
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    return CommandResult(done.returncode, done.stdout, done.stderr)


CommandRunner = Callable[[list[str], float], CommandResult]


def default_config() -> dict:
    return {
        "schema_version": 1,
        "bind_host": "192.168.88.3",
        "bind_port": 8765,
        "health_path": "~/pentium-agent/data/health/latest.json",
        "voice_config_path": "~/pentium-agent/atlas/config_voice.json",
        "deploy_sha_path": "~/pentium-agent/runtime/deploy/current-sha",
        "visual_state_path": "~/pentium-agent/atlas/runtime/visual-state.json",
    }


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != 1:
        raise ValueError("dashboard config schema_version must be 1")
    if cfg.get("bind_host") != "192.168.88.3" or int(cfg.get("bind_port", 0)) != 8765:
        raise ValueError("dashboard bind must be 192.168.88.3:8765")
    return {**default_config(), **cfg}


def _read_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: str) -> str | None:
    try:
        return Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _unit(unit: str, runner: CommandRunner) -> dict:
    active = runner(["systemctl", "--user", "is-active", unit], 2.0)
    enabled = runner(["systemctl", "--user", "is-enabled", unit], 2.0)
    return {
        "active": active.stdout.strip() or "unknown",
        "enabled": enabled.stdout.strip() or "unknown",
    }



import re

_AUDIO_RE = re.compile(r"card\s+(\d+):.*device\s+(\d+):\s+([^\[]+)")
_EVENT_MARKERS = (
    "ATLAS_V1_VOICE_DAEMON_LISTENING",
    "ATLAS_V1_VOICE_DAEMON_PROCESSING",
    "ATLAS_V1_VOICE_DAEMON_SPEAKING",
    "reason=no_speech",
    "reason=non_speech_transcript",
    "reason=wake_phrase_missing",
    "TimeoutExpired",
)


def parse_arecord_devices(text: str) -> list[dict]:
    devices = []
    for line in text.splitlines():
        match = _AUDIO_RE.search(line)
        if match:
            devices.append({
                "card": int(match.group(1)),
                "device": int(match.group(2)),
                "name": match.group(3).strip(),
            })
    return devices


def sanitize_event(line: str) -> dict | None:
    marker = next((item for item in _EVENT_MARKERS if item in line), None)
    if marker is None:
        return None
    severity = "warning" if marker == "TimeoutExpired" else "info"
    reason = next((token for token in line.split() if token.startswith("reason=")), None)
    message = marker if reason is None or reason in marker else f"{marker} {reason}"
    return {"timestamp": None, "source": "atlas-voice", "severity": severity, "message": message}


def collect_events(config: dict, *, command_runner: CommandRunner = run_command) -> list[dict]:
    result = command_runner(
        ["journalctl", "--user", "-u", "atlas-voice.service", "-n", "120", "--no-pager"],
        3.0,
    )
    if result.returncode != 0:
        return []
    events = [event for line in result.stdout.splitlines() if (event := sanitize_event(line))]
    return events[-50:]


def parse_meminfo(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) // 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    swap_total = values.get("SwapTotal")
    swap_free = values.get("SwapFree")
    return {
        "memory_total_mb": total,
        "memory_available_mb": available,
        "memory_used_mb": None if total is None or available is None else max(0, total - available),
        "swap_total_mb": swap_total,
        "swap_free_mb": swap_free,
        "swap_used_mb": None if swap_total is None or swap_free is None else max(0, swap_total - swap_free),
    }


def parse_ip_brief(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        address = next((part for part in parts[2:] if re.fullmatch(r"\d+\.\d+\.\d+\.\d+/\d+", part)), None)
        if address:
            result[parts[0]] = address
    return result


def _fallback_visual_state() -> dict:
    return {
        "versao_avatar": 1,
        "modo": "OCIOSO",
        "expressao": "SERENO",
        "intensidade_expressao": 0.25,
        "foco_visual": "neutro",
        "direcao_olhar": "frente",
        "gesto_atual": "nenhum",
        "velocidade_movimento": 0.2,
        "intensidade_movimento": 0.2,
        "falando": False,
        "ouvindo": False,
        "pensando": False,
        "duvida_identidade": False,
        "transicao_ms": 400,
        "source": "fallback",
    }


def _visual_state(config: dict) -> dict:
    snapshot = _read_json(config["visual_state_path"])
    if not isinstance(snapshot, dict) or snapshot.get("versao_avatar") != 1:
        return _fallback_visual_state()
    required = {
        "modo", "expressao", "intensidade_expressao", "foco_visual", "direcao_olhar",
        "gesto_atual", "velocidade_movimento", "intensidade_movimento", "falando",
        "ouvindo", "pensando", "duvida_identidade", "transicao_ms",
    }
    if not required.issubset(snapshot):
        return _fallback_visual_state()
    return snapshot


def collect_status(config: dict, *, command_runner: CommandRunner = run_command, meminfo_text: str | None = None, uptime_text: str | None = None) -> dict:
    import shutil

    health = _read_json(config["health_path"]) or {}
    voice_cfg = _read_json(config["voice_config_path"]) or {}
    voice_unit = _unit("atlas-voice.service", command_runner)

    audio_result = command_runner(["arecord", "-l"], 2.0)
    devices = parse_arecord_devices(audio_result.stdout) if audio_result.returncode == 0 else []
    ip_result = command_runner(["ip", "-4", "-br", "addr"], 2.0)
    addresses = parse_ip_brief(ip_result.stdout) if ip_result.returncode == 0 else {}

    system = {"pid": os.getpid(), "uptime_s": None, "load_1m": None}
    try:
        system.update(parse_meminfo(meminfo_text if meminfo_text is not None else Path("/proc/meminfo").read_text(encoding="utf-8")))
        uptime_raw = uptime_text if uptime_text is not None else Path("/proc/uptime").read_text(encoding="utf-8")
        system["uptime_s"] = int(float(uptime_raw.split()[0]))
        system["load_1m"] = round(float(Path("/proc/loadavg").read_text().split()[0]), 2)
    except (OSError, ValueError, IndexError):
        pass
    try:
        disk = shutil.disk_usage(Path.home())
        system["disk_free_percent"] = round(disk.free * 100.0 / disk.total, 1)
    except OSError:
        system["disk_free_percent"] = None

    anc_enabled = bool(voice_cfg.get("anc_enabled", False))
    anc_reason = None if anc_enabled else "disabled by configuration"
    return {
        "visual": _visual_state(config),
        "atlas": {"sha": _read_text(config["deploy_sha_path"]), "health": health.get("status", "unknown")},
        "services": {
            "agent": _unit("pentium-agent.service", command_runner),
            "heartbeat": _unit("pentium-heartbeat.timer", command_runner),
            "voice": voice_unit,
            "dashboard": _unit("atlas-dashboard.service", command_runner),
        },
        "voice": {
            "state": "paused" if voice_unit.get("active") != "active" else "unknown",
            "whisper_available": Path(voice_cfg["whisper_binary"]).expanduser().is_file() if voice_cfg.get("whisper_binary") else None,
            "qwen_model": voice_cfg.get("llm_model"),
            "tts": voice_cfg.get("tts_voice"),
        },
        "audio": {"devices": devices, "count": len(devices), "status": "ready" if devices else "degraded"},
        "anc": {"state": "unknown" if anc_enabled else "off", "reason": anc_reason},
        "system": system,
        "network": {
            "lan": addresses.get("enp4s0", "unknown"),
            "wifi": addresses.get("wlp1s0", "unknown"),
            "tailscale": addresses.get("tailscale0", "unknown"),
        },
    }
