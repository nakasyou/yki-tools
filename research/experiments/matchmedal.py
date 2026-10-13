import re
# blog tables (row1 row2 row3, row4=1010 implicit)
tables = {}
cur = None
import subprocess
# I'll embed the fetched tables by re-fetching quickly via saved text? Simpler: hardcode fetch again
import urllib.request
def fetch(eid):
    req=urllib.request.Request('https://ameblo.jp/linatomoyar/entry-%s.html'%eid, headers={'User-Agent':'Mozilla/5.0'})
    html=urllib.request.urlopen(req,timeout=30).read().decode('utf-8','replace')
    m=re.search(r'<div class="entryText[^"]*"[^>]*>(.*?)</div>', html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r'<br\s*/?>','\n',body)
    body = re.sub(r'<[^>]+>','',body)
    return [l.strip() for l in body.split('\n') if re.match(r'^[01]{4} [01]{4} [01]{4}', l.strip())]

rows1111 = fetch('12095417562')
rows1110 = fetch('12098655017')
rows1101 = fetch('12100832688')
print('fetched:', len(rows1111), len(rows1110), len(rows1101))
known = {}
for l in rows1111+rows1110+rows1101:
    p = l.split()
    known[tuple(int(x,2) for x in p[:3])] = ' '.join(p[3:])

user = [0b0111,0b1110,0b1101,0b0101]  # as user wrote, top to bottom
def rev4(x): return int(format(x,'04b')[::-1],2)

transforms = {
 'as-is': lambda g: g,
 'row-rev': lambda g: g[::-1],
 'bit-rev': lambda g: [rev4(x) for x in g],
 'both': lambda g: [rev4(x) for x in g[::-1]],
 'transpose': lambda g: [int(''.join(str((g[r]>>(3-c))&1) for r in range(4)),2) for c in range(4)],
 'transpose+rev': lambda g: [rev4(int(''.join(str((g[r]>>(3-c))&1) for r in range(4)),2)) for c in range(4)],
 'transpose+rowrev': lambda g: [int(''.join(str((g[r]>>(3-c))&1) for r in range(4)),2) for c in range(4)][::-1],
 'transpose+both': lambda g: [rev4(int(''.join(str((g[r]>>(3-c))&1) for r in range(4)),2)) for c in range(4)][::-1],
}
for name,f in transforms.items():
    g = f(user)
    r4 = g[3]
    key = tuple(g[:3])
    hit = known.get(key)
    print('%-18s rows=%s r4=%s -> %s'%(name,[format(x,'04b') for x in g],format(r4,'04b'),hit if hit else ('r4!=1010' if r4!=0b1010 else 'not in table')))
