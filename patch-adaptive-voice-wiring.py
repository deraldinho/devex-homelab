from pathlib import Path

wt = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice')
daemon = wt / 'infrastructure/pentium/atlas/voice_daemon.py'
t = daemon.read_text(encoding='utf-8')
t = t.replace('from .energy_vad import EnergyVad\n', 'from .adaptive_vad import AdaptiveEnergyVad\n')
t = t.replace('from .voice_runtime import VoiceRuntime\n', 'from .transcript_filter import NonSpeechTranscriptFilter\nfrom .voice_runtime import VoiceRuntime\n')
t = t.replace('"wake_phrase", "capture_duration_s", "capture_device", "vad_rms_threshold",\n        "whisper_model"', '"wake_phrase", "capture_duration_s", "capture_device", "vad_rms_threshold",\n        "vad_snr_ratio", "vad_margin", "vad_calibration_frames", "vad_alpha",\n        "whisper_model"')
old = 'vad = EnergyVad(rms_threshold=int(cfg["vad_rms_threshold"]), max_samples=int(cfg["capture_duration_s"]) * 16000)'
new = 'vad = AdaptiveEnergyVad(\n        min_rms_threshold=int(cfg["vad_rms_threshold"]), snr_ratio=float(cfg["vad_snr_ratio"]),\n        margin=int(cfg["vad_margin"]), calibration_frames=int(cfg["vad_calibration_frames"]),\n        alpha=float(cfg["vad_alpha"]), max_samples=int(cfg["capture_duration_s"]) * 16000,\n    )'
t = t.replace(old, new)
t = t.replace('return VoiceRuntime(capture, stt, gate, interaction, tts, vad=vad)', 'transcript_filter = NonSpeechTranscriptFilter()\n    return VoiceRuntime(capture, stt, gate, interaction, tts, vad=vad, transcript_filter=transcript_filter)')
daemon.write_text(t, encoding='utf-8', newline='\n')
