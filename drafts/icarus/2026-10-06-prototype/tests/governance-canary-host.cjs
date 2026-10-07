// Start once, hand ONLY executor role to actual runner; verifier role to separate reviewer.
const http=require('http'),fs=require('fs'),path=require('path'),crypto=require('crypto');const {createFixture}=require('./governance-fixture.cjs');
const directory=process.argv[2];if(!directory)throw Error('DISPOSABLE_DIRECTORY_REQUIRED');
const f=createFixture(directory),executor=crypto.randomBytes(24).toString('hex'),verifier=crypto.randomBytes(24).toString('hex');
const events=[];let chain=Promise.resolve();
const server=http.createServer((req,res)=>{let raw='';req.on('data',x=>{raw+=x;if(raw.length>20000)req.destroy();});req.on('end',()=>{chain=chain.then(()=>{let out;try{const role=req.headers.authorization==='Bearer '+executor?'executor':req.headers.authorization==='Bearer '+verifier?'verifier':'none';if(role==='none')throw Error('AUTHENTICATION_DENIED');const b=raw?JSON.parse(raw):{},id=b.taskId||'fixtureC';
if(req.url==='/preflight'&&role==='executor')out={permit:f.preflight(id,b.plan)};
else if(req.url==='/execute'&&role==='executor')out={result:f.execute(id,b.permit,b.overrides)};
else if(req.url==='/bypass'&&role==='executor')out=f.bypass();
else if(req.url==='/raw-bypass'&&role==='executor')out=f.rawBypass();
else if(req.url==='/self-pass'&&role==='executor')out=f.selfPass(id,b.evidence);
else if(req.url==='/observe'&&role==='verifier')out={evidence:f.observe(id),effect:f.effect()};
else if(req.url==='/verify'&&role==='verifier')out=f.verify(id,b.evidence);
else if(req.url==='/status')out={snapshot:f.snapshot(id),effect:f.effect()};
else throw Error('RPC_ROLE_OR_OPERATION_DENIED');out={ok:true,...out};}catch(e){out={ok:false,error:e.message};}
events.push({at:new Date().toISOString(),path:req.url,requestHash:crypto.createHash('sha256').update(raw).digest('hex'),response:out});fs.writeFileSync(path.join(directory,'rpc-trace.json'),JSON.stringify(events,null,2));res.setHeader('Content-Type','application/json');res.end(JSON.stringify(out));});});});
server.listen(0,'127.0.0.1',()=>{const address='http://127.0.0.1:'+server.address().port;fs.writeFileSync(path.join(directory,'executor-access.json'),JSON.stringify({address,token:executor}));fs.writeFileSync(path.join(directory,'verifier-access.json'),JSON.stringify({address,token:verifier}));console.log(JSON.stringify({address,executorAccess:path.join(directory,'executor-access.json'),verifierAccess:path.join(directory,'verifier-access.json')}));});
