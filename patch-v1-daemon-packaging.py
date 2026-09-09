from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas\install-user.sh')
s=p.read_text(encoding='utf-8')
mods='''  voice_runtime.py \\
  energy_vad.py \\
  human_interaction.py \\
  human_context.py \\
  voice_daemon.py \\
  cli.py; do'''
s=s.replace('''  voice_runtime.py \\
  cli.py; do''', mods)
s=s.replace('config_llama_server.json config_fast_router.json;', 'config_llama_server.json config_fast_router.json config_voice.json;')
compile='''  "${TARGET_DIR}/voice_runtime.py" \\
  "${TARGET_DIR}/energy_vad.py" \\
  "${TARGET_DIR}/human_interaction.py" \\
  "${TARGET_DIR}/human_context.py" \\
  "${TARGET_DIR}/voice_daemon.py" \\
  "${TARGET_DIR}/cli.py"'''
s=s.replace('''  "${TARGET_DIR}/voice_runtime.py" \\
  "${TARGET_DIR}/cli.py"''', compile)
s=s.replace('python3 -m json.tool "${TARGET_DIR}/config_fast_router.json" >/dev/null', 'python3 -m json.tool "${TARGET_DIR}/config_fast_router.json" >/dev/null\npython3 -m json.tool "${TARGET_DIR}/config_voice.json" >/dev/null')
marker='''install -d -m 0755 "${HOME}/.config/systemd/user"
install -m 0644 "${SOURCE_DIR}/atlas-voice.service" "${HOME}/.config/systemd/user/atlas-voice.service"
systemctl --user daemon-reload
systemctl --user enable atlas-voice.service

echo "ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS"'''
s=s.replace('echo "ATLAS_V1_ALWAYS_ON_VOICE_INSTALL_PASS"', marker)
p.write_text(s, encoding='utf-8', newline='\n')
