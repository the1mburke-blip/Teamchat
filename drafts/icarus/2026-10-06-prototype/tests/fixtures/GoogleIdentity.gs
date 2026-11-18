function googleIdentityConfigured_() {
  const p=PropertiesService.getScriptProperties();
  return !!(p.getProperty('GOOGLE_OAUTH_CLIENT_ID') && p.getProperty('OWNER_GOOGLE_EMAIL_SHA256'));
}

function verifyOwnerGoogleIdToken_(idToken, expectedNonce) {
  if(!googleIdentityConfigured_()) return {configured:false,verified:false};
  const token=cleanText_(idToken,8192);
  if(!token) throw new Error('GOOGLE_ID_TOKEN_REQUIRED');
  const clientId=PropertiesService.getScriptProperties().getProperty('GOOGLE_OAUTH_CLIENT_ID');
  const ownerHash=PropertiesService.getScriptProperties().getProperty('OWNER_GOOGLE_EMAIL_SHA256');
  const url='https://oauth2.googleapis.com/tokeninfo?id_token='+encodeURIComponent(token);
  const r=UrlFetchApp.fetch(url,{method:'get',muteHttpExceptions:true,followRedirects:false});
  if(r.getResponseCode()!==200) throw new Error('GOOGLE_ID_TOKEN_INVALID');
  const claims=JSON.parse(r.getContentText());
  if (['accounts.google.com','https://accounts.google.com'].indexOf(String(claims.iss||''))<0) throw new Error('GOOGLE_ID_TOKEN_ISSUER_DENIED');
  if (Number(claims.exp||0)*1000<=Date.now()) throw new Error('GOOGLE_ID_TOKEN_EXPIRED');
  if (!String(claims.sub||'')) throw new Error('GOOGLE_ID_TOKEN_SUBJECT_REQUIRED');
  if (expectedNonce && !constantTimeEquals_(String(expectedNonce),String(claims.nonce||''))) throw new Error('GOOGLE_ID_TOKEN_NONCE_DENIED');
  if(String(claims.aud||'')!==String(clientId)) throw new Error('GOOGLE_ID_TOKEN_AUDIENCE_DENIED');
  if(String(claims.email_verified||'').toLowerCase()!=='true') throw new Error('GOOGLE_EMAIL_NOT_VERIFIED');
  const emailHash=sha256Hex_(String(claims.email||'').toLowerCase());
  if(!constantTimeEquals_(ownerHash,emailHash)) throw new Error('GOOGLE_OWNER_IDENTITY_DENIED');
  return {configured:true,verified:true,subject:String(claims.sub||''),email_hash:emailHash};
}

function assertOwnerIdentityIfConfigured_(body) {
  if(!googleIdentityConfigured_()) return {configured:false,verified:false};
  requireCapability_('owner.google_identity');
  return verifyOwnerGoogleIdToken_(body.googleIdToken);
}
