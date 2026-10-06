const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto'),path=require('path');
const dir=path.resolve(__dirname,'..','server-overlay');
let calls=0,seq=0,reasonCalls=0,triggerSeq=0;
const sheets={};
function sheet(name,rows=[]){
 const s={rows,getLastRow(){return this.rows.length},getLastColumn(){return Math.max(...this.rows.map(r=>r.length),1)},appendRow(row){this.rows.push([...row])},getDataRange(){return {getValues:()=>this.rows.map(r=>[...r])}},getRange(r,c,n=1,m=1){return {getValues:()=>Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>s.rows[r+i-1]?.[c+j-1]??'')),setValue(v){s.rows[r-1]??=[];s.rows[r-1][c-1]=v;return this}}}};
 sheets[name]=s;return s;
}
sheet('TASK_QUEUE',[['task_id','status','source','objective','payload_ref','evidence_ref','created_utc']]);
sheet('LOGS',[Array.from({length:14},(_,i)=>'h'+i)]);
sheet('COMPOSIO',[['task_id','session_id','toolkit','tool_slug','account_id','auth_url','phase','arguments_json','result_json','execute_log_id','verify_log_id','updated_utc']]);
sheet('DEVICES',[['device_id','token_hash','status','paired_utc','last_seen_utc','app_build']]);
let props={STATE_SHEET_ID:'synthetic',RUNTIME_ENV:'NON_PROD',PROVIDER_MODE:'GEMINI_DIRECT',GEMINI_API_KEY:'synthetic-mock-key'};
let triggers=[],scheduleFailure=false;
const context={console,Date,JSON,Object,Array,String,Number,Math,Error,Boolean,ICARUS:{MAX_TEXT:4000,ENV_REQUIRED:'NON_PROD',RUNTIME_VERSION:'synthetic',SHEETS:{TASKS:'TASK_QUEUE',LOGS:'LOGS',COMPOSIO:'COMPOSIO',DEVICES:'DEVICES'},TASK_TERMINAL:['BLOCKED','FAIL','PARTIAL','WORK_COMPLETE_AWAITING_OWNER_VERIFICATION','PASS']},PropertiesService:{getScriptProperties:()=>({getProperty:k=>props[k]??null})},SpreadsheetApp:{openById:()=>({getSheetByName:n=>sheets[n],insertSheet:n=>sheet(n)}),flush(){}},LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock(){}})},Utilities:{getUuid:()=>String(++seq),Charset:{UTF_8:'utf8'},computeHmacSha256Signature:(t,k)=>[...crypto.createHmac('sha256',k).update(t).digest()]},ScriptApp:{getProjectTriggers:()=>[...triggers],newTrigger(handler){return {timeBased(){return this},after(){return this},create(){if(scheduleFailure)throw Error('SYNTHETIC_SCHEDULE_FAILURE');const t={id:++triggerSeq,getHandlerFunction:()=>handler};triggers.push(t);return t}}},deleteTrigger(t){triggers=triggers.filter(x=>x!==t)}},nowIso_:()=>new Date().toISOString(),runtimeEnvAssert_(){},runtimeGenome_:()=>({identity:{genome_revision:'test'}}),reasoningContext_:()=>({experience:[]}),runtimeCapabilities_:()=>({}),requireCapability_(){},measureTwiceStateMutationPreflight_(){},cleanText_:(v,n)=>String(v??'').slice(0,n),parseJsonBody_:e=>JSON.parse(e.postData.contents),jsonResponse_:v=>v,sha256Hex_:v=>crypto.createHash('sha256').update(v).digest('hex'),constantTimeEquals_:(a,b)=>a===b,deviceColumn_:(h,n)=>h.indexOf(n),ownerEvidenceFingerprint_:()=>'',ownerVerificationRecord_:()=>null};
vm.createContext(context);
// Existing StateStore/SignedAuth supplied as exact repository baseline fixtures by validation workflow.
for(const name of ['StateStore.gs','SignedAuth.gs'])vm.runInContext(fs.readFileSync(path.join(__dirname,'fixtures',name),'utf8'),context,{filename:name});
for(const name of ['Code.gs','Runtime.gs','Provider.gs','ComposioV31.gs'])vm.runInContext(fs.readFileSync(path.join(dir,name),'utf8'),context,{filename:name});
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
