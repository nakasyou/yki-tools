import struct, os
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
d=open(os.path.join(BASE,'Ver2_U.yki'),'rb').read()
offs=[]; i=0x200; prev=-1
while i+4<=len(d):
    v=struct.unpack('<I',d[i:i+4])[0]
    if v<=prev or v==0xffffffff: break
    offs.append((v-0x500800)*2); prev=v; i+=4
o,e=offs[1],offs[2]
u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
print('--- window 6990-7050 ---')
for j in range(6990,7050):
    print('   %4d (%04x,%04x)'%(j,ps[j][0],ps[j][1]))
print('--- all pairs with value 0x87 ---')
for k,p in enumerate(ps):
    if p[1]==0x87:
        print('   %4d (%04x,%04x) ctx: %s'%(k,p[0],p[1],['(%04x,%04x)'%q for q in ps[max(0,k-3):k+4]]))
