# Run remotely with crane v0.20.3 and ECR registry authentication. No AWS keys needed.
import subprocess,json,tarfile,io,csv
base='docker.io/wholelottahoopla/mcp-js@sha256:2f2752f606a5ded1a2044aa6ddc3691a7833fe4ea9517351c806d6136b606083'
adapter='public.ecr.aws/awsguru/aws-lambda-adapter@sha256:9d6b29a45b14a4a70f88d53c68b6d5bab1b22d75baca733958fee59308c509b8'
digest=subprocess.check_output(['crane','digest','--platform','linux/amd64',adapter],text=True).strip()
subprocess.run(['crane','export','--platform','linux/amd64',adapter,'/tmp/adapter.tar'],check=True)
with tarfile.open('/tmp/adapter.tar') as src,tarfile.open('/tmp/layer.tar','w') as dst:
 for name in ['opt','opt/extensions','opt/lambda-test']:
  di=tarfile.TarInfo(name);di.type=tarfile.DIRTYPE;di.mode=0o755;dst.addfile(di)
 data=src.extractfile('lambda-adapter').read();i=tarfile.TarInfo('opt/extensions/lambda-adapter');i.size=len(data);i.mode=0o755;dst.addfile(i,io.BytesIO(data))
 dst.add('/tmp/fs.rego',arcname='opt/lambda-test/fs.rego')
cmd=['--session-id','lambda-test','--policies-json',json.dumps({'filesystem':{'policies':[{'url':'file:///opt/lambda-test/fs.rego'}]}},separators=(',',':'))]
s=io.StringIO();csv.writer(s,lineterminator='').writerow(cmd)
args=['crane','mutate',base,'--platform','linux/amd64','--append','/tmp/layer.tar','--cmd',s.getvalue(),'--workdir','/tmp','--tag','390825964154.dkr.ecr.us-east-1.amazonaws.com/mcp-js-lambda-test-20261027:native-v2']
for e in ['PORT=8080','AWS_LWA_PORT=8080','AWS_LWA_READINESS_CHECK_PATH=/api-doc/openapi.json','AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200','AWS_LWA_READINESS_CHECK_TIMEOUT_SECONDS=8','AWS_LWA_INVOKE_MODE=buffered','HOME=/tmp']:args+=['--env',e]
subprocess.run(args,check=True)
out=subprocess.check_output(['crane','digest',args[args.index('--tag')+1]],text=True).strip()
print(json.dumps({'adapterDigest':digest,'imageDigest':out}))
