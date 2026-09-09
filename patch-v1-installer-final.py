from pathlib import Path

p = Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\install-user.sh')
s = p.read_text(encoding='utf-8')
for name in ('alsa_stream.py', 'streaming_vad.py', 'utterance_capture.py', 'chat_cli.py'):
    copy_line = f'  {name} \\\n'
    compile_line = f'  "${{TARGET_DIR}}/{name}" \\\n'
    if copy_line not in s:
        s = s.replace('  voice_runtime.py \\\n', '  voice_runtime.py \\\n' + copy_line, 1)
    if compile_line not in s:
        s = s.replace('  "${TARGET_DIR}/voice_runtime.py" \\\n', '  "${TARGET_DIR}/voice_runtime.py" \\\n' + compile_line, 1)
p.write_text(s, encoding='utf-8', newline='\n')
