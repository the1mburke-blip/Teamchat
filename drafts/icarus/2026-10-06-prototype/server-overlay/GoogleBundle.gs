/** Google Capability Bundle v1. Model selects a tool; deterministic authority remains the original task. */
function googleBundleRange_(range) {
  if(typeof range!=='string'||range.length>96) throw new Error('GOOGLE_RANGE_DENIED');
  const m=range.match(/^(?:([A-Za-z_][A-Za-z0-9_ ]{0,40})!)?([A-Z]{1,3})([1-9][0-9]{0,5})(?::([A-Z]{1,3})([1-9][0-9]{0,5}))?$/);
  if(!m) throw new Error('GOOGLE_RANGE_DENIED');
  function col(s){return s.split('').reduce(function(n,c){return n*26+c.charCodeAt(0)-64;},0);}
  const width=col(m[4]||m[2])-col(m[2])+1,height=Number(m[5]||m[3])-Number(m[3])+1;
  if(width<1||height<1||width*height>100) throw new Error('GOOGLE_RANGE_TOO_LARGE');
  return {range:range,width:width,height:height};
}
function googleBundleValidateOperation_(original, selection) {
  const text=String(original||''), p=selection;
  if(!p||typeof p!=='object'||Array.isArray(p)||JSON.stringify(p).length>6000) throw new Error('GOOGLE_OPERATION_DENIED');
  const d=googlePluginRegistry_()[p.service];
  if(!d||googlePluginService_(text)!==p.service||['calendar','sheets','docs'].indexOf(p.service)<0) throw new Error('GOOGLE_OPERATION_ROUTE_DENIED');
  const allowed={list_events:['timeMin','timeMax'],event_metadata:['eventId'],create_event:['summary','start','end'],sheet_metadata:['resourceId'],read_range:['resourceId','range'],update_range:['resourceId','range','text'],doc_metadata:['resourceId'],read_text:['resourceId'],append_text:['resourceId','text'],insert_text:['resourceId','text','index']};
  if(d.operations.concat(d.writeOperations).indexOf(p.operation)<0)throw new Error('GOOGLE_OPERATION_SERVICE_DENIED');
  const keys=allowed[p.operation];
  if(!keys||Object.keys(p).some(function(k){return ['service','operation'].concat(keys).indexOf(k)<0;})) throw new Error('GOOGLE_UNSUPPORTED_OPERATION');
  const write=d.writeOperations.indexOf(p.operation)>=0;
  if(write && (!/^\s*(create|update|append|insert)\b/i.test(text)||/\b(do not|don't|never|without|read.only)\b/i.test(text))) throw new Error('GOOGLE_READ_WRITE_EXPANSION_DENIED');
  if(!write && /^\s*(create|update|append|insert|delete|send)\b/i.test(text)) throw new Error('GOOGLE_ACTION_MISMATCH');
  const verbs={list_events:/\b(calendar|upcoming|events)\b/i,event_metadata:/\b(event|metadata)\b/i,sheet_metadata:/\b(metadata|spreadsheet)\b/i,read_range:/\b(read|cells|range)\b/i,update_range:/^\s*update\b/i,doc_metadata:/\b(metadata|document|doc)\b/i,read_text:/\b(read|document|doc)\b/i,append_text:/^\s*append\b/i,insert_text:/^\s*insert\b/i,create_event:/^\s*create\b/i};
  if(!verbs[p.operation].test(text)) throw new Error('GOOGLE_OPERATION_AUTHORITY_DENIED');
  function literal(value,name){if(typeof value!=='string'||!value||!text.includes(value)||((name==='RESOURCE'||name==='EVENT')&&!new RegExp('(?:^|[^A-Za-z0-9_-])'+value+'(?:$|[^A-Za-z0-9_-])').test(text))) throw new Error('GOOGLE_'+name+'_EXPANSION_DENIED');if(['START','END','TIME'].indexOf(name)>=0&&!new RegExp('(?:^|[^A-Za-z0-9_])'+value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?:$|[^A-Za-z0-9_])').test(text))throw new Error('GOOGLE_'+name+'_EXPANSION_DENIED');}
  const authorityText=text.replace(/"[^"]*"/g,'');
  if(p.service!=='calendar') {literal(p.resourceId,'RESOURCE');if(!/^[A-Za-z0-9_-]{8,128}$/.test(p.resourceId)) throw new Error('GOOGLE_RESOURCE_DENIED');if(!authorityText.includes(p.resourceId))throw new Error('GOOGLE_RESOURCE_EXPANSION_DENIED');}
  if(/\bmetadata\b/i.test(authorityText)&&['sheet_metadata','doc_metadata','event_metadata'].indexOf(p.operation)<0)throw new Error('GOOGLE_METADATA_CONTENT_EXPANSION_DENIED');
  if(p.operation==='event_metadata'){literal(p.eventId,'EVENT');if(!/^[A-Za-z0-9_-]{5,128}$/.test(p.eventId)) throw new Error('GOOGLE_EVENT_DENIED');}
  if(p.range){const requested=authorityText.match(/(?:^\s*update|\bcells|\brange)\s+((?:[A-Za-z_][A-Za-z0-9_ ]{0,40}!)?[A-Z]{1,3}[1-9][0-9]{0,5}(?::[A-Z]{1,3}[1-9][0-9]{0,5})?)(?=\s|$|[.,])/i);if(!requested||requested[1]!==p.range)throw new Error('GOOGLE_RANGE_EXPANSION_DENIED');googleBundleRange_(p.range);}
  if(['read_range','update_range'].indexOf(p.operation)>=0&&!p.range) throw new Error('GOOGLE_RANGE_REQUIRED');
  if(['append_text','insert_text','update_range'].indexOf(p.operation)>=0){literal(p.text,'TEXT');if(p.text.length>2000||/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(p.text)) throw new Error('GOOGLE_TEXT_DENIED');}
  if(p.operation==='update_range') {
    const r=googleBundleRange_(p.range);if(r.width!==1||r.height!==1)throw new Error('GOOGLE_WRITE_SINGLE_CELL_REQUIRED');
    const quoted=text.match(/"([^"]*)"/g)||[], unquoted=text.match(/\b(?:to|with)\s+(.+?)\s+(?:in|on)\s+(?:the\s+)?(?:spreadsheet|Google Sheets)\b/i);
    const requested=quoted.length===1?quoted[0].slice(1,-1):quoted.length===0&&unquoted?unquoted[1]:null;
    if(requested!==p.text)throw new Error('GOOGLE_WRITE_VALUE_REQUIRED');
  }
  if(['append_text','insert_text'].indexOf(p.operation)>=0){const quoted=text.match(/"([^"]*)"/g)||[];if(quoted.length!==1||quoted[0].slice(1,-1)!==p.text)throw new Error('GOOGLE_TEXT_EXPANSION_DENIED');}
  if(p.operation==='insert_text' && (!Number.isSafeInteger(p.index)||p.index<1||p.index>10000||!(text.match(/\bindex\s+([0-9]+)\b/i)||[])[1]||Number((text.match(/\bindex\s+([0-9]+)\b/i)||[])[1])!==p.index)) throw new Error('GOOGLE_INDEX_EXPANSION_DENIED');
  if(p.operation==='create_event') {
    if(/\bcandidate\b/i.test(text)) return {service:p.service,operation:p.operation,candidate:true,requestedObjective:text};
    literal(p.summary,'SUMMARY');if(!text.includes('"'+p.summary+'"'))throw new Error('GOOGLE_SUMMARY_EXPANSION_DENIED');literal(p.start,'START');literal(p.end,'END');
    if(p.summary.length>200||![p.start,p.end].every(function(v){return /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v));})||Date.parse(p.end)<=Date.parse(p.start)||Date.parse(p.end)-Date.parse(p.start)>86400000) throw new Error('GOOGLE_EVENT_BOUNDS_DENIED');
  }
  if(p.operation==='list_events' && (p.timeMin||p.timeMax)) {
    literal(p.timeMin,'TIME');literal(p.timeMax,'TIME');
    if(!Number.isFinite(Date.parse(p.timeMin))||!Number.isFinite(Date.parse(p.timeMax))||Date.parse(p.timeMax)<=Date.parse(p.timeMin)||Date.parse(p.timeMax)-Date.parse(p.timeMin)>7*86400000) throw new Error('GOOGLE_TIME_BOUNDS_DENIED');
  }
  return JSON.parse(JSON.stringify(p));
}
function googleBundleWindow_(task, plan) {
  if(plan.timeMin) return {timeMin:plan.timeMin,timeMax:plan.timeMax};
  const now=new Date(task.created_utc || nowIso_());
  if(!Number.isFinite(now.getTime())) throw new Error('GOOGLE_TIME_UNKNOWN');
  // Tomorrow uses the owner's named zone, not the scheduler's server timezone.
  const zone=PropertiesService.getScriptProperties().getProperty('GOOGLE_OWNER_TIME_ZONE')||'Europe/Dublin';
  if(/\btomorrow\b/i.test(task.objective)) {
    const local=Utilities.formatDate(now,zone,'yyyy-MM-dd');
    const tomorrow=new Date(local+'T12:00:00Z');tomorrow.setUTCDate(tomorrow.getUTCDate()+1);
    function midnight(day){let instant=new Date(day+'T00:00:00Z');for(let i=0;i<3;i++){const z=Utilities.formatDate(instant,zone,'Z');if(!/^[+-]\d{4}$/.test(z))throw new Error('GOOGLE_TIME_UNKNOWN');const offset=(z[0]==='-'?-1:1)*(Number(z.slice(1,3))*60+Number(z.slice(3,5)));instant=new Date(Date.parse(day+'T00:00:00Z')-offset*60000);}return instant.toISOString();}
    const start=tomorrow.toISOString().slice(0,10);tomorrow.setUTCDate(tomorrow.getUTCDate()+1);
    return {timeMin:midnight(start),timeMax:midnight(tomorrow.toISOString().slice(0,10))};
  }
  return {timeMin:now.toISOString(),timeMax:new Date(now.getTime()+7*86400000).toISOString()};
}
function googleBundleRequest_(method,url,body) {
  const allowed=/^https:\/\/(www\.googleapis\.com\/calendar\/v3\/calendars\/primary\/events(?:\/[A-Za-z0-9_-]+)?|sheets\.googleapis\.com\/v4\/spreadsheets\/[A-Za-z0-9_-]+(?:\/values\/[^?#]+)?|docs\.googleapis\.com\/v1\/documents\/[A-Za-z0-9_-]+(?::batchUpdate)?)(?:\?[^#\s]*)?$/.test(url);
  if(!allowed || ['get','post','put'].indexOf(method)<0)throw new Error('GOOGLE_ENDPOINT_DENIED');
  const token=ScriptApp.getOAuthToken(),options={method:method,headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false};
  if(body){options.contentType='application/json';options.payload=JSON.stringify(body);}
  let response;try{response=UrlFetchApp.fetch(url,options);}catch(_){throw new Error(method==='get'?'GOOGLE_TRANSPORT_UNKNOWN':'GOOGLE_WRITE_OUTCOME_UNKNOWN');}
  const code=response.getResponseCode();
  if(code===401) throw new Error('GOOGLE_EXPIRED_RECONNECT_REQUIRED');
  if(code===403) throw new Error('GOOGLE_PERMISSION_RECONNECT_REQUIRED');
  if(code<200||code>=300) throw new Error('GOOGLE_HTTP_'+code);
  const raw=String(response.getContentText()||'');
  if(raw.length>64000||(token&&raw.includes(token))) throw new Error('GOOGLE_RESPONSE_DENIED');
  let data;try{data=JSON.parse(raw);}catch(_){throw new Error('GOOGLE_INVALID_JSON');}
  if(!data||typeof data!=='object'||Array.isArray(data)) throw new Error('GOOGLE_INVALID_RESPONSE');
  return data;
}
function googleBundleEvent_(event) {
  if(!event||typeof event.id!=='string') throw new Error('GOOGLE_INVALID_RESPONSE');
  return {id:event.id,summary:String(event.summary||'').slice(0,200),start:event.start||{},end:event.end||{},status:String(event.status||''),htmlLink:String(event.htmlLink||'')};
}
function googleBundleDoc_(plan) {
  const fields=plan.operation==='doc_metadata'?'documentId,title,revisionId':'documentId,title,revisionId,body(content(startIndex,endIndex,paragraph(elements(textRun(content)))))';
  const data=googleBundleRequest_('get','https://docs.googleapis.com/v1/documents/'+encodeURIComponent(plan.resourceId)+'?fields='+fields);
  if(data.documentId!==plan.resourceId)throw new Error('GOOGLE_INVALID_RESPONSE');
  if(plan.operation==='doc_metadata')return {service:'docs',documentId:data.documentId,title:String(data.title||'').slice(0,200),revisionId:String(data.revisionId||'')};
  if(data.documentId!==plan.resourceId||!data.body||!Array.isArray(data.body.content)) throw new Error('GOOGLE_INVALID_RESPONSE');
  const elements=data.body.content;
  if(elements.some(function(e){return !e.paragraph&&e.startIndex!==0;})) throw new Error('GOOGLE_DOC_COMPLEX_CONTENT_UNSUPPORTED');
  const text=elements.map(function(e){return (e.paragraph&&e.paragraph.elements||[]).map(function(part){return part.textRun?String(part.textRun.content||''):'';}).join('');}).join('');
  return {service:'docs',documentId:data.documentId,title:String(data.title||'').slice(0,200),revisionId:String(data.revisionId||''),text:text.slice(0,10000),truncated:text.length>10000};
}
function googleBundleRead_(task,plan) {
  if(plan.candidate) return {service:'calendar',candidate:true,requestedObjective:plan.requestedObjective,scope:'candidate only; no Calendar mutation'};
  if(plan.service==='calendar') {
    let url='https://www.googleapis.com/calendar/v3/calendars/primary/events';
    if(plan.eventId)url+='/'+encodeURIComponent(plan.eventId);
    else {const w=googleBundleWindow_(task,plan);url+='?maxResults=10&singleEvents=true&orderBy=startTime&timeMin='+encodeURIComponent(w.timeMin)+'&timeMax='+encodeURIComponent(w.timeMax);}
    const data=googleBundleRequest_('get',url);
    return plan.eventId ? {service:'calendar',event:googleBundleEvent_(data)} : {service:'calendar',events:(data.items||[]).slice(0,10).map(googleBundleEvent_),truncated:!!data.nextPageToken,window:googleBundleWindow_(task,plan)};
  }
  if(plan.service==='sheets') {
    const base='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(plan.resourceId);
    if(plan.operation==='sheet_metadata'){const data=googleBundleRequest_('get',base+'?fields=spreadsheetId,properties(title),sheets(properties(sheetId,title,gridProperties))');if(data.spreadsheetId!==plan.resourceId)throw new Error('GOOGLE_INVALID_RESPONSE');return {service:'sheets',spreadsheetId:data.spreadsheetId,title:(data.properties||{}).title,sheets:(data.sheets||[]).slice(0,20)};}
    const r=googleBundleRange_(plan.range),data=googleBundleRequest_('get',base+'/values/'+encodeURIComponent(plan.range)+'?valueRenderOption=UNFORMATTED_VALUE');
    const values=data.values||[];if(!Array.isArray(values)||values.length>r.height||values.some(function(row){return !Array.isArray(row)||row.length>r.width;}))throw new Error('GOOGLE_RANGE_RESPONSE_DENIED');
    return {service:'sheets',spreadsheetId:plan.resourceId,range:plan.range,values:values};
  }
  const doc=googleBundleDoc_(plan);
  if(plan.operation==='doc_metadata')delete doc.text;
  return doc;
}
function googleBundleWrite_(task,plan,before) {
  if(plan.candidate)return before;
  if(plan.service==='calendar') {
    const id=sha256Hex_('ICARUS:'+task.task_id);
    googleBundleRequest_('post','https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=none',{id:id,summary:plan.summary,start:{dateTime:plan.start},end:{dateTime:plan.end},reminders:{useDefault:false}});
    return googleBundleRead_(task,{service:'calendar',operation:'event_metadata',eventId:id});
  }
  if(plan.service==='sheets') {
    googleBundleRequest_('put','https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(plan.resourceId)+'/values/'+encodeURIComponent(plan.range)+'?valueInputOption=RAW',{range:plan.range,majorDimension:'ROWS',values:[[plan.text]]});
    return googleBundleRead_(task,plan);
  }
  if(plan.text.length+before.text.length>10000 || (plan.operation==='insert_text' && plan.index>before.text.length))throw new Error('GOOGLE_DOC_WRITE_BOUNDS_DENIED');
  if(before.truncated||!before.revisionId)throw new Error('GOOGLE_DOC_WRITE_BOUNDS_UNKNOWN');
  const insert={text:plan.text};if(plan.operation==='append_text')insert.endOfSegmentLocation={};else insert.location={index:plan.index};
  googleBundleRequest_('post','https://docs.googleapis.com/v1/documents/'+encodeURIComponent(plan.resourceId)+':batchUpdate',{writeControl:{requiredRevisionId:before.revisionId},requests:[{insertText:insert}]});
  return googleBundleRead_(task,plan);
}
function executeGoogleBundleTask_(taskId,objective,selection) {
  let task=getTask_(taskId);const service=googlePluginService_(task.objective),device=String(task.source).slice(8);
  const ownerHash=googlePluginOwner_(device);
  const plan=googleBundleValidateOperation_(task.objective,selection),stored=task.google_plugin_plan_json;
  if(stored&&stored!==JSON.stringify(plan))throw new Error('GOOGLE_PLAN_CHANGED_DENIED');
  const descriptor=googlePluginRegistry_()[service],write=descriptor.writeOperations.indexOf(plan.operation)>=0;
  requireCapability_('google.'+service+'.'+(write?'write':'read'));
  googlePluginStore_(taskId,{google_plugin_service:service,google_plugin_plan_json:JSON.stringify(plan),google_plugin_tool:descriptor.tool+'_'+plan.operation.toUpperCase()});
  const state=googlePluginConnection_(device,service,false,plan.operation);
  if(['MISSING','EXPIRED','REVOKED'].indexOf(state.state)>=0){if(task.google_plugin_write_intent)throw new Error('GOOGLE_WRITE_OUTCOME_UNKNOWN');transitionTask_(taskId,'PENDING_AUTH',{evidence_ref:state.reason+'; common Google authorization required'});return taskForClient_(taskId);}
  if(state.state!=='CONNECTED')throw new Error(state.reason||'GOOGLE_AUTHORIZATION_UNKNOWN');
  if(task.status==='PENDING_AUTH')transitionTask_(taskId,'EXECUTING');
  if(task.google_plugin_write_intent)throw new Error('GOOGLE_WRITE_OUTCOME_UNKNOWN');
  const before=googleBundleRead_(task,plan);
  let result=before;
  if(write&&!plan.candidate) {
    googlePluginStore_(taskId,{google_plugin_write_intent:sha256Hex_(JSON.stringify(plan)),google_plugin_before_json:JSON.stringify(before)});
    SpreadsheetApp.flush();task=getTask_(taskId);
    if(!task.google_plugin_write_intent)throw new Error('GOOGLE_INTENT_NOT_PERSISTED');
    result=googleBundleWrite_(task,plan,before);
  }
  const executed=appendLog_(taskId,'EXECUTING',write?'WRITE_COMPLETE':'READ_COMPLETE','Native bounded Google operation completed.','TASK_QUEUE:'+taskId,plan.operation);
  transitionTask_(taskId,'VERIFYING');googlePluginOwner_(device);googlePluginPrincipal_(service,ownerHash);
  let repeat=googleBundleRead_(task,plan.service==='calendar'&&write&&!plan.candidate ? {service:'calendar',operation:'event_metadata',eventId:sha256Hex_('ICARUS:'+taskId)} : plan);
  let match=JSON.stringify(result)===JSON.stringify(repeat);
  if(write&&!plan.candidate){if(service==='sheets')match=match&&JSON.stringify(repeat.values)===JSON.stringify([[plan.text]]);if(service==='calendar')match=match&&repeat.event.summary===plan.summary&&Date.parse(repeat.event.start.dateTime)===Date.parse(plan.start)&&Date.parse(repeat.event.end.dateTime)===Date.parse(plan.end);if(service==='docs'){const expected=plan.operation==='append_text'?before.text.slice(0,-1)+plan.text+before.text.slice(-1):before.text.slice(0,plan.index-1)+plan.text+before.text.slice(plan.index-1);match=match&&!repeat.truncated&&repeat.text===expected;}}
  const verified=appendLog_(taskId,'VERIFYING','READ_COMPLETE','Native repeat read completed.','TASK_QUEUE:'+taskId,plan.operation);
  googlePluginStore_(taskId,{google_plugin_result_json:JSON.stringify(repeat),google_plugin_execute_log:executed,google_plugin_verify_log:verified});
  transitionTask_(taskId,match?'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION':'PARTIAL',{evidence_ref:'GOOGLE_NATIVE '+plan.operation+'; '+(match?'bounded readback matched':'readback mismatch')+'; owner verification required'});
  return taskForClient_(taskId);
}
