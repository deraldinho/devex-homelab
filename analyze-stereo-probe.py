import wave, math, struct
p='/home/deraldinho/pentium-agent/runtime/audio/stereo-probe.wav'
with wave.open(p,'rb') as w:
    raw=w.readframes(w.getnframes())
vals=[x[0] for x in struct.iter_unpack('<h',raw)]
l=vals[0::2]; r=vals[1::2]
ml=sum(l)/len(l); mr=sum(r)/len(r)
dl=[x-ml for x in l]; dr=[x-mr for x in r]
num=sum(a*b for a,b in zip(dl,dr))
den=math.sqrt(sum(a*a for a in dl)*sum(b*b for b in dr))
corr=num/den if den else 0
rmsl=math.sqrt(sum(x*x for x in l)/len(l)); rmsr=math.sqrt(sum(x*x for x in r)/len(r))
print('RMS_L',round(rmsl,1),'RMS_R',round(rmsr,1),'CORR',round(corr,6),'MEAN_L',round(ml,1),'MEAN_R',round(mr,1))
print('IDENTICAL_SAMPLES',sum(a==b for a,b in zip(l,r)),'OF',len(l))
