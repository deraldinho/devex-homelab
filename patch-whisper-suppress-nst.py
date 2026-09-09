from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\whisper_stt.py')
s=p.read_text(encoding='utf-8')
s=s.replace('def __init__(self, binary: str, model: str, *, runner=None, preprocessor=None, max_audio_bytes=1_000_000, timeout_s=30.0, max_output_bytes=4096):','def __init__(self, binary: str, model: str, *, runner=None, preprocessor=None, suppress_nst=False, max_audio_bytes=1_000_000, timeout_s=30.0, max_output_bytes=4096):')
s=s.replace('        self._preprocessor = preprocessor\n','        self._preprocessor = preprocessor\n        self._suppress_nst = bool(suppress_nst)\n',1)
s=s.replace('        argv = [self._binary, "-m", self._model, "-l", "pt", "--no-timestamps", "-nt", "-np"]\n','        argv = [self._binary, "-m", self._model, "-l", "pt", "--no-timestamps", "-nt", "-np"]\n        if self._suppress_nst:\n            argv.append("-sns")\n',1)
p.write_text(s,encoding='utf-8')
