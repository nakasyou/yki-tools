import urllib.request, re, sys, json
eids=['11975418868','11976174364','11976232741','11978180594','11978185258','11978186442','11978187271','11978188775','11978193997','11980973078','11980975340']
out={}
for eid in eids:
    try:
        req=urllib.request.Request('https://ameblo.jp/linatomoyar/entry-%s.html'%eid, headers={'User-Agent':'Mozilla/5.0'})
        html=urllib.request.urlopen(req,timeout=30).read().decode('utf-8','replace')
        m=re.search(r'entryBody[^>]*>(.*?)</div>', html, re.S)
        body=m.group(1) if m else html
        body=re.sub(r'<br\s*/?>','\n',body); body=re.sub(r'<[^>]+>','',body)
        body=body.replace('&nbsp;',' ').replace('&amp;','&')
        for l in body.split('\n'):
            l=l.strip()
            mm=re.match(r'^(\d+)\s+(\S+?)\s+([01]{4})\s+([01]{4})\s+([01]{4})',l)
            if mm:
                no=int(mm.group(1)); name=mm.group(2)
                pat=tuple(int(x,2) for x in (mm.group(3),mm.group(4),mm.group(5)))
                out[no]=(name,pat)
        print(eid,'done, total',len(out))
    except Exception as e:
        print(eid,'ERR',e)
json.dump(out,open('zero_medals.json','w'),ensure_ascii=False)
print('saved',len(out))
