"""Credential-free remote unit tests; no local install/test workload."""
from pathlib import Path
import modal
root=Path(__file__).resolve().parents[1]
app=modal.App.lookup('hill-climb-lifecycle-tests',create_if_missing=True)
s=None
try:
    s=modal.Sandbox.create('sleep','180',app=app,image=modal.Image.debian_slim(python_version='3.12').pip_install('modal==1.6.2','fastapi==0.135.1'),cpu=.25,memory=256,timeout=180)
    s.exec('mkdir','-p','/work/broker/tests').wait()
    for rel in ['broker/__init__.py','broker/lifecycle.py','broker/tests/test_lifecycle.py','broker/app.py','broker/tests/test_api.py']:
        s.filesystem.write_text((root/rel).read_text(),'/work/'+rel)
    p=s.exec('sh','-c','cd /work && python -m unittest discover -s broker/tests -v',timeout=60)
    print(p.stdout.read());print(p.stderr.read());assert p.wait()==0
finally:
    if s:s.terminate();s.wait(raise_on_termination=False)
    print('Active:',[x.object_id for x in modal.Sandbox.list(app_id=app.app_id)])
