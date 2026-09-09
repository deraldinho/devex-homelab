import wave, struct, math, statistics
p='/home/deraldinho/pentium-agent/runtime/audio/voice-diag.wav'
with wave.open(p,'rb') as w:
    n=w.getnframes(); r=w.getframerate(); b=w.readframes(n)
s=[x[0] for x in struct.iter_unpack('<h', b)]
a=[abs(x) for x in s]
q=sorted(a)
print('FRAMES',n,'RATE',r,'SEC',round(n/r,3))
print('RMS',round(math.sqrt(sum(x*x for x in s)/len(s)),1),'PEAK',max(a),'MEAN',round(statistics.fmean(s),1))
print('P50',q[int(.5*len(q))],'P90',q[int(.9*len(q))],'P95',q[int(.95*len(q))],'P99',q[int(.99*len(q))])
print('CLIP',sum(1 for x in a if x>=32760))
