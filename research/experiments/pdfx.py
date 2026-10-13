import re, zlib, sys
d=open('/home/nakasyou/Projects/youkaiwatch/yki/ドライブ.pdf','rb').read()
out=[]
for m in re.finditer(rb'stream\r?\n', d):
    s=m.end()
    e=d.find(b'endstream', s)
    if e<0: continue
    raw=d[s:e].strip(b'\r\n')
    try:
        out.append(zlib.decompress(raw))
    except Exception:
        out.append(raw)
txt=b'\n'.join(out)
# literal strings
res=[]
i=0
while i < len(txt):
    if txt[i]==0x28:  # (
        j=i+1; depth=1; buf=bytearray()
        while j<len(txt) and depth>0:
            c=txt[j]
            if c==0x5c:
                buf.append(txt[j+1]); j+=2; continue
            if c==0x28: depth+=1
            if c==0x29: depth-=1
            if depth>0: buf.append(c)
            j+=1
        res.append(bytes(buf)); i=j
    else:
        i+=1
print('literal strings:',len(res))
seen=set()
for s in res:
    # try utf-16be then utf-8/latin
    for enc in ('utf-16-be','utf-8','latin-1'):
        try:
            t=s.decode(enc)
            if any(ch.isprintable() for ch in t):
                if t not in seen:
                    seen.add(t); print(repr(t))
                break
        except Exception:
            continue
