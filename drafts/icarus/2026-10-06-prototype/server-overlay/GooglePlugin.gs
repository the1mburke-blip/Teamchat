/** Native Google plugin: single configured owner, fixed GET operations, no Composio. */
function googlePluginRegistry_() {
  return {gmail:{scope:'https://www.googleapis.com/auth/gmail.metadata',tool:'GOOGLE_GMAIL_MAILBOX_METADATA',headerTool:'GOOGLE_GMAIL_HEADER_METADATA'},drive:{scope:'https://www.googleapis.com/auth/drive.metadata.readonly',tool:'GOOGLE_DRIVE_LIST_METADATA'}};
}
function googlePluginService_(objective) {
  const text=String(objective || '');
  const gmail=/\b(gmail|email|mailbox)\b/i.test(text), drive=/\b(google drive|drive files|drive metadata)\b/i.test(text);
  if (gmail && drive) throw new Error('GOOGLE_ONE_SERVICE_PER_TASK');
  return gmail ? 'gmail' : drive ? 'drive' : '';
}
function googlePluginOwner_(deviceId) {
  if (!googleIdentityConfigured_()) throw new Error('GOOGLE_UNCONFIGURED');
  requireCapability_('owner.google_identity');
  const rows=sheet_(ICARUS.SHEETS.DEVICES).getDataRange().getValues(), h=rows[0].map(String);
  const ownerHash=String(PropertiesService.getScriptProperties().getProperty('OWNER_GOOGLE_EMAIL_SHA256') || '');
  const row=rows.slice(1).find(function(v){return String(v[h.indexOf('device_id')])===deviceId && String(v[h.indexOf('status')])==='ACTIVE';});
  if (!row) throw new Error('GOOGLE_DEVICE_DENIED');
  if (h.indexOf('google_owner_subject')<0 || !row[h.indexOf('google_owner_subject')]) throw new Error('GOOGLE_REENROLL_REQUIRED');
  if (h.indexOf('google_owner_email_hash')<0 || !constantTimeEquals_(String(row[h.indexOf('google_owner_email_hash')]),ownerHash)) throw new Error('GOOGLE_OWNER_DENIED');
  return ownerHash;
}
function googlePluginAuthorizationUrl_(value) {
  const url=String(value || '');
  // Only native Google OAuth consent endpoints, never client-supplied callback URLs.
  if (!/^https:\/\/(accounts\.google\.com\/o\/oauth2(?:\/v2)?\/auth|script\.google\.com\/oauthcallback)(?:\?|$)/.test(url) || /[\s\\]/.test(url)) throw new Error('GOOGLE_AUTH_URL_DENIED');
  return url;
}
function googlePluginGet_(url) {
  const gmailProfile=url==='https://gmail.googleapis.com/gmail/v1/users/me/profile';
  const gmailList=url==='https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=3';
  const gmailHeaders=/^https:\/\/gmail\.googleapis\.com\/gmail\/v1\/users\/me\/messages\/[A-Za-z0-9_-]{1,128}\?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&fields=id,payload\(headers\)$/.test(url);
  const driveAbout=url==='https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)';
  const driveList=url==='https://www.googleapis.com/drive/v3/files?pageSize=5&orderBy=modifiedTime%20desc&fields=files(id,name,mimeType,modifiedTime)&q=trashed%3Dfalse';
  if (!gmailProfile && !gmailList && !gmailHeaders && !driveAbout && !driveList) throw new Error('GOOGLE_ENDPOINT_DENIED');
  let response;const token=ScriptApp.getOAuthToken();
  try {response=UrlFetchApp.fetch(url,{method:'get',headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false});}
  catch (_) {throw new Error('GOOGLE_TRANSPORT_UNKNOWN');}
  const code=response.getResponseCode();
  if (code===401) throw new Error('GOOGLE_EXPIRED_RECONNECT_REQUIRED');
  if (code===403) throw new Error('GOOGLE_PERMISSION_RECONNECT_REQUIRED');
  if (code!==200) throw new Error('GOOGLE_HTTP_'+code);
  const raw=String(response.getContentText() || '');
  if (raw.length>64000 || (token && raw.indexOf(token)>=0)) throw new Error('GOOGLE_RESPONSE_TOO_LARGE');
  let parsed;try {parsed=JSON.parse(raw);} catch (_) {throw new Error('GOOGLE_INVALID_JSON');}
  if (!parsed || typeof parsed!=='object' || Array.isArray(parsed)) throw new Error('GOOGLE_INVALID_RESPONSE');
  return parsed;
}
function googlePluginPrincipal_(service, ownerHash) {
  const profile=googlePluginGet_(service==='gmail' ? 'https://gmail.googleapis.com/gmail/v1/users/me/profile' : 'https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)');
  const email=service==='gmail' ? profile.emailAddress : (profile.user || {}).emailAddress;
  if (typeof email!=='string' || !constantTimeEquals_(sha256Hex_(email.trim().toLowerCase()),ownerHash)) throw new Error('GOOGLE_API_PRINCIPAL_DENIED');
  return profile;
}
function googlePluginConnection_(deviceId, service, authorize) {
  const descriptor=googlePluginRegistry_()[service];
  if (!descriptor) return {service:service,state:'UNAVAILABLE',reason:'GOOGLE_SERVICE_NOT_IMPLEMENTED'};
  try {
    const ownerHash=googlePluginOwner_(deviceId);
    const info=ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL,[descriptor.scope]);
    const granted=info.getAuthorizedScopes();
    if (!Array.isArray(granted)) return {service:service,state:'UNKNOWN',reason:'GOOGLE_GRANTS_UNKNOWN'};
    if (info.getAuthorizationStatus()!==ScriptApp.AuthorizationStatus.NOT_REQUIRED || granted.indexOf(descriptor.scope)<0) {
      const out={service:service,state:'MISSING',reason:'GOOGLE_SCOPE_REQUIRED'};
      if (authorize) out.authorizationUrl=googlePluginAuthorizationUrl_(info.getAuthorizationUrl());
      return out;
    }
    googlePluginPrincipal_(service,ownerHash);
    return {service:service,state:'CONNECTED',tool:descriptor.tool};
  } catch (err) {
    const reason=String(err.message || err);
    const state=/EXPIRED/.test(reason) ? 'EXPIRED' : /PERMISSION/.test(reason) ? 'REVOKED' : /UNCONFIGURED/.test(reason) ? 'UNCONFIGURED' : /DENIED|REENROLL|CAPABILITY/.test(reason) ? 'BLOCKED' : 'UNKNOWN';
    const out={service:service,state:state,reason:/^GOOGLE_[A-Z_0-9]+$/.test(reason) ? reason : 'GOOGLE_AUTHORIZATION_UNKNOWN'};
    if (authorize && (state==='EXPIRED' || state==='REVOKED')) {
      try {out.authorizationUrl=googlePluginAuthorizationUrl_(ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL,[descriptor.scope]).getAuthorizationUrl());} catch (_) {}
    }
    return out;
  }
}
function googlePluginConnections_(auth, body, authorize) {
  if (Object.keys(body).some(function(k){return ['op','deviceId','service'].indexOf(k)<0;})) throw new Error('GOOGLE_MANAGER_ARGUMENT_DENIED');
  if (authorize) return googlePluginConnection_(auth.deviceId,String(body.service || ''),true);
  return {connections:['gmail','drive','calendar','sheets'].map(function(service){return googlePluginConnection_(auth.deviceId,service,false);})};
}
function googlePluginRead_(service, ownerHash, headerIds) {
  const profile=googlePluginPrincipal_(service,ownerHash);
  if (service==='gmail') {
    if (headerIds) {
      return {service:'gmail',messages:headerIds.map(function(id){
        if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error('GOOGLE_MESSAGE_ID_DENIED');
        const message=googlePluginGet_('https://gmail.googleapis.com/gmail/v1/users/me/messages/'+id+'?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&fields=id,payload(headers)');
        if (message.id!==id || !message.payload || !Array.isArray(message.payload.headers)) throw new Error('GOOGLE_INVALID_RESPONSE');
        const headers={};message.payload.headers.forEach(function(h){const key=String(h.name || '').toLowerCase();if(['from','subject','date'].indexOf(key)>=0 && typeof h.value==='string')headers[key]=h.value.slice(0,2000);});
        return {id:id,from:headers.from || '',subject:headers.subject || '',date:headers.date || ''};
      }),scope:'three selected message headers only; no bodies, snippets or search'};
    }
    if (typeof profile.messagesTotal!=='number' || typeof profile.threadsTotal!=='number' || !Number.isFinite(profile.messagesTotal) || !Number.isFinite(profile.threadsTotal)) throw new Error('GOOGLE_INVALID_RESPONSE');
    return {service:'gmail',messagesTotal:Number(profile.messagesTotal),threadsTotal:Number(profile.threadsTotal),scope:'mailbox counts only; no bodies or search'};
  }
  const data=googlePluginGet_('https://www.googleapis.com/drive/v3/files?pageSize=5&orderBy=modifiedTime%20desc&fields=files(id,name,mimeType,modifiedTime)&q=trashed%3Dfalse');
  if (!Array.isArray(data.files)) throw new Error('GOOGLE_INVALID_RESPONSE');
  return {service:'drive',files:data.files.map(function(f){if (typeof f.id!=='string'||typeof f.name!=='string'||typeof f.mimeType!=='string') throw new Error('GOOGLE_INVALID_RESPONSE');return {id:f.id,name:f.name,mimeType:f.mimeType,modifiedTime:String(f.modifiedTime || '')};}),scope:'up to five recent file metadata records; no contents'};
}
function googlePluginStore_(taskId, fields) {
  const sh=sheet_(ICARUS.SHEETS.TASKS);let found=findTaskRow_(taskId);
  Object.keys(fields).forEach(function(k){if(found.headers.indexOf(k)<0){if(sh.getMaxColumns()<found.headers.length+1)sh.insertColumnsAfter(sh.getMaxColumns(),1);sh.getRange(1,found.headers.length+1).setValue(k);SpreadsheetApp.flush();found=findTaskRow_(taskId);}});
  return updateTaskFields_(taskId,fields);
}
function googlePluginEvidence_(taskId) {
  const task=getTask_(taskId);
  if (task && task.google_plugin_service) return {result_json:task.google_plugin_result_json || '',execute_log_id:task.google_plugin_execute_log || '',verify_log_id:task.google_plugin_verify_log || ''};
  return composioState_(taskId) || {};
}
function executeGooglePluginTask_(taskId, objectiveOverride) {
  const task=getTask_(taskId), service=googlePluginService_(task.objective), descriptor=googlePluginRegistry_()[service];
  if (!descriptor || !/^ANDROID:/.test(String(task.source))) throw new Error('GOOGLE_TASK_ROUTE_DENIED');
  const objective=objectiveOverride==null ? String(task.objective) : geminiExecutionObjective_(objectiveOverride,task.objective);
  if (googlePluginService_(objective)!==service) throw new Error('GOOGLE_REASONING_ROUTE_DENIED');
  // Narrow prototype operations. Unsupported Google requests stay here and cannot fall back to Composio.
  if (/\b(send|delete|remove|create|update|upload|publish|archive|trash|reply|forward|mark|move|rename|share|invite)\b/i.test(String(task.objective)+' '+objective)) throw new Error('GOOGLE_WRITES_DENIED');
  const headersRequested=service==='gmail' && /\b(headers?|recent|latest|list)\b/i.test(String(task.objective));
  if (service==='gmail' && !headersRequested && !/\b(counts?|totals?|profile|summary)\b/i.test(String(task.objective))) throw new Error('GOOGLE_GMAIL_METADATA_ONLY');
  if (service==='gmail' && /\b(search|bodies|body|contents?|attachments?|query)\b|\bfrom:|\bsubject:/i.test(String(task.objective))) throw new Error('GOOGLE_GMAIL_SEARCH_BODY_DENIED');
  if (service==='drive' && !/\b(list|recent|metadata)\b/i.test(String(task.objective))) throw new Error('GOOGLE_DRIVE_METADATA_ONLY');
  const deviceId=String(task.source).slice(8), ownerHash=googlePluginOwner_(deviceId);
  googlePluginStore_(taskId,{google_plugin_service:service,google_plugin_result_json:'',google_plugin_auth_url:''});
  const connection=googlePluginConnection_(deviceId,service,false);
  if (['MISSING','EXPIRED','REVOKED'].indexOf(connection.state)>=0) {transitionTask_(taskId,'PENDING_AUTH',{evidence_ref:connection.reason+'; authorize '+service+' in Google connections, then refresh this task'});return taskForClient_(taskId);}
  if (connection.state!=='CONNECTED') throw new Error(connection.reason || 'GOOGLE_RECONNECT_REQUIRED');
  if (task.status==='PENDING_AUTH') transitionTask_(taskId,'EXECUTING');
  let headerIds=null;
  if(headersRequested){const listed=googlePluginGet_('https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=3');if(listed.messages!==undefined && !Array.isArray(listed.messages))throw new Error('GOOGLE_INVALID_RESPONSE');headerIds=(listed.messages || []).slice(0,3).map(function(m){return String(m.id || '');});}
  const tool=headersRequested ? descriptor.headerTool : descriptor.tool;
  const result=googlePluginRead_(service,ownerHash,headerIds), executeLog=appendLog_(taskId,'EXECUTING','READ_COMPLETE','Native Google read completed.','TASK_QUEUE:'+taskId,tool);
  transitionTask_(taskId,'VERIFYING');
  const repeated=googlePluginRead_(service,googlePluginOwner_(deviceId),headerIds), verifyLog=appendLog_(taskId,'VERIFYING','READ_COMPLETE','Native Google repeat-read completed.','TASK_QUEUE:'+taskId,tool);
  const match=JSON.stringify(result)===JSON.stringify(repeated);
  googlePluginStore_(taskId,{google_plugin_tool:tool,google_plugin_result_json:JSON.stringify(repeated),google_plugin_execute_log:String(executeLog),google_plugin_verify_log:String(verifyLog)});
  transitionTask_(taskId,match ? 'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION' : 'PARTIAL',{evidence_ref:'GOOGLE_NATIVE '+tool+'; repeat-read '+(match?'matched; Michael verification required':'changed; owner inspection required')+'; execute='+executeLog+'; verify='+verifyLog});
  return taskForClient_(taskId);
}
