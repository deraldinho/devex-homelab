from pathlib import Path

p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\install-user.sh')
t = p.read_text(encoding='utf-8')
t = t.replace('  energy_vad.py \\\n  human_interaction.py', '  energy_vad.py \\\n  adaptive_vad.py \\\n  transcript_filter.py \\\n  human_interaction.py')
t = t.replace('  "${TARGET_DIR}/energy_vad.py" \\\n  "${TARGET_DIR}/human_interaction.py"', '  "${TARGET_DIR}/energy_vad.py" \\\n  "${TARGET_DIR}/adaptive_vad.py" \\\n  "${TARGET_DIR}/transcript_filter.py" \\\n  "${TARGET_DIR}/human_interaction.py"')
p.write_text(t, encoding='utf-8', newline='\n')
