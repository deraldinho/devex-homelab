from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_v1_voice_daemon.py')
s = p.read_text(encoding='utf-8')
s = s.replace('            "vad_alpha": 0.2, "vad_frame_ms": 20, "vad_min_speech_frames": 5,\n', '            "vad_alpha": 0.2, "vad_frame_ms": 20, "vad_min_speech_frames": 5,\n            "utterance_start_speech_frames": 3, "utterance_trailing_silence_ms": 800,\n            "utterance_max_s": 12, "utterance_pre_roll_ms": 200, "listen_window_s": 4,\n')
p.write_text(s, encoding='utf-8', newline='\n')
