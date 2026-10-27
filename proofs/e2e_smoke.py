"""Lightweight HTTP orchestration; Pi inference and all JS execute remotely.
Set WEBHOOK_KEY_FILE and BROKER_KEY_FILE to owner-only files, never CLI values.
Writes sanitized evidence only. Requires the already-deployed authorized services.
"""
import json, os, time, uuid
from pathlib import Path
import urllib.request, urllib.error
ORIGIN='https://durable-pi-modal.rwendt1337.workers.dev'
BROKER='https://r33drichards--durable-pi-modal-broker-service.us-east.modal.run'
key=Path(os.environ['WEBHOOK_KEY_FILE']).read_text().strip()
broker_key=Path(os.environ['BROKER_KEY_FILE']).read_text().strip()

def request(path,body=None,auth=key,base=ORIGIN):
    headers={'User-Agent':'durable-pi-e2e/1','Content-Type':'application/json'}
    if auth:headers['Authorization']='Bearer '+auth
    r=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(r,timeout=170) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        error.read()
        return error.code,{}

def run(event,session,prompt):
    body={'id':event,'session':session,'prompt':prompt,'timestamp':int(time.time()*1000)}
    status,receipt=request('/webhook',body)
    assert status==202,(status,receipt)
    for attempt in range(60):
        status,result=request('/runs?id='+event)
        assert status==200,status
        if result['status'] not in ('queued','running'):break
        time.sleep(4)
    summary={'id':event,'session':session,'status':result['status'],'modelResponses':result.get('completedModelResponses'),
             'tools':result.get('tools'),'output':result.get('output'),'reason':result.get('reason')}
    print(json.dumps(summary),flush=True)
    evidence['runs'].append(summary)
    save()
    assert result['status']=='completed',summary
    assert result['tools'] and all(t['terminated'] and not t['isError'] for t in result['tools'])
    status,dup=request('/webhook',{**body,'timestamp':int(time.time()*1000)})
    assert status==200 and dup.get('duplicate') is True
    status,again=request('/runs?id='+event)
    assert again['tools']==result['tools'] and again['finishedAt']==result['finishedAt']
    evidence['duplicate_no_reexecution']=True
    return result

def save():
    Path(__file__).with_name('e2e-results.json').write_text(json.dumps(evidence,indent=2)+'\n')
nonce=uuid.uuid4().hex[:10]
evidence={'startedAt':int(time.time()),'runs':[],'urls':{'webhook':ORIGIN+'/webhook','admin':ORIGIN+'/admin','broker':BROKER+'/tool'}}
assert request('/webhook',{},auth='wrong')[0]==401
assert request('/runs?id=test',auth='wrong')[0]==401
assert request('/tool',{},auth='wrong',base=BROKER)[0]==401
evidence['unauthorized_rejected']=True
marker='pi-file-'+nonce
session_a='e2e-a-'+nonce;session_b='e2e-b-'+nonce
file='/data/workspace/proof.txt'
first=run('write-'+nonce,session_a,f'Use run_js once to write the exact text {marker} to {file}, then read it back and console.log it. Use await fs.writeFile and await fs.readFile(path, "utf8") for text. Report the observed text.')
assert marker in json.dumps(first['tools'])
second=run('read-'+nonce,session_a,f'Use run_js to read {file} and console.log its contents using await fs.readFile(path, "utf8") for text. Do not write anything. Report observed contents.')
assert marker in json.dumps(second['tools'])
assert set(t['sandbox'] for t in first['tools']).isdisjoint(t['sandbox'] for t in second['tools'])
evidence['recreated_sandbox_persistence']=True
third=run('isolation-'+nonce,session_b,f'Use run_js to check whether {file} exists with await fs.exists. console.log("ISOLATED=" + !(await fs.exists("{file}"))). Do not create the file. Report the observed result.')
assert 'ISOLATED=true' in json.dumps(third['tools'])
evidence['two_session_isolation']=True
evidence['sessions']=[session_a,session_b]
evidence['status']='passed'
save()
print('Integrated E2E passed; test volumes still need explicit cleanup.',flush=True)
