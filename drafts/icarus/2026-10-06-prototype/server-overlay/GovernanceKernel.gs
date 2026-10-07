/** Governance v1. Trusted host code owns this closure; executors receive RPC capabilities only.
 * Apps Script admins/code writers are trusted. This is NOT a sandbox for arbitrary JS.
 * All production calls enter under the existing script lock. No secret/permit mint RPC.
 */
const IcarusGovernance = (function() {
  const policy='icarus.governance.v1', table='GOVERNANCE_EVENTS';
  let active=null,composioTask=null;
  function fail(code){throw new Error('GOVERNANCE_'+code);}
  function canon(v){if(Array.isArray(v))return v.map(canon);if(v&&typeof v==='object'){const o={};Object.keys(v).sort().forEach(function(k){o[k]=canon(v[k]);});return o;}return v;}
  function hash(v){return sha256Hex_(JSON.stringify(canon(v)));}
  function events(){const db=SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('STATE_SHEET_ID'));let s=db.getSheetByName(table);if(!s){s=db.insertSheet(table);s.appendRow(['sequence','task_id','record_json','previous_hash','hash']);SpreadsheetApp.flush();}return s;}
  function history(){const rows=events().getDataRange().getValues().slice(1);let previous='';rows.forEach(function(r,i){if(Number(r[0])!==i+1||r[3]!==previous||r[4]!==hash([r[0],r[1],r[2],r[3]]))fail('AUDIT_CORRUPT');previous=r[4];});return rows;}
  function read(id){const rows=history();for(let i=rows.length-1;i>=0;i--)if(rows[i][1]===id)return JSON.parse(rows[i][2]);return null;}
  function append(id,state,event){const rows=history(),seq=rows.length+1,prev=rows.length?rows[rows.length-1][4]:'';state.event=event;state.utc=nowIso_();const raw=JSON.stringify(state),fp=hash([seq,id,raw,prev]);events().appendRow([seq,id,raw,prev,fp]);SpreadsheetApp.flush();const again=history();if(again.length!==seq||again[seq-1][4]!==fp)fail('DURABILITY_FAILED');return JSON.parse(raw);}
  function key(){const props=PropertiesService.getScriptProperties();let k=props.getProperty('GOVERNANCE_PERMIT_SIGNING_KEY');if(!k){k=Utilities.getUuid()+Utilities.getUuid()+Utilities.getUuid();props.setProperty('GOVERNANCE_PERMIT_SIGNING_KEY',k);if(props.getProperty('GOVERNANCE_PERMIT_SIGNING_KEY')!==k)fail('KEY_NOT_PERSISTED');}return k;}
  function mac(v){return Utilities.computeHmacSha256Signature(JSON.stringify(canon(v)),key(),Utilities.Charset.UTF_8).map(function(b){return ('0'+((b+256)%256).toString(16)).slice(-2);}).join('');}
  function principal(p,role){if(!p||p.role!==role||typeof p.id!=='string'||!p.id)fail('IDENTITY_DENIED');return p.id;}
  function specValidate(spec){
    const s=JSON.parse(JSON.stringify(spec));
    const fields=['agentId','tool','service','operation','target','scopes','route','budgetEUR','write','payloadHash','evidenceContract'];
    if(Object.keys(s).some(function(k){return fields.indexOf(k)<0;})||fields.some(function(k){return s[k]===undefined;}))fail('SPEC_INVALID');
    if(s.budgetEUR!==0||!s.route||!s.target||!s.tool||!s.operation||!s.service||!s.agentId||typeof s.write!=='boolean')fail('PREFLIGHT_DENIED');
    if(!Array.isArray(s.scopes)||!s.scopes.length||s.scopes.some(function(v){return typeof v!=='string'||!v;}))fail('SCOPE_DENIED');
    if(!s.evidenceContract||!s.evidenceContract.readPath||!s.evidenceContract.expectedHash)fail('EVIDENCE_REQUIRED');
    return canon(s);
  }
  function prepare(id,spec,p){
    const agent=principal(p,'executor'),task=getTask_(id.replace(/:reasoning$/, '').replace(/:discovery:[^:]+$/, ''));if(!task)fail('TASK_NOT_FOUND');
    const s=specValidate(spec);if(s.agentId!==agent)fail('AGENT_DENIED');
    const old=read(id);
    if(old&&['OUTCOME_UNKNOWN','WORKING','WORK_COMPLETE_AWAITING_VERIFICATION','PASS','FAIL'].indexOf(old.state)>=0)fail('REPLAY_OR_RECONCILIATION_REQUIRED');
    if(old&&old.state==='READY'&&hash(old.spec)===hash(s))return old.permit;
    let rev=old?old.revision+1:1;
    append(id,{revision:rev,state:'PREFLIGHTING',spec:s,objectiveHash:hash(task.objective),subject:agent},'preflight.started');
    const payload={taskId:id,taskRevision:rev,agentId:agent,spec:s,policyVersion:policy,expiry:Date.now()+300000,nonce:Utilities.getUuid(),objectiveHash:hash(task.objective)};
    const permit={payload:payload,signature:mac(payload)};
    append(id,{revision:rev,state:'READY',spec:s,objectiveHash:payload.objectiveHash,subject:agent,permit:permit},'permit.issued');return permit;
  }
  function invalidate(id,reason){const r=read(id);if(r&&r.state==='READY'){r.state='REQUIRES_PREFLIGHT';r.revision++;delete r.permit;r.reason=reason;append(id,r,'permit.revoked');}}
  function run(permit,spec,p,call){
    const agent=principal(p,'executor'),s=specValidate(spec),payload=permit&&permit.payload;
    if(!payload||!constantTimeEquals_(String(permit.signature||''),mac(payload)))fail('PERMIT_SIGNATURE_DENIED');
    const id=payload.taskId,r=read(id),task=getTask_(id.replace(/:reasoning$/, '').replace(/:discovery:[^:]+$/, ''));
    if(!r||r.state!=='READY'||r.revision!==payload.taskRevision||r.permit.signature!==permit.signature)fail('REPLAY_DENIED');
    if(payload.agentId!==agent||s.agentId!==agent)fail('AGENT_DENIED');
    if(payload.expiry<=Date.now()||payload.policyVersion!==policy){invalidate(id,'expiry_or_policy');fail('EXPIRED_OR_POLICY_CHANGED');}
    if(!task||payload.objectiveHash!==hash(task.objective)||hash(payload.spec)!==hash(s)){invalidate(id,'material_change');fail('MATERIAL_CHANGE_PREFLIGHT_REQUIRED');}
    if(active)fail('NESTED_GATEWAY_DENIED');
    // Durable consumption and mutation intent precede ANY adapter/transport invocation.
    r.state='WORKING';r.revision++;r.intent={nonce:payload.nonce,fingerprint:hash(s),mutation:s.write,targetHash:hash(s.target),payloadHash:s.payloadHash};delete r.permit;append(id,r,'gateway.intent.persisted');
    const guard={taskId:id,spec:s,subject:agent};active=guard;
    try {
      const result=call();
      const after=read(id);after.state=(s.operation==='reasoning'&&result.status==='WAITING_REASONING_CAPACITY')?'REQUIRES_PREFLIGHT':'WORK_COMPLETE_AWAITING_VERIFICATION';after.revision++;after.resultHash=hash(result);after.evidenceRef='GOVERNANCE_EVENTS:'+id+':'+after.revision;append(id,after,'execution.completed');
      return result;
    }catch(e){const after=read(id);after.state=s.write?'OUTCOME_UNKNOWN':'FAIL';after.revision++;after.reason='ADAPTER_OUTCOME_UNVERIFIED';append(id,after,s.write?'mutation.outcome_unknown':'execution.failed');throw e;}
    finally{active=null;}
  }
  function guard(task,plan,write){
    if(!active)fail('DIRECT_ADAPTER_BYPASS_DENIED');
    const id=typeof task==='string'?task:task.task_id;
    if(id!==active.taskId)fail('ADAPTER_TASK_DENIED');
    if(write&&(!active.spec.write||hash(plan)!==active.spec.payloadHash))fail('ADAPTER_SCOPE_DENIED');
    if(write)active.plan=canon(plan);
    if(plan.service!==active.spec.service)fail('ADAPTER_SERVICE_DENIED');
    const t=active.spec.target;
    if(plan.service==='sheets'&&(plan.resourceId!==t.resourceId||(plan.range||'')!==t.range))fail('ADAPTER_TARGET_DENIED');
    if(plan.service==='docs'&&plan.resourceId!==t.resourceId)fail('ADAPTER_TARGET_DENIED');
    if(plan.service==='calendar'&&t.eventId&&plan.eventId&&plan.eventId!==t.eventId)fail('ADAPTER_TARGET_DENIED');
    return active;
  }
  function wire(method,url,body){
    if(!active)fail('DIRECT_TRANSPORT_BYPASS_DENIED');
    const s=active.spec;
    if(s.route!=='GOOGLE_NATIVE')fail('ROUTE_DENIED');
    const service=/sheets\.googleapis/.test(url)?'sheets':/docs\.googleapis/.test(url)?'docs':/calendar\/v3/.test(url)?'calendar':'';
    if(service!==s.service)fail('WIRE_SERVICE_DENIED');
    const target=s.target;
    if(method==='get'){
      let urls=[];
      if(service==='calendar'){
        const base='https://www.googleapis.com/calendar/v3/calendars/primary/events';
        if(target.eventId)urls.push(base+'/'+encodeURIComponent(target.eventId));
        if(target.window)urls.push(base+'?maxResults=10&singleEvents=true&orderBy=startTime&timeMin='+encodeURIComponent(target.window.timeMin)+'&timeMax='+encodeURIComponent(target.window.timeMax));
      }
      if(service==='sheets'){
        const base='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(target.resourceId);
        if(s.operation==='sheet_metadata')urls.push(base+'?fields=spreadsheetId,properties(title),sheets(properties(sheetId,title,gridProperties))');
        else urls.push(base+'/values/'+encodeURIComponent(target.range)+'?valueRenderOption=UNFORMATTED_VALUE');
      }
      if(service==='docs')urls.push('https://docs.googleapis.com/v1/documents/'+encodeURIComponent(target.resourceId)+'?fields='+(s.operation==='doc_metadata'?'documentId,title,revisionId':'documentId,title,revisionId,body(content(startIndex,endIndex,paragraph(elements(textRun(content)))))'));
      if(urls.indexOf(url)<0)fail('WIRE_TARGET_DENIED');
    }
    if(method!=='get'){
      if(!s.write||!active.wireMutation||hash([method,url,body])!==active.wireMutation)fail('WIRE_MUTATION_DENIED');
      if(active.wrote)fail('SECOND_MUTATION_DENIED');active.wrote=true;
    }
  }
  function bindWire(method,url,body){
    if(!active||!active.spec.write||!active.plan)fail('WIRE_BIND_DENIED');if(active.wireMutation)fail('WIRE_ALREADY_BOUND');
    const p=active.plan,t=active.spec.target;let expected;
    if(p.service==='calendar')expected=['post','https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=none',{id:t.eventId,summary:p.summary,start:{dateTime:p.start},end:{dateTime:p.end},reminders:{useDefault:false}}];
    if(p.service==='sheets')expected=['put','https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(t.resourceId)+'/values/'+encodeURIComponent(t.range)+'?valueInputOption=RAW',{range:t.range,majorDimension:'ROWS',values:[[p.text]]}];
    if(p.service==='docs'){
      const insert={text:p.text};if(p.operation==='append_text')insert.endOfSegmentLocation={};else insert.location={index:p.index};
      if(!body||!body.writeControl||typeof body.writeControl.requiredRevisionId!=='string'||!body.writeControl.requiredRevisionId)fail('WRITE_REVISION_REQUIRED');
      expected=['post','https://docs.googleapis.com/v1/documents/'+encodeURIComponent(t.resourceId)+':batchUpdate',{writeControl:{requiredRevisionId:body.writeControl.requiredRevisionId},requests:[{insertText:insert}]}];
    }
    if(!expected||hash(expected)!==hash([method,url,body]))fail('WIRE_MUTATION_EXPANSION_DENIED');
    active.wireMutation=hash(expected);
  }
  function composioWire(session,tool,args,account){if(!active)fail('DIRECT_ADAPTER_BYPASS_DENIED');const s=active.spec;if(s.route!=='COMPOSIO_V31'||s.tool!==tool||s.target.session!==session||s.target.account!==account||s.payloadHash!==hash(args)||s.write)fail('COMPOSIO_SCOPE_DENIED');}
  function verdict(id,evidence,p){
    const verifier=principal(p,'verifier'),r=read(id);
    if(!r||r.subject===verifier)fail('SELF_CERTIFICATION_DENIED');
    if(r.state!=='WORK_COMPLETE_AWAITING_VERIFICATION')fail('VERIFICATION_STATE_DENIED');
    if(!evidence||evidence.taskId!==id||evidence.revision!==r.revision||evidence.targetHash!==hash(r.spec.target)||evidence.criteriaHash!==hash(r.spec.evidenceContract)||evidence.observedHash!==r.spec.evidenceContract.expectedHash||!evidence.readRef)fail('INDEPENDENT_EVIDENCE_MISMATCH');
    r.state='PASS';r.revision++;r.verification={verifierId:verifier,evidenceHash:hash(evidence),readRef:evidence.readRef,observedRevision:evidence.revision};append(id,r,'verification.completed');return {taskId:id,state:r.state,revision:r.revision,verification:r.verification};
  }
  function nativeMetadataWire(url){
    if(!active)fail('DIRECT_TRANSPORT_BYPASS_DENIED');
    const s=active.spec;
    if(s.route!=='GOOGLE_NATIVE'||['gmail','drive'].indexOf(s.service)<0)fail('ROUTE_DENIED');
    if(s.service==='gmail'){
      const base='https://gmail.googleapis.com/gmail/v1/users/me/';
      if(url===base+'profile')return;
      if(s.operation!=='header_metadata')fail('WIRE_OPERATION_DENIED');
      if(url===base+'messages?maxResults=3')return;
      const allowed=(active.headerIds||[]).map(function(id){return base+'messages/'+id+'?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&fields=id,payload(headers)';});
      if(allowed.indexOf(url)<0)fail('WIRE_MESSAGE_DENIED');
    }else{
      const about='https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)',files='https://www.googleapis.com/drive/v3/files?pageSize=5&orderBy=modifiedTime%20desc&fields=files(id,name,mimeType,modifiedTime)&q=trashed%3Dfalse';
      if(url!==about&&(s.operation!=='list_metadata'||url!==files))fail('WIRE_OPERATION_DENIED');
    }
  }
  function captureMetadataList(url,data){
    if(url!=='https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=3')return;
    if(!active||active.spec.service!=='gmail'||active.spec.operation!=='header_metadata'||active.headerIds)fail('HEADER_SELECTION_DENIED');
    if(data.messages!==undefined&&!Array.isArray(data.messages))fail('HEADER_SELECTION_DENIED');
    active.headerIds=(data.messages||[]).slice(0,3).map(function(m){if(!m||!/^[A-Za-z0-9_-]{1,128}$/.test(String(m.id||'')))fail('HEADER_SELECTION_DENIED');return m.id;});
  }
  function providerWire(task,model,body){
    if(!active||active.taskId!==task.task_id+':reasoning'||active.spec.service!=='gemini'||active.spec.target.model!==model||active.spec.payloadHash!==hash(body))fail('DIRECT_PROVIDER_BYPASS_DENIED');
  }
  function ownerPrevalidate(id){const r=read(id);if(r&&r.state!=='WORK_COMPLETE_AWAITING_VERIFICATION')fail('VERIFICATION_STATE_DENIED');return r;}
  function ownerVerified(id,record){
    const r=read(id),t=getTask_(id);if(!r)return; // legacy completed tasks retain the unchanged Google owner receipt seam

    if(!t||t.status!==record.decision||String(t.owner_verification_json)!==JSON.stringify(record)||!record.subject||record.subject===r.subject)fail('OWNER_RECEIPT_DENIED');
    if(r.verification&&r.verification.receiptHash===hash(record))return;
    if(r.state!=='WORK_COMPLETE_AWAITING_VERIFICATION')fail('VERIFICATION_STATE_DENIED');
    r.state=record.decision==='PASS'?'PASS':'FAIL';r.revision++;r.verification={verifierId:record.subject,receiptHash:hash(record),authority:'existing_google_owner_receipt'};append(id,r,'owner.verification.completed');
  }
  function withComposioTask(taskId,call){if(composioTask)fail('NESTED_DISCOVERY_DENIED');composioTask=taskId;try{return call();}finally{composioTask=null;}}
  function composioTransport(method,path,body,call){
    if(PropertiesService.getScriptProperties().getProperty('COMPOSIO_ZERO_COST_VERIFIED')!=='true')fail('ZERO_COST_UNVERIFIED');
    if(active){
      const s=active.spec;
      if(s.operation==='discovery'){
        if(s.target.method!==method||s.target.path!==path||s.payloadHash!==hash(body||null))fail('DISCOVERY_SCOPE_DENIED');
      }else{
        const expected='/tool_router/session/'+encodeURIComponent(s.target.session)+'/execute';
        const payload={tool_slug:s.tool,arguments:body&&body.arguments||{}};
        if(s.route!=='COMPOSIO_V31'||path!==expected||method!=='post'||!body||Object.keys(body).some(function(k){return ['tool_slug','arguments'].indexOf(k)<0;})||body.tool_slug!==s.tool||hash(payload.arguments)!==s.payloadHash||s.write)fail('COMPOSIO_SCOPE_DENIED');
      }
      return call();
    }
    if(!composioTask)fail('DIRECT_TRANSPORT_BYPASS_DENIED');
    const discovery=(method==='get'&&path==='/connected_accounts?statuses=ACTIVE&limit=100&account_type=PRIVATE')||
      (method==='post'&&path==='/tool_router/session')||
      (method==='post'&&/^\/tool_router\/session\/[^/]+\/search$/.test(path))||
      (method==='post'&&/^\/tool_router\/session\/[^/]+\/execute_meta$/.test(path)&&body&&body.slug==='COMPOSIO_MANAGE_CONNECTIONS'&&body.arguments&&Array.isArray(body.arguments.toolkits)&&body.arguments.toolkits.length===1&&['list','add'].indexOf(body.arguments.toolkits[0].action)>=0)||
      (method==='post'&&/^\/tools\/execute\/(GMAIL|GOOGLEDRIVE)_[A-Z_]+\/input$/.test(path));
    if(!discovery)fail('DISCOVERY_OPERATION_DENIED');
    const p=governanceRuntimePrincipal_(),id=composioTask+':discovery:'+Utilities.getUuid(),s={agentId:p.id,tool:'COMPOSIO_DISCOVERY',service:'composio',operation:'discovery',target:{method:method,path:path},scopes:['composio.discovery'],route:'COMPOSIO_V31',budgetEUR:0,write:false,payloadHash:hash(body||null),evidenceContract:{readPath:'discovery-response',expectedHash:'owner_required'}};
    return run(prepare(id,s,p),s,p,function(){return composioTransport(method,path,body,call);});
  }
  return Object.freeze({ownerPrevalidate:ownerPrevalidate,withComposioTask:withComposioTask,composioTransport:composioTransport,captureMetadataList:captureMetadataList,nativeMetadataWire:nativeMetadataWire,providerWire:providerWire,ownerVerified:ownerVerified,prepare:prepare,run:run,guard:guard,wire:wire,bindWire:bindWire,composioWire:composioWire,verdict:verdict,snapshot:read,invalidate:invalidate,hash:hash,policyVersion:policy});
})();
function governanceRuntimePrincipal_(){return {id:'icarus-runtime',role:'executor'};}
function governanceGoogleSpec_(task,plan){
  const d=googlePluginRegistry_()[plan.service],write=d.writeOperations.indexOf(plan.operation)>=0&&!plan.candidate;
  const target=plan.service==='calendar'?{calendar:'primary',eventId:plan.eventId|| (write?sha256Hex_('ICARUS:'+task.task_id):''),window:!plan.eventId?googleBundleWindow_(task,plan):null}:{resourceId:plan.resourceId||'owner',range:plan.range||''};
  const expected=write?IcarusGovernance.hash({plan:plan,target:target}):'executor_read_requires_owner';
  return {agentId:'icarus-runtime',tool:d.tool,service:plan.service,operation:plan.operation,target:target,scopes:googlePluginRequiredScopes_(plan.service,plan.operation),route:'GOOGLE_NATIVE',budgetEUR:0,write:write,payloadHash:IcarusGovernance.hash(plan),evidenceContract:{readPath:'native:'+plan.service+':'+plan.operation,expectedHash:expected}};
}
function governanceExecuteGoogle_(task,plan,call){const s=governanceGoogleSpec_(task,plan),p=governanceRuntimePrincipal_();const permit=IcarusGovernance.prepare(task.task_id,s,p);return IcarusGovernance.run(permit,s,p,call);}
function governanceExecuteComposio_(task,session,tool,args,account,call){
  if(PropertiesService.getScriptProperties().getProperty('COMPOSIO_ZERO_COST_VERIFIED')!=='true')throw new Error('GOVERNANCE_ZERO_COST_UNVERIFIED');
  const p=governanceRuntimePrincipal_(),s={agentId:p.id,tool:tool,service:tool.indexOf('GMAIL_')===0?'gmail':'drive',operation:'read',target:{session:session,account:account},scopes:['READ:'+tool],route:'COMPOSIO_V31',budgetEUR:0,write:false,payloadHash:IcarusGovernance.hash(args),evidenceContract:{readPath:'composio:'+tool,expectedHash:'executor_read_requires_owner'}};
  return IcarusGovernance.run(IcarusGovernance.prepare(task.task_id,s,p),s,p,call);
}

function governanceReason_(task,call){
  if(PropertiesService.getScriptProperties().getProperty('GEMINI_ZERO_COST_VERIFIED')!=='true')throw new Error('GOVERNANCE_ZERO_COST_UNVERIFIED');
  const model=geminiModel_(),body=geminiRequestBody_(task,runtimeGenome_(),reasoningContext_(task));
  const p=governanceRuntimePrincipal_(),s={agentId:p.id,tool:'GEMINI_REASON',service:'gemini',operation:'reasoning',target:{model:model},scopes:['provider.reason'],route:'GEMINI_DIRECT',budgetEUR:0,write:false,payloadHash:IcarusGovernance.hash(body),evidenceContract:{readPath:'reasoning-log',expectedHash:'owner_required'}};
  return IcarusGovernance.run(IcarusGovernance.prepare(task.task_id+':reasoning',s,p),s,p,call);
}
