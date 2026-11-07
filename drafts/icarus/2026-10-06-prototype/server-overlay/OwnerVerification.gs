/** Owner-only decision seam. Executor transitions remain unable to write PASS. */
function ownerEvidenceFingerprint_(taskId) {
  const t=getTask_(taskId), c=googlePluginEvidence_(taskId);
  if (!t) throw new Error('TASK_NOT_FOUND');
  return sha256Hex_(JSON.stringify([taskId,String(t.evidence_ref || ''),String(c.result_json || ''),String(c.execute_log_id || ''),String(c.verify_log_id || '')]));
}

function ownerTask_(auth, taskId) {
  const t=getTask_(taskId);
  if (!t) throw new Error('TASK_NOT_FOUND');
  if (String(t.source) !== 'ANDROID:'+auth.deviceId) throw new Error('TASK_ACCESS_DENIED');
  return t;
}

function ownerVerificationChallenge_(auth, body) {
  return withScriptLock_(function() {
    if (!googleIdentityConfigured_()) throw new Error('GOOGLE_OWNER_IDENTITY_NOT_CONFIGURED');
    requireCapability_('owner.google_identity');
    const taskId=cleanText_(body.taskId,256), t=ownerTask_(auth,taskId);
    if (t.status !== 'WORK_COMPLETE_AWAITING_OWNER_VERIFICATION') throw new Error('OWNER_VERIFICATION_STATE_DENIED');
    const decision=String(body.decision || '');
    if (['PASS','PARTIAL'].indexOf(decision)<0) throw new Error('OWNER_DECISION_INVALID');
    const comment=String(body.comment || '');
    if (comment.length>500) throw new Error('OWNER_COMMENT_TOO_LONG');
    const fp=ownerEvidenceFingerprint_(taskId);
    if (!t.evidence_ref || !(googlePluginEvidence_(taskId)).result_json) throw new Error('OWNER_EVIDENCE_MISSING');
    if (String(body.evidenceFingerprint || '') !== fp) throw new Error('OWNER_EVIDENCE_CHANGED_REFRESH');
    const id=Utilities.getUuid(), nonce=Utilities.getUuid()+Utilities.getUuid();
    const challenge={id:id,nonce:nonce,taskId:taskId,deviceId:auth.deviceId,decision:decision,comment:comment,evidenceFingerprint:fp};
    CacheService.getScriptCache().put('OWNER:'+id,JSON.stringify(challenge),300);
    return {id:id,nonce:nonce,taskId:taskId,clientId:PropertiesService.getScriptProperties().getProperty('GOOGLE_OAUTH_CLIENT_ID')};
  });
}

function ownerVerificationRecord_(task) {
  if (!task.owner_verification_json) return null;
  try { return JSON.parse(String(task.owner_verification_json)); }
  catch (_) { throw new Error('OWNER_VERIFICATION_RECORD_INVALID'); }
}

function verifyOwnerTask_(auth, body) {
  return withScriptLock_(function() {
    if (!googleIdentityConfigured_()) throw new Error('GOOGLE_OWNER_IDENTITY_NOT_CONFIGURED');
    requireCapability_('owner.google_identity');
    const taskId=cleanText_(body.taskId,256), id=cleanText_(body.verificationId,128);
    const task=ownerTask_(auth,taskId);
    const existing=ownerVerificationRecord_(task);
    // Lost response recovery is read-only and still requires the owning signed device.
    if (existing) {
      if (existing.id!==id) throw new Error('OWNER_VERIFICATION_ALREADY_RECORDED');
      return taskForClient_(taskId);
    }
    const cache=CacheService.getScriptCache(), raw=cache.get('OWNER:'+id);
    if (!raw) throw new Error('OWNER_CHALLENGE_EXPIRED');
    const c=JSON.parse(raw);
    if (c.taskId!==taskId || c.deviceId!==auth.deviceId) throw new Error('OWNER_CHALLENGE_TARGET_DENIED');
    const identity=verifyOwnerGoogleIdToken_(body.googleIdToken,c.nonce);
    if (!identity.verified) throw new Error('OWNER_IDENTITY_REQUIRED');
    if (task.status!=='WORK_COMPLETE_AWAITING_OWNER_VERIFICATION') throw new Error('OWNER_VERIFICATION_STATE_DENIED');
    if (ownerEvidenceFingerprint_(taskId)!==c.evidenceFingerprint) throw new Error('OWNER_EVIDENCE_CHANGED_REFRESH');
    const record={id:id,decision:c.decision,comment:c.comment,utc:nowIso_(),subject:identity.subject,verifier:'Michael',evidenceFingerprint:c.evidenceFingerprint};
    const sh=sheet_(ICARUS.SHEETS.TASKS);
    let found=findTaskRow_(taskId);
    if (found.headers.indexOf('owner_verification_json')<0) {
      if (sh.getMaxColumns()<found.headers.length+1) sh.insertColumnsAfter(sh.getMaxColumns(),1);
      sh.getRange(1,found.headers.length+1).setValue('owner_verification_json');
      SpreadsheetApp.flush();
      found=findTaskRow_(taskId);
    }
    measureTwiceStateMutationPreflight_(taskId,{status:c.decision,owner_verification_json:JSON.stringify(record)});
    const second=ownerTask_(auth,taskId);
    if (second.status!==task.status || ownerEvidenceFingerprint_(taskId)!==c.evidenceFingerprint) throw new Error('OWNER_TASK_CHANGED');
    const values=found.values.slice();
    while(values.length<found.headers.length) values.push('');
    values[found.headers.indexOf('status')]=c.decision;
    values[found.headers.indexOf('owner_verification_json')]=JSON.stringify(record);
    // One row write persists verdict and receipt together. No generic PASS bypass.
    sh.getRange(found.row,1,1,values.length).setValues([values]);
    SpreadsheetApp.flush();
    const readback=getTask_(taskId), receipt=ownerVerificationRecord_(readback);
    if (!receipt || JSON.stringify(receipt)!==JSON.stringify(record) || readback.task_id!==taskId || readback.status!==c.decision) throw new Error('OWNER_VERIFICATION_READBACK_FAILED');
    cache.remove('OWNER:'+id);
    appendLog_(taskId,'OWNER_VERIFICATION',c.decision,'Michael Google identity verified; persisted verdict reread.','TASK_QUEUE:'+taskId,'verification_id='+id+';fingerprint='+c.evidenceFingerprint);
    return taskForClient_(taskId);
  });
}
