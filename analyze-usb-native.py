import wave, struct, math
p='/home/deraldinho/pentium-agent/runtime/audio/usb-native.wav'
with wave.open(p,'rb') as w:
    s=[x[0] for x in struct.iter_unpack('<h',w.readframes(w.getnframes()))]
print('RMS',round(math.sqrt(sum(v*v for v in s)/len(s)),1),'PEAK',max(map(abs,s)),'N',len(s))