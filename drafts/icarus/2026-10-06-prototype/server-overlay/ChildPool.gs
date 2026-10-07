var CHILD_POOL_ACTIVE = false;
var CHILD_POOL_ALLOWED_CAPABILITIES = ['analysis.read','research.read','code.draft','review.read'];
var CHILD_POOL_VALID_ROUTES = ['GROQ_FREE','OPENROUTER_FREE','GEMINI_FREE','CEREBRAS_FREE'];
var CHILD_POOL_CHILD_BINDINGS_SHEET = 'CHILD_BINDINGS';
var CHILD_POOL_CHILD_RESULTS_SHEET = 'CHILD_RESULTS';
var CHILD_POOL_CHILD_BINDINGS_HEADERS = ['parent_task_id','child_id','governance_id','subobjective_hash','capabilities_json','route','binding_hash','created_utc'];
var CHILD_POOL_CHILD_RESULTS_HEADERS = ['parent_task_id','child_id','governance_id','binding_hash','envelope_json','envelope_hash','evidence_ref','stored_utc'];

function childPoolSpreadsheet_() {
  var id = PropertiesService.getScriptProperties().getProperty('STATE_SHEET_ID');
  if (!id) {
    throw new Error('CHILD_STATE_SHEET_ID_MISSING');
  }
  return SpreadsheetApp.openById(id);
}

function childPoolEnsureSheets_() {
  var ss = childPoolSpreadsheet_();
  var bindingSheet = ss.getSheetByName(CHILD_POOL_CHILD_BINDINGS_SHEET);
  if (!bindingSheet) {
    bindingSheet = ss.insertSheet(CHILD_POOL_CHILD_BINDINGS_SHEET);
    bindingSheet.appendRow(CHILD_POOL_CHILD_BINDINGS_HEADERS);
  }
  var resultSheet = ss.getSheetByName(CHILD_POOL_CHILD_RESULTS_SHEET);
  if (!resultSheet) {
    resultSheet = ss.insertSheet(CHILD_POOL_CHILD_RESULTS_SHEET);
    resultSheet.appendRow(CHILD_POOL_CHILD_RESULTS_HEADERS);
  }
  // Validate schemas
  var bHeader = bindingSheet.getRange(1,1,1,bindingSheet.getLastColumn()).getValues()[0];
  if (bHeader.length !== CHILD_POOL_CHILD_BINDINGS_HEADERS.length) {
    throw new Error('CHILD_SHEET_SCHEMA_INVALID');
  }
  for (var i = 0; i < CHILD_POOL_CHILD_BINDINGS_HEADERS.length; i++) {
    if (bHeader[i] !== CHILD_POOL_CHILD_BINDINGS_HEADERS[i]) {
      throw new Error('CHILD_SHEET_SCHEMA_INVALID');
    }
  }
  var rHeader = resultSheet.getRange(1,1,1,resultSheet.getLastColumn()).getValues()[0];
  if (rHeader.length !== CHILD_POOL_CHILD_RESULTS_HEADERS.length) {
    throw new Error('CHILD_SHEET_SCHEMA_INVALID');
  }
  for (var j = 0; j < CHILD_POOL_CHILD_RESULTS_HEADERS.length; j++) {
    if (rHeader[j] !== CHILD_POOL_CHILD_RESULTS_HEADERS[j]) {
      throw new Error('CHILD_SHEET_SCHEMA_INVALID');
    }
  }
  return {bindingSheet:bindingSheet,resultSheet:resultSheet};
}

function childPoolValidateCapabilities_(caps) {
  if (!Array.isArray(caps) || caps.length === 0) {
    throw new Error('CAPABILITY_DENIED');
  }
  var uniq = {};
  var out = [];
  for (var i = 0; i < caps.length; i++) {
    var cap = caps[i];
    if (CHILD_POOL_ALLOWED_CAPABILITIES.indexOf(cap) === -1) {
      throw new Error('CAPABILITY_DENIED');
    }
    if (!uniq[cap]) {
      uniq[cap] = true;
      out.push(cap);
    }
  }
  out.sort();
  return out;
}

function childPoolValidateRoute_(route) {
  if (CHILD_POOL_VALID_ROUTES.indexOf(route) === -1) {
    throw new Error('ROUTE_DENIED');
  }
  return route;
}

function childPoolValidateChildId_(childId) {
  if (typeof childId !== 'string' || !/^[A-Za-z0-9._-]{1,64}$/.test(childId)) {
    throw new Error('CHILD_ID_INVALID');
  }
  return childId;
}

function childPoolValidateSubobjective_(subobjective) {
  if (typeof subobjective !== 'string') {
    throw new Error('SUBOBJECTIVE_INVALID');
  }
  var trimmed = subobjective.trim();
  if (!trimmed || trimmed.length > 2000) {
    throw new Error('SUBOBJECTIVE_INVALID');
  }
  return trimmed;
}

function childPoolFindBinding_(parentTaskId, childId) {
  var ss = childPoolSpreadsheet_();
  var sheet = ss.getSheetByName(CHILD_POOL_CHILD_BINDINGS_SHEET);
  var data = sheet.getDataRange().getValues();
  var matches = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0] === parentTaskId && row[1] === childId) {
      matches.push(row);
    }
  }
  if (matches.length > 1) {
    throw new Error('CHILD_BINDING_DUPLICATE');
  }
  if (matches.length === 0) {
    return null;
  }
  var r = matches[0];
  var capsRaw;
  try {
    capsRaw = JSON.parse(r[4]);
  } catch (e) {
    throw new Error('CHILD_BINDING_CONFLICT');
  }
  if (!Array.isArray(capsRaw)) {
    throw new Error('CHILD_BINDING_CONFLICT');
  }
  var capsCanonical = childPoolValidateCapabilities_(capsRaw);
  if (JSON.stringify(capsCanonical) !== r[4]) {
    throw new Error('CHILD_BINDING_CONFLICT');
  }
  return {
    parentTaskId: r[0],
    childId: r[1],
    governanceId: r[2],
    subobjectiveHash: r[3],
    capabilities: capsCanonical,
    route: r[5],
    bindingHash: r[6],
    createdUtc: r[7]
  };
}

function childPoolCreate_(parentTaskId, childId, subobjective, capabilities, route) {
  if (CHILD_POOL_ACTIVE) {
    throw new Error('NESTED_CHILD_DISPATCH_DENIED');
  }
  var parentTask = getTask_(parentTaskId);
  if (!parentTask) {
    throw new Error('PARENT_TASK_NOT_FOUND');
  }
  childPoolValidateChildId_(childId);
  var trimmedSub = childPoolValidateSubobjective_(subobjective);
  var caps = childPoolValidateCapabilities_(capabilities);
  var cleanRoute = childPoolValidateRoute_(route);
  var governanceId = parentTaskId + ':child:' + childId;
  var subHash = IcarusGovernance.hash(trimmedSub);
  var bindingObj = {
    parentTaskId: parentTaskId,
    childId: childId,
    governanceId: governanceId,
    subobjectiveHash: subHash,
    capabilities: caps,
    route: cleanRoute,
    depth: 1,
    budgetEUR: 0
  };
  var bindingHash = IcarusGovernance.hash(bindingObj);
  var resultBinding = null;
  withScriptLock_(function() {
    var sheets = childPoolEnsureSheets_();
    var existing = childPoolFindBinding_(parentTaskId, childId);
    if (existing) {
      var same = existing.governanceId === governanceId &&
                 existing.subobjectiveHash === subHash &&
                 JSON.stringify(existing.capabilities) === JSON.stringify(caps) &&
                 existing.route === cleanRoute &&
                 existing.bindingHash === bindingHash;
      if (!same) {
        throw new Error('CHILD_BINDING_CONFLICT');
      }
      resultBinding = existing;
      return;
    }
    var row = [
      parentTaskId,
      childId,
      governanceId,
      subHash,
      JSON.stringify(caps),
      cleanRoute,
      bindingHash,
      nowIso_()
    ];
    sheets.bindingSheet.appendRow(row);
    SpreadsheetApp.flush();
    var verify = childPoolFindBinding_(parentTaskId, childId);
    if (!verify ||
        verify.governanceId !== governanceId ||
        verify.subobjectiveHash !== subHash ||
        JSON.stringify(verify.capabilities) !== JSON.stringify(caps) ||
        verify.route !== cleanRoute ||
        verify.bindingHash !== bindingHash) {
      throw new Error('CHILD_BINDING_PERSISTENCE_FAILED');
    }
    resultBinding = verify;
  });
  return resultBinding;
}

function childPoolSpec_(binding) {
  return {
    agentId: 'ghost:' + binding.childId,
    tool: 'GHOST_SUBAGENT',
    service: 'delegation',
    operation: 'delegate_leaf',
    target: {
      parentTaskId: binding.parentTaskId,
      childId: binding.childId,
      subobjectiveHash: binding.subobjectiveHash,
      depth: 1
    },
    scopes: binding.capabilities,
    route: binding.route,
    budgetEUR: 0,
    write: false,
    payloadHash: binding.bindingHash,
    evidenceContract: {
      readPath: 'CHILD_RESULTS:' + binding.parentTaskId + ':' + binding.childId,
      expectedHash: binding.bindingHash
    }
  };
}

function childPoolFindResult_(bindingHash) {
  var ss = childPoolSpreadsheet_();
  var sheet = ss.getSheetByName(CHILD_POOL_CHILD_RESULTS_SHEET);
  var data = sheet.getDataRange().getValues();
  var matches = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[3] === bindingHash) {
      matches.push(row);
    }
  }
  if (matches.length > 1) {
    throw new Error('CHILD_RESULT_DUPLICATE');
  }
  if (matches.length === 0) {
    return null;
  }
  var r = matches[0];
  var envelope;
  try {
    envelope = JSON.parse(r[4]);
  } catch (e) {
    throw new Error('CHILD_RESULT_INVALID');
  }
  return {
    parentTaskId: r[0],
    childId: r[1],
    governanceId: r[2],
    bindingHash: r[3],
    envelopeJson: r[4],
    envelope: envelope,
    envelopeHash: r[5],
    evidenceRef: r[6],
    storedUtc: r[7]
  };
}

function childPoolPersistEnvelope_(binding, envelope) {
  var existing = childPoolFindResult_(binding.bindingHash);
  if (existing) {
    throw new Error('CHILD_RESULT_DUPLICATE');
  }
  var expectedEvidenceRef = 'CHILD_RESULTS:' + binding.parentTaskId + ':' + binding.childId;
  if (envelope.evidenceRef !== expectedEvidenceRef) {
    throw new Error('CHILD_HANDOFF_DURABILITY_FAILED');
  }
  if (envelope.parentTaskId !== binding.parentTaskId ||
      envelope.childId !== binding.childId ||
      envelope.governanceId !== binding.governanceId ||
      envelope.bindingHash !== binding.bindingHash) {
    throw new Error('CHILD_RESULT_INVALID');
  }
  var envelopeStr;
  try {
    envelopeStr = JSON.stringify(envelope);
  } catch (e) {
    throw new Error('CHILD_RESULT_INVALID');
  }
  if (envelopeStr.length > 16000) {
    throw new Error('CHILD_RESULT_INVALID');
  }
  var envelopeHash = IcarusGovernance.hash(envelope);
  var row = [
    binding.parentTaskId,
    binding.childId,
    binding.governanceId,
    binding.bindingHash,
    envelopeStr,
    envelopeHash,
    envelope.evidenceRef,
    nowIso_()
  ];
  withScriptLock_(function() {
    var sheets = childPoolEnsureSheets_();
    sheets.resultSheet.appendRow(row);
    SpreadsheetApp.flush();
    var verify = childPoolFindResult_(binding.bindingHash);
    if (!verify ||
        verify.parentTaskId !== binding.parentTaskId ||
        verify.childId !== binding.childId ||
        verify.governanceId !== binding.governanceId ||
        verify.bindingHash !== binding.bindingHash ||
        verify.envelopeJson !== envelopeStr ||
        verify.envelopeHash !== envelopeHash ||
        verify.evidenceRef !== envelope.evidenceRef) {
      throw new Error('CHILD_HANDOFF_DURABILITY_FAILED');
    }
    var persistedEnvelope;
    try {
      persistedEnvelope = JSON.parse(verify.envelopeJson);
    } catch (e) {
      throw new Error('CHILD_HANDOFF_DURABILITY_FAILED');
    }
    if (IcarusGovernance.hash(persistedEnvelope) !== verify.envelopeHash) {
      throw new Error('CHILD_HANDOFF_DURABILITY_FAILED');
    }
  });
  return row;
}

function childPoolRun_(parentTaskId, childId, subobjective, capabilities, route, dispatcher) {
  if (CHILD_POOL_ACTIVE) {
    throw new Error('NESTED_CHILD_DISPATCH_DENIED');
  }
  var binding = childPoolCreate_(parentTaskId, childId, subobjective, capabilities, route);
  var parentTask = getTask_(parentTaskId);
  var spec = childPoolSpec_(binding);
  if (typeof skillsAttachSpec_ === 'function') {
    spec = skillsAttachSpec_(parentTask, spec);
  }
  var principal = {id:'ghost:' + childId, role:'executor'};
  var permit = IcarusGovernance.prepare(binding.governanceId, spec, principal);
  CHILD_POOL_ACTIVE = true;
  try {
    return IcarusGovernance.run(permit, spec, principal, function() {
      var descriptor = Object.freeze({
        parentTaskId: parentTaskId,
        childId: childId,
        governanceId: binding.governanceId,
        subobjective: childPoolValidateSubobjective_(subobjective),
        capabilities: binding.capabilities.slice(),
        route: binding.route,
        depth: 1,
        budgetEUR: 0
      });
      var result = dispatcher(descriptor);
      var resultStr;
      try {
        resultStr = JSON.stringify(result);
      } catch (e) {
        throw new Error('CHILD_RESULT_INVALID');
      }
      if (typeof resultStr !== 'string' || resultStr.length > 12000) {
        throw new Error('CHILD_RESULT_INVALID');
      }
      var envelope = {
        parentTaskId: parentTaskId,
        childId: childId,
        governanceId: binding.governanceId,
        bindingHash: binding.bindingHash,
        result: result,
        evidenceRef: 'CHILD_RESULTS:' + parentTaskId + ':' + childId
      };
      childPoolPersistEnvelope_(binding, envelope);
      return envelope;
    });
  } finally {
    CHILD_POOL_ACTIVE = false;
  }
}

function childPoolResult_(parentTaskId, childId) {
  var binding = childPoolFindBinding_(parentTaskId, childId);
  if (!binding) {
    throw new Error('CHILD_BINDING_NOT_FOUND');
  }
  var parentTask = getTask_(parentTaskId);
  if (!parentTask) {
    throw new Error('PARENT_TASK_NOT_FOUND');
  }
  var snap = IcarusGovernance.snapshot(binding.governanceId);
  if (!snap || snap.state !== 'WORK_COMPLETE_AWAITING_VERIFICATION') {
    throw new Error('SNAPSHOT_INVALID');
  }
  var expectedSpec = childPoolSpec_(binding);
  if (typeof skillsAttachSpec_ === 'function') {
    expectedSpec = skillsAttachSpec_(parentTask, expectedSpec);
  }
  if (IcarusGovernance.hash(snap.spec) !== IcarusGovernance.hash(expectedSpec)) {
    throw new Error('SPEC_MISMATCH');
  }
  var resultRow = childPoolFindResult_(binding.bindingHash);
  if (!resultRow) {
    throw new Error('CHILD_RESULT_NOT_FOUND');
  }
  if (resultRow.parentTaskId !== binding.parentTaskId ||
      resultRow.childId !== binding.childId ||
      resultRow.governanceId !== binding.governanceId ||
      resultRow.bindingHash !== binding.bindingHash) {
    throw new Error('RESULT_ROW_INTEGRITY_ERROR');
  }
  var envelope = resultRow.envelope;
  var computedEnvelopeHash = IcarusGovernance.hash(envelope);
  if (computedEnvelopeHash !== resultRow.envelopeHash) {
    throw new Error('ENVELOPE_HASH_MISMATCH');
  }
  if (snap.resultHash !== resultRow.envelopeHash) {
    throw new Error('RESULT_HASH_MISMATCH');
  }
  if (envelope.parentTaskId !== binding.parentTaskId ||
      envelope.childId !== binding.childId ||
      envelope.governanceId !== binding.governanceId ||
      envelope.bindingHash !== binding.bindingHash) {
    throw new Error('ENVELOPE_INTEGRITY_ERROR');
  }
  return JSON.parse(JSON.stringify(envelope));
}