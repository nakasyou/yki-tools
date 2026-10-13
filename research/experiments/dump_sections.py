import struct, os

BASE='/home/nakasyou/Projects/youkaiwatch/yki'

def load(fn):
    d=open(os.path.join(BASE,fn),'rb').read()
    offs=[]; i=0x200; prev=-1
    while i+4<=len(d):
        v=struct.unpack('<I',d[i:i+4])[0]
        if v<=prev or v==0xffffffff: break
        offs.append((v-0x500800)*2); prev=v; i+=4
    return d, offs

def pairs_of(d,o,e):
    u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
    return [(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]

for fn in ['Ver2_U.yki','Ver7_U.yki']:
    d,offs=load(fn)
    n=len(offs)
    print('===',fn,'resources:',n)
    # classify resources
    def is_au(i):
        o=offs[i]; e=offs[i+1] if i+1<n else len(d)
        return d[o:o+2]==b'AU'
    def res_kind(i):
        o=offs[i]; e=offs[i+1] if i+1<n else len(d)
        if d[o:o+2]==b'AU': return 'AU len=%d'%(e-o)
        ps=pairs_of(d,o,e)
        tags={p[0] for p in ps}
        if tags<={1}: return 'pairlist %s'%(' '.join('(1,%#x)'%p[1] for p in ps))
        return 'data %dB first=%s'%(e-o, ps[:4])
    # parse res1
    ps=pairs_of(d,offs[1],offs[2])
    # walk: collect fffe-delimited sections
    secs=[]; cur=None
    k=0
    while k<len(ps):
        p=ps[k]
        if p==(0xfffe,0xfffe):
            if cur is not None: secs.append(cur)
            cur=[]; k+=1; continue
        if cur is not None:
            cur.append(p)
        k+=1
    if cur: secs.append(cur)
    print('fffe sections:',len(secs))
    for si,s in enumerate(secs):
        print(' section %d: %d pairs'%(si,len(s)))
        for p in s:
            if p[0]==1 and p[1]<n:
                print('   (1,%#04x) -> res%d: %s'%(p[1],p[1],res_kind(p[1])))
            else:
                print('   (%x,%x)'%p)
