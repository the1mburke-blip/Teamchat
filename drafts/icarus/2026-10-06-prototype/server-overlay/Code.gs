function doGet(e) {
  try {
    runtimeEnvAssert_();
    const genome = runtimeGenome_();
    const caps = runtimeCapabilities_();
    return jsonResponse_({
      ok:true,
      status:'ONLINE',
      app:'ICARUS',
      environment:'NON_PROD',
      runtimeVersion:ICARUS.RUNTIME_VERSION,
      genomeRevision:genome.identity.genome_revision,
      capabilityRevision:caps.capability_revision,
      googleIdentityConfigured:googleIdentityConfigured_(),
      timestamp:nowIso_()
    });
  } catch (err) {
    return jsonResponse_({ok:false,error:String(err.message || err),timestamp:nowIso_()});
  }
}

function doPost(e) {
  try {
    const envelope = parseJsonBody_(e);
    if (envelope.op === 'enrollment_challenge') return jsonResponse_({ok:true,data:enrollmentChallenge_(envelope)});
    if (envelope.op === 'enroll') return jsonResponse_({ok:true,data:enrollOwnerDevice_(envelope)});
    if (envelope.op === 'pair') return jsonResponse_({ok:true, data:pairDevice_(envelope)});
    const auth = authenticateSigned_(envelope);
    const body = JSON.parse(envelope.payload);
    const op = String(body.op || '');
    if (op === 'owner_challenge') return jsonResponse_({ok:true,data:ownerVerificationChallenge_(auth,body)});
    if (op === 'owner_verify') return jsonResponse_({ok:true,data:verifyOwnerTask_(auth,body)});
    if (op === 'claim' || op === 'result') throw new Error('PC_STAGED_DISCONNECTED');
    if (op === 'submit') {
      const task = createTask_(auth.deviceId, cleanText_(body.clientTaskId,256), cleanText_(body.text,ICARUS.MAX_TEXT));
      try { scheduleTaskAdvance_(); } catch (err) {
        appendLog_(task.task_id,'RUNTIME','FAIL','Continuation scheduling failed.','TASK_QUEUE:'+task.task_id,String(err.message || err));
      }
      return jsonResponse_({ok:true,data:taskForClient_(task.task_id)});
    }
    if (op === 'status') {
      const task = getTask_(cleanText_(body.taskId,256));
      if (!task) throw new Error('TASK_NOT_FOUND');
      if (String(task.source) !== 'ANDROID:' + auth.deviceId) throw new Error('TASK_ACCESS_DENIED');
      if (String(task.status) === 'PENDING_AUTH') return jsonResponse_({ok:true,data:advanceTask_(task.task_id)});
      return jsonResponse_({ok:true,data:taskForClient_(task.task_id)});
    }
    if (op === 'resume') {
      const taskId = cleanText_(body.taskId,256);
      const task = getTask_(taskId);
      if (!task) throw new Error('TASK_NOT_FOUND');
      if (String(task.source) !== 'ANDROID:' + auth.deviceId) throw new Error('TASK_ACCESS_DENIED');
      return jsonResponse_({ok:true,data:advanceTask_(taskId,true)});
    }
    if (op === 'experience_search') {
      requireCapability_('experience.read');
      return jsonResponse_({ok:true,data:retrieveExperiences_(cleanText_(body.query,ICARUS.MAX_TEXT), body.limit)});
    }
    if (op === 'gateway_status') {
      requireCapability_('gateway.registry.read');
      return jsonResponse_({ok:true,data:gatewayStatus_()});
    }
    if (op === 'mcp_list_tools') {
      return jsonResponse_({ok:true,data:mcpListTools_(cleanText_(body.gatewayId,128))});
    }
    if (op === 'mcp_call_tool') {
      return jsonResponse_({ok:true,data:mcpCallTool_(cleanText_(body.gatewayId,128),cleanText_(body.toolName,128),body.arguments || {})});
    }
    if (op === 'runtime') {
      const genome = runtimeGenome_();
      const caps = runtimeCapabilities_();
      return jsonResponse_({ok:true,data:{runtimeVersion:ICARUS.RUNTIME_VERSION,genomeRevision:genome.identity.genome_revision,capabilityRevision:caps.capability_revision,environment:'NON_PROD',googleIdentityConfigured:googleIdentityConfigured_(),gatewayCount:gatewayRows_().length,experienceCount:experienceRows_().length}});
    }
    throw new Error('UNKNOWN_OPERATION');
  } catch (err) {
    return jsonResponse_({ok:false,error:String(err.message || err),timestamp:nowIso_()});
  }
}
