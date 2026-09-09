import json
from pathlib import Path
root=Path(r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice\infrastructure\pentium\atlas')
p=root/'config_voice.json'; cfg=json.loads(p.read_text(encoding='utf-8'))
cfg.update({'anc_enabled':False,'anc_primary_channel':'left','anc_reference_channel':'right','anc_taps':16,'anc_mu':0.3,'anc_calibration_frames':50})
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'install-user.sh'; s=p.read_text(encoding='utf-8')
if '  adaptive_noise_canceller.py \\\n' not in s:
    s=s.replace('  alsa_stream.py \\\n', '  alsa_stream.py \\\n  adaptive_noise_canceller.py \\\n', 1)
if '"${TARGET_DIR}/adaptive_noise_canceller.py" \\\n' not in s:
    s=s.replace('  "${TARGET_DIR}/alsa_stream.py" \\\n', '  "${TARGET_DIR}/alsa_stream.py" \\\n  "${TARGET_DIR}/adaptive_noise_canceller.py" \\\n', 1)
p.write_text(s,encoding='utf-8')
