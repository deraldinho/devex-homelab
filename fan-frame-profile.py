import math, statistics, struct, wave
from pathlib import Path
p=Path.home()/"pentium-agent/runtime/audio/fan-profile.wav"
with wave.open(str(p),'rb') as w:
    rate=w.getframerate(); data=w.readframes(w.getnframes())
s=[x[0] for x in struct.iter_unpack('<h',data)]
size=int(rate*0.020)
r=[]
for i in range(0,len(s)-size+1,size):
    c=s[i:i+size]; r.append(math.sqrt(sum(v*v for v in c)/len(c)))
r_sorted=sorted(r)
def pct(q): return r_sorted[min(len(r_sorted)-1,round((len(r_sorted)-1)*q))]
floor=statistics.median(r); threshold=max(220,floor*1.15+150)
longest=cur=0
for x in r:
    cur=cur+1 if x>=threshold else 0; longest=max(longest,cur)
print('FRAMES',len(r),'MEDIAN',round(floor,1),'P90',round(pct(.9),1),'P95',round(pct(.95),1),'P99',round(pct(.99),1),'MAX',round(max(r),1))
print('CURRENT_THRESHOLD',round(threshold,1),'LONGEST_ABOVE',longest,'ABOVE_COUNT',sum(x>=threshold for x in r))
p.unlink()