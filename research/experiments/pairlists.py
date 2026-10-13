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
    n=len(offs)
    pls=[]
    for ri in range(n):
        o=offs[ri]; e=offs[ri+1] if ri+1<n else len(d)
        if d[o:o+2]==b'AU': continue
        sz=e-o
        if sz==8:
            u16=struct.unpack('<4H',d[o:e])
            if u16[0]==1 and u16[2]==1:
                pls.append((ri,u16[1],u16[3]))
    print(fn,'pairlists:',pls)
