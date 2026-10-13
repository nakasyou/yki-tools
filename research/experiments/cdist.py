import struct, collections
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
d=open(BASE+'/Ver2_U.yki','rb').read()
offs=[]; i=0x200; prev=-1
while i+4<=len(d):
    v=struct.unpack('<I',d[i:i+4])[0]
    if v<=prev or v==0xffffffff: break
    offs.append((v-0x500800)*2); prev=v; i+=4
o,e=offs[1],offs[2]
u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
fidx={k for k,p in enumerate(ps) if p[0]==0xfffe}
# mark which pairs are inside fffe sections (after last fffe before next... sections are sparse; use: within 400 pairs after an fffe until next fffe)
# simpler: for each record tail (0,N)(0,C), find nearest preceding fffe index
ff=sorted(fidx)
import bisect
stats=collections.Counter()
Ns_by_C=collections.defaultdict(list)
for k in range(len(ps)-1):
    if ps[k][0]==0 and ps[k+1][0]==0 and ps[k+1][1] in (0x58,0x59,0x5a,0x5b):
        N,C=ps[k][1],ps[k+1][1]
        prev=bisect.bisect_right(ff,k)
        inside = prev>0 and (ff[prev-1]>=5886)  # song sections start at 5886
        # also check distance: inside section if k - ff[prev-1] < 400
        inside = inside and (k-ff[prev-1]<400)
        stats[(C,'in' if inside else 'out')]+=1
        if inside: Ns_by_C[C].append(N)
print(stats)
for C,ns in Ns_by_C.items():
    print('C=%#x in-section Ns:'%C,[hex(n) for n in ns])
