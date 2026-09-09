from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\voice_daemon.py')
s=p.read_text(encoding='utf-8')
s=s.replace('from .alsa_stream import open_arecord_pcm\n', 'from .alsa_stream import open_arecord_pcm\nfrom .adaptive_noise_canceller import AdaptiveNoiseCancelledFrameSource\n')
needle='def build_runtime(config_path: Path = ROOT / "config_voice.json") -> VoiceRuntime:\n'
helper='def build_audio_source(binary: str, cfg: dict):\n    channels = 2 if bool(cfg.get("anc_enabled", False)) else 1\n    source = open_arecord_pcm(binary, device=cfg["capture_device"], frame_ms=int(cfg["vad_frame_ms"]), channels=channels)\n    if not bool(cfg.get("anc_enabled", False)):\n        return source\n    return AdaptiveNoiseCancelledFrameSource(\n        source, primary_channel=cfg["anc_primary_channel"], reference_channel=cfg["anc_reference_channel"],\n        taps=int(cfg["anc_taps"]), mu=float(cfg["anc_mu"]), calibration_frames=int(cfg["anc_calibration_frames"]),\n    )\n\n\n'
s=s.replace(needle, helper+needle)
s=s.replace('lambda: open_arecord_pcm(str(alsa / "usr/bin/arecord"), device=cfg["capture_device"], frame_ms=int(cfg["vad_frame_ms"]))', 'lambda: build_audio_source(str(alsa / "usr/bin/arecord"), cfg)')
p.write_text(s,encoding='utf-8')
