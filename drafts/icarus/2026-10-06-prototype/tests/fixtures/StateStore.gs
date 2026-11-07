function stateSpreadsheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('STATE_SHEET_ID') || (typeof ICARUS_BOOTSTRAP !== 'undefined' ? ICARUS_BOOTSTRAP.STATE_SHEET_ID : '');
  if (!id) throw new Error('STATE_SHEET_ID_NOT_CONFIGURED');
  return SpreadsheetApp.openById(id);
}

function sheet_(name) {
  const sh = stateSpreadsheet_().getSheetByName(name);
  if (!sh) throw new Error('MISSING_SHEET:' + name);
  return sh;
}

function ensureRuntimeSheets_() {
  const ss = stateSpreadsheet_();
  const defs = [
    [ICARUS.SHEETS.DEVICES, ['device_id','token_hash','status','paired_utc','last_seen_utc','app_build']],
    [ICARUS.SHEETS.MEMORY, ['memory_id','memory_type','status','source_ref','summary','revision','updated_utc','supersedes']],
    [ICARUS.SHEETS.CAPABILITIES, ['capability_id','enabled','scope','production_allowed','cost_class','verification_method','evidence_ref']],
    [ICARUS.SHEETS.EXPERIENCES, ['experience_id','source_agent','created_utc','domain','task_problem','environment_context','failure_signature','attempts_made','what_failed','root_cause','successful_recovery','verification_evidence','do_not_retry','reusable_principle','prerequisites','confidence','freshness_status','superseded_by','customer_safe_summary','internal_agent_detail']],
    [ICARUS.SHEETS.GATEWAYS, ['gateway_id','gateway_type','purpose','auth_mode','endpoint_ref','credential_ref','credential_location','owner_scope','runtime_role','status','enabled','production_allowed','cost_class','read_scope','write_scope','verification_method','last_verified_utc','risk_class','allowed_operations','notes']],
    [ICARUS.SHEETS.COMPOSIO, composioStateHeaders_()]
  ];
  defs.forEach(function(def) {
    let sh = ss.getSheetByName(def[0]);
    if (!sh) sh = ss.insertSheet(def[0]);
    if (sh.getLastRow() === 0) sh.appendRow(def[1]);
  });
}


function withScriptLock_(fn) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) throw new Error('RUNTIME_BUSY_RETRY');
  try { return fn(); }
  finally { lock.releaseLock(); }
}

function appendLog_(taskId, phase, status, action, evidenceRef, notes) {
  const sh = sheet_(ICARUS.SHEETS.LOGS);
  const runId = 'ICARUS-AS-' + Utilities.getUuid();
  // Existing EXECUTION_LOGS is 14 columns. Preserve its established topology.
  sh.appendRow([
    runId, nowIso_(), taskId || '', 'ICARUS Apps Script', phase || '', '', action || '',
    status || '', evidenceRef || '', '', '', '', 0, notes || ''
  ]);
  return runId;
}


function ensureTaskEvidenceColumn_() {
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  const width = Math.max(sh.getLastColumn(), 1);
  const headers = sh.getRange(1,1,1,width).getValues()[0].map(String);
  if (headers.indexOf('evidence_ref') < 0) {
    sh.getRange(1,width+1).setValue('evidence_ref');
    SpreadsheetApp.flush();
  }
}

function taskHeaders_() {
  ensureTaskEvidenceColumn_();
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  const width = Math.max(sh.getLastColumn(), 1);
  return sh.getRange(1,1,1,width).getValues()[0].map(String);
}

function taskRowObject_(rowValues) {
  const headers = taskHeaders_();
  const obj = {};
  headers.forEach(function(h, i) { if (h) obj[h] = rowValues[i]; });
  return obj;
}

function findTaskRow_(taskId) {
  ensureTaskEvidenceColumn_();
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  const values = sh.getDataRange().getValues();
  if (values.length < 2) return null;
  const headers = values[0].map(String);
  const idx = headers.indexOf('task_id');
  if (idx < 0) throw new Error('TASK_QUEUE_MISSING_task_id');
  for (let r = 1; r < values.length; r++) {
    if (String(values[r][idx]) === String(taskId)) return {row:r+1, headers:headers, values:values[r]};
  }
  return null;
}

function updateTaskFields_(taskId, patch) {
  if (patch && patch.status === 'PASS') throw new Error('OWNER_VERIFICATION_REQUIRED');
  if (patch && Object.keys(patch).some(function(k) { return k.indexOf('owner_verification')===0; })) throw new Error('OWNER_VERIFICATION_REQUIRED');
  measureTwiceStateMutationPreflight_(taskId, patch);
  const found = findTaskRow_(taskId);
  if (!found) throw new Error('TASK_NOT_FOUND');
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  Object.keys(patch).forEach(function(key) {
    const idx = found.headers.indexOf(key);
    if (idx >= 0) sh.getRange(found.row, idx + 1).setValue(patch[key]);
  });
  SpreadsheetApp.flush();
  return getTask_(taskId);
}

function getTask_(taskId) {
  const found = findTaskRow_(taskId);
  return found ? taskRowObject_(found.values) : null;
}

function findTaskByClientId_(clientTaskId, deviceId) {
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  const data = sh.getDataRange().getValues();
  if (data.length < 2) return null;
  const headers = data[0].map(String);
  const payloadIdx = headers.indexOf('payload_ref');
  if (payloadIdx < 0) return null;
  const needle = 'client_task_id:' + clientTaskId;
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][payloadIdx]) === needle) {
      const task = taskRowObject_(data[r]);
      if (String(task.source) === 'ANDROID:' + deviceId) return task;
    }
  }
  return null;
}

function createTask_(deviceId, clientTaskId, text) {
  return withScriptLock_(function() {
    if (!clientTaskId || !text.trim()) throw new Error('INVALID_TASK');
    const existing = findTaskByClientId_(clientTaskId, deviceId);
    if (existing) {
      if (String(existing.objective) !== text) throw new Error('IDEMPOTENCY_CONFLICT');
      return existing;
    }
    const taskId = 'ICT-' + Utilities.getUuid();
    const sh = sheet_(ICARUS.SHEETS.TASKS);
    const headers = taskHeaders_();
    const values = new Array(headers.length).fill('');
    const assign = function(key, value) { const i=headers.indexOf(key); if(i>=0) values[i]=value; };
    assign('task_id', taskId);
    assign('status', 'QUEUED');
    assign('priority', 'P1');
    assign('source', 'ANDROID:' + deviceId);
    assign('objective', text);
    assign('target_environment', 'NON_PROD');
    assign('action_type', 'ICARUS_TASK');
    assign('payload_ref', 'client_task_id:' + clientTaskId);
    assign('verification_criteria', 'Evidence-backed terminal state or explicit BLOCKED state.');
    assign('created_utc', nowIso_());
    assign('owner_relay_required', false);
    sh.appendRow(values);
    appendLog_(taskId, 'INTAKE', 'QUEUED', 'Persisted Android task before execution.', 'TASK_QUEUE:' + taskId, 'client_task_id=' + clientTaskId);
    return getTask_(taskId) || {task_id:taskId,status:'QUEUED'};
  });
}
