from pathlib import Path
root=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas')
p=root/'voice_runtime.py'; s=p.read_text(encoding='utf-8')
s=s.replace('        audio = self._capture.capture_utterance()\n        if self._vad is not None', '        audio = self._capture.capture_utterance()\n        if not audio:\n            return VoiceRunResult(VoiceState.LISTENING, "no_speech")\n        if self._vad is not None',1)
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'utterance_capture.py'; s=p.read_text(encoding='utf-8')
s=s.replace('            return self._wav(captured) if captured else self._wav([])', '            return self._wav(captured) if captured else b""',1)
p.write_text(s,encoding='utf-8',newline='\n')
