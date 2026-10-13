import re, zlib
d=open('/home/nakasyou/Projects/youkaiwatch/yki/ドライブ.pdf','rb').read()
streams=[]
for m in re.finditer(rb'stream\r?\n', d):
    s=m.end(); e=d.find(b'endstream', s)
    if e<0: continue
    raw=d[s:e].strip(b'\r\n')
    try: streams.append(zlib.decompress(raw))
    except Exception: streams.append(raw)
# find ToUnicode cmaps: beginbfchar/beginbfrange
cmap={}
for s in streams:
    if b'beginbf' in s:
        for m in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', s):
            src=int(m.group(1),16); dst=m.group(2)
            try:
                cmap[src]=bytes.fromhex(dst.decode()).decode('utf-16-be')
            except Exception: pass
        for m in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[((?:\s*<[0-9A-Fa-f]+>)+)\]', s):
            lo=int(m.group(1),16)
            for k,mm in enumerate(re.finditer(rb'<([0-9A-Fa-f]+)>', m.group(3))):
                try: cmap[lo+k]=bytes.fromhex(mm.group(1).decode()).decode('utf-16-be')
                except Exception: pass
print('cmap size',len(cmap))
# now decode text strings in content streams (2-byte codes)
for s in streams:
    if b'Tj' in s or b'TJ' in s:
        i=0; line=[]
        while i<len(s):
            if s[i]==0x3c and i+1<len(s) and s[i+1]!=0x3c:  # hex string
                j=s.find(b'>',i)
                if j<0: break
                hx=s[i+1:j].replace(b' ',b'')
                try:
                    bb=bytes.fromhex(hx.decode())
                    t=''.join(cmap.get(int.from_bytes(bb[k:k+2],'big'),'?') for k in range(0,len(bb)-1,2))
                    line.append(t)
                except Exception: pass
                i=j+1
            elif s[i]==0x28:
                j=i+1; depth=1; buf=bytearray()
                while j<len(s) and depth>0:
                    c=s[j]
                    if c==0x5c: buf.append(s[j+1]); j+=2; continue
                    if c==0x28: depth+=1
                    if c==0x29: depth-=1
                    if depth>0: buf.append(c)
                    j+=1
                bb=bytes(buf)
                t=''.join(cmap.get(int.from_bytes(bb[k:k+2],'big'), chr(bb[k]) if bb[k]<128 else '?') for k in range(0,len(bb)-1,2)) if len(bb)>1 else ''
                line.append(t); i=j
            elif s[i:i+2]==b'Td' or s[i:i+2]==b'T*':
                line.append('\n'); i+=2
            else:
                i+=1
        print(''.join(line))
        print('---')
