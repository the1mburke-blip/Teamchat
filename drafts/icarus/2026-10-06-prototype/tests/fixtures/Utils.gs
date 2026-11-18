function jsonResponse_(payload, status) {
  const out = ContentService.createTextOutput(JSON.stringify(payload));
  out.setMimeType(ContentService.MimeType.JSON);
  // Apps Script ContentService cannot reliably set arbitrary HTTP status codes.
  // Status is therefore carried explicitly in the response envelope.
  return out;
}

function nowIso_() {
  return new Date().toISOString();
}

function uuid_() {
  return Utilities.getUuid();
}

function sha256Hex_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value, Utilities.Charset.UTF_8);
  return bytes.map(function(b) {
    const n = b < 0 ? b + 256 : b;
    return ('0' + n.toString(16)).slice(-2);
  }).join('');
}

function secureToken_() {
  return Utilities.base64EncodeWebSafe(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    uuid_() + '|' + nowIso_() + '|' + Math.random(),
    Utilities.Charset.UTF_8
  )).replace(/=+$/, '');
}

function parseJsonBody_(e) {
  if (!e || !e.postData || !e.postData.contents) throw new Error('EMPTY_BODY');
  const body = JSON.parse(e.postData.contents);
  if (!body || typeof body !== 'object') throw new Error('INVALID_BODY');
  return body;
}

function cleanText_(value, maxLen) {
  const text = String(value == null ? '' : value).trim();
  if (!text) throw new Error('EMPTY_TEXT');
  if (text.length > maxLen) throw new Error('TEXT_TOO_LONG');
  return text;
}

function constantTimeEquals_(a, b) {
  a = String(a || ''); b = String(b || '');
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}
