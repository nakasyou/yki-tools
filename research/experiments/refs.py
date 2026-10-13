import struct
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
for k,p in enumerate(ps):
    if p[0]==1 and p[1] in (0x28,0x29,0x2a,0x2b,0x2c,0x2d,0x47,0x48,0x49,0x4a,0x4b):
        N=None
        for j in range(k,min(k+12,len(ps)-1)):
            if ps[j][0]==0 and ps[j+1][0]==0 and ps[j+1][1] in (0x58,0x59,0x5a,0x5b):
                N=ps[j][1]; break
        print('pair %4d: (1,%#x)=au%d  owner N=%s'%(k,p[1],p[1]-26,N))
