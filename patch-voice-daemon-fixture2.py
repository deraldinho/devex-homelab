from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\tests\test_v1_voice_daemon.py')
s = p.read_text(encoding='utf-8')
s = s.replace('            "utterance_max_s": 12, "utterance_pre_roll_ms": 200, "listen_window_s": 4,\n', '            "utterance_max_s": 12, "utterance_pre_roll_ms": 200, "utterance_listen_window_s": 4,\n            "stream_vad_calibration_frames": 50, "stream_vad_history_frames": 200,\n')
p.write_text(s, encoding='utf-8', newline='\n')
