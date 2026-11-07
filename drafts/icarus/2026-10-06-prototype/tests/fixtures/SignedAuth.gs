// Signed transport reuses the enrolled device-token hash.
// Deployment requires the matching Android transport patch.
function authenticateSigned_(envelope) {
  runtimeEnvAssert_();
  const id = envelope.deviceId;
  const nonce = envelope.nonce;
  const timestamp = envelope.timestamp;
  if (envelope.v !== 1 || typeof id !== 'string' ||
      !/^[A-Za-z0-9_-]{1,128}$/.test(id) ||
      typeof nonce !== 'string' || !/^[A-Za-z0-9_-]{16,128}$/.test(nonce) ||
      !Number.isSafeInteger(timestamp) || typeof envelope.payload !== 'string' ||
      envelope.payload.length > 30000 || !/^[0-9a-f]{64}$/.test(envelope.signature || '')) {
    throw new Error('INVALID_SIGNED_REQUEST');
  }
  if (Math.abs(Date.now() - timestamp) > 300000) throw new Error('STALE_REQUEST');
  const payload = JSON.parse(envelope.payload);
  if (!payload || typeof payload.op !== 'string' || payload.deviceId !== id ||
      Object.prototype.hasOwnProperty.call(payload, 'token')) throw new Error('INVALID_SIGNED_PAYLOAD');
  const signingText = ['ICARUS_QUEUE_V1', id, String(timestamp), nonce, envelope.payload].join('\n');
  return withScriptLock_(function() {
    const devices = sheet_(ICARUS.SHEETS.DEVICES);
    const rows = devices.getDataRange().getValues();
    const headers = rows[0].map(String);
    const idIdx = deviceColumn_(headers, 'device_id');
    const hashIdx = deviceColumn_(headers, 'token_hash');
    const statusIdx = deviceColumn_(headers, 'status');
    const seenIdx = deviceColumn_(headers, 'last_seen_utc');
    const row = rows.findIndex(function(values, index) {
      return index > 0 && String(values[idIdx]) === id && String(values[statusIdx]) === 'ACTIVE';
    });
    if (row < 0) throw new Error('AUTH_DENIED');
    const key = String(rows[row][hashIdx]);
    if (!/^[0-9a-f]{64}$/.test(key)) throw new Error('AUTH_DENIED');
    const expected = Utilities.computeHmacSha256Signature(signingText, key, Utilities.Charset.UTF_8)
      .map(function(b) { return ('0' + (b & 255).toString(16)).slice(-2); }).join('');
    if (!constantTimeEquals_(expected, envelope.signature)) throw new Error('AUTH_DENIED');
    const ss = stateSpreadsheet_();
    let ledger = ss.getSheetByName('ICARUS_REQUEST_NONCES');
    if (!ledger) ledger = ss.insertSheet('ICARUS_REQUEST_NONCES');
    if (ledger.getLastRow() === 0) ledger.appendRow(['device_id','nonce','request_utc']);
    const previous = ledger.getDataRange().getValues();
    if (previous.slice(1).some(function(values) {
      return String(values[0]) === id && String(values[1]) === nonce;
    })) throw new Error('REPLAY_DENIED');
    ledger.appendRow([id, nonce, new Date(timestamp).toISOString()]);
    devices.getRange(row + 1, seenIdx + 1).setValue(nowIso_());
    SpreadsheetApp.flush();
    return {deviceId:id};
  });
}
