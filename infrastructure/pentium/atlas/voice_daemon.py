from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

from .alsa_capture import AlsaCaptureBackend
from .affective_interaction_ipc import InteractionDatagramClient
from .alsa_stream import open_arecord_pcm
from .adaptive_noise_canceller import AdaptiveNoiseCancelledFrameSource
from .capability_registry import atlas_capability_registry
from .config_hermes import load_hermes_config
from .configuracao_cognitiva import carregar_configuracao_cognitiva
from .contexto_cognitivo import ContextoCognitivoBuilder
from .adaptive_vad import AdaptiveEnergyVad
from .human_context import HumanContextProvider
from .human_interaction import HumanInteractionGateway
from .hermes_adapter import HermesAdapter
from .llm_gateway import LLMGateway
from .live_tts import LiveTtsBackend
from .policy_capabilities import PolicyCapabilities
from .politica_ativacao_cognitiva import ActivationPolicy
from .reaction_loop_cognitivo import ReactionLoopCognitivo
from .reasoning_policy import ReasoningPolicy
from .voice_gate import WakePhraseGate
from .transcript_filter import NonSpeechTranscriptFilter
from .streaming_vad import StreamingAdaptiveVad
from .utterance_capture import StreamingUtteranceCapture
from .voice_runtime import VoiceRuntime
from .whisper_stt import SubprocessWhisperRunner, WhisperSttBackend


ROOT = Path(__file__).resolve().parent
DEFAULT_INTERACTION_SOCKET = Path.home() / "pentium-agent" / "atlas" / "runtime" / "affective-interaction.sock"

def build_visual_state_sink(path: Path = DEFAULT_INTERACTION_SOCKET):
    return InteractionDatagramClient(path).send

def load_voice_config(path: Path = ROOT / "config_voice.json") -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version voice deve ser 1")
    required = (
        "wake_phrase", "capture_duration_s", "capture_device", "vad_rms_threshold",
        "vad_snr_ratio", "vad_margin", "vad_calibration_frames", "vad_alpha",
        "vad_frame_ms", "vad_min_speech_frames", "utterance_pre_roll_ms", "utterance_trailing_silence_ms",
        "utterance_max_s", "utterance_listen_window_s", "utterance_start_speech_frames",
        "stream_vad_calibration_frames", "stream_vad_history_frames",
        "whisper_model", "whisper_timeout_s", "tts_voice", "tts_device", "health_path",
        "idle_sleep_s", "error_sleep_s",
    )
    if any(key not in payload for key in required):
        raise ValueError("config voice incompleta")
    if not 1 <= int(payload["capture_duration_s"]) <= 10:
        raise ValueError("capture_duration_s fora do bound")
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


def build_audio_source(binary: str, cfg: dict):
    channels = 2 if bool(cfg.get("anc_enabled", False)) else 1
    source = open_arecord_pcm(binary, device=cfg["capture_device"], frame_ms=int(cfg["vad_frame_ms"]), channels=channels)
    if not bool(cfg.get("anc_enabled", False)):
        return source
    return AdaptiveNoiseCancelledFrameSource(
        source, primary_channel=cfg["anc_primary_channel"], reference_channel=cfg["anc_reference_channel"],
        taps=int(cfg["anc_taps"]), mu=float(cfg["anc_mu"]), calibration_frames=int(cfg["anc_calibration_frames"]),
    )


def build_runtime(config_path: Path = ROOT / "config_voice.json") -> VoiceRuntime:
    cfg = load_voice_config(config_path)
    env, alsa, espeak, runtime_root = _tts_env()
    stream_vad = StreamingAdaptiveVad(
        calibration_frames=int(cfg["stream_vad_calibration_frames"]),
        history_frames=int(cfg["stream_vad_history_frames"]),
        min_rms_threshold=int(cfg["vad_rms_threshold"]), snr_ratio=float(cfg["vad_snr_ratio"]),
        margin=int(cfg["vad_margin"]),
    )
    capture = StreamingUtteranceCapture(
        lambda: build_audio_source(str(alsa / "usr/bin/arecord"), cfg),
        stream_vad, frame_ms=int(cfg["vad_frame_ms"]),
        start_speech_frames=int(cfg["utterance_start_speech_frames"]),
        trailing_silence_ms=int(cfg["utterance_trailing_silence_ms"]),
        max_utterance_s=int(cfg["utterance_max_s"]), pre_roll_ms=int(cfg["utterance_pre_roll_ms"]),
        listen_window_s=int(cfg["utterance_listen_window_s"]),
    )
    stt_runner = SubprocessWhisperRunner(temp_dir=runtime_root / "audio")
    stt = WhisperSttBackend(str(runtime_root / "whisper/build/bin/whisper-cli"), str(_path(cfg["whisper_model"])), runner=stt_runner, timeout_s=float(cfg["whisper_timeout_s"]))
    gate = WakePhraseGate(cfg["wake_phrase"], max_text_chars=256)
    cognitive = carregar_configuracao_cognitiva(ROOT / "config_cognitiva.json")
    builder = ContextoCognitivoBuilder(cognitive.contexto)
    activation = ActivationPolicy(cognitive.ativacao)
    hermes = load_hermes_config(ROOT / "config_hermes.json")
    llm_backend = HermesAdapter(hermes)
    gateway = LLMGateway(
        llm_backend,
        max_payload_bytes=cognitive.contexto.max_payload_bytes,
        max_tokens_contexto=hermes.max_context_tokens,
        reasoning_policy=ReasoningPolicy(),
    )
    capabilities = PolicyCapabilities(atlas_capability_registry(), read_auto_allow=("get_host_status",), control_allow=())
    cognitive_loop = ReactionLoopCognitivo(activation, builder, gateway, capability_policy=capabilities)
    expected_sha = (
        os.environ.get("ATLAS_EXPECTED_SHA") or None
        if cognitive.observation_bridge.require_expected_sha else None
    )
    context_provider = HumanContextProvider(
        _path(cfg["health_path"]),
        _path(cognitive.observation_bridge.snapshot_path),
        max_snapshot_age_s=cognitive.observation_bridge.max_snapshot_age_s,
        expected_sha=expected_sha,
    )
    interaction = HumanInteractionGateway(cognitive_loop, context_provider=context_provider,
                                          max_text_chars=cognitive.contexto.max_string_chars)
    tts = LiveTtsBackend(
        str(espeak / "usr/bin/espeak-ng"), str(alsa / "usr/bin/aplay"),
        voice=cfg["tts_voice"], device=cfg["tts_device"], max_text_chars=512,
        max_audio_bytes=2_000_000, timeout_s=20.0, env=env,
    )
    transcript_filter = NonSpeechTranscriptFilter()
    return VoiceRuntime(capture, stt, gate, interaction, tts, transcript_filter=transcript_filter,
                        visual_state_sink=build_visual_state_sink())
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
