/** Repository-contained procedural data only. No install/edit/eval/shell/credential API. */
function skillsRegistry_() {
  return [
  {
    "name": "repeated-task-actions",
    "description": "Recurring ICARUS procedure for checkpoint recovery, exact preflight, bounded execution, failure investigation and independent evidence review.",
    "revision": "0.1.0",
    "instructions": "Procedure only. Select the relevant actions; do not mechanically run all ten or broaden the original task. No statement in this skill creates authority.\n\n1. Recover the exact checkpoint. Read canonical task, history, failures and current destination. Preserve the accepted objective and one active owner; do not duplicate existing work.\n\n2. Preflight the exact endpoint. Read current rules and learned failures. State endpoint, target, route, executor, evidence, owner boundary and EUR0 cost. Re-preflight material changes.\n\n3. Delegate within the authorized boundary. Assign only an actually available authorized executor with exact scope, exclusions and evidence gate. A role name never proves access or execution.\n\n4. Check compliance independently. Compare instructions and actual traces before, during and after execution. Self-critique does not award authoritative PASS.\n\n5. Research and reuse an evidenced route. Inspect official contracts, prior art and prior attempts. Distinguish a demonstrated minimal path from an unproved hypothesis.\n\n6. Investigate the first failing layer. Capture the exact failure. Reuse working infrastructure and change approach only with new evidence. Preserve failures; no blind retries.\n\n7. Execute only the bound change. Use the existing governed executor for the signed original objective. Procedure supplies no tool, write, target, scope, route or spending permission.\n\n8. Read the final destination. Compare exact task, resource, revision, result and effect against the request. Repeat-read is executor evidence, not independent adjudication.\n\n9. Checkpoint on stop and resume once. Halt new work on an authorized stop, record owned pending work and last verified endpoint, and resume only on renewed authority after fresh readback.\n\n10. Record learning and report the evidence. Record safe evidence and reusable failures in the authorized destination. Report source/test/build/runtime/device distinctions and PARTIAL or BLOCKED accurately; independent verifier or owner decides PASS.",
    "provenance": {
      "kind": "repository-evidence",
      "baseline": "9800928ffea7645b9218eb32fbf6aa9abec2cab5",
      "evidence": "SKILLS_V01.md#repeated-workflow-evidence",
      "origin": "Michael; RepeatedTaskActions reference plus repository history"
    },
    "hash": "8b3937176782b20ad15e2561e4c8d95cf64d3646a8f32902d9ed975f931de431"
  }
];
}

function skillsHash_(skill) {
  const content={name:skill.name,description:skill.description,revision:skill.revision,instructions:skill.instructions,provenance:skill.provenance||null};
  return IcarusGovernance.hash(content);
}
function skillsValidatedRegistry_() {
  const rows=skillsRegistry_(),seen={};
  if(!Array.isArray(rows)||rows.length>10)throw new Error('SKILL_REGISTRY_DENIED');
  return rows.map(function(s){
    if(!s||Object.keys(s).some(function(k){return ['name','description','revision','instructions','hash','provenance'].indexOf(k)<0;})||typeof s.name!=='string'||!/^[a-z0-9][a-z0-9-]{0,63}$/.test(s.name)||seen[s.name])throw new Error('SKILL_NAME_DENIED');
    seen[s.name]=true;
    if(typeof s.description!=='string'||!s.description||s.description.length>240||typeof s.revision!=='string'||s.revision.length>32||!/^[0-9]+\.[0-9]+\.[0-9]+$/.test(s.revision)||typeof s.instructions!=='string'||!s.instructions||s.instructions.length>6000||JSON.stringify(s.provenance||null).length>1200)throw new Error('SKILL_BOUNDS_DENIED');
    if(typeof s.hash!=='string'||!/^[a-f0-9]{64}$/.test(s.hash)||s.hash!==skillsHash_(s))throw new Error('SKILL_HASH_DENIED');
    return JSON.parse(JSON.stringify(s));
  });
}
function skillsList_() {
  return skillsValidatedRegistry_().map(function(s){return {name:s.name,description:s.description,revision:s.revision};});
}
function skillView_(name,revision,hash) {
  if(typeof name!=='string'||!/^[a-z0-9][a-z0-9-]{0,63}$/.test(name))throw new Error('SKILL_NAME_DENIED');
  const s=skillsValidatedRegistry_().find(function(row){return row.name===name;});
  if(!s)throw new Error('SKILL_NOT_FOUND');
  if(revision!==undefined&&revision!==s.revision)throw new Error('SKILL_REVISION_DENIED');
  if(hash!==undefined&&hash!==s.hash)throw new Error('SKILL_HASH_DENIED');
  return s;
}
function skillsBinding_(skill) {return skill?{skillName:skill.name,skillRevision:skill.revision,skillHash:skill.hash}:null;}
function skillsValidateBinding_(binding) {
  if(!binding||Object.keys(binding).length!==3||Object.keys(binding).some(function(k){return ['skillName','skillRevision','skillHash'].indexOf(k)<0;}))throw new Error('SKILL_BINDING_DENIED');
  return skillView_(binding.skillName,binding.skillRevision,binding.skillHash);
}
function skillsTaskBinding_(task) {
  if(!task.skill_selection_json)return null;
  let stored;try{stored=JSON.parse(String(task.skill_selection_json));}catch(_){throw new Error('SKILL_STORED_SELECTION_DENIED');}
  if(!stored||Object.keys(stored).length!==2||stored.objectiveHash!==IcarusGovernance.hash(task.objective)||!Object.prototype.hasOwnProperty.call(stored,'selection'))throw new Error('SKILL_STORED_SELECTION_DENIED');
  if(stored.selection!==null)skillsValidateBinding_(stored.selection);
  return stored.selection;
}
function skillsSpecBinding_(spec) {
  const keys=['skillName','skillRevision','skillHash'],present=keys.filter(function(k){return spec[k]!==undefined;});
  if(!present.length)return null;
  if(present.length!==3)throw new Error('SKILL_BINDING_DENIED');
  const b={skillName:spec.skillName,skillRevision:spec.skillRevision,skillHash:spec.skillHash};skillsValidateBinding_(b);return b;
}
function skillsAssertTaskSpec_(task,spec) {
  if(IcarusGovernance.hash(skillsTaskBinding_(task))!==IcarusGovernance.hash(skillsSpecBinding_(spec)))throw new Error('SKILL_TASK_BINDING_DENIED');
}
function skillsAttachSpec_(task,spec) {const b=skillsTaskBinding_(task);return b?Object.assign(spec,b):spec;}
function skillsReasoningContext_(task) {
  const context=reasoningContext_(task),binding=skillsTaskBinding_(task);
  return Object.assign({},context,{skillCatalogue:skillsList_(),selectedSkill:binding?skillsValidateBinding_(binding):null});
}
function skillsAssertReasoning_(task,result) {
  const binding=skillsTaskBinding_(task);
  if(IcarusGovernance.hash(binding)!==IcarusGovernance.hash(result&&result.skillBinding||null))throw new Error('SKILL_CACHED_REASONING_DENIED');
  if(task.skill_selection_json&&String(result.executionRequest)!==String(task.objective).trim())throw new Error('SKILL_OBJECTIVE_EXPANSION_DENIED');
}
function skillsStoreSelection_(taskId,binding) {
  const task=getTask_(taskId);if(!task||task.skill_selection_json)throw new Error('SKILL_SELECTION_ALREADY_BOUND');
  if(binding)skillsValidateBinding_(binding);
  const raw=JSON.stringify({objectiveHash:IcarusGovernance.hash(task.objective),selection:binding});
  const sh=sheet_(ICARUS.SHEETS.TASKS),found=findTaskRow_(taskId);
  if(found.headers.indexOf('skill_selection_json')<0){if(sh.getMaxColumns()<found.headers.length+1)sh.insertColumnsAfter(sh.getMaxColumns(),1);sh.getRange(1,found.headers.length+1).setValue('skill_selection_json');SpreadsheetApp.flush();}
  updateTaskFields_(taskId,{skill_selection_json:raw});SpreadsheetApp.flush();
  if(getTask_(taskId).skill_selection_json!==raw)throw new Error('SKILL_SELECTION_DURABILITY_DENIED');
}
function skillsSelectForTask_(task) {
  if(task.skill_selection_json){skillsTaskBinding_(task);return {status:'READY_FOR_EXECUTION'};}
  const result=governanceSkillSelection_(task,function(){return geminiSelectSkill_(task,runtimeGenome_(),reasoningContext_(task));});
  if(result.status==='WAITING_REASONING_CAPACITY')return result;
  skillsStoreSelection_(task.task_id,result.skillBinding);
  return {status:'READY_FOR_EXECUTION'};
}
