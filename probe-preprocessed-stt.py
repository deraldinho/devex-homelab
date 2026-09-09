import importlib.util, pathlib, subprocess, sys, time
root=pathlib.Path('/home/deraldinho/pentium-agent/runtime/probes')
for name in ('audio_preprocessor','whisper_stt'):
    spec=importlib.util.spec_from_file_location(name, root/f'{name}.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); sys.modules[name]=mod
from audio_preprocessor import VoiceAudioPreprocessor
from whisper_stt import SubprocessWhisperRunner, WhisperSttBackend
wav=pathlib.Path('/home/deraldinho/pentium-agent/runtime/audio/voice-diag.wav').read_bytes()
backend=WhisperSttBackend('/home/deraldinho/pentium-agent/runtime/whisper/build/bin/whisper-cli','/home/deraldinho/pentium-agent/runtime/whisper/models/ggml-base-q5_1.bin',runner=SubprocessWhisperRunner(temp_dir='/home/deraldinho/pentium-agent/runtime/audio'),preprocessor=VoiceAudioPreprocessor(highpass_hz=120,target_peak=18000,max_gain=3.0),timeout_s=90)
subprocess.run(['systemctl','--user','stop','atlas-voice.service'],check=False)
try:
    t=time.time(); text=backend.transcribe(wav)
    print('ELAPSED',round(time.time()-t,2)); print('TRANSCRIPT',repr(text))
finally:
    subprocess.run(['systemctl','--user','start','atlas-voice.service'],check=False)
