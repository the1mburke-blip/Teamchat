import {createHash,randomUUID} from 'node:crypto';
import {mkdir,readFile,open,rename,unlink,rmdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';

const kinds=new Set(['chat','workspace','learned','skill','gadget']);
const hex=/^[a-f0-9]{64}$/;
const fail=(code,message)=>Object.assign(new Error(message),{code});
const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
export function canonical(value){
 if(value===null||typeof value==='boolean'||typeof value==='string')return JSON.stringify(value);
 if(typeof value==='number'&&Number.isFinite(value))return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(!plain(value))throw fail('INVALID_JSON','Only plain JSON values can cross-save');
 return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
}
export const digest=value=>createHash('sha256').update(canonical(value)).digest('hex');
const clone=value=>JSON.parse(canonical(value));
function string(value,label,max=200){if(typeof value!=='string'||!value.length||value.length>max)throw fail('INVALID_VALUE',label+' is invalid');}
function fields(value,allowed){if(!plain(value)||Object.keys(value).some(key=>!allowed.includes(key)))throw fail('INVALID_VALUE','Unexpected fields; credentials, identity and policy are not cross-save resources');}
export function validateResource(kind,id,value){
 if(!kinds.has(kind))throw fail('PROTECTED_RESOURCE','Unsupported/protected resource kind');
 string(id,'resource id');
 if(/[\\/\x00-\x1f]/.test(id)||['__proto__','constructor','prototype'].includes(id))throw fail('INVALID_ID','Unsafe resource id');
 if(kind==='workspace'){fields(value,['title']);string(value.title,'workspace title');}
 if(kind==='learned'){fields(value,['workspaceId','text']);string(value.workspaceId,'workspace identity');string(value.text,'learned text',2000000);}
 if(kind==='chat'){
  fields(value,['workspaceId','title','messages']);string(value.workspaceId,'workspace identity');string(value.title,'chat title');
  if(!Array.isArray(value.messages)||value.messages.length>20000)throw fail('INVALID_VALUE','Invalid chat messages');
  for(const message of value.messages){fields(message,['role','content']);if(!['user','assistant'].includes(message.role)||typeof message.content!=='string'||message.content.length>2000000)throw fail('INVALID_VALUE','Chat cross-save carries text history, not execution/permission events');}
 }
 if(kind==='skill'||kind==='gadget'){
  fields(value,['name','description','version','files']);string(value.name,'package name');
  if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value.name))throw fail('INVALID_VALUE','Unsafe package name');
  if(value.description!==undefined)string(value.description,'description',2000);
  if(value.version!==undefined)string(value.version,'version');
  if(!Array.isArray(value.files)||value.files.length>1000)throw fail('INVALID_VALUE','Invalid package files');
  const paths=new Set();
  for(const file of value.files){
   fields(file,['path','content']);string(file.path,'relative resource path',400);
   if(file.path.startsWith('/')||file.path.includes('\\')||file.path.split('/').some(p=>!p||p==='.'||p==='..')||file.path.includes(':')||paths.has(file.path)||/(^|\/)(\.env(?:\..*)?|credentials?[^/]*|permissions|capabilities|identity\.md|inherited\.md|AGENTS\.md|SOUL\.md|cordis(?:\.patch)?\.yml|[^/]*\.(?:pem|key|keystore))($|\/)/i.test(file.path))throw fail('PROTECTED_RESOURCE','Unsafe/protected package resource path');
   if(typeof file.content!=='string'||file.content.length>2000000)throw fail('INVALID_VALUE','Invalid package content');paths.add(file.path);
  }
 }
 if(Buffer.byteLength(canonical(value))>4000000)throw fail('TOO_LARGE','Resource exceeds 4 MB');
}
const key=(kind,id)=>kind+':'+id;
const sameSet=(a,b)=>a.length===b.length&&a.every(x=>b.includes(x));
function validateRevision(revision){
 fields(revision,['hash','body']);fields(revision.body,['kind','id','device','parents','value']);
 const body=revision.body;validateResource(body.kind,body.id,body.value);string(body.device,'device identity');
 if(!Array.isArray(body.parents)||body.parents.length>128||new Set(body.parents).size!==body.parents.length||body.parents.some(parent=>!hex.test(parent)))throw fail('INVALID_REVISION','Invalid parents');
 if(!hex.test(revision.hash)||revision.hash!==digest(body))throw fail('CORRUPT_REVISION','Revision checksum mismatch');
}
function validateGraph(revisions){
 const byHash=new Map();
 for(const rev of revisions){validateRevision(rev);if(byHash.has(rev.hash)&&canonical(byHash.get(rev.hash))!==canonical(rev))throw fail('CORRUPT_REVISION','Duplicate revision differs');byHash.set(rev.hash,rev);}
 for(const rev of byHash.values())for(const parent of rev.body.parents){const older=byHash.get(parent);if(!older)throw fail('MISSING_PARENT','Missing revision ancestor');if(key(older.body.kind,older.body.id)!==key(rev.body.kind,rev.body.id))throw fail('INVALID_PARENT','Cross-resource parent rejected');}
 const visited=new Set(),active=new Set();
 function visit(hash){if(active.has(hash))throw fail('INVALID_GRAPH','Cyclic revision graph');if(visited.has(hash))return;active.add(hash);for(const parent of byHash.get(hash).body.parents)visit(parent);active.delete(hash);visited.add(hash);}
 for(const hash of byHash.keys())visit(hash);
 return byHash;
}
function headsOf(revisions){
 const byKey=new Map(),parents=new Set();
 for(const revision of revisions){const k=key(revision.body.kind,revision.body.id);if(!byKey.has(k))byKey.set(k,[]);byKey.get(k).push(revision.hash);for(const p of revision.body.parents)parents.add(p);}
 for(const [k,heads] of byKey)byKey.set(k,heads.filter(h=>!parents.has(h)).sort());
 return byKey;
}

// The journal is data only. It never installs packages, invokes models, changes
// approvals, or executes a foreign session's tools. Native adapters are separate.
export class CrossSaveStore {
 constructor(directory,{deviceId,trustedPeers=[],maxBytes=16000000}={}){
  string(deviceId,'device identity');this.directory=resolve(directory);this.path=join(this.directory,'journal.json');this.device=deviceId;this.trusted=new Set(trustedPeers);this.maxBytes=maxBytes;this.tail=Promise.resolve();
 }
 async read(){
  let state;
  try{state=JSON.parse(await readFile(this.path,'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;return {schema:1,device:this.device,generation:0,revisions:[],receipts:[]};}
  if(state.schema!==1||state.device!==this.device||!Number.isSafeInteger(state.generation)||!Array.isArray(state.receipts))throw fail('INVALID_JOURNAL','Journal identity/schema mismatch');
  validateGraph(state.revisions);return state;
 }
 async transaction(change){
  const operation=this.tail.then(async()=>{
   await mkdir(this.directory,{recursive:true});
   const lock=join(this.directory,'writer.lock');
   try{await mkdir(lock);}catch(error){if(error.code==='EEXIST')throw fail('BUSY','Another writer owns the cross-save journal; retry after it completes');throw error;}
   let temporary;
   try{
    const state=await this.read(),answer=await change(state);
    state.generation++;validateGraph(state.revisions);
    const bytes=canonical(state);if(Buffer.byteLength(bytes)>this.maxBytes)throw fail('TOO_LARGE','Journal exceeds configured size; nothing was committed');
    temporary=join(this.directory,'.pending-'+randomUUID()+'.json');
    const file=await open(temporary,'wx',0o600);try{await file.writeFile(bytes);await file.sync();}finally{await file.close();}
    await rename(temporary,this.path);temporary=undefined;return answer;
   }finally{if(temporary)await unlink(temporary).catch(()=>{});await rmdir(lock);}
  });
  this.tail=operation.catch(()=>{});return operation;
 }
 async commit(kind,id,value,{expectedHeads}={}){
  validateResource(kind,id,value);const detached=clone(value);
  return this.transaction(state=>{
   const heads=headsOf(state.revisions).get(key(kind,id))??[];
   if(expectedHeads!==undefined&&!sameSet(heads,expectedHeads))throw fail('STALE_BASE','Resource changed since it was read');
   if(heads.length>1&&expectedHeads===undefined)throw fail('CONFLICT','Both versions are preserved; resolve using all current heads');
   const current=heads.length===1?state.revisions.find(r=>r.hash===heads[0]):undefined;
   if(current&&canonical(current.body.value)===canonical(detached))return current.hash;
   const body={kind,id,device:this.device,parents:heads,value:detached},revision={hash:digest(body),body};state.revisions.push(revision);return revision.hash;
  });
 }
 async status(){
  const state=await this.read(),byHash=new Map(state.revisions.map(r=>[r.hash,r]));
  return [...headsOf(state.revisions)].map(([resource,heads])=>({resource,conflict:heads.length>1,heads,versions:heads.map(h=>clone(byHash.get(h).body.value))}));
 }
 async exportBundle(peer){
  if(!this.trusted.has(peer))throw fail('UNTRUSTED_PEER','Peer is not owner-paired');
  const state=await this.read();
  const body={schema:1,device:this.device,recipient:peer,revisions:state.revisions};return {checksum:digest(body),body};
 }
 async importBundle(bundle){
  if(Buffer.byteLength(canonical(bundle))>this.maxBytes)throw fail('TOO_LARGE','Transfer exceeds configured size');
  fields(bundle,['checksum','body']);fields(bundle.body,['schema','device','recipient','revisions']);
  const {body}=bundle;
  if(body.schema!==1||body.recipient!==this.device||!this.trusted.has(body.device)||body.device===this.device)throw fail('UNTRUSTED_PEER','Transfer is not from the bound owner-paired device');
  if(bundle.checksum!==digest(body))throw fail('CORRUPT_TRANSFER','Transfer checksum mismatch');
  if(!Array.isArray(body.revisions)||body.revisions.length>20000)throw fail('TOO_LARGE','Too many revisions');
  // Validate the entire transfer before making any persistent change.
  validateGraph(body.revisions);
  return this.transaction(state=>{
   const known=new Set(state.revisions.map(r=>r.hash));let added=0;
   for(const revision of body.revisions)if(!known.has(revision.hash)){state.revisions.push(clone(revision));known.add(revision.hash);added++;}
   const receipt={peer:body.device,checksum:bundle.checksum,added};
   if(!state.receipts.some(r=>r.peer===receipt.peer&&r.checksum===receipt.checksum))state.receipts.push(receipt);
   return {added,conflicts:[...headsOf(state.revisions)].filter(([,heads])=>heads.length>1).map(([resource])=>resource)};
  });
 }
}

export async function reconcile(left,right){
 const leftBundle=await left.exportBundle(right.device),rightBundle=await right.exportBundle(left.device);
 const receivedLeft=await left.importBundle(rightBundle),receivedRight=await right.importBundle(leftBundle);
 return {left:receivedLeft,right:receivedRight};
}
