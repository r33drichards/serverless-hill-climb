"""Remote-only storage proof; ephemeral test volumes survive sandbox recreation."""
import json
import modal
IMAGE = 'docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083'

app = modal.App.lookup('durable-pi-modal-volume-proof', create_if_missing=True)
active = []
evidence = []
def start(volume, session):
    s = modal.Sandbox.create('--session-id', session, app=app,
        image=modal.Image.from_registry(IMAGE), env={'PORT': ''},
        volumes={'/data': volume}, cpu=0.25, memory=512, timeout=120)
    active.append(s)
    return s

def command(s, code):
    p = s.exec('/bin/sh', '-c', code, timeout=20)
    out = p.stdout.read()
    err = p.stderr.read()
    p.wait()
    assert p.returncode == 0, (p.returncode, err)
    return out.strip()

def stop(s):
    s.terminate()
    s.wait(raise_on_termination=False)
    assert s.poll() is not None
    active.remove(s)
    evidence.append({'sandbox': s.object_id, 'terminated': True})

try:
    with modal.Volume.ephemeral() as a, modal.Volume.ephemeral() as b:
        s = start(a, 'a')
        command(s, "printf session-a > /data/owner; sync")
        stop(s)
        s = start(a, 'a-recreated')
        assert command(s, 'cat /data/owner') == 'session-a'
        evidence.append({'recreation_persistence': True})
        stop(s)
        s = start(b, 'b')
        assert command(s, 'test ! -e /data/owner && echo isolated') == 'isolated'
        command(s, 'printf session-b > /data/owner; sync')
        stop(s)
        s = start(a, 'a-final')
        assert command(s, 'cat /data/owner') == 'session-a'
        evidence.append({'distinct_volume_isolation': True})
        stop(s)
finally:
    for s in list(active):
        stop(s)
print(json.dumps({'image': IMAGE, 'evidence': evidence,
 'scope': 'Volume files via sandbox exec, not engine filesystem policy or broker authentication',
 'test_volumes': 'ephemeral context closed'}, indent=2))
