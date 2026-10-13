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
for j in range(0,120):
    print('%4d (%04x,%04x)'%(j,ps[j][0],ps[j][1]))
