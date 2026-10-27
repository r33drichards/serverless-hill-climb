import {SignJWT,importPKCS8} from 'jose';
import {pkcs8} from './github.mjs';
import {activeLabel,newJob,parseCommand,steer,startupComment,marker,ciState,consumeAttempt} from './hillclimb-state.mjs';
const API='https://api.github.com';
const permitted=p=>p.admin===true||p.push===true||['admin','maintain','write'].includes(p.permission);
export async function installationHeaders(a,job) {
 const app=await a.read('github-app');
 const key=await importPKCS8(pkcs8(app.privateKey),'RS256');
 const jwt=await new SignJWT({}).setProtectedHeader({alg:'RS256'}).setIssuer(String(app.id)).setIssuedAt(Math.floor(a.now()/1000)-60).setExpirationTime(Math.floor(a.now()/1000)+300).sign(key);
 const headers={Authorization:'Bearer '+jwt,'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'};
 const inst=await a.json(`${API}/app/installations/${job.installation}`,{headers});
 if(String(inst.account?.id)!==a.env.GITHUB_OWNER_ID||String(inst.app_id)!==String(app.id))throw Error('installation-scope');
 const grant=await a.json(`${API}/app/installations/${job.installation}/access_tokens`,{method:'POST',headers,body:JSON.stringify({repository_ids:[job.repoId],permissions:{contents:'write',pull_requests:'write',actions:'read',checks:'read'}})});
 if(!grant.token)throw Error('installation-token');
 return {Authorization:'Bearer '+grant.token,'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'};
}
export async function list(a,url,headers,field) {
 const result=[];
 for(let page=1;page<=10;page++){
  const value=await a.json(`${url}${url.includes('?')?'&':'?'}per_page=100&page=${page}`,{headers});
  const rows=field?value[field]:value;if(!Array.isArray(rows))throw Error('github-list-response');
  result.push(...rows);if(rows.length<100)return result;
 }
 throw Error('github-pagination-limit');
}
async function enqueue(a,job){
 const q=await a.storage.get('hc-queue')||[];
 if(!q.includes(job.key)){if(q.length>=50)throw Error('queue-capacity');q.push(job.key);}
 await a.storage.setAlarm(a.now()+1000);
 await a.save(job.key,job);await a.storage.put('hc-queue',q);
 await a.save('gh-last',{...job,status:job.phase});
}
// Called only after github.mjs has authenticated the raw webhook signature.
export async function hillclimbEvent(a,p,event,delivery){
 const issue=event==='issue_comment'?p.issue:p.pull_request;
 if(event==='issue_comment'&&(!issue?.pull_request||p.action!=='created'||p.comment?.user?.type==='Bot'))return {status:'ignored'};
 if(event!=='issue_comment'&&event!=='pull_request')return {status:'ignored'};
 const command=event==='issue_comment'?parseCommand(p.comment?.body):null;
 if(event==='issue_comment'&&!command)return {status:'ignored'};
 const start=event==='pull_request'&&p.action==='labeled'&&activeLabel([p.label]);
 if(!start&&!command&&!['synchronize','closed','unlabeled'].includes(p.action))return {status:'ignored'};
 const repo=p.repository,number=issue?.number||p.number,installation=p.installation?.id;
 if(String(repo?.owner?.id)!==a.env.GITHUB_OWNER_ID)throw Error('repository-owner');
 if(!Number.isSafeInteger(repo?.id)||!Number.isSafeInteger(number)||number<1||!Number.isSafeInteger(installation)||!/^[-\w.]+\/[-\w.]+$/.test(repo.full_name||''))throw Error('invalid-event');
 if(!/^[\w-]{1,100}$/.test(delivery||''))throw Error('delivery');
 const key=`hc:${repo.id}:${number}`;let job=await a.read(key);
 if(!job&&!start)return {status:'ignored'};
 job ||= newJob({repo:repo.full_name,repoId:repo.id,number,installation,now:a.now()});
 if(job.installation!==installation||job.repo!==repo.full_name)throw Error('job-scope');
 if(job.deliveries.includes(delivery))return {status:job.phase,duplicate:true};
 const headers=await installationHeaders(a,job);
 if(start||command){
  const actor=command?p.comment.user:p.sender;
  if(!actor?.login||actor.type==='Bot')return {status:'ignored'};
  const permissions=await a.json(`${API}/repos/${job.repo}/collaborators/${encodeURIComponent(actor.login)}/permission`,{headers});
  if(!permitted(permissions))return {status:'ignored',reason:'actor-permission'};
 }
 const pr=await a.json(`${API}/repos/${job.repo}/pulls/${number}`,{headers});
 if(pr.base?.repo?.id!==job.repoId)throw Error('base-repository');
 if(pr.state!=='open'||!activeLabel(pr.labels)){job.paused=true;job.phase='paused';job.reason='PR closed or activation label removed';}
 else if(command){
  if(!Number.isSafeInteger(p.comment.id))throw Error('comment-id');
  steer(job,command,p.comment.id);
  if(command.command==='status'){await report(a,job,headers);return {status:job.phase};}
 }else if(p.action==='synchronize'&&!job.paused)job.phase='assessment';
 job.deliveries.push(delivery);job.deliveries=job.deliveries.slice(-200);
 await enqueue(a,job);return {status:job.phase};
}
async function report(a,job,headers){
 const body=startupComment(job)+`\n\n### Current status: ${job.phase}\n${job.summary||job.reason||'Assessing the current PR head.'}\n\nFix attempts: ${job.iterations}/10.`;
 if(!job.commentId){
  // Reconcile a potentially lost create response before considering another POST.
  const comments=await list(a,`${API}/repos/${job.repo}/issues/${job.number}/comments`,headers);
  const app=await a.read('github-app');
  const previous=comments.find(c=>c.user?.type==='Bot'&&c.user?.login===app.slug+'[bot]'&&c.body?.includes(marker(job)));
  if(previous)job.commentId=previous.id;
  else if(job.commentIntent){job.phase='blocked';job.reason='Startup comment outcome uncertain; inspect before retry';await a.save(job.key,job);return;}
  else {
   job.commentIntent=true;await a.save(job.key,job);
   const c=await a.json(`${API}/repos/${job.repo}/issues/${job.number}/comments`,{method:'POST',headers,body:JSON.stringify({body})});
   if(!c.id)throw Error('comment-response');job.commentId=c.id;
  }
 }else await a.json(`${API}/repos/${job.repo}/issues/comments/${job.commentId}`,{method:'PATCH',headers,body:JSON.stringify({body})});
 job.reportRequested=false;await a.save(job.key,job);
}
export async function hillclimbAlarm(a){
 const q=await a.storage.get('hc-queue')||[];if(!q.length)return false;
 const key=q.shift(),job=await a.read(key);
 await a.storage.setAlarm(a.now()+60000);
 if(!job){await a.storage.put('hc-queue',q);return true;}
 try {
  const headers=await installationHeaders(a,job);
  const pr=await a.json(`${API}/repos/${job.repo}/pulls/${job.number}`,{headers});
  if(pr.state!=='open'||!activeLabel(pr.labels)){job.paused=true;job.phase='paused';job.reason='PR closed or activation label removed';}
  if(job.phase==='executing') {job.phase='blocked';job.reason='Interrupted tool execution: inspect persisted intent before resuming';}
  if(!job.commentId||job.reportRequested||job.paused)await report(a,job,headers);
  if(!job.paused&&!['blocked','budget_exhausted'].includes(job.phase)){
   if(pr.head?.repo?.id!==job.repoId)throw Error('fork-head-not-authorized');
   const head=pr.head.sha;if(!/^[a-f0-9]{40}$/.test(head))throw Error('invalid-head');
   const checks=await list(a,`${API}/repos/${job.repo}/commits/${head}/check-runs`,headers,'check_runs');
   const statuses=await list(a,`${API}/repos/${job.repo}/commits/${head}/statuses`,headers);
   const ci=ciState(checks,statuses);job.ciPolls=(job.ciPolls||0)+1;
   if(job.ciPolls>120)throw Object.assign(Error('ci-wait-budget'),{hillclimbReason:'CI observation limit reached; inspect checks and resume when ready.'});
   job.head=head;job.branch=pr.head.ref;job.baseBranch=pr.base.ref;
   if(ci.phase==='failing'){
    const fingerprint=ci.failures.map(c=>c.name||c.context).sort().join('|');
    if(consumeAttempt(job,fingerprint)){
     // Intent survives crash; unknown mutations are never automatically replayed.
     job.phase='executing';await a.save(key,job);
     await a.hillclimbStep(job,{pr,ci,headers});
     job.ciPolls=0;job.phase='waiting_ci';
    }
   }else job.phase=ci.phase;
   job.summary=`Observed [${head.slice(0,12)}](${pr.html_url}/commits/${head}): ${ci.failures.length} failing, ${ci.pending.length} pending checks.`;
   await report(a,job,headers);
  }
 }catch(e){job.phase='blocked';job.reason=typeof e.hillclimbReason==='string'?e.hillclimbReason:'Capability or execution failed; inspect owner-only diagnostics before resuming';}
 await a.save(key,job);await a.save('gh-last',{...job,status:job.phase});
 if(['assessment','waiting_ci'].includes(job.phase)&&!job.paused)q.push(key);
 await a.storage.put('hc-queue',q);
 if(q.length)await a.storage.setAlarm(a.now()+60000);
 else if(!await a.storage.get('active-run')&&!(await a.storage.get('gh-queue'))?.length)await a.storage.deleteAlarm();
 return true;
}
