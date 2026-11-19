// Offline test of Athena.gs: Apps Script services are stubbed, GitHub contents are served from the local
// Teamchat checkout, Gemini answers are scripted. No network, no credentials.
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const REPO_DIR = process.argv[2];
const SRC = fs.readFileSync(process.argv[3] || path.join(REPO_DIR, 'icarus/athena-gas/Athena.gs'), 'utf8');
const SECRET = 'ghp_TESTSECRET123456', GKEY = 'AIzaTESTKEY';
const crypto = require('node:crypto');
const REPO = 'the1mburke-blip/Teamchat';
const GH = 'https://api.github.com/repos/' + REPO;
const ACTOR = 324897963;
const OLD_ID = 6704645457;
const QUARANTINE = 'ATHENA_QUARANTINE_V1|' + REPO.toLowerCase() + '/6/' + OLD_ID;
const JOURNAL = 'ATHENA_ATTEMPT_V1|';
const CURSOR = 'ATHENA_COMMENT_CURSOR_V1|' + REPO;
const PROOF = 'ATHENA_CUTOVER_OBSERVED_V1';
const config = { repo: REPO, mode: 'active', sourceRevision: 'f'.repeat(40),
  historicalThrough: '2026-10-28T00:00:00Z', receiptActorId: ACTOR, hourlyReceiptIssue: 42 };
const proof = (c) => JSON.stringify([c.repo, c.sourceRevision, c.historicalThrough,
  c.receiptActorId, c.hourlyReceiptIssue, REPO.toLowerCase() + '/6/' + OLD_ID]);
const attemptOf = (env, id = 5001, issue = 120) => JSON.parse(env.props[JOURNAL + REPO.toLowerCase() + '/' + issue + '/' + id]);

function fmt(d, f) {
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return f.replace(/'([^']*)'/g, '\u0001$1\u0001').replace(/yyyy|MM|dd|HH|mm|ss/g, (t) => ({
    yyyy: d.getUTCFullYear(), MM: p(d.getUTCMonth() + 1), dd: p(d.getUTCDate()), HH: p(d.getUTCHours()), mm: p(d.getUTCMinutes()), ss: p(d.getUTCSeconds()) }[t])).replace(/\u0001([^\u0001]*)\u0001/g, '$1');
}

function makeEnv(scenario) {
  const props = { ATHENA_SELF_QUEUE_V1: 'off', /* self-queue has its own suite: test-selfqueue.js */ GITHUB_PAT: SECRET, GEMINI_API_KEY: GKEY, ATHENA_CUTOVER_V1: JSON.stringify(config),
    [QUARANTINE]: 'QUARANTINED_UNCERTAIN', [PROOF]: proof(config) };
  const writes = {}, posted = [], remoteReceipts = [], geminiCalls = [], requests = [];
  const logs = [], created = [];
  let locked = false;
  const blob = (x) => {
    const buf = Buffer.isBuffer(x) ? x : Array.isArray(x) ? Buffer.from(x.map((b) => b & 255)) : Buffer.from(String(x), 'utf8');
    return { getDataAsString: () => buf.toString('utf8'), getBytes: () => [...buf] };
  };
  const res = (code, obj, headers = {}) => ({ getResponseCode: () => code, getAllHeaders: () => headers,
    getContentText: () => typeof obj === 'string' ? obj : JSON.stringify(obj) });
  const pageOf = (rows, rest) => {
    const page = Number(new URL('https://example.test/' + rest).searchParams.get('page') || '1');
    const from = (page - 1) * 100;
    return res(200, rows.slice(from, from + 100), rows.length > from + 100 ? { Link: '<next>; rel="next"' } : {});
  };
  function contents(rel, method, body) {
    const full = path.join(REPO_DIR, rel);
    if (scenario.contents) {
      const override = scenario.contents(rel, method, body);
      if (override) return res(override.code, override.body || {});
    }
    if (method === 'put') { writes[rel] = Buffer.from(body.content, 'base64').toString('utf8'); return res(201, { commit: { sha: 'abc1234' } }); }
    if (writes[rel] !== undefined) return res(200, { type: 'file', sha: 's', content: Buffer.from(writes[rel]).toString('base64') });
    if (!fs.existsSync(full)) return res(404, { message: 'Not Found' });
    if (fs.statSync(full).isDirectory()) return res(200, fs.readdirSync(full).map((n) => ({ name: n, path: rel ? rel + '/' + n : n, type: fs.statSync(path.join(full, n)).isDirectory() ? 'dir' : 'file' })));
    return res(200, { type: 'file', sha: 's', content: fs.readFileSync(full).toString('base64') });
  }
  const UrlFetchApp = { fetch(url, opt) {
    const m = opt.method || 'get', body = opt.payload ? JSON.parse(opt.payload) : null;
    if (url.startsWith('https://generativelanguage.googleapis.com')) {
      assert.strictEqual(opt.headers['x-goog-api-key'], GKEY);
      geminiCalls.push({ url, body });
      const r = scenario.gemini(geminiCalls.length, body);
      return res(r.code || 200, r.code && r.code !== 200 ? r.text : { candidates: [{ content: { parts: [{ text: JSON.stringify(r) }] } }] });
    }
    const gh = url.match(/^https:\/\/api\.github\.com\/repos\/[^/]+\/[^/]+\/(.*)$/);
    assert(gh, 'unexpected url ' + url);
    assert.strictEqual(opt.headers.Authorization, 'Bearer ' + SECRET);
    let rest = gh[1];
    requests.push({ method: m, rest });
    if (rest.startsWith('contents/')) return contents(decodeURIComponent(rest.slice(9).split('?')[0]), m, body);
    if (rest.startsWith('contents?')) return contents('', m, body);
    if (rest.startsWith('issues/comments?')) return pageOf(scenario.comments, rest);
    if (rest.startsWith('commits/')) return res((scenario.commits || []).includes(rest.slice(8)) ? 200 : 404, {});
    if (/^issues\/comments\/\d+$/.test(rest)) {
      const id = Number(rest.split('/').pop());
      const c = remoteReceipts.concat(scenario.comments).find((x) => x.id === id);
      if (!c) return res(404, {});
      const override = scenario.receiptReadback && scenario.receiptReadback(c);
      return override ? res(override.code, override.body) : res(200, c);
    }
    if (/^issues\/\d+\/comments/.test(rest)) {
      const issue = rest.split('/')[1];
      if (m === 'post') {
        const stamp = new Date().toISOString();
        const c = { id: 100000 + posted.length, body: body.body, user: { id: ACTOR },
          issue_url: GH + '/issues/' + issue, created_at: stamp, updated_at: stamp };
        posted.push({ issue, body: body.body });
        const override = scenario.receiptPost && scenario.receiptPost(c, props);
        if (!override || override.commit) remoteReceipts.push(c);
        if (override && override.throw) throw new Error('transport lost');
        return res(override ? override.code : 201, c);
      }
      if (scenario.receiptListError && scenario.receiptListError()) return res(503, {});
      return pageOf(remoteReceipts.filter((c) => c.issue_url === GH + '/issues/' + issue), rest);
    }
    if (/^issues\/\d+$/.test(rest)) { const made = created.find((x) => x.number === Number(rest.split('/')[1])); return res(200, made || { number: Number(rest.split('/')[1]), title: 'Test issue', body: 'body', state: 'open', comments: 0 }); }
    if (rest.startsWith('issues?') && m === 'post') return res(201, { number: 999, html_url: 'https://github.com/i/999' });
    if (rest.startsWith('issues?')) return res(200, [{ number: 120, title: 'Phone loop', state: 'open', comments: 3 }]);
    if (rest === 'issues' && m === 'post') { const made = { number: 999 + created.length, html_url: 'https://github.com/i/' + (999 + created.length), title: body.title, body: body.body, state: 'open' }; created.push(made); posted.push({ newIssue: body.title }); return res(201, made); }
    return res(404, 'no stub for ' + rest);
  } };
  const ctx = {
    console: { log(value) { logs.push(value); }, error: console.error }, JSON, Math, Date, Array, Object, String, Number, RegExp, Error,
    encodeURIComponent, decodeURIComponent, parseInt, isNaN,
    UrlFetchApp,
    Utilities: { base64Decode: (s) => [...Buffer.from(s, 'base64')], base64Encode: (s) => Buffer.from(s, 'utf8').toString('base64'),
      getUuid: crypto.randomUUID, DigestAlgorithm: { SHA_256: 'SHA-256' },
      computeDigest: (_algorithm, text) => [...crypto.createHash('sha256').update(text).digest()],
      newBlob: blob, formatDate: (d, tz, f) => fmt(d, f), sleep: () => {}, Charset: { UTF_8: 'UTF-8' } },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), getProperties: () => ({ ...props }),
      setProperty: (k, v) => { if (!scenario.propertyWrite || scenario.propertyWrite(k, v) !== false) props[k] = String(v); } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => { if (locked) return false; locked = true; return true; },
      releaseLock: () => { locked = false; } }) },
    ScriptApp: { getProjectTriggers: () => [] }
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx, { filename: 'Athena.gs' });
  return { ctx, props, writes, posted, remoteReceipts, geminiCalls, requests, logs, created };
}

let failures = 0;
function test(name, fn) { try { fn(); console.log('ok   ' + name); } catch (e) { failures++; console.log('FAIL ' + name + '\n     ' + (e.stack || e).toString().split('\n').slice(0, 12).join('\n     ')); } }

const ownerComment = (body, id = 5001) => [{ id, body, author_association: 'OWNER', user: { login: 'the1mburke-blip' },
  html_url: 'https://github.com/o/r/issues/120#issuecomment-' + id, issue_url: GH + '/issues/120', created_at: '2026-10-28T22:00:00Z' }];


const rcpt = (env) => { const p = env.posted.filter((x) => x.issue === '120' && /Icarus run/.test(x.body || '')); return p.length ? p[p.length - 1].body : ''; };
const lineOf = (t, re) => (t.split('\n').find((l) => re.test(l)) || '').slice(0, 400);
const say = (answer) => ({ answer, tool: null, unverified_claims: [], needs_owner: false, owner_reason: '', lesson: '' });
const del = (objective) => ({ answer: '', tool: { name: 'delegate', args: { to: 'SOL', objective, evidence: 'A REQUESTED task issue readback' } } });
const CMD = 'ICARUS_RUN Run the loop and DELEGATE the top undelegated item to SOL.\nVERIFY_FILE: STATUS.md';

test('A: model that keeps calling delegate in every step still ends in exactly ONE real delegation (receipt 6905217187 case)', () => {
  const env = makeEnv({ comments: ownerComment(CMD), gemini: () => del('Reconstruct task denominator and score failures (source issue #214)') });
  env.ctx.athenaPoll();
  const t = rcpt(env);
  console.log('     gemini calls=' + env.geminiCalls.length + ' issues created=' + env.created.length + ' | ' + lineOf(t, /Execution verdict/) + ' | ' + lineOf(t, /Execution integrity/));
  console.log('     ' + lineOf(t, /calls used/).replace(/.*\(/, '('));
  assert.strictEqual(env.created.length, 1, 'expected exactly one task issue');
  assert(/\[TO\] \[SOL\]/.test(env.created[0].body) && /\[STATUS\] REQUESTED/.test(env.created[0].body));
  assert(env.geminiCalls.length <= 3, 'model calls not bounded: ' + env.geminiCalls.length);
  assert(/runtime:delegate\(/.test(t), 'ACT dispatcher delegate not logged');
  assert(/Execution verdict: PASS/.test(t), 'verdict: ' + lineOf(t, /Execution verdict/));
  assert(/#999/.test(t), 'new task number not in receipt');
});

test('B: plan emitted in DISCOVER, prose only in DECIDE (receipt 6905135569 case) still delegates once', () => {
  const env = makeEnv({ comments: ownerComment(CMD), gemini: (n) => n === 1
    ? say('Board read.\nACTION_TO: SOL\nACTION_OBJECTIVE: Reconstruct task denominator and score failures (source issue #214)\nACTION_EVIDENCE: REQUESTED task readback\nDECISION: DELEGATE')
    : n === 2 ? say('Selected #214 and chose to delegate to SOL.') : say('Delegated; see runtime readback. PARTIAL') });
  env.ctx.athenaPoll();
  const t = rcpt(env);
  console.log('     gemini calls=' + env.geminiCalls.length + ' issues created=' + env.created.length + ' | ' + lineOf(t, /Execution verdict/));
  assert.strictEqual(env.created.length, 1);
  assert(/Execution verdict: PASS/.test(t), lineOf(t, /Execution verdict/) + lineOf(t, /^[A-Z_]+/));
});

test('C: well-formed DECIDE (markdown-bold labels) delegates once; model answer in ACT', () => {
  const env = makeEnv({ comments: ownerComment(CMD), gemini: (n) => n === 1 ? say('Board read; #214 undelegated.')
    : n === 2 ? say('**ACTION_TO:** SOL\n**ACTION_OBJECTIVE:** Reconstruct task denominator and score failures (source issue #214)\n**ACTION_EVIDENCE:** REQUESTED task readback\n**DECISION: DELEGATE**')
    : say('Task #999 is REQUESTED for SOL. PARTIAL') });
  env.ctx.athenaPoll();
  const t = rcpt(env);
  console.log('     gemini calls=' + env.geminiCalls.length + ' issues created=' + env.created.length + ' | ' + lineOf(t, /Execution verdict/));
  assert.strictEqual(env.created.length, 1);
  assert.strictEqual(env.geminiCalls.length, 3);
  assert(/Execution verdict: PASS/.test(t), lineOf(t, /Execution verdict/));
});

test('D: READ_ONLY decision performs no delegation', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN Report endpoint status. Read only.\nVERIFY_FILE: STATUS.md'), gemini: (n) => n === 2 ? say('DECISION: READ_ONLY') : say('step ' + n + ' PARTIAL') });
  env.ctx.athenaPoll();
  const t = rcpt(env);
  console.log('     gemini calls=' + env.geminiCalls.length + ' issues created=' + env.created.length + ' | ' + lineOf(t, /Execution verdict/));
  assert.strictEqual(env.created.length, 0);
  assert(/Execution verdict: PASS/.test(t), lineOf(t, /Execution verdict/));
});

console.log(failures ? failures + ' FAILED' : 'all passed');
process.exit(failures ? 1 : 0);
