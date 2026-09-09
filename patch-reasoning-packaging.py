from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\install-user.sh')
s=p.read_text(encoding='utf-8')
old='  reaction_loop_cognitivo.py \\\n  capability_registry.py \\\n'
new='  reaction_loop_cognitivo.py \\\n  reasoning_policy.py \\\n  capability_registry.py \\\n'
if old not in s:
    raise SystemExit('copy anchor not found')
s=s.replace(old,new,1)
old2='  "${TARGET_DIR}/reaction_loop_cognitivo.py" \\\n  "${TARGET_DIR}/capability_registry.py" \\\n'
new2='  "${TARGET_DIR}/reaction_loop_cognitivo.py" \\\n  "${TARGET_DIR}/reasoning_policy.py" \\\n  "${TARGET_DIR}/capability_registry.py" \\\n'
if old2 not in s:
    raise SystemExit('compile anchor not found')
s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8',newline='\n')
