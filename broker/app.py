"""Single-writer, bounded MCP broker. No model credentials enter this service."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
import modal

app = modal.App('durable-pi-modal-broker')
IMAGE = 'docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083'
# Built from the pinned registry image plus only fs.rego; see engine-image.txt.
engine = modal.Image.from_id('im-wpacPP0MhtAXUsZExQRJrQ')
web = modal.Image.debian_slim(python_version='3.12').pip_install('fastapi==0.135.1')
ledger = modal.Dict.from_name('durable-pi-modal-tool-ledger', create_if_missing=True)

@app.function(image=web, secrets=[modal.Secret.from_name('durable-pi-modal-broker-auth')],
              cpu=0.25, memory=256, timeout=180, max_containers=1, min_containers=0, scaledown_window=2)
@modal.asgi_app()
def service():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import asyncio
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    lock = asyncio.Lock()

    def execute(body):
        session, call, code = body.get('session'), body.get('call'), body.get('code')
        if not isinstance(session,str) or not re.fullmatch(r'[a-z0-9-]{1,64}',session):
            return {'error':'invalid-session'},400
        if not isinstance(call,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',call):
            return {'error':'invalid-call'},400
        if not isinstance(code,str) or len(code)>8192:
            return {'error':'invalid-code'},400
        digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        key=session+':'+call
        previous=ledger.get(key,None)
        if previous:
            if previous['digest']!=digest:return {'error':'idempotency-conflict'},409
            if previous.get('result'):return previous['result'],200
            return {'error':'uncertain-prior-call-no-replay'},409
        # Refuse overlapping writers even across container restarts/unknown allocation.
        lease=ledger.get('lease',None)
        if lease and lease['until']>time.time():
            return {'error':'prior-lease-active-or-uncertain'},409
        ledger['lease']={'until':time.time()+150,'call':key}
        ledger[key]={'digest':digest,'status':'reserved'}
        sandbox=None
        stage='volume'
        try:
            volume=modal.Volume.from_name('durable-pi-session-'+hashlib.sha256(('57335981:'+session).encode()).hexdigest()[:24],create_if_missing=True)
            stage='allocation'
            sandbox=modal.Sandbox.create('--session-id',session,'--policies-json',json.dumps({'filesystem':{'policies':[{'url':'file:///etc/durablepi/fs.rego'}]}}),app=app,image=engine,
                env={'PORT':''},volumes={'/data':volume},cpu=0.25,memory=512,timeout=120)
            ledger['lease']={'until':time.time()+130,'sandbox':sandbox.object_id,'call':key}
            stage='engine'
            p=sandbox.exec('mkdir','-p','/data/workspace',timeout=10);p.wait()
            requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'durable-pi','version':'1'}}},
              {'jsonrpc':'2.0','method':'notifications/initialized'},
              {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'run_js','arguments':{'code':code}}}]
            for request in requests:
                sandbox.stdin.write(json.dumps(request)+'\n');sandbox.stdin.drain()
            result=None
            for line in sandbox.stdout:
                if len(line)>32768:raise RuntimeError('output-limit')
                try:msg=json.loads(line)
                except ValueError:continue
                if msg.get('id')==2:
                    result=msg.get('result')
                    break
            if result is None:raise RuntimeError('missing-mcp-result')
            p=sandbox.exec('sync',timeout=10);p.wait()
            sid=sandbox.object_id
            sandbox.terminate();sandbox.wait(raise_on_termination=False)
            if sandbox.poll() is None:raise RuntimeError('termination-unverified')
            sandbox=None
            output={'result':result,'sandbox':sid,'terminated':True,'image':IMAGE}
            ledger[key]={'digest':digest,'status':'completed','result':output}
            ledger['lease']={'until':0}
            return output,200
        except Exception as error:
            # No engine code, response bodies, or credentials in error logs.
            return {'error':'engine-operation-failed-no-automatic-replay','stage':stage,'exception':type(error).__name__},502
        finally:
            if sandbox:
                sandbox.terminate();sandbox.wait(raise_on_termination=False)
                ledger['lease']={'until':0}

    @api.post('/tool')
    async def tool(request:Request):
        auth=request.headers.get('authorization','')
        if not hmac.compare_digest(auth,'Bearer '+os.environ['BROKER_KEY']):
            return JSONResponse({'error':'unauthorized'},status_code=401)
        raw=await request.body()
        if len(raw)>12000:return JSONResponse({'error':'too-large'},status_code=413)
        try:body=json.loads(raw)
        except ValueError:return JSONResponse({'error':'invalid-json'},status_code=400)
        if not isinstance(body,dict):return JSONResponse({'error':'invalid-json'},status_code=400)
        async with lock:
            output,status=await asyncio.to_thread(execute,body)
        return JSONResponse(output,status_code=status)
    return api
