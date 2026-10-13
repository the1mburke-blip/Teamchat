// DSH's browser module format; the same UI runs on PC and in both mobile modes.
window.__ModuleLoader__.load({id:'dsh-plugin-tether',factory:()=>{
const inject=['commandUi','modelDirectories','sessions'];
const unknown=v=>v===null||v===undefined?'unknown':String(v);
const time=ms=>ms===null||ms===undefined?'unknown':`${Math.ceil(ms/1000)}s`;
function summary(quota,elapsed=0) {
  const remains=ms=>ms===null||ms===undefined?null:Math.max(0,ms-elapsed);
  const lines=[`Status: ${quota.status}; quota hit: ${unknown(quota.quotaHit)}`,`Provider retry/reset: ${time(remains(quota.retryRemainingMs))}; local cooldown: ${time(remains(quota.localCooldownRemainingMs))}`];
  for(const key of ['RPM','RPD','TPM','ITPM','OTPM','requests','tokens']) {
    const m=quota.metrics[key];if(!['RPM','RPD','TPM'].includes(key)&&m.source==='unknown')continue;
    lines.push(`${key}: ${unknown(m.remaining)}/${unknown(m.limit)} remaining; hit: ${unknown(m.hit)}; reset: ${time(remains(m.resetRemainingMs))}`);
  }
  if(quota.credit?.source==='provider API')lines.push(`Credits remaining (USD): ${unknown(quota.credit.remaining)}; budget reset: ${quota.credit.resetAt===null?'unknown':new Date(quota.credit.resetAt).toISOString()}`);
  if(quota.observedAt!==null)lines.push(`Observed ${new Date(quota.observedAt).toISOString()}`);
  return lines.join('\n');
}
function node(tag,text,parent) {const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(parent)parent.append(element);return element;}
function openSelector(ctx,session) {
  const dialog=node('dialog');dialog.setAttribute('aria-label','ICARUS models and quotas');
  dialog.style.cssText='width:min(940px,94vw);max-height:85vh;box-sizing:border-box;border:1px solid #888;border-radius:12px;padding:16px;background:var(--dsw-alias-bg-base,#20232a);color:var(--dsw-alias-label-primary,#fff);font:14px system-ui;overflow:auto';
  const top=node('div',undefined,dialog);top.style.cssText='display:flex;align-items:center;gap:10px;flex-wrap:wrap';
  node('h2','ICARUS models and quotas',top).style.margin='0';
  const close=node('button','Close',top),reload=node('button','Refresh status',top),api=node('button','Refresh provider APIs',top);
  const search=node('input',undefined,dialog);search.type='search';search.placeholder='Search provider or model';search.setAttribute('aria-label','Search provider or model');search.style.cssText='box-sizing:border-box;width:100%;margin:12px 0;padding:8px';
  const notice=node('p','Loading…',dialog),list=node('div',undefined,dialog);
  let directory,status,snapshotAt=0,disposed=false,busy=false,rows=[];
  const timer=setInterval(()=>{if(disposed)return;const elapsed=Math.max(0,performance.now()-snapshotAt);for(const row of rows){row.pre.textContent=row.info?`Model\n${summary(row.info.modelQuota,elapsed)}\n\nProvider/shared\n${summary(row.info.providerQuota,elapsed)}`:'Quota hit: unknown; RPM/RPD/TPM: unknown; reset: unknown';}},1000);
  const dispose=()=>{if(disposed)return;disposed=true;clearInterval(timer);dialog.remove();};
  dialog.addEventListener('close',dispose);close.onclick=()=>dialog.close();
  function render() {
    list.replaceChildren();rows=[];
    const query=search.value.toLowerCase();
    for(const group of directory?.groups??[]) {
      const models=group.models.filter(m=>`${group.name} ${group.id} ${m.name} ${m.id}`.toLowerCase().includes(query));if(!models.length)continue;
      node('h3',group.name??group.id,list);
      for(const model of models) {
        const info=status?.groups.find(g=>g.id===group.id)?.models.find(m=>m.id===model.id);
        const section=node('section',undefined,list);section.style.cssText='border:1px solid #777;border-radius:8px;padding:12px;margin-bottom:10px';
        const active=directory.current?.provider===group.id&&directory.current?.model===model.id;
        node('strong',`${model.name} (${model.id})${active?' — selected':''}`,section);
        const elapsed=Math.max(0,performance.now()-snapshotAt);
        const pre=node('pre',info?`Model\n${summary(info.modelQuota,elapsed)}\n\nProvider/shared\n${summary(info.providerQuota,elapsed)}`:'Quota hit: unknown; RPM/RPD/TPM: unknown; reset: unknown',section);pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 system-ui';rows.push({pre,info});
        const select=node('button',active?'Selected':'Select this model',section);select.disabled=busy||active;
        select.onclick=async()=>{
          if(busy)return;busy=true;render();notice.textContent='Selecting model…';
          try {
            const fresh=await ctx.modelDirectories.directoryFor(session.sessionId).load();
            if(!fresh.groups.some(g=>g.id===group.id&&g.models.some(m=>m.id===model.id)))throw new Error('Model is no longer registered. Refresh status.');
            const result=await ctx.modelDirectories.directoryFor(session.sessionId).select({provider:group.id,model:model.id});if(!result.ok)throw result.error;
            if(disposed)return;directory=await ctx.modelDirectories.directoryFor(session.sessionId).load();notice.textContent='Model selected. ICARUS identity and permissions are unchanged.';
          }catch(error){if(!disposed)notice.textContent=error.message??'Model selection failed';}
          finally{busy=false;if(!disposed)render();}
        };
      }
    }
    for(const failure of directory?.failures??[])node('p',`${failure.name??failure.id}: catalog unavailable`,list);
  }
  async function refresh() {
    if(disposed)return;reload.disabled=true;
    try {
      const [current,response]=await Promise.all([ctx.modelDirectories.directoryFor(session.sessionId).load(),fetch('/dsh-tether/model-quotas',{cache:'no-store'})]);
      if(!response.ok)throw new Error(`Quota status unavailable (${response.status})`);
      const snapshot=await response.json();if(disposed)return;directory=current;status=snapshot;snapshotAt=performance.now();notice.textContent=`Automatic fallback: ${status.autoFallback?'enabled for approved zero-cost routes':'disabled'}. Countdown reaching zero does not prove quota is available.`;render();
    }catch(error){if(!disposed)notice.textContent=error.message??'Status unavailable';}finally{if(!disposed)reload.disabled=false;}
  }
  reload.onclick=refresh;search.oninput=render;
  api.onclick=async()=>{
    api.disabled=true;
    try {
      const response=await fetch('/dsh-tether/model-quotas/refresh',{method:'POST'});if(!response.ok)throw new Error(`API refresh failed (${response.status})`);
      const result=await response.json();await refresh();if(disposed)return;
      notice.textContent=result.reports.length?result.reports.map(r=>`${r.provider}: ${r.status}`).join('; '):'No provider quota API configured. Response headers and errors are still observed.';
    }catch(error){if(!disposed)notice.textContent=error.message??'API refresh unavailable';}finally{if(!disposed)api.disabled=false;}
  };
  document.body.append(dialog);dialog.showModal();refresh();return dispose;
}
function apply(ctx) {
  let dispose;
  ctx.effect(()=>()=>dispose?.());
  ctx.effect(()=>ctx.commandUi.register({name:'models',label:()=> 'ICARUS models and quotas',description:()=> 'Switch provider/model, including registered local models; view observed quotas and countdowns.',available:session=>ctx.sessions.subagentAddress(session.sessionId)===undefined,ui:{kind:'action',run(session){dispose?.();dispose=openSelector(ctx,session);}}}));
}
return {inject,apply,summary,openSelector};
}});
