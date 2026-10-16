import re,html,sys
for fid in ['12095416222','12095417562','12098655017','12100832688']:
    h=open('lina_%s.html'%fid,encoding='utf-8',errors='replace').read()
    m=re.search(r'entryBody">(.*?)<!--',h,re.S)
    if not m: m=re.search(r'entryBody">(.*)',h,re.S)
    t=m.group(1) if m else ''
    t=re.sub(r'<br\s*/?>','\n',t)
    t=re.sub(r'<[^>]+>','',t)
    t=html.unescape(t)
    open('lina_%s.txt'%fid,'w').write(t)
    # extract pattern lines
    lines=[l.strip() for l in t.split('\n')]
    pats=[l for l in lines if re.match(r'^[01]{4} [01]{4} [01]{4} ',l)]
    recog=[l for l in pats if not l.rstrip().endswith(' そ') and not l.rstrip().endswith(' 無')]
    print('===',fid,'patterns:',len(pats),'recognized (excluding source markers):',len(recog))
    for l in recog[:60]:
        print('  ',l)
