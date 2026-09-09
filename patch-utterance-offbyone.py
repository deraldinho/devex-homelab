from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\utterance_capture.py')
s=p.read_text(encoding='utf-8')
s=s.replace('            for index in range(total_limit):\n                frame = source.read_frame()','            for index in range(total_limit):\n                if not started and index >= self._listen_frames:\n                    break\n                frame = source.read_frame()')
s=s.replace('                if not started:\n                    if index >= self._listen_frames:\n                        break\n                    pre_roll.append(frame)','                if not started:\n                    pre_roll.append(frame)')
p.write_text(s,encoding='utf-8',newline='\n')
