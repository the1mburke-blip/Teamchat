const assert=require('assert'),fs=require('fs'),os=require('os'),path=require('path');
const {createFixture}=require('./governance-fixture.cjs');const dir=fs.mkdtempSync(path.join(os.tmpdir(),'icarus-governance-test-')),f=createFixture(dir);
try{
 assert.throws(()=>f.preflight('fixtureA',{...f.plan,text:'evil'}),/VALUE_REQUIRED|TEXT_EXPANSION|PLAN_DENIED/);
 assert.throws(()=>f.bypass(),/DIRECT_ADAPTER_BYPASS_DENIED/);assert.throws(()=>f.rawBypass(),/DIRECT_TRANSPORT_BYPASS_DENIED/);
 const pc=f.preflight('fixtureC');f.execute('fixtureC',pc);assert.equal(f.effect().mutations,1);assert.equal(f.snapshot('fixtureC').state,'WORK_COMPLETE_AWAITING_VERIFICATION');
 const pd=f.preflight('fixtureD');assert.throws(()=>f.execute('fixtureD',pd,{scopes:['write:anything']}),/MATERIAL_CHANGE_PREFLIGHT_REQUIRED/);assert.equal(f.snapshot('fixtureD').state,'REQUIRES_PREFLIGHT');
 const pe=f.preflight('fixtureE');assert.throws(()=>f.execute('fixtureE',pe,{route:'COMPOSIO_V31'}),/MATERIAL_CHANGE_PREFLIGHT_REQUIRED/);assert.equal(f.snapshot('fixtureE').state,'REQUIRES_PREFLIGHT');
 assert.throws(()=>f.execute('fixtureC',pc),/REPLAY_DENIED/);assert.equal(f.effect().mutations,1);
 assert.throws(()=>f.selfPass('fixtureC',f.observe('fixtureC')),/IDENTITY_DENIED|SELF_CERTIFICATION_DENIED/);
 const evidence=f.observe('fixtureC');assert.throws(()=>f.verify('fixtureC',{...evidence,taskId:'fixtureH'}),/EVIDENCE_MISMATCH/);assert.throws(()=>f.verify('fixtureC',{...evidence,observedHash:'forged'}),/EVIDENCE_MISMATCH/);assert.equal(f.verify('fixtureC',evidence).state,'PASS');
 const pu=f.preflight('fixtureU');f.setUncertain(true);assert.throws(()=>f.execute('fixtureU',pu),/WRITE_OUTCOME_UNKNOWN/);assert.equal(f.snapshot('fixtureU').state,'OUTCOME_UNKNOWN');assert.throws(()=>f.preflight('fixtureU'),/RECONCILIATION_REQUIRED/);assert.throws(()=>f.execute('fixtureU',pu),/REPLAY_DENIED/);assert.equal(f.effect().mutations,2);
 const px=f.preflight('fixtureX');const tampered=structuredClone(px);tampered.payload.agentId='attacker';assert.throws(()=>f.execute('fixtureX',tampered),/SIGNATURE_DENIED/);
 assert.throws(()=>f.kernel.run(px,f.spec('fixtureX'),f.actor,()=>{f.ctx.googleBundleWrite_({task_id:'fixtureX'}, {...f.plan,range:'B5'},{});}),/ADAPTER_SCOPE_DENIED/);
 const gmailSpec={...f.spec('fixtureX'),service:'gmail',operation:'mailbox_counts',write:false,tool:'GOOGLE_GMAIL_MAILBOX_METADATA',target:{owner:'fixture'},payloadHash:'metadata-only',scopes:['gmail.metadata']};
 const pg=f.kernel.prepare('fixtureG',gmailSpec,f.actor);f.kernel.run(pg,gmailSpec,f.actor,()=>{assert.throws(()=>f.ctx.googlePluginGet_('https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=3'),/WIRE_OPERATION_DENIED/);return {counts:0};});
 assert.equal(f.effect().mutations,2);console.log('Governance adversarial source gates A-H plus uncertain/replay/signature/exact adapter scope completed. Disposable fixture only; independent actual runner still required.');
}finally{fs.rmSync(dir,{recursive:true,force:true});}
