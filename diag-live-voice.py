from pathlib import Path
from atlas.alsa_capture import AlsaCaptureBackend
from atlas.energy_vad import EnergyVad
from atlas.whisper_stt import WhisperSttBackend, SubprocessWhisperRunner
from atlas.voice_gate import WakePhraseGate
root = Path.home() / 'pentium-agent' / 'runtime'
capture = AlsaCaptureBackend(str(root/'alsa-root/usr/bin/arecord'), device='plughw:0,0', duration_s=8, max_audio_bytes=300000)
audio = capture.capture_utterance()
vad = EnergyVad(rms_threshold=220, max_samples=8*16000)
print('HAS_SPEECH=', vad.has_speech(audio), flush=True)
stt = WhisperSttBackend(str(root/'whisper/build/bin/whisper-cli'), str(root/'whisper/models/ggml-tiny-q5_1.bin'), runner=SubprocessWhisperRunner(temp_dir=root/'audio'), timeout_s=45)
text = stt.transcribe(audio)
print('TRANSCRIPT=', repr(text), flush=True)
print('WAKE=', WakePhraseGate('Atlas', max_text_chars=256).evaluate(text), flush=True)
