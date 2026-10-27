import {Agent} from '@earendil-works/pi-agent-core';
import {stream as streamResponses} from '@earendil-works/pi-ai/api/openai-responses';
import {LambdaMcp} from './mcp.mjs';
import systemPrompt from './hillclimb-prompt.mjs';
import {bundlePath} from './git-bundle.mjs';
const hash=async s=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s))),x=>x.toString(16).padStart(2,'0')).join('');
const blocked=reason=>Object.assign(Error('hillclimb-blocked'),{hillclimbReason:reason});
export async function runHillclimb(a,job,{pr,ci,headers}){
 if(!a.env.GIT_RELAY_KEY||a.env.HILLCLIMB_LAMBDA_READY!=='true')throw blocked('Lambda Git/network policies and credential relay have not been verified.');
 const proof=await a.read('inference-proof-v2');
 if(proof?.status!=='passed')throw blocked('Connect ChatGPT and verify the model from the admin page.');
 if(job.tools.some(t=>t.status==='intent'||t.status==='uncertain'))throw blocked('A previous JavaScript call has an uncertain outcome; reconcile it before resuming.');
 const credential=await a.modelCredential();
 const session='pi-'+await hash(job.key),dir='/work/repository';
 const transport=new LambdaMcp(a.fetcher,a.env.LAMBDA_CLIENT_SECRET,session);
 const deadline=a.now()+180000;let turns=0,completed=0;
 job.gitLeaseUntil=deadline;await a.save(job.key,job);await a.storage.put('hc-active',job.key);
 const run=async code=>{
  if(a.now()>deadline||job.tools.length>=120)throw blocked('Execution/tool budget exhausted.');
  const entry={id:crypto.randomUUID(),status:'intent',iteration:job.iterations};job.tools.push(entry);await a.save(job.key,job);
  let result;
  try{result=await transport.run(code);}catch{entry.status='uncertain';await a.save(job.key,job);throw blocked('Lambda response was lost; the call will not be replayed automatically.');}
  entry.status='completed';entry.isError=!!result.isError;await a.save(job.key,job);
  return result;
 };
 try{
  const moduleURL=a.env.PUBLIC_ORIGIN+bundlePath,remote=a.env.PUBLIC_ORIGIN+`/git/${job.repoId}/${job.number}`;
  const bootstrap=`const {git,http}=await import(${JSON.stringify(moduleURL)});const dir=${JSON.stringify(dir)};const url=${JSON.stringify(remote)};const ref=${JSON.stringify(job.branch)};
if(!await fs.exists(dir+'/.git')){await fs.mkdir(dir,{recursive:true});await git.clone({fs,http,dir,url,ref,singleBranch:true,depth:1});}
else{const dirty=(await git.statusMatrix({fs,dir})).some(r=>r[1]!==r[2]||r[2]!==r[3]);if(dirty)throw Error('Uncommitted work needs reconciliation');await git.fetch({fs,http,dir,url,ref,singleBranch:true,depth:1});await git.checkout({fs,dir,ref:await git.resolveRef({fs,dir,ref:'refs/remotes/origin/'+ref})});await git.branch({fs,dir,ref,checkout:true,force:true});}
if(await git.resolveRef({fs,dir,ref:'HEAD'})!==${JSON.stringify(pr.head.sha)})throw Error('PR head mismatch');console.log('CLONE_HEAD_VERIFIED');`;
  const clone=await run(bootstrap);
  if(clone.isError||!JSON.stringify(clone).includes('CLONE_HEAD_VERIFIED'))throw blocked('Clone/checkout could not verify the exact PR head.');
  const annotations=[];
  for(const c of ci.failures.slice(0,8))if(c.id){
   const rows=await a.json(`https://api.github.com/repos/${job.repo}/check-runs/${c.id}/annotations?per_page=50`,{headers});
   annotations.push({name:c.name,annotations:rows,output:c.output});
  }
  const model={id:proof.model,name:proof.model,api:'openai-responses',provider:'openai',baseUrl:'https://api.openai.com/v1',reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:32000,maxTokens:4096};
  const tool={name:'run_js',label:'JavaScript in Lambda',description:'Execute bounded JavaScript with durable fs. Use the approved git module and remote from trusted context. All filesystem calls are async. Console.log observed results. No shell or subprocess. Never print credentials.',parameters:{type:'object',properties:{code:{type:'string'}},required:['code'],additionalProperties:false},execute:async(id,args)=>{
   if(typeof args.code!=='string'||args.code.length>16000)throw Error('invalid-code');
   const result=await run(args.code);return {content:[{type:'text',text:JSON.stringify(result)}],details:{}};
  }};
  const agent=new Agent({initialState:{model,systemPrompt,tools:[tool]},toolExecution:'sequential',streamFn:async(m,c,o)=>{
   if(++turns>10||a.now()>deadline)throw Error('model-budget');
   return streamResponses(m,c,{...o,apiKey:credential.access,maxTokens:4096,maxRetries:0,signal:AbortSignal.timeout(45000),fetch:(u,opts)=>a.fetcher(u,{...opts,redirect:'manual'}),onPayload:p=>({...p,store:false,stream:true}),onProviderStreamEvent:e=>{if(e.type==='response.completed')completed++;}});
  }});
  await agent.prompt(JSON.stringify({trustedContext:{repository:job.repo,pr:job.number,head:job.head,headRef:job.branch,baseRef:job.baseBranch,workDir:dir,approvedGitBundleUrl:moduleURL,headCloneUrl:remote,session,author:{name:'Hillclimb',email:'hillclimb@users.noreply.github.com'},remainingIterations:10-job.iterations},task:'The exact head is cloned. Inspect the failing checks and source, make one focused repair, commit it with isomorphic-git and push normally to the assigned branch using the approved remote. No merges or test weakening. CI will run after you yield. Re-import git and http in each tool call. Tell the controller if blocked.',untrustedEvidence:{ci,annotations,humanGuidance:job.guidance}}));
  if(completed!==turns)throw blocked('Model inference did not complete.');
  const latest=await a.json(`https://api.github.com/repos/${job.repo}/pulls/${job.number}`,{headers});
  const push=await a.read('hc-push:'+job.key);
  if(!push||push.old!==job.head||push.next!==latest.head.sha||latest.head.sha===job.head)throw blocked('Agent did not produce a verified pushed repair; inspect its result before resuming.');
  job.previousHead=job.head;job.head=latest.head.sha;
  const last=agent.state.messages.filter(x=>x.role==='assistant').at(-1);
  job.lastResult=(last?.content||[]).filter(x=>x.type==='text').map(x=>x.text).join('\n').slice(0,8000);
 }finally{
  job.gitLeaseUntil=0;await a.save(job.key,job);await a.storage.delete('hc-active');
 }
}
