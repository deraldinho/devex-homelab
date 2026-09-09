from pathlib import Path

root = Path(r"C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice")
p = root / "infrastructure/pentium/atlas/install-user.sh"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "  voice_gate.py \\\n  live_tts.py \\\n  cli.py; do",
    "  voice_gate.py \\\n  live_tts.py \\\n  alsa_capture.py \\\n  whisper_stt.py \\\n  voice_runtime.py \\\n  cli.py; do",
)
s = s.replace(
    '  "${TARGET_DIR}/voice_gate.py" \\\n  "${TARGET_DIR}/live_tts.py" \\\n  "${TARGET_DIR}/cli.py"',
    '  "${TARGET_DIR}/voice_gate.py" \\\n  "${TARGET_DIR}/live_tts.py" \\\n  "${TARGET_DIR}/alsa_capture.py" \\\n  "${TARGET_DIR}/whisper_stt.py" \\\n  "${TARGET_DIR}/voice_runtime.py" \\\n  "${TARGET_DIR}/cli.py"',
)
p.write_text(s, encoding="utf-8")