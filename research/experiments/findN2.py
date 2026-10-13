import struct, os
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
for fn in ['Ver2_U.yki','Ver7_U.yki']:
    d=open(os.path.join(BASE,fn),'rb').read()
    offs=[]; i=0x200; prev=-1
    while i+4<=len(d):
        v=struct.unpack('<I',d[i:i+4])[0]
        if v<=prev or v==0xffffffff: break
        offs.append((v-0x500800)*2); prev=v; i+=4
    n=len(offs)
    o,e=offs[1],offs[2]
    u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
    ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
    print('===',fn)
    for k,p in enumerate(ps):
        if p[0]==0 and p[1] in (0x215,0x214,0x216,0x213):
            ctx=['(%04x,%04x)'%q for q in ps[max(0,k-9):k+4]]
            print('  %4d N=%#x ctx: %s'%(k,p[1],' '.join(ctx)))
