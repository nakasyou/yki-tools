import struct, os
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
d=open(os.path.join(BASE,'Ver2_U.yki'),'rb').read()
offs=[]; i=0x200; prev=-1
while i+4<=len(d):
    v=struct.unpack('<I',d[i:i+4])[0]
    if v<=prev or v==0xffffffff: break
    offs.append((v-0x500800)*2); prev=v; i+=4
n=len(offs)
o,e=offs[1],offs[2]
u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
# print all pairs with index, marking fffe and (1,x)
for k,p in enumerate(ps):
    mark=''
    if p[0]==0xfffe: mark=' <== FFFE'
    elif p[0]==1: mark=' <- (1,%#x)'%p[1]
    elif p[0]==0: mark=''
    if mark or p[0]==0xfffe:
        print('%4d: (%04x,%04x)%s'%(k,p[0],p[1],mark))
