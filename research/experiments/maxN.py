import struct, os
BASE='/home/nakasyou/Projects/youkaiwatch/yki'
for fn in sorted(os.listdir(BASE)):
    if not fn.endswith('.yki'): continue
    d=open(os.path.join(BASE,fn),'rb').read()
    offs=[]; i=0x200; prev=-1
    while i+4<=len(d):
        v=struct.unpack('<I',d[i:i+4])[0]
        if v<=prev or v==0xffffffff: break
        offs.append((v-0x500800)*2); prev=v; i+=4
    o,e=offs[1],offs[2]
    u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
    ps=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
    Ns=[p[1] for k,p in enumerate(ps) if p[0]==0 and k+1<len(ps) and ps[k+1][0]==0 and ps[k+1][1] in (0x58,0x59,0x5a,0x5b)]
    print(fn,'records=%d maxN=%#x'%(len(Ns),max(Ns)))
    # top 20 largest N
    print('  largest:',sorted(set(Ns))[-15:])
