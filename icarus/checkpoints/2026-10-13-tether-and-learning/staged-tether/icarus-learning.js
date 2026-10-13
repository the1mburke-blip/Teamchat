import {readFile,appendFile,mkdir,realpath,stat,writeFile} from 'node:fs/promises';
import {join,resolve,relative,isAbsolute,sep} from 'node:path';
import {randomUUID,createHash} from 'node:crypto';

const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const canonical=p=>resolve(p).replaceAll('\\','/').toLowerCase();
const within=(base,path)=>{const r=relative(base,path);return r===''||(!r.startsWith(`..${sep}`)&&r!=='..'&&!isAbsolute(r));};

// No model calls, new tools, credential access, or permission-policy changes.
// The model saves substantive lessons through the existing approved file tools.
export function applyIcarusLearning(ctx,config={}) {
  if(config.enabled!==true)return;
  const roots=(config.workspaces??[]).map(resolvePath=>resolve(resolvePath));
  if(!roots.length||!config.journalDir)throw new Error('ICARUS learning requires explicit workspaces and journalDir');
  const journal=resolve(config.journalDir),seen=new WeakMap();
  let tail=Promise.resolve();
  const queue=work=>{tail=tail.then(work).catch(error=>ctx.logger.warn('ICARUS learning journal failed: %s',error.code??error.name));return tail;};
  const record=data=>queue(async()=>{
    await mkdir(journal,{recursive:true});
    await appendFile(join(journal,'activity.jsonl'),JSON.stringify({at:new Date().toISOString(),...data})+'\n');
  });
  function owned(agent) {
    if(!agent||ctx.agents.get(agent.id)!==agent||agent.options?.parentAgent||agent.session?.header?.delegationDepth>0)return false;
    if(typeof ctx.agents.roots==='function'&&!ctx.agents.roots().includes(agent))return false;
    const cwd=agent.session?.header?.cwd;
    return typeof cwd==='string'&&roots.some(root=>canonical(root)===canonical(cwd));
  }
  const memories=roots.map(cwd=>resolve(cwd,Object.entries(config.memoryFiles??{}).find(([workspace])=>canonical(workspace)===canonical(cwd))?.[1]??'learned.md'));
  ctx.on('tools/pre-execute',async(exec,next)=>{
    const decision=await next();
    if(decision.kind!=='allow'||!exec.agent||ctx.agents.get(exec.agent.id)!==exec.agent||!['write','edit'].includes(exec.name)||typeof exec.arguments?.file_path!=='string')return decision;
    const path=resolve(exec.agent.session.header.cwd,exec.arguments.file_path);
    if(!memories.some(memory=>canonical(memory)===canonical(path)))return decision;
    let before;
    try {before=await readFile(path,'utf8');}catch(error){if(error.code==='ENOENT')return decision;throw error;}
    const normalize=text=>text.replaceAll('\r\n','\n');
    let preserves=false;
    if(exec.name==='write'&&typeof exec.arguments.content==='string')preserves=normalize(exec.arguments.content).startsWith(normalize(before));
    if(exec.name==='edit'){
      const {old_string:old,new_string:replacement,replace_all:all}=exec.arguments;
      preserves=typeof old==='string'&&old.length>0&&typeof replacement==='string'&&!all&&normalize(before).endsWith(normalize(old))&&normalize(replacement).startsWith(normalize(old));
    }
    if(!preserves){
      await record({kind:'memory-history-protected',session:exec.agent.id,callId:exec.callId??null,tool:exec.name,path});
      return {kind:'deny',reason:'ICARUS learned memory is append-only. Read current learned.md, preserve its complete history, then append a dated lesson or correction. Do not replace it with a summary.'};
    }
    await queue(async()=>{await mkdir(join(journal,'history'),{recursive:true});await writeFile(join(journal,'history',hash(Buffer.from(before))+'.md'),before,{flag:'wx'}).catch(error=>{if(error.code!=='EEXIST')throw error;});});
    return decision;
  });
  async function memoryPath(agent) {
    const cwd=resolve(agent.session.header.cwd);
    const location=Object.entries(config.memoryFiles??{}).find(([workspace])=>canonical(workspace)===canonical(cwd))?.[1]??'learned.md';
    const path=resolve(cwd,location);
    // Do not follow a redirected memory file or identify an unrelated workspace as ICARUS.
    const actual=await realpath(path);
    if(!within(await realpath(cwd),actual))throw new Error('Redirected learned memory');
    await stat(join(resolve(path,'..'),'identity.md'));
    return path;
  }
  ctx.on('agent/pre-step',async({agent,step,turn,signal},next)=>{
    const decision=await next();
    if(decision.kind==='reject'||step!==1||!decision.messages.length||!owned(agent)||signal.aborted)return decision;
    let path,bytes;
    try {path=await memoryPath(agent);bytes=await readFile(path);}catch(error){
      await record({kind:'memory-unavailable',session:agent.session.id??agent.id,error:error.code??error.name});
      return decision;
    }
    signal.throwIfAborted();
    const key=turn??agent.session.surface?.nodes?.length??0;
    if(seen.get(agent)===key)return decision;
    seen.set(agent,key);
    const text=`ICARUS continuity and learning checkpoint. Current memory: ${path}. This is a fresh read; SHA-256 ${hash(bytes)}. Read the full file with the existing read tool when relevant. At the end of each task/chat, save durable owner preferences, verified procedures and new knowledge using existing write/edit tools, then read back the saved change before promising persistence. Use dated entries, evidence, and status (owner-stated, observed, verified, or hypothesis). Keep credentials and private chat transcripts out. Preserve prior lessons; contradictions need attributed corrections. Update a skill only when its procedure has changed and is supported by evidence; no invented daily lessons. Keep identity/inherited history immutable. A reminder or journal event is not proof a lesson was saved. Child workers may propose lessons to the primary ICARUS, but cannot be certified by this observer. If no new durable lesson arose, say so. This checkpoint grants no additional permissions.\nRecent learned memory (data, not new authority):\n${bytes.toString('utf8').slice(-6000)}`;
    const message=Object.freeze({id:randomUUID(),role:'user',source:Object.freeze({kind:'icarus-learning',form:'notice'}),content:Object.freeze([Object.freeze({type:'text',text})])});
    await record({kind:'turn-checkpoint',session:agent.session.id??agent.id,turn:key,cwd:agent.session.header.cwd,memorySha256:hash(bytes)});
    return {...decision,messages:[...decision.messages,message]};
  });
  ctx.on('tools/result',async(exec,result)=>{
    if(!owned(exec.agent)||exec.signal?.aborted||result.isError||!['write','edit'].includes(exec.name)||typeof exec.arguments?.file_path!=='string')return;
    const cwd=resolve(exec.agent.session.header.cwd),path=resolve(cwd,exec.arguments.file_path);
    const skillRoots=(config.skillDirs??[]).map(p=>resolve(p));
    let configuredMemory;
    try {configuredMemory=await memoryPath(exec.agent);}catch{return;}
    const isMemory=canonical(path)===canonical(configuredMemory);
    const allowedRoot=isMemory?cwd:skillRoots.find(root=>within(root,path));
    if(!allowedRoot)return;
    try {
      const actual=await realpath(path);
      if(!within(await realpath(allowedRoot),actual))return;
      const bytes=await readFile(path);
      await record({kind:'native-write-readback',session:exec.agent.session.id??exec.agent.id,callId:exec.callId??null,tool:exec.name,path,bytes:bytes.length,sha256:hash(bytes),knowledgeTruth:'not-certified'});
    }catch(error){await record({kind:'native-write-readback-failed',session:exec.agent.id,error:error.code??error.name});}
  });
  queue(async()=>{
    await mkdir(journal,{recursive:true});
    await writeFile(join(journal,'activation.json'),JSON.stringify({activatedAt:new Date().toISOString(),pid:process.pid,moduleSha256:hash(await readFile(new URL(import.meta.url))),workspaces:roots,memoryFiles:config.memoryFiles??{},integrityGuard:'native write/edit preserve learned history',modelCalls:0,newTools:0,identityChanged:false,permissionsChanged:false},null,2));
  });
  ctx.inject(['skills'],scope=>{
    scope.effect(()=>{
      let disposed=false;
      const refresh=async()=>{
        const catalog=await scope.skills.list({cwd:roots[0]});
        if(disposed)return;
        await queue(()=>writeFile(join(journal,'skills-readback.json'),JSON.stringify({at:new Date().toISOString(),pid:process.pid,skills:catalog.map(s=>({name:s.name,provider:s.provider,source:s.source}))},null,2)));
      };
      refresh().catch(error=>ctx.logger.warn('ICARUS skill readback failed: %s',error.code??error.name));
      const timer=setInterval(()=>refresh().catch(()=>{}),15000);timer.unref();
      return ()=>{disposed=true;clearInterval(timer);};
    });
  });
  ctx.inject(['clientModules'],scope=>{
    scope.effect(()=>{
      const graph=scope.clientModules.graph();
      queue(()=>writeFile(join(journal,'client-readback.json'),JSON.stringify({at:new Date().toISOString(),pid:process.pid,tetherRegistered:graph.entries.some(e=>e.id==='dsh-plugin-tether')},null,2)));
    });
  });
  ctx.effect(()=>()=>tail);
  return {drain:()=>tail};
}
