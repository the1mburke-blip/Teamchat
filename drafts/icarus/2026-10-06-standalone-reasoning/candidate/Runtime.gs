function transitionAllowed_(from, to) {
  const allowed = {
    'QUEUED':['INSPECTING','BLOCKED','FAIL'],
    'INSPECTING':['REASONING','EXECUTING','BLOCKED','FAIL'],
    'REASONING':['EXECUTING','WAITING_REASONING_CAPACITY','BLOCKED','FAIL'],
    'WAITING_REASONING_CAPACITY':['REASONING','BLOCKED','FAIL'],
    'EXECUTING':['PENDING_AUTH','VERIFYING','BLOCKED','FAIL'],
    'PENDING_AUTH':['EXECUTING','BLOCKED','FAIL'],
    'VERIFYING':['WORK_COMPLETE_AWAITING_OWNER_VERIFICATION','PARTIAL','BLOCKED','FAIL']
  };
  return !!(allowed[from] && allowed[from].indexOf(to) >= 0);
}

function transitionTask_(taskId, toStatus, patch) {
  if (toStatus === 'PASS') throw new Error('OWNER_VERIFICATION_REQUIRED');
  const task = getTask_(taskId);
  if (!task) throw new Error('TASK_NOT_FOUND');
  const from = String(task.status || '');
  if (from !== toStatus && !transitionAllowed_(from, toStatus)) {
    throw new Error('INVALID_STATE_TRANSITION:' + from + '->' + toStatus);
  }
  const next = Object.assign({}, patch || {}, {status:toStatus});
  return updateTaskFields_(taskId, next);
}

function advanceTask_(taskId, explicitResume) {
  return withScriptLock_(function() { return advanceTaskLocked_(taskId, explicitResume); });
}

function taskReasoningLog_(taskId) {
  const rows=sheet_(ICARUS.SHEETS.LOGS).getDataRange().getValues();
  for (let r=rows.length-1;r>0;r--) {
    if (String(rows[r][2]) === String(taskId) && String(rows[r][4]) === 'REASONING') {
      if (String(rows[r][7]) === 'READY_FOR_EXECUTION') return JSON.parse(String(rows[r][13]));
      return {status:String(rows[r][7])};
    }
  }
  return null;
}

function advanceTaskLocked_(taskId, explicitResume) {
  const task = getTask_(taskId);
  if (!task) throw new Error('TASK_NOT_FOUND');
  const status = String(task.status || '');
  if (ICARUS.TASK_TERMINAL.indexOf(status) >= 0) return taskForClient_(taskId);
  try {
    if (status === 'QUEUED') {
      transitionTask_(taskId,'INSPECTING');
      appendLog_(taskId,'INSPECTING','IN_PROGRESS','Loaded durable task state.','TASK_QUEUE:'+taskId,'route=COMPOSIO_V31');
    }
    let current = String(getTask_(taskId).status || '');
    const mode=PropertiesService.getScriptProperties().getProperty('PROVIDER_MODE') || 'NONE';
    if (current === 'WAITING_REASONING_CAPACITY') {
      if (!explicitResume) return taskForClient_(taskId);
      transitionTask_(taskId,'REASONING');
      current='REASONING';
    }
    if (current === 'INSPECTING') {
      transitionTask_(taskId,mode === 'NONE' ? 'EXECUTING' : 'REASONING');
      current=String(getTask_(taskId).status);
    }
    let reasoning=taskReasoningLog_(taskId);
    if (current === 'REASONING') {
      if (reasoning && reasoning.status === 'IN_PROGRESS') return taskForClient_(taskId);
      if (!reasoning || reasoning.status !== 'READY_FOR_EXECUTION') {
        appendLog_(taskId,'REASONING','IN_PROGRESS','Provider attempt started.','TASK_QUEUE:'+taskId,'provider='+mode);
        SpreadsheetApp.flush();
        reasoning=reason_(getTask_(taskId));
        appendLog_(taskId,'REASONING',reasoning.status,'Provider reasoning returned.',reasoning.evidence,JSON.stringify(reasoning));
        SpreadsheetApp.flush();
      }
      if (reasoning.status === 'WAITING_REASONING_CAPACITY') {
        transitionTask_(taskId,'WAITING_REASONING_CAPACITY',{evidence_ref:reasoning.evidence});
        return taskForClient_(taskId);
      }
      if (reasoning.status !== 'READY_FOR_EXECUTION') throw new Error('REASONING_BLOCKED');
      transitionTask_(taskId,'EXECUTING');
    }
    return executeComposioTask_(taskId,reasoning && reasoning.executionRequest);
  } catch (err) {
    const current = getTask_(taskId);
    const state = current ? String(current.status || '') : '';
    const reasoningFailure=state === 'REASONING';
    if (ICARUS.TASK_TERMINAL.indexOf(state) < 0 && state !== 'PENDING_AUTH') {
      try { transitionTask_(taskId,'BLOCKED',{evidence_ref:(reasoningFailure ? 'REASONING_BLOCKED ' : 'COMPOSIO_BLOCKED ') + String(err.message || err).slice(0,1000)}); } catch (_) {}
    }
    appendLog_(taskId,reasoningFailure ? 'REASONING' : 'EXECUTING','BLOCKED',reasoningFailure ? 'Reasoning blocked.' : 'Composio v3.1 execution blocked.','COMPOSIO_TASK_STATE:'+taskId,String(err.message || err));
    return taskForClient_(taskId);
  }
}

function resumePendingTasks_() {
  runtimeEnvAssert_();
  const sh = sheet_(ICARUS.SHEETS.TASKS);
  const data = sh.getDataRange().getValues();
  if (data.length < 2) return;
  const headers = data[0].map(String);
  const idIdx = headers.indexOf('task_id');
  const statusIdx = headers.indexOf('status');
  if (idIdx < 0 || statusIdx < 0) throw new Error('TASK_QUEUE_SCHEMA_INVALID');
  // PENDING_AUTH is intentionally not polled by the timer; phone resume/status drives it after authorization.
  const eligible = ['QUEUED','INSPECTING','EXECUTING','VERIFYING'];
  data.slice(1).forEach(function(row) {
    if (eligible.indexOf(String(row[statusIdx])) >= 0) {
      try { advanceTask_(String(row[idIdx])); }
      catch (err) { appendLog_(String(row[idIdx]),'RUNTIME','FAIL','resumePendingTasks failure','',String(err)); }
    }
  });
}

function scheduleTaskAdvance_() {
  const handler = 'resumePendingTasksSoon_';
  const exists = ScriptApp.getProjectTriggers().some(function(t) {
    return t.getHandlerFunction() === handler;
  });
  if (exists) return;
  ScriptApp.newTrigger(handler).timeBased().after(1000).create();
}

function resumePendingTasksSoon_() {
  try {
    resumePendingTasks_();
  } finally {
    ScriptApp.getProjectTriggers().forEach(function(t) {
      if (t.getHandlerFunction() === 'resumePendingTasksSoon_') ScriptApp.deleteTrigger(t);
    });
  }
}

