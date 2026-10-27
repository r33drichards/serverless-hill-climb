// Durable controller state: no credentials or model-generated authority.
export const COMMANDS = ['status', 'pause', 'stop', 'resume'];
export const activeLabel = labels => labels?.some(x => ['hill climb', 'hillclimb'].includes(x.name));
export const marker = job => `<!-- hillclimb:${job.repoId}:${job.number}:v1 -->`;
export function startupComment(job) {
  return `## Hillclimb started\n\nI’ll inspect CI for this PR, push focused fixes, and update this comment as checks run. I won’t merge the PR.\n\n### How to use Hillclimb\nPost a new comment on this PR (no mention needed):\n\n- \`/hillclimb status\` — get the current status.\n- \`/hillclimb pause\` or \`/hillclimb stop\` — stop new changes.\n- \`/hillclimb resume\` — continue this job.\n- \`/hillclimb Please preserve the public API\` — give repair guidance.\n\nCommands require repository write access. I’ll explain any blockers or exhausted repair budget.\n\n${marker(job)}`;
}
export function parseCommand(body) {
  if (typeof body !== 'string' || body.length > 4000) return null;
  const m = /^\/hillclimb(?:\s+([^\n]+))?\s*$/.exec(body.trim());
  if (!m) return null;
  const text = (m[1] || 'status').trim();
  return {command:COMMANDS.includes(text) ? text : 'guidance', text};
}
export function newJob({repo,repoId,number,installation,now}) {
  return {key:`hc:${repoId}:${number}`,repo,repoId,number,installation,phase:'assessment',createdAt:now,
    iterations:0,failures:{},guidance:[],deliveries:[],comments:[],tools:[],head:null,paused:false};
}
export function steer(job, command, commentId) {
  if (job.comments.includes(commentId)) return false;
  if (job.comments.length >= 200) throw Error('comment-retention-limit');
  job.comments.push(commentId);
  if (['pause','stop'].includes(command.command)) {job.paused=true;job.phase='paused';}
  if (command.command === 'resume') {job.paused=false;job.phase='assessment';}
  if (command.command === 'guidance') {
    if(job.guidance.length>=30)throw Error('guidance-limit');
    job.guidance.push({commentId,text:command.text});
  }
  job.reportRequested=true;
  return true;
}
export function consumeAttempt(job, fingerprint) {
  if (job.iterations>=10 || (job.failures[fingerprint] || 0)>=3) {
    job.phase='budget_exhausted';return false;
  }
  job.iterations++;job.failures[fingerprint]=(job.failures[fingerprint] || 0)+1;
  return true;
}
export function ciState(checks,statuses) {
  const failures=[],pending=[];
  for(const c of checks){
    if(c.status!=='completed')pending.push(c);
    else if(!['success','neutral','skipped'].includes(c.conclusion))failures.push(c);
  }
  // Status API can return history. Most recent status per context wins.
  const latest=new Map();
  for(const s of statuses)if(!latest.has(s.context))latest.set(s.context,s);
  for(const s of latest.values()){
    if(s.state==='pending')pending.push(s);
    else if(s.state!=='success')failures.push(s);
  }
  return {phase:failures.length?'failing':pending.length||!checks.length&&!latest.size?'waiting_ci':'green',failures,pending};
}
