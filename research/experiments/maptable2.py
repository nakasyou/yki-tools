import struct, collections

for fn in ['Ver2_U.yki','Ver7_U.yki']:
    d=open('/home/nakasyou/Projects/youkaiwatch/yki/'+fn,'rb').read()
    i=0x200; prev=-1
    while i+4<=len(d):
        v=struct.unpack('<I',d[i:i+4])[0]
        if v<=prev or v==0xffffffff: break
        prev=v; i+=4
    tbl=i
    end=min(tbl+0x100000,len(d))
    u16=struct.unpack('<%dH'%((end-tbl)//2), d[tbl:end])
    pairs=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
    print('===',fn,'table@0x%x'%tbl)
    recs=[]
    k=0
    while k < len(pairs)-10:
        p=pairs[k:k+10]
        if (p[0][0]==0 and p[1]==(0xffff,0xffff) and p[2][0]==0 and p[3]==(0xffff,0xffff)
            and p[4][0]==0 and p[5][0]==0 and p[6]==(0xffff,0xffff) and p[7]==(0xffff,0xffff)
            and p[8]==(0xffff,0xffff) and p[9]==(0xffff,0xffff)):
            recs.append((p[0][1],p[2][1],p[4][1],p[5][1]))
            k+=10
        else:
            k+=1
    print('records found:',len(recs))
    groups=collections.defaultdict(list)
    for A,B,N,C in recs:
        groups[(A,B,C)].append(N)
    for g,ns in list(groups.items())[:40]:
        print('  fields=%s N: 0x%x..0x%x count=%d'%(tuple(hex(x) for x in g),min(ns),max(ns),len(ns)))
