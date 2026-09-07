from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

from .alsa_capture import AlsaCaptureBackend
from .capability_registry import atlas_capability_registry
from .configuracao_cognitiva import carregar_configuracao_cognitiva
from .contexto_cognitivo import ContextoCognitivoBuilder
from .energy_vad import EnergyVad
from .human_context import HumanContextProvider
from .human_interaction import HumanInteractionGateway
from .llama_cpp_backend import LlamaCppBackend
from .llm_gateway import LLMGateway
from .live_tts import LiveTtsBackend
from .policy_capabilities import PolicyCapabilities
from .politica_ativacao_cognitiva import ActivationPolicy
from .reaction_loop_cognitivo import ReactionLoopCognitivo
from .reasoning_policy import ReasoningPolicy
from .voice_gate import WakePhraseGate
from .voice_runtime import VoiceRuntime
from .whisper_stt import SubprocessWhisperRunner, WhisperSttBackend


ROOT = Path(__file__).resolve().parent
def load_voice_config(path: Path = ROOT / "config_voice.json") -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version voice deve ser 1")
    required = (
        "wake_phrase", "capture_duration_s", "capture_device", "vad_rms_threshold",
        "whisper_model", "whisper_timeout_s", "llm_model", "llm_timeout_s",
        "llm_context_tokens", "tts_voice", "tts_device", "health_path",
        "idle_sleep_s", "error_sleep_s",
    )
    if any(key not in payload for key in required):
        raise ValueError("config voice incompleta")
    if not 1 <= int(payload["capture_duration_s"]) <= 10:
        raise ValueError("capture_duration_s fora do bound")
    if not 256 <= int(payload["llm_context_tokens"]) <= 4096:
        raise ValueError("llm_context_tokens fora do bound")
    if float(payload["idle_sleep_s"]) < 0 or float(payload["error_sleep_s"]) <= 0:
        raise ValueError("sleep voice invalido")
    return payload


def _path(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()
def _tts_env() -> tuple[dict[str, str], Path, Path, Path]:
    home = Path.home() / "pentium-agent" / "runtime"
    alsa = home / "alsa-root"
    espeak = home / "espeak-root"
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join((
        str(espeak / "usr/lib/x86_64-linux-gnu"),
        str(espeak / "usr/lib/x86_64-linux-gnu/pulseaudio"),
        str(alsa / "usr/lib/x86_64-linux-gnu"),
    ))
    env["ALSA_CONFIG_PATH"] = str(alsa / "usr/share/alsa/alsa.conf")
    env["ALSA_CONFIG_DIR"] = str(alsa / "usr/share/alsa")
    env["ESPEAK_DATA_PATH"] = str(espeak / "usr/lib/x86_64-linux-gnu/espeak-ng-data")
    return env, alsa, espeak, home


def build_runtime(config_path: Path = ROOT / "config_voice.json") -> VoiceRuntime:
    cfg = load_voice_config(config_path)
    env, alsa, espeak, runtime_root = _tts_env()
    capture = AlsaCaptureBackend(str(alsa / "usr/bin/arecord"), device=cfg["capture_device"], duration_s=int(cfg["capture_duration_s"]))
    vad = EnergyVad(rms_threshold=int(cfg["vad_rms_threshold"]), max_samples=int(cfg["capture_duration_s"]) * 16000)
    stt_runner = SubprocessWhisperRunner(temp_dir=runtime_root / "audio")
    stt = WhisperSttBackend(str(runtime_root / "whisper/build/bin/whisper-cli"), str(_path(cfg["whisper_model"])), runner=stt_runner, timeout_s=float(cfg["whisper_timeout_s"]))
    gate = WakePhraseGate(cfg["wake_phrase"], max_text_chars=256)
    cognitive = carregar_configuracao_cognitiva(ROOT / "config_cognitiva.json")
    builder = ContextoCognitivoBuilder(cognitive.contexto)
    activation = ActivationPolicy(cognitive.ativacao)
    llm_backend = LlamaCppBackend(
        runtime_root / "llama/build/bin/llama-cli", _path(cfg["llm_model"]),
        timeout_s=float(cfg["llm_timeout_s"]), max_saida_bytes=8192,
    )
    gateway = LLMGateway(llm_backend, max_payload_bytes=cognitive.contexto.max_payload_bytes,
                         max_tokens_contexto=int(cfg["llm_context_tokens"]), reasoning_policy=ReasoningPolicy())
    capabilities = PolicyCapabilities(atlas_capability_registry(), read_auto_allow=("get_host_status",), control_allow=())
    cognitive_loop = ReactionLoopCognitivo(activation, builder, gateway, capability_policy=capabilities)
    context_provider = HumanContextProvider(_path(cfg["health_path"]))
    interaction = HumanInteractionGateway(cognitive_loop, context_provider=context_provider,
                                          max_text_chars=cognitive.contexto.max_string_chars)
    tts = LiveTtsBackend(
        str(espeak / "usr/bin/espeak-ng"), str(alsa / "usr/bin/aplay"),
        voice=cfg["tts_voice"], device=cfg["tts_device"], max_text_chars=512,
        max_audio_bytes=2_000_000, timeout_s=20.0, env=env,
    )
    return VoiceRuntime(capture, stt, gate, interaction, tts, vad=vad)
def main() -> int:
    cfg = load_voice_config()
    runtime = build_runtime()
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("ATLAS_V1_VOICE_DAEMON_LISTENING", flush=True)
    while not stopped:
        try:
            result = runtime.run_once()
            print(f"ATLAS_V1_VOICE_STATE={result.state.value} reason={result.reason or 'none'}", flush=True)
            time.sleep(float(cfg["idle_sleep_s"]))
        except Exception as exc:
            print(f"ATLAS_V1_VOICE_DEGRADED type={type(exc).__name__}", flush=True)
            time.sleep(float(cfg["error_sleep_s"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
