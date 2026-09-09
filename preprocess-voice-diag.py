from pathlib import Path
import sys
sys.path.insert(0,'/home/deraldinho/pentium-agent/runtime/probes')
from audio_preprocessor import VoiceAudioPreprocessor
src=Path('/home/deraldinho/pentium-agent/runtime/audio/voice-diag.wav')
dst=Path('/home/deraldinho/pentium-agent/runtime/audio/voice-diag-pre.wav')
dst.write_bytes(VoiceAudioPreprocessor(highpass_hz=120,target_peak=18000,max_gain=3.0).process(src.read_bytes()))
print(dst, dst.stat().st_size)
