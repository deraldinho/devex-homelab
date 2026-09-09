import math, struct, wave, sys
sys.path.insert(0, r'C:\Users\deral\DevEx-HomeLab\.worktrees\issue-20-atlas-v1-always-on-voice')
from infrastructure.pentium.atlas.adaptive_noise_canceller import NlmsCanceller
p=r'C:\Users\deral\DevEx-HomeLab\stereo-probe.wav'
with wave.open(p,'rb') as w:
    raw=w.readframes(w.getnframes()); rate=w.getframerate()
vals=[x for pair in struct.iter_unpack('<hh', raw) for x in pair]
l=vals[0::2]; r=vals[1::2]
def rms(a): return math.sqrt(sum(x*x for x in a)/len(a))
for primary, ref, name in [(l,r,'L<-R'),(r,l,'R<-L')]:
    for taps in (8,16,32,64):
        c=NlmsCanceller(taps=taps, mu=0.2)
        cal=min(len(primary)//3, rate//2)
        for i in range(cal): c.process_sample(primary[i],ref[i],adapt=True)
        out=[c.process_sample(primary[i],ref[i],adapt=False) for i in range(cal,len(primary))]
        before=rms(primary[cal:]); after=rms(out)
        print(name,'taps',taps,'before',round(before,1),'after',round(after,1),'reduction_pct',round((1-after/before)*100,1))
