import importlib.util, pathlib, subprocess, sys, time
root=pathlib.Path('/home/deraldinho/pentium-agent/runtime/probes')
spec=importlib.util.spec_from_file_location('whisper_stt',root/'whisper_stt.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); sys.modules['whisper_stt']=mod
from whisper_stt import SubprocessWhisperRunner, WhisperSttBackend
wav=pathlib.Path('/home/deraldinho/pentium-agent/runtime/audio/voice-diag.wav').read_bytes()
backend=WhisperSttBackend('/home/deraldinho/pentium-agent/runtime/whisper/build/bin/whisper-cli','/home/deraldinho/pentium-agent/runtime/whisper/models/ggml-base-q5_1.bin',runner=SubprocessWhisperRunner(temp_dir='/home/deraldinho/pentium-agent/runtime/audio'),suppress_nst=True,timeout_s=90)
subprocess.run(['systemctl','--user','stop','atlas-voice.service'],check=False)
try:
    t=time.time(); text=backend.transcribe(wav)
    print('ELAPSED',round(time.time()-t,2)); print('TRANSCRIPT',repr(text))
finally:
    subprocess.run(['systemctl','--user','start','atlas-voice.service'],check=False)
