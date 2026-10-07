// Real signed/task/runtime/provider/native functions, synthetic HTTP only; no API calls or owner actions.
require('./google-plugin.test.cjs');
const {context:c,sheets,props,enrolled}=require('./runtime.test.cjs');
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
vm.runInContext(fs.readFileSync(path.join(__dirname,'../server-overlay/GoogleBundle.gs'),'utf8'),c,{filename:'GoogleBundle.gs'});
let sequence=50000,objective='',operation=null,granted=null,code=200,owner='owner@example.invalid',mutations=0,nativeRequests=[],failureAfterWrite=false,leak=false;
const docs=new Map(),values=new Map(),events=new Map();
const id='synthetic_resource_123',eventId='synthetic_event_123';docs.set(id,'Original paragraph\n');values.set('B4',[['Pending']]);
c.Utilities.formatDate=(date,zone,format)=>{assert.equal(zone,'UTC');return format==='Z'?'+0000':date.toISOString().slice(0,10);};props.GOOGLE_OWNER_TIME_ZONE='UTC';
c.ScriptApp.getAuthorizationInfo=(mode,scopes)=>({getAuthorizedScopes:()=>granted===null?scopes:scopes.filter(s=>granted.includes(s)),getAuthorizationStatus:()=>granted===null||scopes.every(s=>granted.includes(s))?'NOT_REQUIRED':'REQUIRED',getAuthorizationUrl:()=> 'https://accounts.google.com/o/oauth2/auth?client_id=synthetic'});
let callsToComposio=0;c.composioCreateSession_=()=>{callsToComposio++;throw Error('COMPOSIO_FORBIDDEN');};
function response(data){return {getResponseCode:()=>code,getContentText:()=>leak?JSON.stringify({data:'synthetic_native_oauth_token'}):JSON.stringify(data)};}
c.UrlFetchApp={fetch(url,opt){
  if(url.startsWith('https://generativelanguage.googleapis.com/'))return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({candidates:[{content:{parts:[{functionCall:{name:'execute_authorized_task',args:{objective,googleOperation:operation}}}]}}]})};
  assert.equal(opt.followRedirects,false);assert.equal(opt.headers.Authorization,'Bearer synthetic_native_oauth_token');nativeRequests.push({url,method:opt.method});
  if(url.endsWith('/profile'))return response({emailAddress:owner,messagesTotal:7,threadsTotal:5});
  if(url.includes('/about?'))return response({user:{emailAddress:owner}});
  if(url.includes('calendar/v3')){
    if(opt.method==='post'){mutations++;const body=JSON.parse(opt.payload);assert.equal(body.attendees,undefined);assert.equal(body.reminders.useDefault,false);assert(url.endsWith('sendUpdates=none'));events.set(body.id,{...body,status:'confirmed',htmlLink:'https://calendar.google.com/calendar/event?eid=synthetic'});return response(events.get(body.id));}
    const suffix=url.split('/events')[1];if(suffix.startsWith('/'))return response(events.get(suffix.slice(1))||{id:eventId,summary:'Read only',start:{dateTime:'2026-10-09T15:00:00Z'},end:{dateTime:'2026-10-09T16:00:00Z'}});
    return response({items:[{id:eventId,summary:'Read only',start:{dateTime:'2026-10-09T15:00:00Z'},end:{dateTime:'2026-10-09T16:00:00Z'}}]});
  }
  if(url.includes('sheets.googleapis.com')){
    if(!url.includes('/values/'))return response({spreadsheetId:id,properties:{title:'Synthetic sheet'},sheets:[{properties:{sheetId:0,title:'Sheet1'}}]});
    const range=decodeURIComponent(url.split('/values/')[1].split('?')[0]);
    if(opt.method==='put'){mutations++;const body=JSON.parse(opt.payload);assert(url.endsWith('valueInputOption=RAW'));assert.equal(body.range,range);values.set(range,body.values);if(failureAfterWrite)throw Error('secret transport detail');return response({updatedRange:range,updatedCells:1});}
    return response({range,values:values.get(range)||[['Synthetic']]});
  }
  if(url.includes('docs.googleapis.com')){
    if(opt.method==='post'){mutations++;const body=JSON.parse(opt.payload);assert.equal(body.requests.length,1);assert.equal(body.writeControl.requiredRevisionId,'synthetic_revision');const insert=body.requests[0].insertText;assert(insert);const previous=docs.get(id);const index=insert.endOfSegmentLocation?previous.length-1:insert.location.index-1;docs.set(id,previous.slice(0,index)+insert.text+previous.slice(index));return response({documentId:id,replies:[{}]});}
    return response({documentId:id,title:'Synthetic Doc',revisionId:'synthetic_revision',body:{content:[{startIndex:0,endIndex:1},{startIndex:1,endIndex:docs.get(id).length+1,paragraph:{elements:[{textRun:{content:docs.get(id)}}]}}]}});
  }
  throw Error('UNEXPECTED_URL');
}};
function signed(body,device=enrolled.deviceId){const payload=JSON.stringify({...body,deviceId:device}),timestamp=Date.now(),nonce='bundle_nonce_'+(++sequence),signature=crypto.createHmac('sha256',c.sha256Hex_(enrolled.token)).update(['ICARUS_QUEUE_V1',device,timestamp,nonce,payload].join('\n')).digest('hex');return {postData:{contents:JSON.stringify({v:1,deviceId:device,timestamp,nonce,payload,signature})}};}
function task(text,plan,clientId='bundle_client_'+(++sequence)){objective=text;operation=plan;const accepted=c.doPost(signed({op:'submit',clientTaskId:clientId,text}));assert(accepted.ok);c.resumePendingTasksSoon_();const result=c.doPost(signed({op:'status',taskId:accepted.data.task_id}));assert(result.ok);return result.data;}
function complete(text,plan){const result=task(text,plan);assert.equal(result.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION',result.evidence_ref);return result;}
let result=complete('What is on my calendar tomorrow?',{service:'calendar',operation:'list_events'});assert.equal(result.result.events[0].id,eventId);const w=result.result.window;assert.equal(Date.parse(w.timeMax)-Date.parse(w.timeMin),86400000);assert.equal(mutations,0);
complete('Read calendar event metadata '+eventId,{service:'calendar',operation:'event_metadata',eventId});
result=complete('Create a calendar event candidate for Friday at 3 PM.',{service:'calendar',operation:'create_event'});assert(result.result.candidate);assert.equal(mutations,0);
complete('Read spreadsheet metadata '+id,{service:'sheets',operation:'sheet_metadata',resourceId:id});
complete('Read cells A1:C10 from spreadsheet '+id,{service:'sheets',operation:'read_range',resourceId:id,range:'A1:C10'});
complete('Read this Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id});
const metaStart=nativeRequests.length;complete('Read Google Doc metadata '+id,{service:'docs',operation:'doc_metadata',resourceId:id});assert(nativeRequests.slice(metaStart).filter(r=>r.url.includes('docs.googleapis.com')).every(r=>!r.url.includes('body(')));
const writesBefore=mutations;
result=complete('Update B4 to Approved in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4',text:'Approved'});assert.equal(result.result.values[0][0],'Approved');assert.equal(mutations,writesBefore+1);
const taskId=result.task_id;const duplicate=c.doPost(signed({op:'submit',clientTaskId:c.getTask_(taskId).payload_ref.slice(15),text:objective}));assert.equal(duplicate.data.task_id,taskId);c.resumePendingTasks_();c.doPost(signed({op:'status',taskId}));assert.equal(mutations,writesBefore+1);
complete('Append "New paragraph" to the document '+id,{service:'docs',operation:'append_text',resourceId:id,text:'New paragraph'});assert.equal(docs.get(id),'Original paragraphNew paragraph\n');
complete('Insert "First " at index 1 into Google Doc '+id,{service:'docs',operation:'insert_text',resourceId:id,text:'First ',index:1});
complete('Create calendar event "Review" start 2026-10-09T15:00:00Z end 2026-10-09T16:00:00Z',{service:'calendar',operation:'create_event',summary:'Review',start:'2026-10-09T15:00:00Z',end:'2026-10-09T16:00:00Z'});
for(const [text,plan] of [
 ['What is on my calendar tomorrow?',{service:'calendar',operation:'create_event'}],
 ['Read cells A1:C10 from spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'A1:C10',text:'Approved'}],
 ['Update B4 to Approved in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4:C5',text:'Approved'}],
 ['Read this Google Doc '+id,{service:'docs',operation:'append_text',resourceId:id,text:'Read'}],
 ['Append "New paragraph" to the document '+id,{service:'docs',operation:'append_text',resourceId:'different_resource_123',text:'New paragraph'}],
 ['Append "New paragraph" to the document '+id,{service:'docs',operation:'append_text',resourceId:id,text:'Unrequested'}],
 ['Read this Google Doc '+id,{service:'docs',operation:'delete_document',resourceId:id}],
 ['Update AB4 to Approved in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4',text:'Approved'}],
 ['Update Sheet2!B4 to Approved in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4',text:'Approved'}],
 ['Append "Approved for release" to Google Doc '+id,{service:'docs',operation:'append_text',resourceId:id,text:'Google'}],
 ['Read metadata of Google Doc '+id,{service:'docs',operation:'sheet_metadata',resourceId:id}],
 ['Read metadata of Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id}],
 ['Update B4 to Approved for release in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4',text:'Approved'}],
 ['Create calendar event "Budget Review" start 2026-10-09T15:00:00Z end 2026-10-09T16:00:00Z',{service:'calendar',operation:'create_event',summary:'calendar',start:'2026-10-09T15:00:00Z',end:'2026-10-09T16:00:00Z'}],
 ['Insert "Exact text" at index 10 into Google Doc '+id,{service:'docs',operation:'insert_text',resourceId:id,text:'Exact text',index:1}],
 ['Create calendar event "Review" start 2026-10-09T15:00:00Z_INVALID end 2026-10-09T16:00:00Z_INVALID',{service:'calendar',operation:'create_event',summary:'Review',start:'2026-10-09T15:00:00Z',end:'2026-10-09T16:00:00Z'}],
 ['Read cells A1:XFD1000 from spreadsheet '+id,{service:'sheets',operation:'read_range',resourceId:id,range:'A1:XFD1000'}]
]){const old=mutations;assert.equal(task(text,plan).status,'BLOCKED');assert.equal(mutations,old);}
owner='wrong@example.invalid';assert.equal(c.doPost(signed({op:'google_authorize',service:'bundle'})).data.state,'BLOCKED');assert.equal(task('Read this Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id}).status,'BLOCKED');owner='owner@example.invalid';
granted=[c.googlePluginRegistry_().drive.scope,c.googlePluginRegistry_().gmail.scope];
let connections=c.doPost(signed({op:'google_connections'}));assert(connections.ok);assert.equal(connections.data.connections.length,5);assert.equal(connections.data.connections[0].state,'CONNECTED');assert.equal(connections.data.connections[2].state,'MISSING');
const bundle=c.doPost(signed({op:'google_authorize',service:'bundle',access:'read'}));assert(bundle.ok);assert.equal(bundle.data.state,'MISSING');assert(bundle.data.missingScopes.includes(c.googlePluginRegistry_().calendar.scope));assert(bundle.data.authorizationUrl.startsWith('https://accounts.google.com/'));
result=task('Read this Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id});assert.equal(result.status,'PENDING_AUTH');const pendingId=result.task_id;assert.equal(c.getTask_(pendingId).google_plugin_plan_json.includes('read_text'),true);
granted=null;result=c.doPost(signed({op:'status',taskId:pendingId}));assert.equal(result.data.task_id,pendingId);assert.equal(result.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');
for(const failure of [401,403]){code=failure;result=task('Read this Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id});assert.equal(result.status,'PENDING_AUTH');}code=200;
assert.throws(()=>c.googleBundleRequest_('get','https://evil.invalid'),/GOOGLE_ENDPOINT_DENIED/);
const oldMutations=mutations;failureAfterWrite=true;result=task('Update B4 to RetryEvidence in spreadsheet '+id,{service:'sheets',operation:'update_range',resourceId:id,range:'B4',text:'RetryEvidence'});failureAfterWrite=false;assert.equal(result.status,'OUTCOME_UNKNOWN');assert(result.evidence_ref.includes('GOOGLE_WRITE_OUTCOME_UNKNOWN'));assert.equal(mutations,oldMutations+1);c.resumePendingTasks_();assert.equal(mutations,oldMutations+1);
const originalAuthorization=c.ScriptApp.getAuthorizationInfo;c.ScriptApp.getAuthorizationInfo=(mode,scopes)=>({getAuthorizedScopes:()=>scopes,getAuthorizationStatus:()=> 'REQUIRED',getAuthorizationUrl:()=> 'https://accounts.google.com/o/oauth2/auth?client_id=synthetic'});assert.equal(c.googlePluginConnection_(enrolled.deviceId,'docs',false).state,'MISSING');assert.equal(c.doPost(signed({op:'google_authorize',service:'bundle'})).data.state,'MISSING');c.ScriptApp.getAuthorizationInfo=originalAuthorization;
const origCapability=c.requireCapability_;c.requireCapability_=cap=>{if(cap==='google.docs.write')throw Error('GOOGLE_CAPABILITY_DENIED');};assert.equal(task('Append "Denied" to document '+id,{service:'docs',operation:'append_text',resourceId:id,text:'Denied'}).status,'BLOCKED');c.requireCapability_=origCapability;
leak=true;result=task('Read this Google Doc '+id,{service:'docs',operation:'read_text',resourceId:id});assert.equal(result.status,'BLOCKED');leak=false;
assert.equal(callsToComposio,0);assert(!JSON.stringify(sheets.LOGS.rows).includes('synthetic_native_oauth_token'));assert(!JSON.stringify(result).includes('synthetic_native_oauth_token'));assert(!JSON.stringify(sheets.LOGS.rows).includes('secret transport detail'));assert.throws(()=>c.transitionTask_(taskId,'PASS'),/OWNER_VERIFICATION_REQUIRED/);
const android=fs.readFileSync(path.join(__dirname,'../android/app/src/main/java/com/icarus/shell/IcarusShellScreen.kt'),'utf8');assert(android.includes('Authorize Google reads'));assert(android.includes('Authorize supported Google writes'));assert(!android.includes('Authorize ${connection.service}'));
console.log('Google Bundle deterministic gates complete: Gmail/Drive retained; Calendar tomorrow/event metadata/candidate/create, Sheets metadata/bounded read/single-cell RAW write, Docs metadata/bounded text/append/insert, original-authority no expansion, partial grants/common auth, owner/capability isolation, persistent auth interruption, signed idempotent mutation and uncertain-write no retry, no Composio or token leakage. Mock transport only, not live consent or phone proof.');
