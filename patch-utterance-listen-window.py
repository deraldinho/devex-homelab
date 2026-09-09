from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\utterance_capture.py')
s=p.read_text(encoding='utf-8')
s=s.replace('max_utterance_s=12, pre_roll_ms=200):','max_utterance_s=12, pre_roll_ms=200, listen_window_s=4):')
s=s.replace('if max_utterance_s <= 0 or pre_roll_ms < 0:\n            raise ValueError("utterance bounds invalid")','if max_utterance_s <= 0 or pre_roll_ms < 0 or listen_window_s <= 0:\n            raise ValueError("utterance bounds invalid")')
s=s.replace('self._pre_roll_frames = max(0, int(pre_roll_ms // frame_ms))','self._pre_roll_frames = max(0, int(pre_roll_ms // frame_ms))\n        self._listen_frames = max(1, int(listen_window_s * 1000 // frame_ms))')
s=s.replace('            for _ in range(self._max_frames):','            total_limit = self._listen_frames + self._max_frames\n            for index in range(total_limit):')
s=s.replace('                if not started:\n                    pre_roll.append(frame)','                if not started:\n                    if index >= self._listen_frames:\n                        break\n                    pre_roll.append(frame)')
p.write_text(s,encoding='utf-8',newline='\n')
