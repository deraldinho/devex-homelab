import wave, struct, math
p='/home/deraldinho/pentium-agent/runtime/audio/voice-diag.wav'
with wave.open(p,'rb') as w:
    rate=w.getframerate(); n=w.getnframes(); raw=w.readframes(n)
s=[x[0] for x in struct.iter_unpack('<h',raw)]
size=rate//10
rows=[]
for i in range(0,len(s)-size+1,size):
    c=s[i:i+size]; rms=math.sqrt(sum(x*x for x in c)/len(c)); peak=max(abs(x) for x in c)
    rows.append((i/rate,rms,peak))
print('TOP_RMS')
for t,r,p in sorted(rows,key=lambda x:x[1],reverse=True)[:20]: print(f'{t:4.1f}s RMS={r:7.1f} PEAK={p:5d}')
print('TIMELINE')
for t,r,p in rows: print(f'{t:4.1f} {r:7.1f} {p:5d}')
