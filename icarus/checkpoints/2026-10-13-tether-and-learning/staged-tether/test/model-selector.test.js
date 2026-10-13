import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
import {mkdtemp,cp,appendFile,rm,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,dirname,basename} from 'node:path';
import {fileURLToPath} from 'node:url';
import {runtimeManifest,runtimePluginFiles} from '../scripts/runtime-manifest.mjs';
import {QuotaStore,duration,deadline} from '../quota-state.js';
import {SafeRouter,observeTransport,scopedStream,applyModelSelector} from '../model-selector.js';
const a={provider:'groq',model:'a',approved:true,costPolicy:'verified-zero-cost',compatibilityVerified:true};
const b={provider:'local',model:'b',approved:true,costPolicy:'verified-zero-cost',compatibilityVerified:true};
const llm={resolveModelInfo:async(p,m)=>({provider:p,id:m,name:m,context:{contextWindow:8192},inputModalities:['text','image']})};
const payload=()=>({agent:{},turn:1,step:1,signal:new AbortController().signal});
test('unknown stays unknown; no fallback resets invented',()=>{
  const s=new QuotaStore(()=>1000);s.observe(a,{failure:{code:'QUOTA'}});
  const q=s.snapshot(a).modelQuota;assert.equal(q.quotaHit,true);assert.equal(q.retryAt,null);assert.equal(q.metrics.RPM.limit,null);assert.equal(s.ready(a),false);
});
test('compound durations, milliseconds, zero and invalid values',()=>{
  assert.equal(duration('2m59.56s'),179560);assert.equal(duration('250ms'),250);assert.equal(duration('0'),0);
  for(const bad of ['tomorrow','-4','1e3','2s junk',' 2m','Infinity'])assert.equal(duration(bad),null);
  assert.equal(deadline('1699999999',1000,'epoch-seconds'),1699999999000);assert.equal(deadline('2026-10-12T12:00:00',1000,'date'),null);
});
test('Groq means RPD and TPM; unknown RPM',()=>{
  const s=new QuotaStore(()=>1000);s.observe(a,{status:429,headers:{'X-RateLimit-Limit-Requests':'14400','x-ratelimit-remaining-requests':'0','x-ratelimit-reset-requests':'2m59.56s','x-ratelimit-limit-tokens':'18000','x-ratelimit-remaining-tokens':'42','retry-after':'3'}});
  const q=s.snapshot(a).modelQuota;assert.equal(q.metrics.RPM.limit,null);assert.equal(q.metrics.RPD.limit,14400);assert.equal(q.metrics.TPM.remaining,42);assert.equal(q.metrics.RPD.resetRemainingMs,179560);assert.equal(q.retryRemainingMs,3000);
});
test('Anthropic separates input and output TPM',()=>{
  const now=Date.parse('2026-10-12T12:00:00Z'),s=new QuotaStore(()=>now);
  s.observe({provider:'anthropic',model:'a'},{status:200,headers:{'anthropic-ratelimit-requests-limit':'20','anthropic-ratelimit-input-tokens-remaining':'0','anthropic-ratelimit-input-tokens-reset':'2026-10-12T12:00:30Z','anthropic-ratelimit-output-tokens-remaining':'30'}});
  const q=s.snapshot({provider:'anthropic',model:'a'}).modelQuota;assert.equal(q.metrics.ITPM.hit,true);assert.equal(q.metrics.ITPM.resetRemainingMs,30000);assert.equal(q.metrics.OTPM.remaining,30);assert.equal(q.metrics.TPM.remaining,null);
});
test('Retry-After HTTP date and malformed reset',()=>{
  let now=Date.parse('2026-10-12T12:00:00Z');const s=new QuotaStore(()=>now);
  s.observe(a,{status:429,headers:{'retry-after':'Mon, 12 Oct 2026 12:00:05 GMT'}});assert.equal(s.snapshot(a).modelQuota.retryRemainingMs,5000);
  now+=7000;assert.equal(s.snapshot(a).modelQuota.retryRemainingMs,0);
  s.observe(a,{status:429,headers:{'retry-after':'soon'}});assert.equal(s.snapshot(a).modelQuota.retryRemainingMs,null);
});
test('structured Google RetryInfo and quota dimension',()=>{
  const s=new QuotaStore(()=>0),route={provider:'google',model:'g'};
  s.observe(route,{body:{error:{code:429,details:[{'@type':'type.googleapis.com/google.rpc.RetryInfo',retryDelay:'3.25s'},{'@type':'type.googleapis.com/google.rpc.QuotaFailure',violations:[{quotaId:'GenerateRequestsPerDayPerProjectPerModel',quotaValue:'20'}]}]}}});
  const q=s.snapshot(route).modelQuota;assert.equal(q.retryRemainingMs,3250);assert.equal(q.metrics.RPD.hit,true);assert.equal(q.metrics.RPD.limit,20);assert.equal(q.metrics.RPD.resetAt,null);
});
test('OpenRouter API RPD data is distinct from credit dollars and deprecated rate_limit',()=>{
  const s=new QuotaStore(()=>0);s.observeOpenRouterKey('openrouter',{limit_remaining:1.2,rate_limit:{requests:20},free_model_daily_requests:{limit:50,used:50,remaining:0}});
  const q=s.snapshot({provider:'openrouter',model:'x'}).providerQuota;assert.equal(q.metrics.RPD.remaining,0);assert.equal(q.metrics.RPM.limit,null);assert.equal(q.credit.remaining,1.2);assert.equal(q.metrics.RPD.resetAt,null);assert.equal(s.ready({provider:'openrouter',model:'y'}),false);
});
test('provider shared limit blocks every sibling; another provider remains eligible',()=>{
  const s=new QuotaStore(()=>0);s.observe({provider:'openrouter',model:'x'},{failure:{code:'QUOTA',metadata:{limit_source:'openrouter_free_tier_daily'}}});
  assert.equal(s.ready({provider:'openrouter',model:'y'}),false);assert.equal(s.ready(b),true);
});
test('success without quota headers does not imply full quota or retain stale header data',()=>{
  const s=new QuotaStore(()=>0);s.observe(a,{status:429,headers:{'x-ratelimit-remaining-requests':'0'}});s.observe(a,{status:200});
  const q=s.snapshot(a).modelQuota;assert.equal(q.status,'observed OK');assert.equal(q.quotaHit,null);assert.equal(q.metrics.RPD.remaining,null);
});
test('safe fallback changes route only; frozen seed and agent identity untouched',async()=>{
  const s=new QuotaStore(()=>0),r=new SafeRouter(s,{autoFallback:true,routes:[a,b]},llm),p=payload();
  const seed=Object.freeze({provider:'groq',model:'a',reasoningEffort:'high',maxTokens:900});
  assert.equal(await r.select(p,seed),seed);const before=p.agent;
  assert.deepEqual(r.fail({...p,provider:'groq',failure:{code:'RATE_LIMIT'}}),{kind:'retry'});
  assert.deepEqual(await r.select(p,seed),{provider:'local',model:'b'});assert.equal(p.agent,before);assert.equal(seed.reasoningEffort,'high');
  assert.throws(()=>r.fail({...p,provider:'local',failure:{code:'QUOTA'}}),{code:'ICARUS_FAILOVER_BLOCKED'});
});
test('local cooldown is labeled separately from actual provider retry/reset',async()=>{
  let now=0;const s=new QuotaStore(()=>now),r=new SafeRouter(s,{autoFallback:true,localCooldownMs:1000,routes:[a,b]},llm),p=payload();
  await r.select(p,a);r.fail({...p,provider:'groq',failure:{code:'RATE_LIMIT',providerRetryAfterMs:4000}});
  const q=s.snapshot(a).modelQuota;assert.equal(q.retryRemainingMs,4000);assert.equal(q.localCooldownRemainingMs,1000);
  now=2000;assert.equal(s.ready(a),false);now=4001;assert.equal(s.ready(a),true);
});
test('paid, unapproved, duplicate, or unverified routes are rejected',()=>{
  for(const route of [{...a,costPolicy:'owner-approved-paid'},{...a,approved:false},{...a,compatibilityVerified:false}])assert.throws(()=>new SafeRouter(new QuotaStore(),{routes:[route]},llm));
  assert.throws(()=>new SafeRouter(new QuotaStore(),{routes:[a,a]},llm));
});
test('cancelled, unrelated errors, unlisted selection and disabled mode compose',async()=>{
  const r=new SafeRouter(new QuotaStore(),{autoFallback:true,routes:[a,b]},llm),p=payload();
  const seed={provider:'other',model:'m'};assert.equal(await r.select(p,seed),seed);assert.equal(r.fail({...p,provider:'other',failure:{code:'QUOTA'}}),null);
  await r.select(p,a);assert.equal(r.fail({...p,provider:'groq',failure:{code:'INVALID_CREDENTIAL'}}),null);
  const c=new AbortController();c.abort();await assert.rejects(r.select({...p,signal:c.signal},a),{name:'AbortError'});
  const disabled=new SafeRouter(new QuotaStore(),{},llm);assert.equal(await disabled.select(p,a),a);
});
test('insufficient context or modalities stop fallback',async()=>{
  for(const target of [{context:{contextWindow:1000},inputModalities:['text','image']},{context:{contextWindow:8192},inputModalities:['text']},{}]){
    const service={resolveModelInfo:async(p,m)=>p==='groq'?await llm.resolveModelInfo(p,m):target};
    const s=new QuotaStore(),r=new SafeRouter(s,{autoFallback:true,routes:[a,b]},service),p=payload();await r.select(p,a);r.fail({...p,provider:'groq',failure:{code:'QUOTA'}});
    await assert.rejects(r.select(p,a),{code:'ICARUS_FAILOVER_BLOCKED'});
  }
});
test('transport captures real local HTTP headers without consuming body; concurrent routes isolated',async()=>{
  const server=createServer((req,res)=>{res.writeHead(429,{'retry-after':req.url==='/a'?'2':'5','x-ratelimit-remaining-requests':'0'});res.end('original error body');});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`,s=new QuotaStore(),t=observeTransport(s);
  try{
    const streams=[a,b].map((route,i)=>scopedStream(t,route,()=> (async function*(){const response=await fetch(base+(i===0?'/a':'/b'));assert.equal(await response.text(),'original error body');yield {type:'finish',reason:{kind:'error',failure:{code:'RATE_LIMIT'}}};})(),s));
    await Promise.all(streams.map(async stream=>{for await(const chunk of stream)assert.equal(chunk.type,'finish');}));
    assert(s.snapshot(a).modelQuota.retryRemainingMs<=2000&&s.snapshot(a).modelQuota.retryRemainingMs>1000);
    assert(s.snapshot(b).modelQuota.retryRemainingMs<=5000&&s.snapshot(b).modelQuota.retryRemainingMs>4000);
    assert.equal(JSON.stringify(s.snapshot(a)).includes('original error body'),false);
  }finally{t.dispose();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('stream cancellation closes original iterator',async()=>{
  const s=new QuotaStore(),t=observeTransport(s);let closed=false;
  try{for await(const x of scopedStream(t,a,()=> (async function*(){try{yield 1;yield 2;}finally{closed=true;}})(),s))break;assert.equal(closed,true);}finally{t.dispose();}
});
test('web quota endpoint retains trust fence and secrets are absent',async()=>{
  const handlers=new Map(),events=new Map(),disposers=[];
  const ctx={llm:{...llm,listProviders:()=>[{id:'groq'}],listModels:async()=>[{id:'a',name:'A'}]},effect(fn){const dispose=fn();if(typeof dispose==='function')disposers.push(dispose);},on(name,fn){events.set(name,fn);},get(){return undefined;},webServer:{register(r){handlers.set(r.path,r.handler);}}};
  applyModelSelector(ctx,{},req=>req.headers.host==='127.0.0.1',res=>{res.writeHead(403);res.end('forbidden');});
  const call=async(req,path='/dsh-tether/model-quotas')=>{let code,body;await handlers.get(path)(req,{writeHead(c){code=c;},end(b){body=b;}});return {code,body};};
  try{assert.equal((await call({headers:{host:'evil.test'},method:'GET'})).code,403);assert.equal((await call({headers:{host:'127.0.0.1'},method:'POST'})).code,405);const result=await call({headers:{host:'127.0.0.1'},method:'GET'});assert.equal(result.code,200);assert.equal(JSON.parse(result.body).groups[0].models[0].modelQuota.retryAt,null);}finally{for(const f of disposers)f();}
});
test('packaging includes runtime modules and identity; Android skeleton includes modules',async()=>{
  const pkg=JSON.parse(await readFile(new URL('../package.json',import.meta.url)));
  for(const file of ['model-selector.js','quota-state.js','client.js','AGENTS.md','identity.md','inherited.md','learned.md','current-state.md'])assert(pkg.files.includes(file));
  const script=await readFile(new URL('../scripts/build-android-runtime.mjs',import.meta.url),'utf8');assert(script.includes('for (const f of runtimePluginFiles)'));assert(runtimePluginFiles.includes('model-selector.js'));assert(runtimePluginFiles.includes('hermes-skills.js'));assert(script.includes('runtimeManifest(root, pkg)'));
});
test('every exhausted metric reset constrains fallback; old retry header is not reused',()=>{
  let now=0;const s=new QuotaStore(()=>now);
  s.observe(a,{status:429,headers:{'retry-after':'2','x-ratelimit-remaining-requests':'0','x-ratelimit-reset-requests':'8s'}});
  now=3000;assert.equal(s.ready(a),false);now=9000;assert.equal(s.ready(a),true);
  s.observe(a,{status:429});assert.equal(s.snapshot(a).modelQuota.retryAt,null);assert.equal(s.ready(a),false);
});
test('client uses actual DSH browser module loader and unknown/countdown rendering',async()=>{
  let registration;const source=await readFile(new URL('../client.js',import.meta.url),'utf8');
  runInNewContext(source,{window:{__ModuleLoader__:{load(r){registration=r;}}}});
  assert.equal(registration.id,'dsh-plugin-tether');const client=registration.factory();
  const s=new QuotaStore(()=>0);s.observe(a,{status:429,headers:{'retry-after':'4'}});s.block(a,'model',1000);
  const text=client.summary(s.snapshot(a).modelQuota,1500);
  assert(text.includes('Provider retry/reset: 3s'));assert(text.includes('local cooldown: 0s'));assert(text.includes('RPM: unknown/unknown'));assert(text.includes('reset: unknown'));
  let command;const ctx={effect(fn){fn();},commandUi:{register(c){command=c;}},sessions:{subagentAddress:()=>undefined}};
  client.apply(ctx);assert.equal(command.name,'models');assert.equal(command.ui.kind,'action');assert.equal(command.available({sessionId:'s'}),true);
});
test('same-version Android rebuild changes manifest when plugin changes',async()=>{
  const root=fileURLToPath(new URL('../',import.meta.url)),pkg=JSON.parse(await readFile(join(root,'package.json'))),dir=await mkdtemp(join(tmpdir(),'icarus-runtime-manifest-'));
  try{
    for(const name of runtimePluginFiles){await mkdir(dirname(join(dir,name)),{recursive:true});await cp(join(root,name),join(dir,name));}
    const before=runtimeManifest(dir,pkg);assert.equal(before,runtimeManifest(root,pkg));
    await appendFile(join(dir,'quota-state.js'),'\n// fixture modification\n');
    const after=runtimeManifest(dir,pkg);assert.notEqual(before,after);assert.equal(JSON.parse(before).app,JSON.parse(after).app);
    assert.equal((await readFile(join(dir,'identity.md'))).equals(await readFile(join(root,'identity.md'))),true);
  }finally{assert.equal(dirname(resolve(dir)),resolve(tmpdir()));assert(basename(dir).startsWith('icarus-runtime-manifest-'));await rm(dir,{recursive:true,force:true});}
});
test('negative budgets block without fabricating a reset; out-of-range dates stay unknown',()=>{
  const s=new QuotaStore(()=>0);s.observeOpenRouterKey('openrouter',{limit_remaining:-1,effective_budget:{remaining_usd:-2,resets_at:null}});
  const q=s.snapshot({provider:'openrouter',model:'m'}).providerQuota;assert.equal(q.credit.remaining,-1);assert.equal(q.quotaHit,true);assert.equal(q.retryAt,null);
  assert.equal(deadline('999999999999999999999',0,'epoch-seconds'),null);assert.equal(deadline('999999999999999999999',0),null);
});
