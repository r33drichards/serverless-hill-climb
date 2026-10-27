// Direct MCP client. Lifecycle service sees only session/lease IDs, never code.
// No automatic retries: a lost tool response may represent a completed side effect.
export class NativeMcp {
  constructor(fetcher, lease) {
    const u=new URL(lease.url);
    if(u.protocol!=='https:' || u.username || u.password || u.search || u.hash || !u.hostname.endsWith('.modal.host')) throw Error('invalid-connect-url');
    if(typeof lease.token!=='string'||!lease.token||typeof lease.sandbox!=='string')throw Error('invalid-lease');
    this.fetcher=fetcher;this.lease=lease;this.sequence=0;
  }
  async rpc(method,params,notify=false) {
    const id=notify?undefined:++this.sequence;
    const headers={Authorization:'Bearer '+this.lease.token,'Content-Type':'application/json',Accept:'application/json, text/event-stream','MCP-Protocol-Version':this.protocol || '2024-11-05'};
    if(this.session)headers['Mcp-Session-Id']=this.session;
    const r=await this.fetcher(this.lease.url,{method:'POST',redirect:'manual',headers,body:JSON.stringify({jsonrpc:'2.0',...(notify?{}:{id}),method,...(params?{params}:{})}),signal:AbortSignal.timeout(45000)});
    if(!r.ok){await r.body?.cancel();throw Error('mcp-http-failed-no-replay');}
    const session=r.headers.get('Mcp-Session-Id');if(session)this.session=session;
    if(notify){await r.body?.cancel();return;}
    const reader=r.body?.getReader();if(!reader)throw Error('mcp-empty');
    const decoder=new TextDecoder();let total=0,buffer='';
    const sse=(r.headers.get('Content-Type')||'').includes('text/event-stream');
    const result=msg=>{if(msg?.jsonrpc!=='2.0'||msg.id!==id)return; if(msg.error)throw Error('mcp-protocol-error');if(!('result' in msg))throw Error('mcp-invalid-result');return {value:msg.result};};
    try {
      for(;;){
        const {value,done}=await reader.read();
        if(value){total+=value.length;if(total>65536)throw Error('mcp-output-limit');buffer+=decoder.decode(value,{stream:true});}
        if(sse){
          // Normalize split CRLF safely only after complete events have arrived.
          let match;
          while((match=/\r?\n\r?\n/.exec(buffer))){
            const event=buffer.slice(0,match.index);buffer=buffer.slice(match.index+match[0].length);
            const data=event.split(/\r?\n/).filter(x=>x.startsWith('data:')).map(x=>x.slice(5).replace(/^ /,'')).join('\n');
            if(!data.trim())continue;
            const found=result(JSON.parse(data));if(found)return found.value;
          }
        }
        if(done){if(!sse){const found=result(JSON.parse(buffer));if(found)return found.value;}throw Error('mcp-missing-result');}
      }
    } finally {await reader.cancel().catch(()=>{});}
  }
  async initialize(){
    const info=await this.rpc('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'serverless-hill-climb',version:'1'}});
    if(info.protocolVersion!=='2024-11-05')throw Error('unsupported-mcp-version');
    this.protocol=info.protocolVersion;
    await this.rpc('notifications/initialized',undefined,true);
  }
  async run(code){
    const result=await this.rpc('tools/call',{name:'run_js',arguments:{code}});
    if(!Array.isArray(result?.content))throw Error('invalid-mcp-tool-result');
    return result;
  }
}
