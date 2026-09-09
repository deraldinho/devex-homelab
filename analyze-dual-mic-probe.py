import wave, math, struct
from pathlib import Path

def load(path):
    with wave.open(str(path),'rb') as w:
        x=[v[0] for v in struct.iter_unpack('<h',w.readframes(w.getnframes()))]
    return x

a=load(Path('/home/deraldinho/pentium-agent/runtime/audio/internal-probe.wav'))
b=load(Path('/home/deraldinho/pentium-agent/runtime/audio/usb-probe.wav'))
n=min(len(a),len(b)); a=a[:n]; b=b[:n]

def rms(x): return math.sqrt(sum(v*v for v in x)/len(x))
def corr(x,y):
    mx=sum(x)/len(x); my=sum(y)/len(y)
    num=sum((u-mx)*(v-my) for u,v in zip(x,y))
    dx=math.sqrt(sum((u-mx)**2 for u in x)); dy=math.sqrt(sum((v-my)**2 for v in y))
    return num/(dx*dy) if dx and dy else 0
print('INTERNAL_RMS',round(rms(a),1),'USB_RMS',round(rms(b),1),'CORR0',round(corr(a,b),4))
print('INTERNAL_PEAK',max(map(abs,a)),'USB_PEAK',max(map(abs,b)))