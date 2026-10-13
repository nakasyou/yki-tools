import struct, os
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
d=open(BASE+'/Ver2_U.yki','rb').read()
offs=[]; i=0x200; prev=-1
while i+4<=len(d):
    v=struct.unpack('<I',d[i:i+4])[0]
    if v<=prev or v==0xffffffff: break
    offs.append((v-0x500800)*2); prev=v; i+=4
n=len(offs)
for ri in range(0,30):
    o=offs[ri]; e=offs[ri+1] if ri+1<n else len(d)
    if d[o:o+2]==b'AU':
        print('res%d: AU %d bytes'%(ri,e-o)); continue
    u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
    ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
    print('res%d: %d bytes pairs=%s'%(ri,e-o,ps[:14]))
