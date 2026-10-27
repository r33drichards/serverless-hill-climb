"""Real native MCP HTTP proof. API orchestration only on Gateway.

Uses isolated Modal apps/ephemeral ledger, remote Node client, bounded sandboxes,
unique test volumes, no production deployment, no model calls. Never prints tokens.
"""
import hashlib
import json
from pathlib import Path
import sys
import uuid
import urllib.parse
import modal
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from broker.app import Backend, IMAGE
from broker.lifecycle import Controller

app=modal.App.lookup('hill-climb-direct-http-proof',create_if_missing=True)
client_app=modal.App.lookup('hill-climb-direct-client-proof',create_if_missing=True)
prefix='hcl-http-proof-'+uuid.uuid4().hex[:8]+'-'
backend=Backend(app,prefix=prefix)
client=None
sessions=['session-a','session-b'];result={'image':IMAGE,'checks':[],'sandboxes':[]}

def identity(n):return hashlib.sha256((prefix+str(n)).encode()).hexdigest()

# Client program is executed remotely, not on the compute-constrained Gateway.
program='''import {readFileSync} from 'node:fs';
import {NativeMcp} from './mcp.mjs';
const input=JSON.parse(readFileSync('/work/input.json','utf8'));
let calls=0;
const c=new NativeMcp((...args)=>{calls++;return fetch(...args);},input.lease);
const denied=await fetch(input.lease.url,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
if(denied.status!==401 && denied.status!==403)throw Error('unauthorized-not-denied');
await denied.body?.cancel();
await c.initialize();
const outputs=[];
for(const code of input.codes){const r=await c.run(code);if(r.isError)throw Error('engine-tool-error');outputs.push(r);}
console.log(JSON.stringify({unauthorized:denied.status,outputs,calls}));
'''
try:
    client=modal.Sandbox.create('sleep','600',app=client_app,image=modal.Image.from_registry('node:24-bookworm-slim'),cpu=.25,memory=256,timeout=600)
    client.exec('mkdir','-p','/work').wait()
    client.filesystem.write_text((root/'admin/src/mcp.mjs').read_text(),'/work/mcp.mjs')
    client.filesystem.write_text(program,'/work/probe.mjs')
    with modal.Dict.ephemeral() as ledger:
        controller=Controller(ledger,backend)
        for n,(session,codes,expected) in enumerate([
            ('session-a',["console.log(6*7)","await fs.writeFile('/data/workspace/proof.txt','native-http-persisted');console.log(await fs.readFile('/data/workspace/proof.txt','utf8'))"],['42','native-http-persisted']),
            ('session-a',["console.log(await fs.readFile('/data/workspace/proof.txt','utf8'))"],['native-http-persisted']),
            ('session-b',["console.log(await fs.exists('/data/workspace/proof.txt'))"],['false']),
        ]):
            lease_id=identity(n)
            try:
                lease=controller.acquire({'session':session,'lease':lease_id})
                # Never persist or print the credential in proof artifacts.
                print('connect hostname suffix', '.'.join(urllib.parse.urlparse(lease['url']).hostname.split('.')[-2:]),flush=True)
                again=controller.acquire({'session':session,'lease':lease_id})
                assert again['sandbox']==lease['sandbox']
                client.filesystem.write_text(json.dumps({'lease':lease,'codes':codes}),'/work/input.json')
                p=client.exec('node','/work/probe.mjs',timeout=100)
                stdout=p.stdout.read();error=p.stderr.read();exit_code=p.wait()
                if exit_code:
                    # Node stacks include filenames but never echo input/token.
                    print(error[-1500:],flush=True);raise RuntimeError('remote-client-failed')
                observed=json.loads(stdout)
                print('tool outputs',json.dumps(observed['outputs']),flush=True)
                assert len(observed['outputs'])==len(expected)
                for r,want in zip(observed['outputs'],expected):
                    text='\n'.join(c.get('text','') for c in r['content']);assert want in text
                result['checks'].append({'session':session,'unauthorized':observed['unauthorized'],'expected':expected,'calls':observed['calls'],'sameLeaseReused':True})
                result['sandboxes'].append(lease['sandbox'])
                print('passed',session,expected,flush=True)
            finally:
                released=controller.release({'lease':lease_id})
                assert released['terminated']
                client.exec('rm','-f','/work/input.json').wait()
        assert len(set(result['sandboxes']))==3
finally:
    for sandbox in modal.Sandbox.list(app_id=app.app_id):
        sandbox.terminate();sandbox.wait(raise_on_termination=False)
    if client:client.terminate();client.wait(raise_on_termination=False)
    for session in sessions:
        try:modal.Volume.objects.delete(backend.volume_name(session))
        except modal.exception.NotFoundError:pass
    for session in sessions:
        try:
            modal.Volume.from_name(backend.volume_name(session)).hydrate()
        except modal.exception.NotFoundError:
            continue
        raise RuntimeError('test-volume-deletion-unverified')
    result['testVolumesDeleted']=True
    result['activeEngineSandboxes']=[s.object_id for s in modal.Sandbox.list(app_id=app.app_id)]
    result['activeClientSandboxes']=[s.object_id for s in modal.Sandbox.list(app_id=client_app.app_id)]
    assert not result['activeEngineSandboxes'] and not result['activeClientSandboxes']
    print('cleanup verified',flush=True)
result['status']='passed'
(root/'proofs/direct-mcp-results.json').write_text(json.dumps(result,indent=2)+'\n')
