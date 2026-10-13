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
    print('===',fn,'nres=%d pairs=%d'%(n,len(ps)))
    # find fffe indices
    fidx=[k for k,p in enumerate(ps) if p[0]==0xfffe]
    print('fffe at:',fidx)
    for fi in fidx:
        print('-- section starting at pair %d --'%fi)
        k=fi+1
        while k<len(ps) and ps[k][0]!=0xfffe and k<fi+60:
            p=ps[k]
            extra=''
            if p[0]==1 and p[1]<n:
                ro,re_=offs[p[1]],(offs[p[1]+1] if p[1]+1<n else len(d))
                if d[ro:ro+2]==b'AU': extra=' AU res%d len=%d'%(p[1],re_-ro)
                else:
                    q16=struct.unpack('<%dH'%((re_-ro)//2),d[ro:re_])
                    qp=[(q16[j],q16[j+1]) for j in range(0,len(q16)-1,2)]
                    extra=' res%d pairs=%s'%(p[1],qp)
            print('   %4d (%04x,%04x)%s'%(k,p[0],p[1],extra))
            k+=1
