from pathlib import Path
wp = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\whisper_stt.py')
t = wp.read_text(encoding='utf-8')
t = t.replace('import tempfile\n', 'import tempfile\nfrom pathlib import Path\n', 1)
t = t.replace('class SubprocessWhisperRunner:\n    def run(self, argv, *, input_bytes: bytes, timeout_s: float, max_output_bytes: int) -> str:\n        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:', 'class SubprocessWhisperRunner:\n    def __init__(self, *, temp_dir: str | Path | None = None, executor=subprocess.run):\n        self._temp_dir = Path(temp_dir) if temp_dir is not None else None\n        self._executor = executor\n\n    def run(self, argv, *, input_bytes: bytes, timeout_s: float, max_output_bytes: int) -> str:\n        if self._temp_dir is not None:\n            self._temp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)\n            os.chmod(self._temp_dir, 0o700)\n        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self._temp_dir) as tmp:', 1)
t = t.replace('            completed = subprocess.run(', '            completed = self._executor(', 1)
wp.write_text(t, encoding='utf-8')
vp = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\voice_daemon.py')
v = vp.read_text(encoding='utf-8')
v = v.replace('from .whisper_stt import WhisperSttBackend', 'from .whisper_stt import SubprocessWhisperRunner, WhisperSttBackend', 1)
old = '    stt = WhisperSttBackend(str(runtime_root / "whisper/build/bin/whisper-cli"), str(_path(cfg["whisper_model"])), timeout_s=float(cfg["whisper_timeout_s"]))'
new = '    stt_runner = SubprocessWhisperRunner(temp_dir=runtime_root / "audio")\n    stt = WhisperSttBackend(str(runtime_root / "whisper/build/bin/whisper-cli"), str(_path(cfg["whisper_model"])), runner=stt_runner, timeout_s=float(cfg["whisper_timeout_s"]))'
if old not in v:
    raise SystemExit('voice daemon needle not found')
vp.write_text(v.replace(old, new, 1), encoding='utf-8')
