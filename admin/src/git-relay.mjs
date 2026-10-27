import {installationHeaders} from './hillclimb-controller.mjs';
const deny=(status=403)=>new Response('Git relay request rejected',{status});
export function validatePush(bytes,branch,expected){
 const dec=new TextDecoder();let offset=0,commands=0;
 while(offset+4<=bytes.length){
  const prefix=dec.decode(bytes.slice(offset,offset+4));if(!/^[a-f\d]{4}$/i.test(prefix))throw Error('packet');
  const length=parseInt(prefix,16);offset+=4;if(length===0)break;
  if(length<4||offset+length-4>bytes.length)throw Error('packet');
  const line=dec.decode(bytes.slice(offset,offset+length-4)).split('\0')[0].trim();offset+=length-4;
  const parts=line.split(' ');
  if(parts.length!==3||parts[0]!==expected||!/^[a-f0-9]{40}$/.test(parts[1])||/^0+$/.test(parts[1])||parts[2]!==`refs/heads/${branch}`)throw Error('push-scope');
  if(++commands>1)throw Error('multiple-refs');
 }
 if(commands!==1)throw Error('missing-command');
}
async function readBounded(body,max){
 const chunks=[];let size=0;const r=body?.getReader();if(!r)return new Uint8Array();
 try{for(;;){const {done,value}=await r.read();if(done)break;size+=value.length;if(size>max)throw Error('size');chunks.push(value);}}finally{await r.cancel().catch(()=>{});}
 const out=new Uint8Array(size);let i=0;for(const c of chunks){out.set(c,i);i+=c.length;}return out;
}
export async function gitRelay(a,r){
 if(!a.env.GIT_RELAY_KEY||r.headers.get('Authorization')!=='Bearer '+a.env.GIT_RELAY_KEY)return deny();
 const u=new URL(r.url),m=/^\/git\/(\d+)\/(\d+)\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(u.pathname);
 if(!m)return deny(404);
 const job=await a.read(`hc:${m[1]}:${m[2]}`),active=await a.storage.get('hc-active');
 if(!job||active!==job.key||job.paused||job.phase!=='executing'||!job.gitLeaseUntil||job.gitLeaseUntil<a.now())return deny();
 if(!/^[-\w.]+\/[-\w.]+$/.test(job.repo)||job.branch===job.baseBranch)return deny();
 const service=u.searchParams.get('service');
 if(m[3]==='info/refs'&&(r.method!=='GET'||!['git-upload-pack','git-receive-pack'].includes(service)))return deny();
 if(m[3]!=='info/refs'&&(r.method!=='POST'||u.search))return deny();
 const headers=await installationHeaders(a,job);
 const pr=await a.json(`https://api.github.com/repos/${job.repo}/pulls/${job.number}`,{headers});
 if(pr.state!=='open'||pr.head?.sha!==job.head||pr.head?.ref!==job.branch||pr.head?.repo?.id!==job.repoId||!pr.labels?.some(x=>['hill climb','hillclimb'].includes(x.name)))return deny(409);
 let body;
 if(r.method==='POST'){
  body=await readBounded(r.body,10*1024*1024);
  if(m[3]==='git-receive-pack')try{validatePush(body,job.branch,job.head);}catch{return deny();}
 }
 const token=headers.Authorization.slice(7);
 const response=await a.fetcher(`https://github.com/${job.repo}.git/${m[3]}${service?'?service='+service:''}`,{
  method:r.method,redirect:'manual',signal:AbortSignal.timeout(25000),
  headers:{Authorization:'Basic '+btoa('x-access-token:'+token),'User-Agent':'serverless-hill-climb',...(body?{'Content-Type':`application/x-${m[3]}-request`}:{})},body});
 if(!response.ok){await response.body?.cancel();return deny(502);}
 return new Response(await readBounded(response.body,15*1024*1024),{headers:{'Content-Type':response.headers.get('Content-Type')||'application/octet-stream','Cache-Control':'no-store'}});
}
