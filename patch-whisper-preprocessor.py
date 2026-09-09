from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\whisper_stt.py')
s=p.read_text(encoding='utf-8')
s=s.replace('def __init__(self, binary: str, model: str, *, runner=None, max_audio_bytes=1_000_000, timeout_s=30.0, max_output_bytes=4096):','def __init__(self, binary: str, model: str, *, runner=None, preprocessor=None, max_audio_bytes=1_000_000, timeout_s=30.0, max_output_bytes=4096):')
s=s.replace('        self._runner = runner or SubprocessWhisperRunner()\n','        self._runner = runner or SubprocessWhisperRunner()\n        self._preprocessor = preprocessor\n',1)
s=s.replace('        argv = [self._binary,','        processed = self._preprocessor.process(audio) if self._preprocessor is not None else audio\n        argv = [self._binary,',1)
s=s.replace('input_bytes=audio, timeout_s=','input_bytes=processed, timeout_s=',1)
p.write_text(s,encoding='utf-8')
