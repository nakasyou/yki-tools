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
# print window around each (1,X) extra where X in 14..25 (pair lists)
for k,p in enumerate(ps):
    if p[0]==1 and 14<=p[1]<=25:
        print('--- extra at pair %d: (1,%#x) ---'%(k,p[1]))
        for j in range(max(0,k-12),min(len(ps),k+6)):
            print('   %4d (%04x,%04x)%s'%(j,ps[j][0],ps[j][1],' <==' if j==k else ''))
