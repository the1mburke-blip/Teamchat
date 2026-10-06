function runtimeEnvAssert_() {
  const env = PropertiesService.getScriptProperties().getProperty('RUNTIME_ENV') || ICARUS.ENV_REQUIRED;
  if (env !== ICARUS.ENV_REQUIRED) throw new Error('RUNTIME_ENV_MUST_BE_NON_PROD');
}

function deviceHeaders_() {
  const sh = sheet_(ICARUS.SHEETS.DEVICES);
  const width = Math.max(sh.getLastColumn(), 1);
  return sh.getRange(1, 1, 1, width).getValues()[0].map(String);
}

function deviceRowObject_(headers, values) {
  const obj = {};
  headers.forEach(function(h, i) { if (h) obj[h] = values[i]; });
  return obj;
}

function deviceColumn_(headers, name) {
  const idx = headers.indexOf(name);
  if (idx < 0) throw new Error('DEVICE_REGISTRY_MISSING_' + name);
  return idx;
}

function pairDevice_(body) {
  runtimeEnvAssert_();
  const ownerIdentity = assertOwnerIdentityIfConfigured_(body);
  return withScriptLock_(function() {
    const props = PropertiesService.getScriptProperties();
    const fallbackConsumed = (props.getProperty('PAIRING_FALLBACK_CONSUMED') || 'false').toLowerCase() === 'true';
    const expectedHash = props.getProperty('PAIRING_CODE_SHA256') || (fallbackConsumed ? '' : ICARUS_BOOTSTRAP.PAIRING_CODE_SHA256);
    if (!expectedHash) throw new Error('PAIRING_NOT_CONFIGURED');
    const suppliedHash = sha256Hex_(cleanText_(body.pairingCode, 256));
    if (!constantTimeEquals_(expectedHash, suppliedHash)) throw new Error('PAIRING_DENIED');

    const deviceId = cleanText_(body.deviceId, 256);
    const enrolled = registerDeviceToken_(deviceId, body.clientVersion, ownerIdentity, true);

    if ((props.getProperty('PAIRING_SINGLE_USE') || 'true').toLowerCase() !== 'false') {
      props.deleteProperty('PAIRING_CODE_SHA256');
      props.setProperty('PAIRING_FALLBACK_CONSUMED', 'true');
    }

    appendLog_('', 'PAIRING', 'PAIRED', 'Paired Android device.', 'DEVICE_REGISTRY:' + deviceId, 'token hash stored; plaintext token returned once; prior active device row revoked');
    return enrolled;
  });
}

function authenticate_(body) {
  runtimeEnvAssert_();
  const deviceId = cleanText_(body.deviceId, 256);
  const token = cleanText_(body.token, 2048);
  const tokenHash = sha256Hex_(token);
  const sh = sheet_(ICARUS.SHEETS.DEVICES);
  const values = sh.getDataRange().getValues();
  if (values.length < 2) throw new Error('AUTH_DENIED');
  const headers = values[0].map(String);
  const idIdx = deviceColumn_(headers, 'device_id');
  const hashIdx = deviceColumn_(headers, 'token_hash');
  const statusIdx = deviceColumn_(headers, 'status');
  const seenIdx = deviceColumn_(headers, 'last_seen_utc');
  for (let r = 1; r < values.length; r++) {
    if (String(values[r][idIdx]) === deviceId && String(values[r][statusIdx]) === 'ACTIVE' && constantTimeEquals_(String(values[r][hashIdx]), tokenHash)) {
      sh.getRange(r + 1, seenIdx + 1).setValue(nowIso_());
      return {deviceId:deviceId};
    }
  }
  throw new Error('AUTH_DENIED');
}


// Shared token minting preserves pairing behavior; fresh owner enrollment never replaces a device.
function registerDeviceToken_(deviceId, clientVersion, ownerIdentity, allowReplacement) {
    const sh = sheet_(ICARUS.SHEETS.DEVICES);
    const values = sh.getDataRange().getValues();
    const headers = values.length ? values[0].map(String) : deviceHeaders_();
    const idIdx = deviceColumn_(headers, 'device_id');
    const hashIdx = deviceColumn_(headers, 'token_hash');
    const statusIdx = deviceColumn_(headers, 'status');
    const pairedIdx = deviceColumn_(headers, 'paired_utc');
    const seenIdx = deviceColumn_(headers, 'last_seen_utc');
    const buildIdx = deviceColumn_(headers, 'app_build');

    for (let r = 1; r < values.length; r++) {
      if (String(values[r][idIdx]) === deviceId && String(values[r][statusIdx]) === 'ACTIVE') {
        if (!allowReplacement) throw new Error('ENROLLMENT_DEVICE_ALREADY_ACTIVE');
        sh.getRange(r + 1, statusIdx + 1).setValue('REVOKED');
      }
    }

    const token = secureToken_(), tokenHash = sha256Hex_(token);
    const row = new Array(headers.length).fill('');
    row[idIdx] = deviceId;
    row[hashIdx] = tokenHash;
    row[statusIdx] = 'ACTIVE';
    row[pairedIdx] = nowIso_();
    row[seenIdx] = nowIso_();
    row[buildIdx] = String(clientVersion || '');
    sh.appendRow(row);

    SpreadsheetApp.flush();
    return {deviceId:deviceId, token:token, runtimeVersion:ICARUS.RUNTIME_VERSION, environment:'NON_PROD', googleIdentityVerified:!!ownerIdentity.verified};
}
