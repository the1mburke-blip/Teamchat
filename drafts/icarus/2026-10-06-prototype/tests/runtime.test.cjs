const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto'),path=require('path');
const dir=path.resolve(__dirname,'..','server-overlay');
let calls=0,seq=0,reasonCalls=0,triggerSeq=0;
const sheets={};
function sheet(name,rows=[]){
 const s={rows,getMaxColumns(){return 100},insertColumnsAfter(){},getLastRow(){return this.rows.length},getLastColumn(){return Math.max(...this.rows.map(r=>r.length),1)},appendRow(row){this.rows.push([...row])},getDataRange(){return {getValues:()=>this.rows.map(r=>[...r])}},getRange(r,c,n=1,m=1){return {getValues:()=>Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>s.rows[r+i-1]?.[c+j-1]??'')),setValue(v){s.rows[r-1]??=[];s.rows[r-1][c-1]=v;return this}}}};
 sheets[name]=s;return s;
}
sheet('TASK_QUEUE',[['task_id','status','source','objective','payload_ref','evidence_ref','created_utc']]);
sheet('LOGS',[Array.from({length:14},(_,i)=>'h'+i)]);
sheet('COMPOSIO',[['task_id','session_id','toolkit','tool_slug','account_id','auth_url','phase','arguments_json','result_json','execute_log_id','verify_log_id','updated_utc']]);
sheet('DEVICES',[['device_id','token_hash','status','paired_utc','last_seen_utc','app_build']]);
let props={STATE_SHEET_ID:'synthetic',RUNTIME_ENV:'NON_PROD',PROVIDER_MODE:'GEMINI_DIRECT',GEMINI_API_KEY:'synthetic-mock-key',GEMINI_ZERO_COST_VERIFIED:'true',COMPOSIO_ZERO_COST_VERIFIED:'true'};
let triggers=[],scheduleFailure=false;
const context={console,Date,JSON,Object,Array,String,Number,Math,Error,Boolean,ICARUS:{MAX_TEXT:4000,ENV_REQUIRED:'NON_PROD',RUNTIME_VERSION:'synthetic',SHEETS:{TASKS:'TASK_QUEUE',LOGS:'LOGS',COMPOSIO:'COMPOSIO',DEVICES:'DEVICES'},TASK_TERMINAL:['BLOCKED','FAIL','PARTIAL','WORK_COMPLETE_AWAITING_OWNER_VERIFICATION','PASS']},PropertiesService:{getScriptProperties:()=>({getProperty:k=>props[k]??null,setProperty:(k,v)=>{props[k]=v}})},SpreadsheetApp:{openById:()=>({getSheetByName:n=>sheets[n],insertSheet:n=>sheet(n)}),flush(){}},LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock(){}})},Utilities:{getUuid:()=>String(++seq),Charset:{UTF_8:'utf8'},computeHmacSha256Signature:(t,k)=>[...crypto.createHmac('sha256',k).update(t).digest()]},ScriptApp:{getProjectTriggers:()=>[...triggers],newTrigger(handler){return {timeBased(){return this},after(){return this},create(){if(scheduleFailure)throw Error('SYNTHETIC_SCHEDULE_FAILURE');const t={id:++triggerSeq,getHandlerFunction:()=>handler};triggers.push(t);return t}}},deleteTrigger(t){triggers=triggers.filter(x=>x!==t)}},nowIso_:()=>new Date().toISOString(),runtimeEnvAssert_(){},runtimeGenome_:()=>({identity:{genome_revision:'test'}}),reasoningContext_:()=>({experience:[]}),runtimeCapabilities_:()=>({}),requireCapability_(){},measureTwiceStateMutationPreflight_(){},cleanText_:(v,n)=>String(v??'').slice(0,n),parseJsonBody_:e=>JSON.parse(e.postData.contents),jsonResponse_:v=>v,sha256Hex_:v=>crypto.createHash('sha256').update(v).digest('hex'),constantTimeEquals_:(a,b)=>a===b,deviceColumn_:(h,n)=>h.indexOf(n),ownerEvidenceFingerprint_:()=>'',ownerVerificationRecord_:()=>null};
vm.createContext(context);
// Existing StateStore/SignedAuth supplied as exact repository baseline fixtures by validation workflow.
for(const name of ['StateStore.gs','SignedAuth.gs'])vm.runInContext(fs.readFileSync(path.join(__dirname,'fixtures',name),'utf8'),context,{filename:name});
context.googlePluginService_=()=>'';context.googlePluginRegistry_=()=>({});context.googlePluginEvidence_=id=>context.composioState_(id)||{};
for(const name of ['GovernanceKernel.gs','Code.gs','Runtime.gs','Provider.gs','ComposioV31.gs'])vm.runInContext(fs.readFileSync(path.join(dir,name),'utf8'),context,{filename:name});
context.UrlFetchApp={fetch(){reasonCalls++;return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({candidates:[{content:{parts:[{functionCall:{name:'execute_authorized_task',args:{objective:'Check Gmail mailbox counts without modifying messages'}}}]}}]})}}};
context.composioCreateSession_=id=>'trs_synthetic_'+id;
context.composioSearch_=()=>({data:{results:[{primary_tool_slugs:['GMAIL_LIST_MESSAGES'],toolkits:['gmail']}],toolkit_connection_statuses:[{toolkit:'gmail',has_active_connection:true}]}});
context.composioManage_=()=>({data:{results:{gmail:{status:'active',accounts:[{id:'synthetic',status:'ACTIVE'}]}}}});
context.composioGenerateArguments_=()=>({max_results:3});
context.composioExecuteInSession_=()=>{calls++;return {data:{count:3},log_id:'mock-log-'+calls}};
const device='synthetic_device_id',token='synthetic_token_not_a_real_secret';
sheets.DEVICES.appendRow([device,context.sha256Hex_(token),'ACTIVE','','','test']);
function request(inner,nonce){const payload=JSON.stringify({...inner,deviceId:device}),timestamp=Date.now(),signing=['ICARUS_QUEUE_V1',device,timestamp,nonce,payload].join('\n');return {postData:{contents:JSON.stringify({v:1,deviceId:device,timestamp,nonce,payload,signature:crypto.createHmac('sha256',context.sha256Hex_(token)).update(signing).digest('hex')})}}}
const e=request({op:'submit',clientTaskId:'one',text:'Check Gmail mailbox counts without modifying messages'},'synthetic_nonce_0001');
const accepted=context.doPost(e);assert(accepted.ok);assert.equal(accepted.data.status,'QUEUED');assert.equal(reasonCalls,0);assert.equal(calls,0);assert.equal(triggers.length,1);
assert.equal(context.doPost(e).error,'REPLAY_DENIED');
const duplicate=context.doPost(request({op:'submit',clientTaskId:'one',text:'Check Gmail mailbox counts without modifying messages'},'synthetic_nonce_0002'));
assert.equal(duplicate.data.task_id,accepted.data.task_id);assert.equal(sheets.TASK_QUEUE.rows.length,2);assert.equal(triggers.length,1);
context.resumePendingTasksSoon_();assert.equal(triggers.length,0);assert.equal(reasonCalls,1);assert.equal(calls,2);
const status=context.doPost(request({op:'status',taskId:accepted.data.task_id},'synthetic_nonce_0003'));assert.equal(status.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');assert.equal(status.data.result.count,3);assert.equal(status.data.task_id,accepted.data.task_id);
context.resumePendingTasks_();assert.equal(calls,2);assert.throws(()=>context.transitionTask_(accepted.data.task_id,'PASS'),/OWNER_VERIFICATION_REQUIRED/);
for(const slug of ['GMAIL_DELETE_MESSAGE','GOOGLEDRIVE_CREATE_FILE','SHOPIFY_GET_PRODUCT','PASSCREATOR_LIST_PASSES'])assert.equal(context.composioToolMode_(slug),'DENY');assert.equal(context.composioToolMode_('GOOGLEDRIVE_LIST_FILES'),'READ');
props.PROVIDER_MODE='NONE';assert.throws(()=>context.reason_({objective:'Check email'}),/PROTOTYPE_GEMINI_DIRECT_REQUIRED/);props.PROVIDER_MODE='GEMINI_DIRECT';
assert.throws(()=>context.geminiParseFunctionCall_({candidates:[{content:{parts:[{functionCall:{name:'execute_authorized_task',args:{objective:'delete all messages'}}}]}}]},'Check Gmail'),/WRITE_EXPANSION/);
// A scheduling failure preserves task intake so the existing recurring trigger can recover it.
scheduleFailure=true;const queued=context.doPost(request({op:'submit',clientTaskId:'two',text:'Check Gmail mailbox counts without modifying messages'},'synthetic_nonce_0004'));assert.equal(queued.data.status,'QUEUED');scheduleFailure=false;context.resumePendingTasks_();assert.equal(context.getTask_(queued.data.task_id).status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');
// Submissions while a fired trigger is draining must retain their new continuation.
context.scheduleTaskAdvance_();const original=context.resumePendingTasks_;context.resumePendingTasks_=()=>{assert.equal(triggers.length,0);context.scheduleTaskAdvance_()};context.resumePendingTasksSoon_();assert.equal(triggers.length,1);context.resumePendingTasks_=original;
console.log('12 integration assertions groups completed: actual signed intake/replay, durable idempotency, async reasoning, real executor state machine with mock transport, repeat-read, terminal no-reexecute, owner gate, service/write constraints, provider gate, argument guard, scheduler fallback, concurrent scheduling. No live API/phone evidence.');

// Enrollment uses the exact existing GoogleIdentity/Auth/Utils functions; only Google HTTP is mocked.
const cache=new Map();
context.CacheService={getScriptCache:()=>({put:(k,v)=>cache.set(k,v),get:k=>cache.get(k)??null,remove:k=>cache.delete(k)})};
context.Utilities.DigestAlgorithm={SHA_256:'sha256'};
context.Utilities.computeDigest=(algorithm,value)=>[...crypto.createHash('sha256').update(value).digest()];
context.Utilities.base64EncodeWebSafe=bytes=>Buffer.from(bytes).toString('base64url');
const response=context.jsonResponse_;
for(const name of ['Utils.gs','GoogleIdentity.gs'])vm.runInContext(fs.readFileSync(path.join(__dirname,'fixtures',name),'utf8'),context,{filename:name});
context.jsonResponse_=response;
for(const name of ['Auth.gs','Enrollment.gs'])vm.runInContext(fs.readFileSync(path.join(dir,name),'utf8'),context,{filename:name});
let denyOwnerCapability=false;
context.requireCapability_=cap=>{if(cap==='owner.google_identity'&&denyOwnerCapability)throw Error('OWNER_CAPABILITY_DENIED')};
context.gatewayRows_=()=>[];context.experienceRows_=()=>[];
props.GOOGLE_OAUTH_CLIENT_ID='synthetic_web_client';props.OWNER_GOOGLE_EMAIL_SHA256=context.sha256Hex_('owner@example.invalid');
function claims(challenge,changes={}){return {iss:'https://accounts.google.com',exp:Math.floor(Date.now()/1000)+300,sub:'synthetic_subject',nonce:challenge.nonce,aud:props.GOOGLE_OAUTH_CLIENT_ID,email_verified:'true',email:'owner@example.invalid',...changes}}
let tokenClaims={};
context.UrlFetchApp={fetch(url){assert(url.startsWith('https://oauth2.googleapis.com/tokeninfo?id_token='));return {getResponseCode:()=>200,getContentText:()=>JSON.stringify(tokenClaims)}}};
let uuidCounter=100;
function deviceUuid(){return '12345678-1234-4abc-8def-'+String(++uuidCounter).padStart(12,'0')}
function challenge(){return context.enrollmentChallenge_({deviceId:deviceUuid()})}
function enroll(c,overrides={}){return context.enrollOwnerDevice_({deviceId:c.deviceId,challengeId:c.id,googleIdToken:'synthetic_google_id_token',clientVersion:'test',...overrides})}
const initialDevices=sheets.DEVICES.rows.length;
let c=challenge();tokenClaims=claims(c,{email:'wrong@example.invalid'});assert.throws(()=>enroll(c),/GOOGLE_OWNER_IDENTITY_DENIED/);
tokenClaims=claims(c,{nonce:'wrong'});assert.throws(()=>enroll(c),/GOOGLE_ID_TOKEN_NONCE_DENIED/);
tokenClaims=claims(c,{aud:'wrong'});assert.throws(()=>enroll(c),/GOOGLE_ID_TOKEN_AUDIENCE_DENIED/);
tokenClaims=claims(c,{iss:'https://wrong.invalid'});assert.throws(()=>enroll(c),/GOOGLE_ID_TOKEN_ISSUER_DENIED/);
tokenClaims=claims(c,{exp:1});assert.throws(()=>enroll(c),/GOOGLE_ID_TOKEN_EXPIRED/);
tokenClaims=claims(c,{email_verified:'false'});assert.throws(()=>enroll(c),/GOOGLE_EMAIL_NOT_VERIFIED/);
assert.equal(sheets.DEVICES.rows.length,initialDevices);
props.GOOGLE_OAUTH_CLIENT_ID='';assert.throws(()=>challenge(),/NOT_CONFIGURED/);props.GOOGLE_OAUTH_CLIENT_ID='synthetic_web_client';
denyOwnerCapability=true;assert.throws(()=>challenge(),/OWNER_CAPABILITY_DENIED/);denyOwnerCapability=false;
tokenClaims=claims(c);assert.throws(()=>enroll(c,{deviceId:deviceUuid()}),/CHALLENGE_TARGET_DENIED/);
const expired=challenge(),raw=JSON.parse(cache.get('ENROLL:'+expired.id));raw.expiresAt=Date.now()-1;cache.set('ENROLL:'+expired.id,JSON.stringify(raw));assert.throws(()=>enroll(expired),/EXPIRED_OR_USED/);
const enrolled=enroll(c);assert(enrolled.googleIdentityVerified);assert.equal(enrolled.deviceId,c.deviceId);assert(enrolled.token.length>24);assert.equal(sheets.DEVICES.rows.length,initialDevices+1);
assert.throws(()=>enroll(c),/EXPIRED_OR_USED/);
const conflict=context.enrollmentChallenge_({deviceId:c.deviceId});tokenClaims=claims(conflict);assert.throws(()=>enroll(conflict),/DEVICE_ALREADY_ACTIVE/);assert.equal(sheets.DEVICES.rows.length,initialDevices+1);
const originalActive=sheets.DEVICES.rows.find(r=>r[0]===device);assert.equal(originalActive[2],'ACTIVE');
const inner=JSON.stringify({op:'runtime',deviceId:enrolled.deviceId}),timestamp=Date.now(),nonce='synthetic_enrolled_nonce';
const envelope={v:1,deviceId:enrolled.deviceId,timestamp,nonce,payload:inner,signature:crypto.createHmac('sha256',context.sha256Hex_(enrolled.token)).update(['ICARUS_QUEUE_V1',enrolled.deviceId,timestamp,nonce,inner].join('\n')).digest('hex')};
const runtime=context.doPost({postData:{contents:JSON.stringify(envelope)}});assert(runtime.ok);assert.equal(runtime.data.runtimeVersion,'synthetic');
assert(!JSON.stringify(sheets.LOGS.rows).includes(enrolled.token));assert(!JSON.stringify(sheets.LOGS.rows).includes('synthetic_google_id_token'));
console.log('Enrollment negative gates and fresh owner token -> enrolled device -> signed runtime readback completed with mocked Google HTTP only; no physical Google consent or live device evidence.');

module.exports={context,sheets,props,enrolled,request,cache};
