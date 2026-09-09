from atlas.voice_daemon import _tts_env
from atlas.live_tts import LiveTtsBackend
env, alsa, espeak, _ = _tts_env()
tts=LiveTtsBackend(str(espeak/'usr/bin/espeak-ng'),str(alsa/'usr/bin/aplay'),voice='pt-br',device='plughw:0,0',max_text_chars=256,max_audio_bytes=2000000,timeout_s=20,env=env)
tts.speak('Atlas, está me ouvindo?')
print('ACOUSTIC_STIMULUS_PLAYED')
