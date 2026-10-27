"""Bounded real-image MCP stdio probe; run with the authenticated Modal SDK."""
import json
import modal
IMAGE = 'docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083'
app = modal.App.lookup('durable-pi-modal-proof', create_if_missing=True)
s = None
try:
    s = modal.Sandbox.create('--session-id', 'probe', app=app,
        image=modal.Image.from_registry(IMAGE), env={'PORT': ''},
        cpu=0.25, memory=512, timeout=60)
    print('sandbox', s.object_id, flush=True)
    requests = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'modal-proof','version':'1'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'run_js','arguments':{'code':'console.log(6 * 7)'}}},
    ]
    for request in requests:
        s.stdin.write(json.dumps(request)+'\n')
        s.stdin.drain()
    for line in s.stdout:
        print(line, end='', flush=True)
        try:
            if json.loads(line).get('id') == 2:
                break
        except ValueError:
            pass
finally:
    if s:
        s.terminate()
        print('terminated', s.poll(), flush=True)
