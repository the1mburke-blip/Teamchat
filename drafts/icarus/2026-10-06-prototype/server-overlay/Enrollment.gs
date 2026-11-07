// Reuse existing strict Google owner identity and challenge pattern; no anonymous device minting.
function enrollmentPreflight_() {
  runtimeEnvAssert_();
  if (!googleIdentityConfigured_()) throw new Error('GOOGLE_OWNER_IDENTITY_NOT_CONFIGURED');
  requireCapability_('owner.google_identity');
}
function enrollmentDeviceId_(value) {
  const id=cleanText_(value,128);
  if (!/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(id)) throw new Error('ENROLLMENT_DEVICE_ID_INVALID');
  return id;
}
function enrollmentChallenge_(body) {
  enrollmentPreflight_();
  const deviceId=enrollmentDeviceId_(body.deviceId);
  return withScriptLock_(function() {
    const id=Utilities.getUuid(), nonce=Utilities.getUuid()+Utilities.getUuid();
    const challenge={id:id,deviceId:deviceId,nonce:nonce,expiresAt:Date.now()+300000};
    CacheService.getScriptCache().put('ENROLL:'+id,JSON.stringify(challenge),300);
    return {id:id,deviceId:deviceId,nonce:nonce,clientId:PropertiesService.getScriptProperties().getProperty('GOOGLE_OAUTH_CLIENT_ID')};
  });
}
function enrollOwnerDevice_(body) {
  enrollmentPreflight_();
  const deviceId=enrollmentDeviceId_(body.deviceId), id=cleanText_(body.challengeId,128);
  return withScriptLock_(function() {
    const cache=CacheService.getScriptCache(), raw=cache.get('ENROLL:'+id);
    if (!raw) throw new Error('ENROLLMENT_CHALLENGE_EXPIRED_OR_USED');
    const challenge=JSON.parse(raw);
    if (challenge.id!==id || challenge.deviceId!==deviceId) throw new Error('ENROLLMENT_CHALLENGE_TARGET_DENIED');
    if (!Number.isSafeInteger(challenge.expiresAt) || challenge.expiresAt<=Date.now()) throw new Error('ENROLLMENT_CHALLENGE_EXPIRED_OR_USED');
    let identity;
    try { identity=verifyOwnerGoogleIdToken_(body.googleIdToken,challenge.nonce); }
    catch(err) {
      // Never return the transport URL or raw Google credential in an error.
      const message=String(err.message || err);
      throw new Error(/^GOOGLE_[A-Z_]+$/.test(message) ? message : 'ENROLLMENT_IDENTITY_CHECK_FAILED');
    }
    if (!identity.verified) throw new Error('OWNER_IDENTITY_REQUIRED');
    cache.remove('ENROLL:'+id);
    const enrolled=registerDeviceToken_(deviceId,String(body.clientVersion || '').slice(0,128),identity,false);
    appendLog_('','ENROLLMENT','ENROLLED','Google owner identity verified; fresh device enrolled.','DEVICE_REGISTRY:'+deviceId,'token hash stored; no prior device replaced');
    return enrolled;
  });
}
