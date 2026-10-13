// Stores only normalized limit facts. Raw errors, headers and credentials never leave the observer.
export const routeKey = r => JSON.stringify([r.provider, r.model]);
const number = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)) && Number(v) >= 0 ? Number(v) : null;
const signedNumber = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null;
export function duration(v) {
  if (typeof v !== 'string' || !v.trim()) return null;
  if (/^\d+(?:\.\d+)?$/.test(v.trim())) return Number(v) * 1000;
  let total = 0, end = 0;
  for (const match of v.matchAll(/(\d+(?:\.\d+)?)(ms|s|m|h|d)/g)) {
    if (match.index !== end) return null;
    total += Number(match[1]) * ({ms:1,s:1000,m:60000,h:3600000,d:86400000}[match[2]]);
    end = match.index + match[0].length;
  }
  return end === v.length && end > 0 && Number.isFinite(total) ? total : null;
}
export function deadline(value, now, format = 'duration') {
  if (value === undefined || value === null || value === '') return null;
  if (format === 'epoch-seconds') {
    const seconds = number(value); return seconds === null || seconds*1000>8640000000000000 ? null : seconds * 1000;
  }
  if (format === 'duration') { const ms = duration(String(value)); return ms === null || !Number.isFinite(now+ms) || now+ms>8640000000000000 ? null : now + ms; }
  // Require an explicit timezone. No local-date guesses or date parsing of numeric strings.
  if (!/(?:GMT|Z|[+-]\d\d:\d\d)$/i.test(String(value))) return null;
  const date = Date.parse(value); return Number.isFinite(date) ? date : null;
}
function headersOf(input) {
  const out = {};
  if (input?.forEach && !Array.isArray(input)) input.forEach((v,k) => { out[k.toLowerCase()] = String(v); });
  else if (Array.isArray(input)) {
    for (let i=0; i<input.length; i+=2) out[String(input[i]).toLowerCase()] = String(input[i+1]);
  } else for (const [k,v] of Object.entries(input ?? {})) out[k.toLowerCase()] = String(v);
  return out;
}
const blankMetric = () => ({limit:null,remaining:null,hit:null,resetAt:null,observedAt:null,source:'unknown'});
function blank() { return {status:'unknown',quotaHit:null,scope:'model',observedAt:null,retryAt:null,localCooldownAt:null,metrics:{RPM:blankMetric(),RPD:blankMetric(),TPM:blankMetric(),ITPM:blankMetric(),OTPM:blankMetric(),requests:blankMetric(),tokens:blankMetric()},credit:{remaining:null,resetAt:null,source:'unknown'}}; }
function metric(h, prefix, format, now) {
  const limit = number(h[prefix+'limit']), remaining = number(h[prefix+'remaining']);
  const resetAt = deadline(h[prefix+'reset'],now,format);
  if (limit === null && remaining === null && resetAt === null) return null;
  return {limit,remaining,hit:remaining === null ? null : remaining === 0,resetAt,observedAt:now,source:'response headers'};
}
function xMetric(h, suffix, now) {
  return metric({['x-limit']:h['x-ratelimit-limit-'+suffix],['x-remaining']:h['x-ratelimit-remaining-'+suffix],['x-reset']:h['x-ratelimit-reset-'+suffix]},'x-','duration',now);
}
export function classifyFailure(f = {}) {
  const metadata = f.metadata ?? f.error?.metadata ?? f.providerMetadata ?? {};
  const source = f.limit_source ?? f.limitSource ?? metadata.limit_source;
  const message = String(f.message ?? f.error?.message ?? '');
  const code = f.code ?? f.error?.code;
  const quota = code === 'QUOTA' || code === 'insufficient_quota' || code === 'RESOURCE_EXHAUSTED';
  const limited = quota || code === 'RATE_LIMIT' || code === 'rate_limit_error' || f.status === 429 || code === 429 || /^openrouter_(?:free_tier_daily|credits|key_limit|guardrail_budget|workspace_budget|in_flight_budget)$/.test(source ?? '');
  if (!limited) return null;
  const scope = /^openrouter_/.test(source ?? '') || /account[- ]wide|organization[- ]wide|project[- ]wide|free[- ]models?[- ]per[- ]day|daily.{0,40}free.{0,20}(?:requests|models)/i.test(message) ? 'provider' : 'model';
  return {quota,scope,source};
}
export class QuotaStore {
  constructor(clock = Date.now) { this.clock=clock; this.models=new Map(); this.providers=new Map();this.attemptFailures=new WeakMap(); }
  failureFor(route,signal) {return signal?this.attemptFailures.get(signal)?.get(routeKey(route)):undefined;}
  beginAttempt(route) {
    if(!route.signal)return;
    if(!this.attemptFailures.has(route.signal))this.attemptFailures.set(route.signal,new Map());
    this.attemptFailures.get(route.signal).delete(routeKey(route));
    const state=this.models.get(routeKey(route));if(state)state.retryAt=null;
  }
  state(route,scope='model') {
    const map=scope==='provider'?this.providers:this.models, key=scope==='provider'?route.provider:routeKey(route);
    if(!map.has(key)) map.set(key,blank()); return map.get(key);
  }
  observe(route,{headers,status,failure,body}={}) {
    const now=this.clock(), h=headersOf(headers);
    // Parse only structured error JSON if exposed; never mine arbitrary text for guessed resets.
    let f=failure ?? body?.error ?? {};
    if (typeof f.message === 'string') { try {const parsed=JSON.parse(f.message);f={...f,...(parsed.error??parsed)};} catch {} }
    if(status !== undefined) f={...f,status};
    if(route.signal && status!==undefined) {
      if(!this.attemptFailures.has(route.signal))this.attemptFailures.set(route.signal,new Map());
      this.attemptFailures.get(route.signal).set(routeKey(route),status>=400?{status}:undefined);
    }
    const reason=classifyFailure(f);
    const state=this.state(route,reason?.scope ?? 'model');
    state.scope=reason?.scope ?? 'model';state.observedAt=now;
    // Each HTTP response supersedes this route's previous header observation.
    if(status!==undefined) {state.metrics=blank().metrics;state.retryAt=null;}
    const provider=route.family ?? route.provider;
    const requests=xMetric(h,'requests',now), tokens=xMetric(h,'tokens',now);
    if(requests) state.metrics[provider==='groq'?'RPD':provider==='openai'?'RPM':'requests']=requests;
    if(tokens) state.metrics[provider==='groq'||provider==='openai'?'TPM':'tokens']=tokens;
    for(const [suffix,key] of [['requests','RPM'],['input-tokens','ITPM'],['output-tokens','OTPM'],['tokens','TPM']]) {
      const value=metric(h,`anthropic-ratelimit-${suffix}-`,'date',now);
      if(value) state.metrics[key]=value;
    }
    // OpenRouter generic request headers have no declared RPM/RPD dimension.
    if(provider==='openrouter' && h['x-ratelimit-reset']) {
      state.metrics.requests={limit:number(h['x-ratelimit-limit']),remaining:number(h['x-ratelimit-remaining']),hit:number(h['x-ratelimit-remaining'])===null?null:number(h['x-ratelimit-remaining'])===0,resetAt:deadline(h['x-ratelimit-reset'],now,'epoch-seconds'),observedAt:now,source:'response headers'};
    }
    for(const detail of f.details ?? []) {
      if(detail['@type']==='type.googleapis.com/google.rpc.RetryInfo') {
        const delay=duration(detail.retryDelay); if(delay!==null) state.retryAt=now+delay;
      }
      if(detail['@type']==='type.googleapis.com/google.rpc.QuotaFailure') {
        for(const violation of detail.violations ?? []) {
          const id=String(violation.quotaId??violation.quotaMetric??'');
          const key=/perday|per_day/i.test(id)?'RPD':/tokens.*perminute|tokens_per_minute/i.test(id)?'TPM':/requests.*perminute|requests_per_minute/i.test(id)?'RPM':null;
          if(key) state.metrics[key]={limit:number(violation.quotaValue),remaining:null,hit:true,resetAt:null,observedAt:now,source:'provider error'};
        }
      }
    }
    const metadata=f.metadata??{};
    const reset=deadline(metadata.resets_at,now,'date');
    if(reset!==null) state.retryAt=reset;
    const retry=h['retry-after'];
    if(retry!==undefined) state.retryAt=/^\d+(?:\.\d+)?$/.test(retry.trim())?deadline(retry.trim(),now):deadline(retry,now,'date');
    if(number(f.providerRetryAfterMs)!==null) state.retryAt=now+number(f.providerRetryAfterMs);
    if(reason || status===429) {state.status=reason?.quota?'quota hit':'rate limited';state.quotaHit=true;}
    else if(status>=200 && status<300) { state.status='observed OK';const hits=Object.values(state.metrics).map(m=>m.hit).filter(v=>v!==null);state.quotaHit=hits.length?hits.includes(true):null;state.retryAt=null; }
    return state;
  }
  observeOpenRouterKey(provider, data) {
    const state=this.state({provider},'provider');state.scope='provider';state.observedAt=this.clock();
    const q=data.free_model_daily_requests;
    if(q) {state.metrics.RPD={limit:number(q.limit),remaining:number(q.remaining),hit:number(q.remaining)===null?null:number(q.remaining)===0,resetAt:null,observedAt:this.clock(),source:'provider API'};}
    state.credit={remaining:signedNumber(data.limit_remaining),resetAt:deadline(data.effective_budget?.resets_at,this.clock(),'date'),source:'provider API'};
    // Credits and request quota remain separate. No deprecated rate_limit mapping.
    const budgetRemaining=signedNumber(data.effective_budget?.remaining_usd);
    const budgetBlocked=budgetRemaining!==null && budgetRemaining<=0;
    state.quotaHit=q ? state.metrics.RPD.hit : null;
    if(state.quotaHit===true || budgetBlocked) {state.status='quota hit';state.quotaHit=true;}
    else state.status='unknown';
  }
  block(route,scope,ms) {
    const state=this.state(route,scope); state.scope=scope;
    state.localCooldownAt=this.clock()+ms;
  }
  snapshot(route) {
    const model=this.models.get(routeKey(route))??blank(), provider=this.providers.get(route.provider)??blank(),now=this.clock();
    const detach=s=>({...structuredClone(s),retryRemainingMs:s.retryAt===null?null:Math.max(0,s.retryAt-now),localCooldownRemainingMs:s.localCooldownAt===null?null:Math.max(0,s.localCooldownAt-now),metrics:Object.fromEntries(Object.entries(s.metrics).map(([k,m])=>[k,{...m,resetRemainingMs:m.resetAt===null?null:Math.max(0,m.resetAt-now)}]))});
    return {provider:route.provider,model:route.model,modelQuota:detach(model),providerQuota:detach(provider)};
  }
  ready(route) {
    return [this.models.get(routeKey(route)),this.providers.get(route.provider)].every(s=>{
      if(!s)return true;
      if((s.localCooldownAt??0)>this.clock()||(s.retryAt??0)>this.clock())return false;
      const hit=Object.values(s.metrics).filter(m=>m.hit===true);
      if(hit.some(m=>m.resetAt!==null && m.resetAt>this.clock()))return false;
      if(s.quotaHit===true && s.retryAt===null && (!hit.length||hit.some(m=>m.resetAt===null)))return false;
      return true;
    });
  }
}
