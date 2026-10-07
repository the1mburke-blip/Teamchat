function setupIcarusRuntime_() {
  runtimeEnvAssert_();
  ensureRuntimeSheets_();
  appendLog_('', 'SETUP', 'PASS', 'ICARUS Apps Script runtime sheets verified.', 'CONTROL_PLANE', 'No production permission granted.');
}

function installResumeTrigger_() {
  // Install once after deployment. This is runtime infrastructure, not model identity.
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'resumePendingTasks_') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('resumePendingTasks_').timeBased().everyMinutes(5).create();
}
