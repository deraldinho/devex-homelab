from pathlib import Path
import sys
sys.path.insert(0, r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice')
from infrastructure.pentium.atlas.audio_preprocessor import VoiceAudioPreprocessor
src=Path(r'C:\Users\deral\DevEx-HomeLab\voice-diag.wav')
out=Path(r'C:\Users\deral\DevEx-HomeLab\voice-diag-clean.wav')
p=VoiceAudioPreprocessor(highpass_hz=120,target_peak=18000,max_gain=3.0)
out.write_bytes(p.process(src.read_bytes()))
print(out, out.stat().st_size)
