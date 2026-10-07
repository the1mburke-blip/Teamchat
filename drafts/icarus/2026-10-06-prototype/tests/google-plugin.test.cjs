const {context:c,sheets,props,enrolled}=require('./runtime.test.cjs');
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
for(const name of ['GooglePlugin.gs','OwnerVerification.gs'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../server-overlay',name),'utf8'),c,{filename:name});
let grants=true,nullGrants=false,httpCode=200,badJson=false,principal='owner@example.invalid',composioCalls=0,reads=0;
let authUrl='https://accounts.google.com/o/oauth2/auth?client_id=synthetic';
c.ScriptApp.AuthMode={FULL:'FULL'};c.ScriptApp.AuthorizationStatus={NOT_REQUIRED:'NOT_REQUIRED'};
c.ScriptApp.getAuthorizationInfo=(mode,scopes)=>({getAuthorizedScopes:()=>nullGrants?null:grants?scopes:[],getAuthorizationStatus:()=>grants?'NOT_REQUIRED':'REQUIRED',getAuthorizationUrl:()=>authUrl});
c.ScriptApp.getOAuthToken=()=> 'synthetic_native_oauth_token';
c.composioCreateSession_=()=>{composioCalls++;throw Error('COMPOSIO_MUST_NOT_RUN')};
c.UrlFetchApp={fetch(url,options){
 if(url.startsWith('https://generativelanguage.googleapis.com/')&&JSON.parse(options.payload).toolConfig.functionCallingConfig.allowedFunctionNames[0]==='select_procedural_skill')return {getResponseCode:()=>200,getContentText:()=>JSON.stringify({candidates:[{content:{parts:[{functionCall:{name:'select_procedural_skill',args:{name:'',revision:''}}}]}}]})};
 if(url.startsWith('https://generativelanguage.googleapis.com/'))return response({candidates:[{content:{parts:[{functionCall:{name:'execute_authorized_task',args:{objective:reasonObjective}}}]}}]});
 assert.equal(options.method,'get');assert.equal(options.followRedirects,false);assert(!url.includes('access_token'));if(url.includes('gmail.googleapis.com'))assert(!url.includes('q='));
 reads++;
 if(url.includes('/messages?'))return response({messages:[{id:'mock_message_1'}]});
 if(url.includes('/messages/')){assert(url.includes('format=metadata'));assert(url.includes('metadataHeaders=From'));return response({id:'mock_message_1',snippet:'must not return',payload:{headers:[{name:'From',value:'Sender <sender@example.invalid>'},{name:'Subject',value:'Synthetic subject'},{name:'Date',value:'Mon, 1 Jan 2026'},{name:'Unrequested',value:'must not return'}],body:{data:'must not return'}}});}
 if(url.endsWith('/profile'))return response({emailAddress:principal,messagesTotal:7,threadsTotal:5});
 if(url.includes('/about?'))return response({user:{emailAddress:principal}});
 if(url.includes('/files?'))return response({files:[{id:'synthetic_file',name:'Synthetic file',mimeType:'text/plain',modifiedTime:'2026-01-01T00:00:00Z'}]});
 throw Error('UNEXPECTED_GOOGLE_URL');
}};
function response(value){return {getResponseCode:()=>value.candidates?200:httpCode,getContentText:()=>badJson?'not-json':JSON.stringify(value)}}
let nonceSeq=10000,reasonObjective='Check Gmail mailbox counts without modifying messages';
function signed(inner,device=enrolled.deviceId,token=enrolled.token){const payload=JSON.stringify({...inner,deviceId:device}),timestamp=Date.now(),nonce='native_nonce_'+(++nonceSeq),signature=crypto.createHmac('sha256',c.sha256Hex_(token)).update(['ICARUS_QUEUE_V1',device,timestamp,nonce,payload].join('\n')).digest('hex');return {postData:{contents:JSON.stringify({v:1,deviceId:device,timestamp,nonce,payload,signature})}}}
let status=c.doPost(signed({op:'google_connections'}));assert(status.ok);assert.equal(status.data.connections[0].state,'CONNECTED');assert.equal(status.data.connections[1].state,'CONNECTED');assert.equal(status.data.connections[2].state,'CONNECTED');assert.equal(status.data.connections.length,5);
assert.equal(c.doPost(signed({op:'google_connections',email:'injected@example.invalid'})).error,'GOOGLE_MANAGER_ARGUMENT_DENIED');
assert(!c.doPost(signed({op:'google_connections'},'wrong_device',enrolled.token)).ok);
const replay=signed({op:'google_connections'});assert(c.doPost(replay).ok);assert.equal(c.doPost(replay).error,'REPLAY_DENIED');
assert.equal(c.googlePluginConnection_('synthetic_device_id','gmail',false).reason,'GOOGLE_REENROLL_REQUIRED');
principal='wrong@example.invalid';const before=reads;assert.equal(c.googlePluginConnection_(enrolled.deviceId,'drive',false).state,'BLOCKED');assert.equal(reads,before+1);principal='owner@example.invalid';
const ownerHash=props.OWNER_GOOGLE_EMAIL_SHA256;props.OWNER_GOOGLE_EMAIL_SHA256=c.sha256Hex_('wrong@example.invalid');assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',false).reason,'GOOGLE_OWNER_DENIED');props.OWNER_GOOGLE_EMAIL_SHA256=ownerHash;
nullGrants=true;assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',false).state,'UNKNOWN');nullGrants=false;
props.GOOGLE_OAUTH_CLIENT_ID='';assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',false).state,'UNCONFIGURED');props.GOOGLE_OAUTH_CLIENT_ID='synthetic_web_client';
grants=false;let authorization=c.doPost(signed({op:'google_authorize',service:'gmail'}));assert.equal(authorization.data.state,'MISSING');assert.equal(authorization.data.authorizationUrl,authUrl);assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',false).state,'MISSING');
authUrl='https://evil.invalid/?success=true';assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',true).state,'BLOCKED');authUrl='https://accounts.google.com/o/oauth2/auth?client_id=synthetic';
assert.equal(c.doPost(signed({op:'google_connections',success:true})).error,'GOOGLE_MANAGER_ARGUMENT_DENIED');
let accepted=c.doPost(signed({op:'submit',clientTaskId:'native_pending',text:reasonObjective}));c.resumePendingTasksSoon_();assert.equal(c.getTask_(accepted.data.task_id).status,'PENDING_AUTH');assert.equal(composioCalls,0);
grants=true;let result=c.doPost(signed({op:'status',taskId:accepted.data.task_id}));assert.equal(result.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');assert.equal(result.data.result.messagesTotal,7);assert.equal(result.data.google_tool,'GOOGLE_GMAIL_MAILBOX_METADATA');assert(result.data.evidence_fingerprint);assert.equal(composioCalls,0);
const fingerprint=c.ownerEvidenceFingerprint_(accepted.data.task_id);assert.equal(fingerprint,result.data.evidence_fingerprint);const challenge=c.ownerVerificationChallenge_({deviceId:enrolled.deviceId},{taskId:accepted.data.task_id,decision:'PARTIAL',evidenceFingerprint:fingerprint,comment:'synthetic fixture'});assert(challenge.nonce);
reasonObjective='List recent Google Drive files metadata';accepted=c.doPost(signed({op:'submit',clientTaskId:'native_drive',text:reasonObjective}));c.resumePendingTasksSoon_();result=c.doPost(signed({op:'status',taskId:accepted.data.task_id}));assert.equal(result.data.result.files[0].name,'Synthetic file');assert.equal(result.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');assert.equal(composioCalls,0);
for(const code of [401,403,500]){httpCode=code;status=c.googlePluginConnection_(enrolled.deviceId,'gmail',true);assert.equal(status.state,code===401?'EXPIRED':code===403?'REVOKED':'UNKNOWN');}httpCode=200;badJson=true;assert.equal(c.googlePluginConnection_(enrolled.deviceId,'gmail',false).state,'UNKNOWN');badJson=false;
const originalGet=c.googlePluginGet_;assert.throws(()=>originalGet('https://gmail.googleapis.com/gmail/v1/users/me/messages?q=private'),/ENDPOINT_DENIED/);assert.throws(()=>originalGet('https://evil.invalid'),/ENDPOINT_DENIED/);
assert.throws(()=>c.executeGooglePluginTask_(accepted.data.task_id,'Send Gmail mail'),/ROUTE_DENIED|WRITE_EXPANSION/);
const write=c.createTask_(enrolled.deviceId,'native_write','Delete Gmail messages');assert.throws(()=>c.executeGooglePluginTask_(write.task_id,'Delete Gmail messages'),/WRITES_DENIED/);
const nonGoogle=c.createTask_(enrolled.deviceId,'native_nongoogle','List Shopify products');assert.throws(()=>c.executeGooglePluginTask_(nonGoogle.task_id),/ROUTE_DENIED/);c.transitionTask_(nonGoogle.task_id,'BLOCKED');
assert(!JSON.stringify(sheets.LOGS.rows).includes('synthetic_native_oauth_token'));assert(!JSON.stringify(result).includes('synthetic_native_oauth_token'));assert.equal(composioCalls,0);
console.log('Native Google integration: exact baseline identity/enrollment, signed manager/device/replay/owner binding, scope/principal separation, consent URL/callback rejection, fresh missing grant -> same-task result, actual Gemini->Runtime->native repeat-read->owner evidence, Drive metadata, expired/revoked/HTTP/JSON gates, no search/write/nonGoogle and zero Composio transport. Mock transport only.');

reasonObjective='List recent Gmail headers';accepted=c.doPost(signed({op:'submit',clientTaskId:'native_headers',text:reasonObjective}));c.resumePendingTasksSoon_();result=c.doPost(signed({op:'status',taskId:accepted.data.task_id}));assert.equal(result.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');assert.equal(result.data.result.messages[0].subject,'Synthetic subject');assert(!JSON.stringify(result).includes('must not return'));assert.equal(result.data.google_tool,'GOOGLE_GMAIL_HEADER_METADATA');assert.equal(composioCalls,0);
console.log('Gmail metadata headers frozen-ID repeat-read through the actual runtime completed; body/snippet/unrequested header excluded.');

const headerReads=reads;principal='wrong@example.invalid';assert.throws(()=>c.googlePluginRead_('gmail',ownerHash,['mock_message_1']),/DIRECT_ADAPTER_BYPASS_DENIED/);assert.equal(reads,headerReads);principal='owner@example.invalid';
reasonObjective='Check Gmail mailbox counts';httpCode=401;accepted=c.doPost(signed({op:'submit',clientTaskId:'native_expired_task',text:reasonObjective}));c.resumePendingTasksSoon_();assert.equal(c.getTask_(accepted.data.task_id).status,'PENDING_AUTH');assert.equal(composioCalls,0);httpCode=200;result=c.doPost(signed({op:'status',taskId:accepted.data.task_id}));assert.equal(result.data.status,'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION');
console.log('Wrong native owner stops before header read; expired native grant persists same-task auth gate then resumes after actual server recheck.');
