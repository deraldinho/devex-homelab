import os
from atlas.live_tts import LiveTtsBackend

home = os.path.expanduser("~")
alsa = f"{home}/pentium-agent/runtime/alsa-root"
espeak = f"{home}/pentium-agent/runtime/espeak-root"
env = dict(os.environ)
env["LD_LIBRARY_PATH"] = f"{espeak}/usr/lib/x86_64-linux-gnu:{espeak}/usr/lib/x86_64-linux-gnu/pulseaudio:{alsa}/usr/lib/x86_64-linux-gnu"
env["ALSA_CONFIG_PATH"] = f"{alsa}/usr/share/alsa/alsa.conf"
env["ALSA_CONFIG_DIR"] = f"{alsa}/usr/share/alsa"
env["ESPEAK_DATA_PATH"] = f"{espeak}/usr/lib/x86_64-linux-gnu/espeak-ng-data"
tts = LiveTtsBackend(
    f"{espeak}/usr/bin/espeak-ng", f"{alsa}/usr/bin/aplay",
    voice="pt-br", device="plughw:0,0", max_text_chars=512,
    max_audio_bytes=2_000_000, timeout_s=20, env=env,
)
tts.speak("Olá, Deraldinho. Aqui é o Atlas. A minha voz ao vivo já está funcionando no Pentium.")
print("ATLAS_V1_LIVE_TTS_PHYSICAL_PASS")
