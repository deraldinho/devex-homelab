import math
import struct
import sys
import wave

with wave.open(sys.argv[1], 'rb') as wav:
    frames = wav.readframes(wav.getnframes())
samples = [item[0] for item in struct.iter_unpack('<h', frames)]
rms = math.sqrt(sum(value * value for value in samples) / len(samples))
print(f'FAN_RMS={rms:.2f}')
