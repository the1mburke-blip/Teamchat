// ICARUS Composio v3.1 server-side execution adapter.
// Secret: COMPOSIO_PROJECT_API_KEY in Apps Script Properties only.
// Optional: COMPOSIO_USER_ID. If omitted, ICARUS discovers exactly one active
// Composio user_id from the project and persists it. If the project has no
// active accounts yet, ICARUS uses the stable non-secret id "icarus-owner".
// Optional governance overrides:
//   COMPOSIO_ALLOWED_READ_TOOLS_JSON   e.g. ["GOOGLEDRIVE_FIND_FILE"]
//   COMPOSIO_ALLOWED_WRITE_TOOLS_JSON  exact tool slugs; empty by default.

function composioApiConfig_() {
  const props = PropertiesService.getScriptProperties();
  const apiKey = String(props.getProperty('COMPOSIO_PROJECT_API_KEY') || '').trim();
  if (!apiKey) throw new Error('COMPOSIO_PROJECT_API_KEY_NOT_CONFIGURED');
  return {apiKey:apiKey, base:'https://backend.composio.dev/api/v3.1'};
}

function composioJsonProperty_(name) {
  const raw = PropertiesService.getScriptProperties().getProperty(name);
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error(name + '_MUST_BE_JSON_ARRAY');
  return parsed.map(function(v){return String(v || '').trim().toUpperCase();}).filter(Boolean);
}

function composioErrorDetail_(parsed) {
  if (!parsed) return '';
  if (typeof parsed.error === 'string') return parsed.error.slice(0,300);
  if (parsed.error && typeof parsed.error === 'object') {
    return String(parsed.error.message || parsed.error.code || JSON.stringify(parsed.error)).slice(0,300);
  }
  return String(parsed.message || '').slice(0,300);
}

function composioChargeAmount_(obj) {
  if (!obj || typeof obj !== 'object') return 0;
  const charges = [obj.instant_charge,obj.premium_charge];
  if (obj.data && typeof obj.data === 'object') charges.push(obj.data.instant_charge,obj.data.premium_charge);
  let total=0;
  charges.forEach(function(charge){
    if (!charge || charge.amount === undefined || charge.amount === null || charge.amount === '') return;
    const n=Number(charge.amount);
    if (Number.isFinite(n)) total += n;
  });
  return total;
}

function composioRequest_(method, path, body) {
  return IcarusGovernance.composioTransport(method,path,body,function(){return composioTransportHttp_(method,path,body);});
}
function composioTransportHttp_(method,path,body) {
  // Recheck even on direct helper access: only the active governed request may fetch.
  IcarusGovernance.composioTransport(method,path,body,function(){return null;});
  const cfg = composioApiConfig_();
  const options = {
    method:String(method || 'get').toLowerCase(),
    headers:{'x-api-key':cfg.apiKey,'Accept':'application/json'},
    muteHttpExceptions:true,
    followRedirects:false
  };
  if (body !== undefined && body !== null) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }
  const resp = UrlFetchApp.fetch(cfg.base + path, options);
  const code = resp.getResponseCode();
  const raw = String(resp.getContentText() || '');
  if (raw.length > ICARUS.MAX_GATEWAY_RESPONSE) throw new Error('COMPOSIO_RESPONSE_TOO_LARGE');
  let parsed={};
  try { parsed = raw ? JSON.parse(raw) : {}; }
  catch (_) { throw new Error('COMPOSIO_INVALID_JSON_HTTP_' + code); }
  if (code < 200 || code >= 300) throw new Error('COMPOSIO_HTTP_' + code + (composioErrorDetail_(parsed) ? ':' + composioErrorDetail_(parsed) : ''));
  if (composioChargeAmount_(parsed) > 0) throw new Error('COMPOSIO_NONZERO_CHARGE_REPORTED');
  return parsed;
}

function composioData_(obj) {
  if (obj && typeof obj === 'object' && obj.data && typeof obj.data === 'object') return obj.data;
  return obj || {};
}

function composioFindString_(obj, key) {
  if (!obj || typeof obj !== 'object') return '';
  if (typeof obj[key] === 'string' && obj[key].trim()) return obj[key].trim();
  const keys = Object.keys(obj);
  for (let i=0;i<keys.length;i++) {
    const v=obj[keys[i]];
    if (v && typeof v === 'object') {
      const found=composioFindString_(v,key);
      if (found) return found;
    }
  }
  return '';
}

function composioResolveUserId_() {
  const props=PropertiesService.getScriptProperties();
  const configured=String(props.getProperty('COMPOSIO_USER_ID') || '').trim();
  if (configured) return configured;
  const listed=composioRequest_('get','/connected_accounts?statuses=ACTIVE&limit=100&account_type=PRIVATE');
  const items=Array.isArray(listed.items) ? listed.items : (Array.isArray(composioData_(listed).items) ? composioData_(listed).items : []);
  const ids=[];
  items.forEach(function(a){
    const id=String(a && a.user_id || '').trim();
    if (id && ids.indexOf(id) < 0) ids.push(id);
  });
  if (ids.length > 1) throw new Error('COMPOSIO_MULTIPLE_USER_IDS_SET_COMPOSIO_USER_ID');
  const resolved=ids.length === 1 ? ids[0] : 'icarus-owner';
  props.setProperty('COMPOSIO_USER_ID',resolved);
  return resolved;
}

function composioStateHeaders_() {
  return ['task_id','session_id','toolkit','tool_slug','account_id','auth_url','phase','arguments_json','result_json','execute_log_id','verify_log_id','updated_utc'];
}

function composioStateSheet_() {
  let sh=stateSpreadsheet_().getSheetByName(ICARUS.SHEETS.COMPOSIO);
  if (!sh) { sh=stateSpreadsheet_().insertSheet(ICARUS.SHEETS.COMPOSIO); sh.appendRow(composioStateHeaders_()); }
  else if (sh.getLastRow() === 0) sh.appendRow(composioStateHeaders_());
  return sh;
}

function composioState_(taskId) {
  const sh=composioStateSheet_();
  const data=sh.getDataRange().getValues();
  if (data.length < 2) return null;
  const headers=data[0].map(String), idIdx=headers.indexOf('task_id');
  for (let r=1;r<data.length;r++) if (String(data[r][idIdx]) === String(taskId)) {
    const o={}; headers.forEach(function(h,i){if(h)o[h]=data[r][i];}); return o;
  }
  return null;
}

function upsertComposioState_(taskId, patch) {
  const sh=composioStateSheet_();
  const headers=sh.getRange(1,1,1,Math.max(sh.getLastColumn(),1)).getValues()[0].map(String);
  const data=sh.getDataRange().getValues(), idIdx=headers.indexOf('task_id');
  let row=-1;
  for (let r=1;r<data.length;r++) if (String(data[r][idIdx]) === String(taskId)) {row=r+1;break;}
  if (row < 0) { const values=new Array(headers.length).fill(''); values[idIdx]=taskId; sh.appendRow(values); row=sh.getLastRow(); }
  const merged=Object.assign({},patch || {},{updated_utc:nowIso_()});
  Object.keys(merged).forEach(function(k){const idx=headers.indexOf(k);if(idx>=0)sh.getRange(row,idx+1).setValue(merged[k]);});
  SpreadsheetApp.flush();
  return composioState_(taskId);
}

function composioCreateSession_(taskId) {
  const existing=composioState_(taskId);
  if (existing && String(existing.session_id || '').trim()) return String(existing.session_id).trim();
  const created=composioRequest_('post','/tool_router/session',{
    user_id:composioResolveUserId_(),
    manage_connections:{enable:true,enable_wait_for_connections:false,enable_connection_removal:false}
  });
  const data=composioData_(created);
  const sessionId=String(data.session_id || created.session_id || data.id || created.id || '').trim();
  if (!/^trs_[A-Za-z0-9_-]+$/.test(sessionId)) throw new Error('COMPOSIO_SESSION_ID_MISSING');
  upsertComposioState_(taskId,{session_id:sessionId,phase:'SESSION_CREATED'});
  return sessionId;
}

function composioDiscoveryUseCase_(objective) {
  const text=String(objective || '').slice(0,ICARUS.MAX_TEXT);
  if (/\b(find|search|list|locate)\b/i.test(text) && /\b(drive|files?)\b/i.test(text)) {
    return 'Search or list Google Drive files by name. Return existing file metadata (name and ID) only. Do not export or download content. User request: ' + text;
  }
  return text;
}
function composioSearch_(sessionId, objective) {
  return composioRequest_('post','/tool_router/session/' + encodeURIComponent(sessionId) + '/search',{
    queries:[{use_case:composioDiscoveryUseCase_(objective)}],
    search_strategy:'tool_search'
  });
}

function composioPickRoute_(searchResponse, previous, objective) {
  const data=composioData_(searchResponse);
  const results=Array.isArray(data.results) ? data.results : (Array.isArray(searchResponse.results) ? searchResponse.results : []);
  if (!results.length) throw new Error('COMPOSIO_NO_TOOL_MATCH');
  const first=results[0] || {};
  const tools=Array.isArray(first.primary_tool_slugs) ? first.primary_tool_slugs : [];
  const toolkits=Array.isArray(first.toolkits) ? first.toolkits : [];
  let selected=tools[0] || '';
  // Drive metadata lookup must not follow a top-ranked export recommendation.
  // Select only a discovered lookup tool; never invent a tool slug.
  if (/\b(find|search|list|locate)\b/i.test(String(objective || '')) && /\b(drive|files?)\b/i.test(String(objective || ''))) {
    const lookup=tools.filter(function(slug){return /^GOOGLEDRIVE_.*(?:FIND|SEARCH|LIST).*FILES?$/.test(String(slug).toUpperCase());});
    if (!lookup.length) throw new Error('COMPOSIO_NO_DISCOVERED_DRIVE_LOOKUP_TOOL');
    selected=lookup[0];
  }
  const toolSlug=String((previous && previous.tool_slug) || selected).trim().toUpperCase();
  const toolkit=String((previous && previous.toolkit) || toolkits[0] || '').trim().toLowerCase();
  if (!toolSlug || !toolkit) throw new Error('COMPOSIO_ROUTE_INCOMPLETE');
  const statuses=Array.isArray(data.toolkit_connection_statuses) ? data.toolkit_connection_statuses :
    (Array.isArray(searchResponse.toolkit_connection_statuses) ? searchResponse.toolkit_connection_statuses : []);
  const status=statuses.find(function(s){return String(s && s.toolkit || '').trim().toLowerCase() === toolkit;});
  // This exact machine field was the old parser defect. Unknown is never coerced.
  if (!status || typeof status.has_active_connection !== 'boolean') throw new Error('COMPOSIO_CONNECTION_STATE_UNKNOWN');
  return {toolSlug:toolSlug,toolkit:toolkit,hasActiveConnection:status.has_active_connection};
}

function composioManage_(sessionId, toolkit, action) {
  return composioRequest_('post','/tool_router/session/' + encodeURIComponent(sessionId) + '/execute_meta',{
    slug:'COMPOSIO_MANAGE_CONNECTIONS',
    arguments:{toolkits:[{name:toolkit,action:action}],session_id:sessionId}
  });
}

function composioManageState_(response, toolkit) {
  const data=composioData_(response);
  const results=(data && data.results && typeof data.results === 'object') ? data.results : {};
  let entry=null;
  Object.keys(results).some(function(k){
    if (String(k).toLowerCase() === String(toolkit).toLowerCase()) {entry=results[k];return true;}
    return false;
  });
  if (!entry || typeof entry !== 'object') return {status:'unknown',accounts:[],redirectUrl:composioFindString_(response,'redirect_url')};
  const accounts=Array.isArray(entry.accounts) ? entry.accounts : [];
  // Platform list can return one explicitly identified active account instead of an array.
  if (!accounts.length && entry.has_active_connection === true &&
      String(entry.status || '').trim().toLowerCase() === 'active' &&
      typeof entry.connected_account_id === 'string' && entry.connected_account_id.trim()) {
    accounts.push({id:entry.connected_account_id.trim(),status:'ACTIVE'});
  }
  return {
    status:String(entry.status || '').trim().toLowerCase() || 'unknown',
    accounts:accounts,
    redirectUrl:composioFindString_(entry,'redirect_url') || composioFindString_(response,'redirect_url')
  };
}

function composioSelectAccount_(accounts, previousAccountId) {
  const active=(accounts || []).filter(function(a){return String(a && a.status || '').toUpperCase() === 'ACTIVE';});
  if (previousAccountId) {
    const match=active.find(function(a){return String(a.id) === String(previousAccountId);});
    if (match) return String(match.id);
    throw new Error('COMPOSIO_SELECTED_ACCOUNT_NO_LONGER_ACTIVE');
  }
  const defaults=active.filter(function(a){return a && a.is_default === true;});
  if (defaults.length === 1) return String(defaults[0].id);
  if (active.length === 1) return String(active[0].id);
  if (!active.length) throw new Error('COMPOSIO_ACTIVE_ACCOUNT_MISSING');
  throw new Error('COMPOSIO_ACCOUNT_SELECTION_REQUIRED');
}

function composioToolMode_(toolSlug) {
  const slug=String(toolSlug || '').trim().toUpperCase();
  if (!/^(GMAIL|GOOGLEDRIVE)_/.test(slug)) return 'DENY';
  if (/(^|_)(CREATE|UPDATE|DELETE|SEND|POST|PUT|PATCH|REMOVE|ADD|UPLOAD|MOVE|RENAME|ARCHIVE|TRASH|REPLY|FORWARD|MARK|SHARE|INVITE)(_|$)/.test(slug)) return 'DENY';
  const explicitReads=composioJsonProperty_('COMPOSIO_ALLOWED_READ_TOOLS_JSON');
  const explicitWrites=composioJsonProperty_('COMPOSIO_ALLOWED_WRITE_TOOLS_JSON');
  // This deployment is read-only until independent governance is operational.
  if (explicitWrites.indexOf(slug) >= 0) return 'DENY';
  if (explicitReads.indexOf(slug) >= 0) return 'READ';
  const mutating=/(^|_)(CREATE|UPDATE|DELETE|SEND|POST|PUT|PATCH|REMOVE|ADD|UPLOAD|MOVE|RENAME|ARCHIVE|TRASH|CANCEL|REFUND|FULFILL|PUBLISH|INVITE|SHARE|RUN|START|STOP|REPLY|FORWARD|MARK)(_|$)/.test(slug);
  if (mutating) return 'DENY';
  if (/(^|_)(GET|LIST|SEARCH|READ|FETCH|FIND|LOOKUP|QUERY|COUNT|CHECK|DESCRIBE|VIEW|INSPECT)(_|$)/.test(slug)) return 'READ';
  return 'DENY';
}

function composioBeginAuth_(taskId, sessionId, toolkit, toolSlug) {
  const previous=composioState_(taskId) || {};
  if (String(previous.auth_url || '').indexOf('https://') === 0) return taskForClient_(taskId);
  const managed=composioManage_(sessionId,toolkit,'add');
  const state=composioManageState_(managed,toolkit);
  const url=state.redirectUrl || composioFindString_(managed,'redirect_url');
  if (!url || url.indexOf('https://') !== 0) throw new Error('COMPOSIO_AUTH_REDIRECT_MISSING');
  const accountId=composioFindString_(managed,'connected_account_id');
  upsertComposioState_(taskId,{session_id:sessionId,toolkit:toolkit,tool_slug:toolSlug,account_id:accountId || '',auth_url:url,phase:'PENDING_AUTH'});
  transitionTask_(taskId,'PENDING_AUTH',{evidence_ref:'AUTH_REQUIRED ' + url});
  appendLog_(taskId,'EXECUTING','PENDING_AUTH','Composio connection authorization required.','COMPOSIO_SESSION:'+sessionId,'toolkit='+toolkit+';tool='+toolSlug);
  return taskForClient_(taskId);
}

function composioGenerateArguments_(toolSlug, objective) {
  // Legacy compatibility seam: Composio still supports this v3.1 endpoint but marks it deprecated.
  // Isolated here so it can be replaced without touching task/session/auth state.
  const generated=composioRequest_('post','/tools/execute/' + encodeURIComponent(toolSlug) + '/input',{
    text:String(objective || '').slice(0,ICARUS.MAX_TEXT),
    system_prompt:'Generate only schema-valid arguments for the selected tool. Do not add actions beyond the user request. Do not invent identifiers.',
    version:'latest'
  });
  const data=composioData_(generated);
  const args=data.arguments || generated.arguments;
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('COMPOSIO_ARGUMENT_GENERATION_FAILED');
  return args;
}

function composioExecuteInSession_(sessionId, toolSlug, args, accountId) {
  IcarusGovernance.composioWire(sessionId,toolSlug,args,accountId);
  const payload={
    tool_slug:toolSlug,
    arguments:args || {}
  };
  // This project's Drive session uses its default active connection; per-call
  // account selection is unsupported. Keep the observed account in durable evidence.
  if (String(toolSlug).indexOf('GOOGLEDRIVE_') !== 0 && String(toolSlug).indexOf('GMAIL_') !== 0) payload.account=accountId;
  return composioRequest_('post','/tool_router/session/' + encodeURIComponent(sessionId) + '/execute',payload);
}

function composioExecutionSucceeded_(obj) {
  if (!obj || typeof obj !== 'object' || obj.error || obj.successful === false) return false;
  const d=composioData_(obj);
  return !(d && (d.error || d.successful === false));
}

function composioStable_(value) {
  const volatile={log_id:true,request_id:true,session_id:true,timestamp:true,created_at:true,updated_at:true,expires_at:true,duration:true,duration_ms:true};
  if (Array.isArray(value)) return value.map(composioStable_);
  if (value && typeof value === 'object') {
    const out={};
    Object.keys(value).sort().forEach(function(k){if(!volatile[String(k).toLowerCase()])out[k]=composioStable_(value[k]);});
    return out;
  }
  return value;
}

function composioFingerprint_(obj) {
  return sha256Hex_(JSON.stringify(composioStable_(composioData_(obj))));
}

function composioResultSummary_(obj) {
  let text='';
  try { text=JSON.stringify(composioData_(obj)); } catch(_) { text=String(composioData_(obj)); }
  if (text.length > 1200) text=text.slice(0,1200)+'…';
  return text;
}

function taskForClient_(taskId) {
  const task=getTask_(taskId);
  if (!task) throw new Error('TASK_NOT_FOUND');
  const c=googlePluginEvidence_(taskId);
  const out=Object.assign({},task);
  const g=IcarusGovernance.snapshot(taskId);if(g)out.governance={state:g.state,revision:g.revision,policyVersion:IcarusGovernance.policyVersion,evidenceRef:g.evidenceRef||'',verification:g.verification||null};
  out.evidence_fingerprint=ownerEvidenceFingerprint_(taskId);
  out.owner_verification=ownerVerificationRecord_(task);
  if (task.google_plugin_service) out.google_tool=task.google_plugin_tool || googlePluginRegistry_()[task.google_plugin_service].tool;
  if (task.google_plugin_service) out.google_tool=task.google_plugin_tool || googlePluginRegistry_()[task.google_plugin_service].tool;
  if (c.auth_url) out.auth_url=String(c.auth_url);
  if (c.tool_slug) out.composio_tool=String(c.tool_slug);
  if (c.account_id) out.composio_account_id=String(c.account_id);
  if (c.result_json) {
    try { out.result=JSON.parse(String(c.result_json)); }
    catch(_) { out.result=String(c.result_json); }
  }
  return out;
}

function executeComposioTask_(taskId, objectiveOverride) {
  if(PropertiesService.getScriptProperties().getProperty('COMPOSIO_ZERO_COST_VERIFIED')!=='true')throw new Error('GOVERNANCE_ZERO_COST_UNVERIFIED');
  return IcarusGovernance.withComposioTask(taskId,function(){return executeComposioTaskGoverned_(taskId,objectiveOverride);});
}
function executeComposioTaskGoverned_(taskId,objectiveOverride) {
  const task=getTask_(taskId);
  if (!task) throw new Error('TASK_NOT_FOUND');
  const objective=objectiveOverride === undefined || objectiveOverride === null ? String(task.objective || '').trim() : geminiExecutionObjective_(objectiveOverride,task.objective);
  if (!objective) throw new Error('TASK_OBJECTIVE_MISSING');
  const previous=composioState_(taskId) || {};
  const sessionId=composioCreateSession_(taskId);

  // Measurement 1: exact tool discovery + exact has_active_connection machine field.
  const searched=composioSearch_(sessionId,objective);
  const route=composioPickRoute_(searched,previous,objective);
  const mode=composioToolMode_(route.toolSlug);
  if (mode === 'DENY') {
    transitionTask_(taskId,'BLOCKED',{evidence_ref:'POLICY_DENIED tool=' + route.toolSlug});
    upsertComposioState_(taskId,{session_id:sessionId,toolkit:route.toolkit,tool_slug:route.toolSlug,phase:'POLICY_DENIED'});
    appendLog_(taskId,'EXECUTING','BLOCKED','Composio tool denied before execution.','COMPOSIO_SESSION:'+sessionId,'tool='+route.toolSlug);
    return taskForClient_(taskId);
  }
  upsertComposioState_(taskId,{session_id:sessionId,toolkit:route.toolkit,tool_slug:route.toolSlug,phase:'ROUTED'});

  // Measurement 2: COMPOSIO_MANAGE_CONNECTIONS list using the SAME session.
  const listed=composioManage_(sessionId,route.toolkit,'list');
  const managed=composioManageState_(listed,route.toolkit);
  const activeAccounts=managed.accounts.filter(function(a){return String(a && a.status || '').toUpperCase()==='ACTIVE';});
  const manageProvesActive=managed.status === 'active' && activeAccounts.length > 0;

  if (route.hasActiveConnection && !manageProvesActive) throw new Error('COMPOSIO_CONNECTION_STATE_CONFLICT');
  if (!manageProvesActive) return composioBeginAuth_(taskId,sessionId,route.toolkit,route.toolSlug);

  const accountId=composioSelectAccount_(activeAccounts,previous.account_id);
  upsertComposioState_(taskId,{account_id:accountId,auth_url:'',phase:'ARGUMENTS'});
  const args=previous.arguments_json ? JSON.parse(String(previous.arguments_json)) : composioGenerateArguments_(route.toolSlug,objective);
  upsertComposioState_(taskId,{arguments_json:JSON.stringify(args),phase:'EXECUTING'});

  const currentStatus=String(getTask_(taskId).status || '');
  if (currentStatus === 'PENDING_AUTH' || currentStatus === 'INSPECTING') transitionTask_(taskId,'EXECUTING');
  else if (currentStatus !== 'EXECUTING' && currentStatus !== 'VERIFYING') throw new Error('COMPOSIO_UNEXPECTED_TASK_STATE:' + currentStatus);

  return governanceExecuteComposio_(task,sessionId,route.toolSlug,args,accountId,function(){
  const executed=composioExecuteInSession_(sessionId,route.toolSlug,args,accountId);
  if (!composioExecutionSucceeded_(executed)) throw new Error('COMPOSIO_EXECUTION_FAILED');
  const executeLog=String(executed.log_id || composioFindString_(executed,'log_id') || '');

  if (mode === 'WRITE') {
    const resultJson=JSON.stringify(composioData_(executed));
    upsertComposioState_(taskId,{phase:'PARTIAL',result_json:resultJson,execute_log_id:executeLog});
    transitionTask_(taskId,'VERIFYING');
    transitionTask_(taskId,'PARTIAL',{evidence_ref:'WRITE_EXECUTED_UNVERIFIED tool=' + route.toolSlug + '; account=' + accountId + '; execute=' + executeLog});
    appendLog_(taskId,'VERIFYING','PARTIAL','Write executed once; generic independent readback unavailable.','COMPOSIO_SESSION:'+sessionId,'tool='+route.toolSlug+';account='+accountId+';execute='+executeLog);
    return taskForClient_(taskId);
  }

  transitionTask_(taskId,'VERIFYING');
  const verified=composioExecuteInSession_(sessionId,route.toolSlug,args,accountId);
  if (!composioExecutionSucceeded_(verified)) throw new Error('COMPOSIO_READBACK_FAILED');
  const verifyLog=String(verified.log_id || composioFindString_(verified,'log_id') || '');
  const fp1=composioFingerprint_(executed), fp2=composioFingerprint_(verified);
  const resultJson=JSON.stringify(composioData_(verified));
  if (fp1 !== fp2) {
    upsertComposioState_(taskId,{phase:'PARTIAL',result_json:resultJson,execute_log_id:executeLog,verify_log_id:verifyLog});
    transitionTask_(taskId,'PARTIAL',{evidence_ref:'READBACK_MISMATCH tool=' + route.toolSlug + '; execute=' + executeLog + '; verify=' + verifyLog});
    appendLog_(taskId,'VERIFYING','PARTIAL','Two read-only executions succeeded but semantic readback differed.','COMPOSIO_SESSION:'+sessionId,'tool='+route.toolSlug+';account='+accountId+';execute='+executeLog+';verify='+verifyLog);
    return taskForClient_(taskId);
  }
  upsertComposioState_(taskId,{phase:'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION',result_json:resultJson,execute_log_id:executeLog,verify_log_id:verifyLog});
  const evidence='WORK COMPLETE — AWAITING OWNER VERIFICATION; executor repeat-read matched; tool=' + route.toolSlug + '; account=' + accountId + '; execute=' + executeLog + '; verify=' + verifyLog + '; fingerprint=' + fp2 + '; result=' + composioResultSummary_(verified);
  transitionTask_(taskId,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION',{evidence_ref:evidence});
  appendLog_(taskId,'VERIFYING','WORK_COMPLETE_AWAITING_OWNER_VERIFICATION','Executor repeat-read matched; Michael verification required.','COMPOSIO_SESSION:'+sessionId,'tool='+route.toolSlug+';account='+accountId+';execute='+executeLog+';verify='+verifyLog+';fingerprint='+fp2);
  return taskForClient_(taskId);
  });
}
