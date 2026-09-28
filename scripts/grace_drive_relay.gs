// HumanVibe Prime → Grace Drive relay.
// Install in the authenticated Grace Apps Script project. No secrets in source.
// Script Properties: GITHUB_PAT. HANDOFF_DOC_ID may override the default.
// Time trigger: relayPrimeHandoff, every 5 minutes. One trigger only.
const PRIME_HANDOFF_DOC_ID = '1oNpEauSETadTxmeh5waX1Q6hVW6z2215e1sOyXjLe9g';
const PRIME_REPO = 'the1mburke-blip/Teamchat';
const PRIME_ISSUE = 6;

function relayPrimeHandoff() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const token = props.getProperty('GITHUB_PAT');
    if (!token) throw new Error('GITHUB_PAT Script Property missing');
    const docId = props.getProperty('HANDOFF_DOC_ID') || PRIME_HANDOFF_DOC_ID;
    const docText = DocumentApp.openById(docId).getBody().getText();
    const packet = parsePrimeHandoff_(docText);
    if (packet.ready === 'NO') return;
    const marker = 'PRIME_HANDOFF_ID: ' + packet.id;
    const url = 'https://api.github.com/repos/' + PRIME_REPO +
      '/issues/' + PRIME_ISSUE + '/comments';
    const existing = findPrimeHandoff_(url, token, marker);
    if (existing) {
      props.setProperty('LAST_RELAYED_HANDOFF_ID', packet.id);
      console.log('ALREADY_POSTED id=' + existing.id);
      return;
    }
    const comment = '[GRACE] PRIME DOCUMENT RELAY\n' + marker +
      '\nSOURCE_DOC_ID: ' + docId +
      '\nEXECUTOR: Grace relay\n\n' + packet.body;
    const posted = primeGithub_(url, token, comment);
    if (!posted.id || posted.body !== comment) {
      throw new Error('POST response uncertain; inspect Issue #6 before retry');
    }
    const confirmed = primeGithub_(
      'https://api.github.com/repos/' + PRIME_REPO +
      '/issues/comments/' + posted.id, token);
    if (confirmed.body !== comment) {
      throw new Error('GitHub comment readback mismatch');
    }
    props.setProperty('LAST_RELAYED_HANDOFF_ID', packet.id);
    console.log('RELAY_POSTED handoff=' + packet.id +
      ' comment=' + confirmed.id + ' url=' + confirmed.html_url);
  } finally {
    lock.releaseLock();
  }
}

function parsePrimeHandoff_(text) {
  const id = uniquePrimeField_(text, /^HANDOFF_ID:\s*([A-Za-z0-9_-]+)\s*$/gm);
  const ready = uniquePrimeField_(text, /^READY:\s*(YES|NO)\s*$/gm);
  const body = uniquePrimeField_(text, /^BODY_BEGIN\s*\n([\s\S]*?)\nBODY_END\s*(?:\n|$)/gm).trim();
  if (ready === 'YES') {
    if (id === 'PRIME_HANDOFF_PENDING' || !body ||
        body.length > 500 || body.indexOf('Pending a new authenticated') >= 0) {
      throw new Error('Ready handoff has invalid ID or body');
    }
  }
  return { id: id, ready: ready, body: body };
}

function uniquePrimeField_(text, re) {
  const matches = Array.from(text.matchAll(re));
  if (matches.length !== 1) throw new Error('Expected exactly one ' + re.source);
  return matches[0][1];
}

function findPrimeHandoff_(baseUrl, token, marker) {
  for (let page = 1; page <= 20; page++) {
    const comments = primeGithub_(
      baseUrl + '?per_page=100&page=' + page, token);
    const match = comments.find(c => (c.body || '').includes(marker));
    if (match) return match;
    if (comments.length < 100) return null;
  }
  throw new Error('Comment search limit reached; no POST made');
}

function primeGithub_(url, token, body) {
  const opts = {
    method: body === undefined ? 'get' : 'post',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    muteHttpExceptions: true
  };
  if (body !== undefined) {
    opts.contentType = 'application/json';
    opts.payload = JSON.stringify({ body: body });
  }
  const response = UrlFetchApp.fetch(url, opts);
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('GitHub HTTP ' + status + '; inspect target before retry');
  }
  return JSON.parse(response.getContentText());
}

// Integrate with the EXISTING Apps Script time trigger by changing that trigger's
// handler to runGraceDualRole. Do not create a second trigger.
// The live project's original runPrimeGmailBridge function must already exist.
// Existing OAuth scopes must retain Gmail/Calendar/external_request and add
// https://www.googleapis.com/auth/documents (DocumentApp.openById).
function runGraceDualRole() {
  var bridgeFailure = null;
  var relayFailure = null;
  try {
    runPrimeGmailBridge();
  } catch (e) {
    bridgeFailure = e;
    console.error('Existing bridge failed: ' + String(e));
  }
  try {
    relayPrimeHandoff();
  } catch (e) {
    relayFailure = e;
    console.error('Drive relay failed: ' + String(e));
  }
  if (bridgeFailure || relayFailure) {
    throw new Error('Dual-role wake failed; inspect Apps Script execution logs');
  }
}
