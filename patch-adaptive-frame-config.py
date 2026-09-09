from pathlib import Path

p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\voice_daemon.py')
t = p.read_text(encoding='utf-8')
t = t.replace('"vad_snr_ratio", "vad_margin", "vad_calibration_frames", "vad_alpha",\n        "whisper_model"', '"vad_snr_ratio", "vad_margin", "vad_calibration_frames", "vad_alpha",\n        "vad_frame_ms", "vad_min_speech_frames", "whisper_model"')
t = t.replace('alpha=float(cfg["vad_alpha"]), max_samples=int(cfg["capture_duration_s"]) * 16000,', 'alpha=float(cfg["vad_alpha"]), frame_ms=int(cfg["vad_frame_ms"]),\n        min_speech_frames=int(cfg["vad_min_speech_frames"]),\n        max_samples=int(cfg["capture_duration_s"]) * 16000,')
p.write_text(t, encoding='utf-8', newline='\n')
