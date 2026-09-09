from pathlib import Path
p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\llama_cpp_backend.py')
t = p.read_text(encoding='utf-8')
needle = '            "--single-turn",\n            "--simple-io",\n'
if needle not in t:
    raise SystemExit('needle not found')
p.write_text(t.replace(needle, needle + '            "--log-disable",\n', 1), encoding='utf-8')
