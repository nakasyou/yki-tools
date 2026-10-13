import struct, os
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
    if p[0]==0 and k+1<len(ps) and ps[k+1]==(0,0x5a):
        N=p[1]
        ctx=['(%04x,%04x)'%q for q in ps[max(0,k-8):k+4]]
        print('%4d N=%#x(%d) ctx: %s'%(k,N,N,' '.join(ctx)))
