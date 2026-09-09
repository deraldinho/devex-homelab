from pathlib import Path
p=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\.github\workflows\foundation-ci.yml')
s=p.read_text(encoding='utf-8')
mods='''              "$atlas/unix_http.py" \\
              "$atlas/voice_gate.py" \\
              "$atlas/live_tts.py" \\
              "$atlas/alsa_capture.py" \\
              "$atlas/whisper_stt.py" \\
              "$atlas/voice_runtime.py" \\
              "$atlas/energy_vad.py" \\
              "$atlas/human_interaction.py" \\
              "$atlas/human_context.py" \\
              "$atlas/voice_daemon.py" \\
              "$atlas/cli.py"'''
s=s.replace('''              "$atlas/unix_http.py" \\
              "$atlas/cli.py"''', mods)
s=s.replace('''            python3 -m json.tool "$atlas/config_fast_router.json" >/dev/null''', '''            python3 -m json.tool "$atlas/config_fast_router.json" >/dev/null
            python3 -m json.tool "$atlas/config_voice.json" >/dev/null''')
s=s.replace("            echo 'DEVEX_HOMELAB_ATLAS_I1_OBSERVATION_INTEGRATION_PASS'", "            echo 'DEVEX_HOMELAB_ATLAS_I1_OBSERVATION_INTEGRATION_PASS'\n            echo 'DEVEX_HOMELAB_ATLAS_V1_ALWAYS_ON_VOICE_PASS'")
p.write_text(s, encoding='utf-8', newline='\n')
