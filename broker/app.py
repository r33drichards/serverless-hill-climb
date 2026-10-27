"""Authenticated lifecycle API; mcp-js serves MCP directly through Modal Connect.

Not a tool relay: no JavaScript, MCP messages, tool results, or model credentials
are accepted here. Deploy separately from the historical durable-pi broker.
"""
import asyncio
import hashlib
import hmac
import json
import os
import modal
from broker.lifecycle import Controller, Rejected, LIFETIME

APP_NAME = 'serverless-hill-climb-lifecycle'
app = modal.App(APP_NAME)
IMAGE = 'docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083'
# Same pinned image plus /etc/durablepi/fs.rego; no HTTP sidecar/proxy added.
engine = modal.Image.from_id('im-wpacPP0MhtAXUsZExQRJrQ')
web = (modal.Image.debian_slim(python_version='3.12')
       .pip_install('fastapi==0.135.1').add_local_python_source('broker'))
ledger = modal.Dict.from_name(APP_NAME + '-leases', create_if_missing=True)


class Backend:
    image = IMAGE

    def __init__(self, application=app, prefix='hill-climb-session-', sandbox_name='single-engine'):
        self.app, self.prefix, self.name = application, prefix, sandbox_name

    def create(self, session):
        volume = modal.Volume.from_name(self.volume_name(session), create_if_missing=True)
        return modal.Sandbox.create(
            '--session-id', session, '--policies-json', json.dumps({
                'filesystem': {'policies': [{'url': 'file:///etc/durablepi/fs.rego'}]}}),
            app=self.app, name=self.name, image=engine, env={'PORT': '8080'},
            volumes={'/data': volume}, cpu=0.25, memory=512, timeout=LIFETIME,
            readiness_probe=modal.Probe.with_tcp(8080))
        # Deliberately NO encrypted_ports/unencrypted_ports/h2_ports. Only
        # Modal's authenticated Connect endpoint can reach the native server.

    def volume_name(self, session):
        return self.prefix + hashlib.sha256(('57335981:' + session).encode()).hexdigest()[:24]

    def ready(self, sandbox):
        p = sandbox.exec('mkdir', '-p', '/data/workspace', timeout=10)
        if p.wait() != 0:
            raise RuntimeError('workspace-init-failed')
        sandbox.wait_until_ready()

    def get(self, identity):
        try:
            return modal.Sandbox.from_id(identity)
        except modal.exception.NotFoundError:
            return None

    def find(self):
        try:
            return modal.Sandbox.from_name(self.app.name, self.name)
        except modal.exception.NotFoundError:
            return None

    def connect(self, sandbox):
        return sandbox.create_connect_token(port=8080)

    def terminate(self, sandbox):
        if sandbox.poll() is None:
            try:
                p = sandbox.exec('sync', timeout=10)
                p.wait()
            finally:
                sandbox.terminate()
        sandbox.wait(raise_on_termination=False)


@app.function(image=web, secrets=[modal.Secret.from_name('serverless-hill-climb-lifecycle-auth')],
              cpu=0.25, memory=256, timeout=90, max_containers=1,
              min_containers=0, scaledown_window=2)
@modal.asgi_app()
def service():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    lock = asyncio.Lock()
    controller = Controller(ledger, Backend())

    @api.post('/leases/{operation}')
    async def lifecycle(operation: str, request: Request):
        headers = {'Cache-Control': 'no-store'}
        key = os.environ.get('BROKER_KEY', '')
        if not key or not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + key):
            return JSONResponse({'error': 'unauthorized'}, status_code=401, headers=headers)
        if operation not in ('acquire', 'release'):
            return JSONResponse({'error': 'not-found'}, status_code=404, headers=headers)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 1024:
                return JSONResponse({'error': 'too-large'}, status_code=413, headers=headers)
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            return JSONResponse({'error': 'invalid-json'}, status_code=400, headers=headers)
        fields = {'session', 'lease'} if operation == 'acquire' else {'lease'}
        if not isinstance(body, dict) or set(body) != fields:
            return JSONResponse({'error': 'invalid-fields'}, status_code=400, headers=headers)
        async with lock:
            try:
                result = await asyncio.to_thread(getattr(controller, operation), body)
                return JSONResponse(result, headers=headers)
            except Rejected as error:
                return JSONResponse({'error': error.reason}, status_code=error.status, headers=headers)
            except Exception:
                # Never print request/response bodies or Connect credentials.
                return JSONResponse({'error': 'lifecycle-failed-no-replay'}, status_code=502, headers=headers)
    return api
