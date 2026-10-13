import struct, os, csv, collections

BASE='/home/nakasyou/Projects/youkaiwatch/yki'
OUT='/home/nakasyou/Projects/youkaiwatch/outputs'

for fn in sorted(f for f in os.listdir(BASE) if f.endswith('.yki')):
    d=open(os.path.join(BASE,fn),'rb').read()
    offs=[]; i=0x200; prev=-1
    while i+4<=len(d):
        v=struct.unpack('<I',d[i:i+4])[0]
        if v<=prev or v==0xffffffff: break
        offs.append((v-0x500800)*2); prev=v; i+=4
    o,e=offs[1],offs[2]
    u16=struct.unpack('<%dH'%((e-o)//2), d[o:e])
    pairs=[(u16[k],u16[k+1]) for k in range(0,len(u16)-1,2)]
    recs=[];i=0
    while i<len(pairs)-9:
        p=pairs[i:i+9]
        if p[0][0]==0 and p[1]==(0xffff,0xffff) and p[4][0]==0 and p[5][0]==0:
            recs.append((p[0][1],p[2][1],p[4][1],p[5][1])); i+=9
        else: i+=1
    ver=fn.replace('.yki','')
    with open(os.path.join(OUT,f'medals_{ver}.csv'),'w',newline='') as f:
        w=csv.writer(f)
        w.writerow(['medal_id','field_A','field_B','field_C'])
        for A,B,N,C in recs:
            w.writerow([f'0x{N:03x}',f'0x{A:02x}',f'0x{B:02x}' if B!=0xffff else 'none',f'0x{C:02x}'])
    print(ver,len(recs),'medal records ->',f'medals_{ver}.csv')
