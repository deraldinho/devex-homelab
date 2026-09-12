#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
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
        "cognitive_snapshot_path": "~/pentium-agent/atlas/runtime/cognitive-observation-context.json",
        "cognitive_health_path": "~/pentium-agent/atlas/runtime/observation-affective-health.json",
        "cognitive_runtime_path": "~/pentium-agent/atlas/runtime/cognitive-runtime.json",
        "continuous_intent_path": "~/pentium-agent/atlas/runtime/continuous-intent.json",
        "workspace_economy_path": "~/pentium-agent/atlas/runtime/workspace-economy-health.json",
        "cognitive_activity_path": "~/pentium-agent/atlas/runtime/cognitive-activity.jsonl",
        "action_plan_path": "~/pentium-agent/atlas/runtime/action-plan-current.json",
        "dashboard_events_path": "~/pentium-agent/atlas/runtime/dashboard-events.jsonl",
        "chat_inbox_path": "~/pentium-agent/atlas/runtime/chat-inbox.json",
        "cognitive_max_age_s": 180,
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


def _unavailable(reason: str) -> dict:
    return {"status": "unavailable", "reason": reason}


def collect_cognition(config: dict, *, now=lambda: datetime.now(timezone.utc)) -> dict:
    snapshot = _read_json(config["cognitive_snapshot_path"])
    health = _read_json(config["cognitive_health_path"])
    if not isinstance(snapshot, dict):
        return _unavailable("snapshot_unavailable")
    if snapshot.get("schema_version") != 1:
        return _unavailable("schema_invalid")
    expected_sha = config.get("cognitive_expected_sha") or (health or {}).get("expected_sha")
    if expected_sha and snapshot.get("expected_sha") != expected_sha:
        return _unavailable("sha_mismatch")
    try:
        generated_at = datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00"))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        age_s = max(0.0, (now() - generated_at.astimezone(timezone.utc)).total_seconds())
    except (KeyError, TypeError, ValueError):
        return _unavailable("generated_at_invalid")
    if age_s > float(config.get("cognitive_max_age_s", 180)):
        return {"status": "stale", "reason": "snapshot_stale", "age_s": round(age_s, 3), "generated_at": snapshot.get("generated_at")}
    perception = snapshot.get("perception") if isinstance(snapshot.get("perception"), dict) else {}
    affective = snapshot.get("affective_state") if isinstance(snapshot.get("affective_state"), dict) else {}
    emotion = snapshot.get("emotion") if isinstance(snapshot.get("emotion"), dict) else {}
    focus = snapshot.get("focus") if isinstance(snapshot.get("focus"), dict) else {}
    def pct(value):
        return round(max(0.0, min(1.0, float(value or 0))) * 100)
    recent = []
    for item in snapshot.get("recent_changes", [])[-8:]:
        if isinstance(item, dict):
            recent.append({key: item.get(key) for key in ("timestamp", "source", "kind", "severity", "stimulus_id")})
    return {
        "status": "available", "age_s": round(age_s, 3), "generated_at": snapshot.get("generated_at"),
        "expected_sha": expected_sha, "observed_sha": snapshot.get("expected_sha"), "entity_id": snapshot.get("entity_id"),
        "source_stimulus_id": snapshot.get("source_stimulus_id"),
        "perception": {**perception, "confidence_percent": pct(perception.get("confianca"))},
        "affective_state": {**affective, "valence_percent": pct(affective.get("valencia")), "activation_percent": pct(affective.get("ativacao")), "stress_percent": pct(affective.get("estresse")), "confidence_percent": pct(affective.get("confianca")), "engagement_percent": pct(affective.get("engajamento")), "curiosity_percent": pct(affective.get("curiosidade"))},
        "emotion": emotion, "focus": focus, "incident": snapshot.get("incident"), "recent_changes": recent,
        "bridge": {"current_error": ((health or {}).get("cognitive_bridge") or {}).get("current_error")},
    }



def collect_cognitive_runtime(config: dict) -> dict:
    payload = _read_json(config["cognitive_runtime_path"])
    if not isinstance(payload, dict):
        return {"status": "unavailable"}
    schema = payload.get("schema_version")
    if schema == 1:
        return _enrich_runtime({
            "status":"available","schema_version":1,"generated_at":payload.get("generated_at"),
            "source_stimulus_id":payload.get("source_stimulus_id"),"activated":bool(payload.get("activated",False)),
            "reason":payload.get("reason"),"motivo":payload.get("motivo"),"backend":payload.get("backend"),
            "duration_ms":payload.get("duracao_ms"),"confidence":payload.get("confianca"),
            "requires_confirmation":bool(payload.get("requer_confirmacao",False)),
        },config)
    if schema != 2:
        return {"status":"unavailable"}
    result = payload.get("last_result") if isinstance(payload.get("last_result"),dict) else {}
    return _enrich_runtime({
        "status":"available","schema_version":2,"generated_at":payload.get("generated_at"),
        "source_stimulus_id":payload.get("source_stimulus_id"),"entity_id":payload.get("entity_id"),
        "state":payload.get("state"),"activity":payload.get("activity"),"task":payload.get("task"),
        "motivo":payload.get("motivo"),"detail":payload.get("detail"),
        "activated":bool(result.get("activated",False)),"reason":result.get("reason"),
        "summary":result.get("summary"),"response_preview":result.get("response_preview"),
        "intention":result.get("intention"),"confidence":result.get("confidence"),
        "backend":result.get("backend"),"duration_ms":result.get("duration_ms"),
        "requires_confirmation":bool(result.get("requires_confirmation",False)),
        "intention_authorized":bool(result.get("intention_authorized",False)),
    },config)


def _collect_action_plan(config: dict) -> dict | None:
    payload=_read_json(config.get("action_plan_path",""))
    if not isinstance(payload,dict) or payload.get("schema_version")!=1:return None
    allowed_plan=("plan_id","stimulus_id","created_at","objective","confidence","response_text","requires_confirmation","policy_decision","trigger_kind")
    actions=[]
    for item in payload.get("actions",[])[:16]:
        if not isinstance(item,dict):continue
        params=item.get("parameters") if isinstance(item.get("parameters"),dict) else {}
        safe_params={k:v for k,v in params.items() if str(k) in {"direction","expression","intensity","gesture","arm","posture","duration_ms","capability"}}
        actions.append({k:item.get(k) for k in ("action_id","type","target","status","reason","created_at","authorized_at","started_at","finished_at")}|{"parameters":safe_params})
    return {k:payload.get(k) for k in allowed_plan}|{"actions":actions}


def _collect_operational_events(config: dict, limit: int = 64) -> list[dict]:
    path=Path(config.get("dashboard_events_path","")).expanduser()
    try: lines=path.read_text(encoding="utf-8").splitlines()[-max(1,min(128,int(limit))):]
    except OSError:return []
    out=[]
    payload_keys={"plan_id","stimulus_id","message_id","action_id","type","status","reason","target","role","message","objective","confidence","error"}
    for line in lines:
        try:item=json.loads(line)
        except json.JSONDecodeError:continue
        if not isinstance(item,dict):continue
        raw=item.get("payload") if isinstance(item.get("payload"),dict) else {}
        out.append({"id":item.get("id"),"timestamp":item.get("timestamp"),"type":item.get("type"),"payload":{k:raw.get(k) for k in payload_keys if k in raw}})
    return out


def _enrich_runtime(runtime: dict, config: dict) -> dict:
    events=_collect_operational_events(config)
    runtime=dict(runtime);runtime["action_plan"]=_collect_action_plan(config)
    runtime["operational_timeline"]=events
    runtime["chat_history"]=[e for e in events if e.get("type")=="chat_message"][-32:]
    return runtime

def collect_continuous_intent(config: dict) -> dict:
    payload = _read_json(config.get("continuous_intent_path", ""))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"status": "unavailable", "intent": None}
    raw = payload.get("intent")
    allowed = (
        "intencao_id", "tipo", "estado", "assunto_id", "entidade_id", "motivo",
        "prioridade", "iniciado_em", "atualizado_em", "valido_ate",
        "notificado_usuario", "episodio_id",
    )
    intent = None if raw is None else {key: raw.get(key) for key in allowed if key in raw}
    return {
        "status": "available",
        "communication_mode": str(payload.get("communication_mode") or "normal")[:64],
        "material_fingerprint": str(payload.get("material_fingerprint") or "")[:256],
        "intent": intent,
    }


def collect_workspace_economy(config: dict) -> dict:
    payload = _read_json(config.get("workspace_economy_path", ""))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"status": "unavailable", "workspace": {}, "self_work": {}, "economy": {}}
    workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else {}
    self_work = payload.get("self_work") if isinstance(payload.get("self_work"), dict) else {}
    economy = payload.get("economy") if isinstance(payload.get("economy"), dict) else {}
    routes = economy.get("routes") if isinstance(economy.get("routes"), dict) else {}
    return {
        "status": str(payload.get("status") or "unknown")[:32],
        "generated_at": payload.get("generated_at"), "expected_sha": payload.get("expected_sha"),
        "workspace": {k: workspace.get(k) for k in ("files","bytes","max_files","max_bytes")},
        "self_work": {k: self_work.get(k) for k in ("active","item_id","objective","area","state","operations_used","inferences_used")},
        "economy": {
            "mode": economy.get("mode"), "tokens_used": economy.get("tokens_used"),
            "window_budget": economy.get("window_budget"), "pressure": economy.get("pressure"),
            "routes": {str(k): int(v) for k,v in routes.items() if isinstance(v,int)},
        },
    }


def collect_cognitive_activity(config: dict, limit: int = 40) -> list[dict]:
    path=Path(config["cognitive_activity_path"]).expanduser()
    try: lines=path.read_text(encoding="utf-8").splitlines()[-max(1,min(100,int(limit))):]
    except OSError: return []
    events=[]
    allowed=("timestamp","source_stimulus_id","state","activity","motivo","summary","intention","confidence")
    for line in lines:
        try: item=json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(item,dict): events.append({k:item.get(k) for k in allowed})
    return events

def collect_status(config: dict, *, command_runner: CommandRunner = run_command, meminfo_text: str | None = None, uptime_text: str | None = None, cognition_now=lambda: datetime.now(timezone.utc)) -> dict:
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
        "cognition": collect_cognition(config, now=cognition_now),
        "cognitive_runtime": {**collect_cognitive_runtime(config), "timeline": collect_cognitive_activity(config)},
        "continuous_intent": collect_continuous_intent(config),
        "workspace": collect_workspace_economy(config),
        "atlas": {"sha": _read_text(config["deploy_sha_path"]), "health": health.get("status", "unknown")},
        "services": {
            "agent": _unit("pentium-agent.service", command_runner),
            "heartbeat": _unit("pentium-heartbeat.timer", command_runner),
            "voice": voice_unit,
            "observation": _unit("atlas-observation.service", command_runner),
            "cognitive": _unit("atlas-cognitive.service", command_runner),
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
