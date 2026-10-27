"""Bounded remote Node build/tests. No credentials enter the sandbox."""
from pathlib import Path
import modal

root = Path(__file__).resolve().parents[1] / 'admin'
app = modal.App.lookup('serverless-hill-climb-build', create_if_missing=True)
sandbox = None
try:
    sandbox = modal.Sandbox.create('sleep', '900', app=app,
        image=modal.Image.from_registry('node:24-bookworm-slim'),
        cpu=0.5, memory=1024, timeout=900)
    print('Sandbox:', sandbox.object_id, flush=True)
    p = sandbox.exec('mkdir', '-p', '/work/src', '/work/test')
    p.wait()
    for rel in ['package.json', 'wrangler.jsonc'] + [str(p.relative_to(root)) for d in ['src','test'] for p in (root/d).glob('*.mjs')]:
        sandbox.filesystem.write_text((root / rel).read_text(), '/work/' + rel)
    if (root / 'package-lock.json').exists():
        sandbox.filesystem.write_text((root / 'package-lock.json').read_text(), '/work/package-lock.json')
    command = 'cd /work && npm ci --no-audit --no-fund && npm test && npm run build && WRANGLER_SEND_METRICS=false npm run check:worker'
    p = sandbox.exec('sh', '-c', command, timeout=650)
    for line in p.stdout:
        print(line, end='', flush=True)
    stderr = p.stderr.read()
    print(stderr[-6000:], flush=True)
    code = p.wait()
    if code != 0:
        raise RuntimeError(f'Remote checks failed: {code}')
    for rel in ['package-lock.json', 'dist/worker.mjs']:
        data = sandbox.filesystem.read_text('/work/' + rel)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)
    print('Remote tests, bundle, and Wrangler dry-run passed.', flush=True)
finally:
    if sandbox:
        sandbox.terminate()
        sandbox.wait(raise_on_termination=False)
        print('Sandbox terminated.', flush=True)
    print('Active:', [s.object_id for s in modal.Sandbox.list(app_id=app.app_id)], flush=True)
