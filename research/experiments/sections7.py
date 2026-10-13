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
    fidx=[k for k,p in enumerate(ps) if p[0]==0xfffe]
    print('===',fn,'fffe count:',len(fidx))
    for fi in fidx:
        # collect (1,X) refs and (0,N) entries until next fffe or 200 pairs
        refs=[]; Ns=[]
        k=fi+1
        while k<len(ps) and ps[k][0]!=0xfffe and k<fi+400:
            p=ps[k]
            if p[0]==1: refs.append(p[1])
            elif p[0]==0: Ns.append(p[1])
            k+=1
        def refname(x):
            if x<n:
                ro=offs[x]; re_=offs[x+1] if x+1<n else len(d)
                if d[ro:ro+2]==b'AU': return 'au%d'%(x-26)
                q16=struct.unpack('<%dH'%((re_-ro)//2),d[ro:re_])
                if re_-ro==8 and q16[0]==1 and q16[2]==1: return 'pair(au%d,au%d)'%(q16[1],q16[3])
            return 'res%d'%x
        print('  @%d refs=%s Ns=%s'%(fi,[refname(x) for x in refs],Ns[:20]))
