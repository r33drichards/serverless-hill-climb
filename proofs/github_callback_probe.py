import urllib.request,urllib.error,http.cookiejar,re
origin='https://durable-pi-modal.rwendt1337.workers.dev'
c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path):
 try:
  with c.open(urllib.request.Request(origin+path,headers={'User-Agent':'durable-pi-modal-smoke/1.0'})) as r:return r.status,r.read().decode()
 except urllib.error.HTTPError as e:return e.code,e.read().decode()
s,b=get('/admin')
m=re.search(r'apps/new\?state=([^"&]+)',b)
if not m:raise SystemExit('Setup no longer pending; no probe performed')
s,b=get('/setup/callback?state='+m[1]+'&code=invalidruntimeprobe0000000000000000000000')
print('Synthetic setup callback HTTP:',s)
print('Generic runtime failure:', 'No sensitive details have been logged' in b)
print('Handled provider rejection:', 'The sign-in provider could not complete' in b)
assert s==502 and 'The sign-in provider could not complete' in b, 'Provider transport regression'
