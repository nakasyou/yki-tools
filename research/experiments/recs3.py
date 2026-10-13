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
    # record start: (0,v) where next is (f,f) and pattern (0,a)(f,f)(0,b)(f,f)(0,n)(0,c) or variant
    # simpler: find all (0,N)(0,C) consecutive pairs = record tails
    print('===',fn)
    recs=[]
    k=0
    while k < len(ps)-1:
        if ps[k][0]==0 and ps[k+1][0]==0 and ps[k+1][1] in (0x58,0x59,0x5a,0x5b):
            N=ps[k][1]; C=ps[k+1][1]
            # look back for extras (1,X) and A,B fields within previous 12 pairs
            extras=[]; fields=[]
            j=k-1
            while j>=0 and j>k-15:
                p=ps[j]
                if p[0]==1: extras.append(p[1])
                elif p[0]==0: fields.append(p[1])
                elif p[0]==0xfffe: break
                j-=1
            recs.append((N,C,list(reversed(fields)),sorted(extras)))
            k+=2
        else:
            k+=1
    print('records:',len(recs))
    import collections
    cc=collections.Counter(r[1] for r in recs)
    print('C distribution:',dict(cc))
    for N,C,fields,extras in recs:
        if C==0x5b or extras:
            print('  N=%#05x C=%#x fields=%s extras=%s'%(N,C,[hex(f) for f in fields],[hex(x) for x in extras]))
