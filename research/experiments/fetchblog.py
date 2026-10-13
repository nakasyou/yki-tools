import urllib.request, re, sys
for eid in sys.argv[1:]:
    url='https://ameblo.jp/linatomoyar/entry-%s.html'%eid
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    html=urllib.request.urlopen(req,timeout=20).read().decode('utf-8','replace')
    m=re.search(r'entryBody[^>]*>(.*?)</div><!-- /entryBody -->', html, re.S) or re.search(r'class="entryText"(.*?)</div>', html, re.S)
    body=m.group(1) if m else html
    body=re.sub(r'<br\s*/?>','\n',body)
    body=re.sub(r'<[^>]+>','',body)
    body=body.replace('&nbsp;',' ').replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
    body=re.sub(r'\n{3,}','\n\n',body)
    print('='*20, eid, '='*20)
    print(body[:8000])
