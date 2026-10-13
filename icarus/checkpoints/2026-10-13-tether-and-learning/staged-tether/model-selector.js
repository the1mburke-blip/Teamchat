import { AsyncLocalStorage } from 'node:async_hooks';
import { subscribe, unsubscribe } from 'node:diagnostics_channel';
import { QuotaStore, classifyFailure, routeKey } from './quota-state.js';
export const QUOTA_PATH='/dsh-tether/model-quotas';
const blocked=message=>Object.assign(new Error(message),{code:'ICARUS_FAILOVER_BLOCKED'});

// Capture undici headers without replacing fetch, touching response bodies, or observing unrelated calls.
export function observeTransport(store) {
  const scope=new AsyncLocalStorage(), requests=new WeakMap();
  const create=({request})=>{const route=scope.getStore();if(route) requests.set(request,route);};
  const headers=({request,response})=>{const route=requests.get(request);if(route) {try{store.observe(route,{status:response.statusCode,headers:response.headers});}catch{ /* diagnostics subscribers must never throw into the transport */ }}};
  subscribe('undici:request:create',create);subscribe('undici:request:headers',headers);
  return {scope,dispose(){unsubscribe('undici:request:create',create);unsubscribe('undici:request:headers',headers);scope.disable();}};
}
export function scopedStream(transport,route,next,store) {
  return (async function*(){
    store.beginAttempt(route);
    const stream=await transport.scope.run(route,next);
    const iterator=stream[Symbol.asyncIterator]();let done=false;
    try {
      while(true) {
        const item=await transport.scope.run(route,()=>iterator.next());
        if(item.done) {done=true;return;}
        const chunk=item.value;
        if(chunk.type==='finish' && chunk.reason?.kind==='error') store.observe(route,{failure:chunk.reason.failure});
        yield chunk;
      }
    } catch(error) {store.observe(route,{failure:error.failure??error});throw error;}
    finally {if(!done && iterator.return) await transport.scope.run(route,()=>iterator.return());}
  })();
}
export class SafeRouter {
  constructor(store, config={}, llm) {
    this.store=store;this.llm=llm;this.states=new WeakMap();this.routes=config.routes??[];
    this.enabled=config.autoFallback===true;this.delay=config.localCooldownMs??60000;
    if(!Number.isFinite(this.delay)||this.delay<1000||this.delay>604800000) throw new Error('Invalid local cooldown.');
    const seen=new Set();
    for(const r of this.routes) {
      if(!r.provider||!r.model||r.approved!==true||r.costPolicy!=='verified-zero-cost'||r.compatibilityVerified!==true||seen.has(routeKey(r))) throw new Error('Fallback routes require unique IDs, approval, verified zero cost and compatibility.');
      seen.add(routeKey(r));
    }
  }
  state(payload) {
    if(!payload.agent || typeof payload.agent!=='object') throw blocked('Agent context unavailable.');
    let s=this.states.get(payload.agent);if(!s){s={tried:new Set()};this.states.set(payload.agent,s);}
    if(s.turn!==payload.turn) {s.turn=payload.turn;s.tried.clear();s.last=null;}
    return s;
  }
  async select(payload,seed) {
    const s=this.state(payload);payload.signal?.throwIfAborted();
    if(!this.enabled || !this.routes.some(r=>routeKey(r)===routeKey(seed))) {s.last=null;return seed;}
    const source=await this.llm.resolveModelInfo(seed.provider,seed.model,payload.signal);
    for(const r of [this.routes.find(r=>routeKey(r)===routeKey(seed)),...this.routes.filter(r=>routeKey(r)!==routeKey(seed))]) {
      if(s.tried.has(routeKey(r))||!this.store.ready(r)) continue;
      const changed=routeKey(r)!==routeKey(seed);
      if(changed) {
        let target;try{target=await this.llm.resolveModelInfo(r.provider,r.model,payload.signal);}catch(error){payload.signal?.throwIfAborted();continue;}
        if(!source.context?.contextWindow||!target.context?.contextWindow||target.context.contextWindow<source.context.contextWindow) continue;
        if(!source.inputModalities||!target.inputModalities||source.inputModalities.some(m=>!target.inputModalities.includes(m))) continue;
      }
      payload.signal?.throwIfAborted();s.last=r;
      if(!changed) return seed;
      // Session, task, messages, tools, approval policy and memory are owned by the harness.
      // Model-specific call tuning does not carry to another adapter.
      return {provider:r.provider,model:r.model};
    }
    throw blocked('No compatible approved zero-cost fallback remains; reset may be unknown.');
  }
  fail(payload) {
    if(payload.signal?.aborted)return null;
    const s=this.state(payload), route=s.last;if(!route||route.provider!==payload.provider)return null;
    const failure={...this.store.failureFor(route,payload.signal),...payload.failure};
    const reason=classifyFailure(failure);if(!this.enabled||!reason)return null;
    const observed=this.store.observe(route,{failure});
    s.tried.add(routeKey(route));this.store.block(route,observed.scope,this.delay);
    if(!this.routes.some(r=>!s.tried.has(routeKey(r))&&this.store.ready(r))) throw blocked('All approved zero-cost routes exhausted; retries stopped.');
    return {kind:'retry'};
  }
}
export function applyModelSelector(ctx,config,isTrustedRequest,refuse) {
  const store=new QuotaStore(), transport=observeTransport(store),router=new SafeRouter(store,config,ctx.llm);
  ctx.effect(()=>()=>transport.dispose());
  ctx.on('llm/stream',(options,next)=>scopedStream(transport,options,next,store),{prepend:true});
  ctx.on('agent/request',async(payload,next)=>router.select(payload,await next()),{prepend:true});
  ctx.on('agent/request-error',(payload,next)=>router.fail(payload)??next(),{prepend:true});
  const reply=(res,status,value)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store'});res.end(JSON.stringify(value));};
  ctx.effect(()=>ctx.webServer.register({kind:'exact',path:QUOTA_PATH,handler:async(req,res)=>{
    if(!isTrustedRequest(req))return refuse(res);
    if(req.method!=='GET')return reply(res,405,{error:'GET required'});
    const groups=[];
    for(const provider of ctx.llm.listProviders()) {
      try {const models=await ctx.llm.listModels(provider.id);groups.push({id:provider.id,models:models.map(m=>({id:m.id,name:m.name,...store.snapshot({provider:provider.id,model:m.id})}))});}
      catch {groups.push({id:provider.id,models:[],status:'catalog unavailable'});}
    }
    reply(res,200,{groups,observedAt:Date.now(),autoFallback:router.enabled,transport:'undici response headers; normalized provider errors; configured API readers'});
  }}));
  // Explicit read-only API refresh: no polling, inference, top-up, or arbitrary URLs.
  ctx.effect(()=>ctx.webServer.register({kind:'exact',path:QUOTA_PATH+'/refresh',handler:async(req,res)=>{
    if(!isTrustedRequest(req))return refuse(res);
    if(req.method!=='POST')return reply(res,405,{error:'POST required'});
    const reports=[];
    for(const reader of config.providerApis??[]) {
      if(reader.kind!=='openrouter-key'||!reader.provider||!reader.credentialRef) {reports.push({provider:reader.provider,status:'unsupported API configuration'});continue;}
      try {
        const key=(await ctx.get('credentials')?.resolve(reader.credentialRef))?.value;
        if(!key) {reports.push({provider:reader.provider,status:'credential unavailable'});continue;}
        const response=await fetch('https://openrouter.ai/api/v1/key',{headers:{authorization:`Bearer ${key}`},redirect:'error',signal:AbortSignal.timeout(10000)});
        if(!response.ok) {reports.push({provider:reader.provider,status:`API HTTP ${response.status}`});continue;}
        const text=await response.text();if(text.length>65536)throw new Error('Oversized API response');
        store.observeOpenRouterKey(reader.provider,JSON.parse(text).data??{});reports.push({provider:reader.provider,status:'observed'});
      }catch{reports.push({provider:reader.provider,status:'API unavailable'});}
    }
    reply(res,200,{reports});
  }}));
  return {store,router};
}
