// Offline test of Athena.gs: Apps Script services are stubbed, GitHub contents are served from the local
// Teamchat checkout, Gemini answers are scripted. No network, no credentials.
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const REPO_DIR = process.argv[2];
const SRC = fs.readFileSync(path.join(REPO_DIR, 'icarus/athena-gas/Athena.gs'), 'utf8');
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
  const props = { GITHUB_PAT: SECRET, GEMINI_API_KEY: GKEY, ATHENA_CUTOVER_V1: JSON.stringify(config),
    [QUARANTINE]: 'QUARANTINED_UNCERTAIN', [PROOF]: proof(config) };
  const writes = {}, posted = [], remoteReceipts = [], geminiCalls = [], requests = [];
  const logs = [];
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
    if (/^issues\/\d+$/.test(rest)) return res(200, { number: Number(rest.split('/')[1]), title: 'Test issue', body: 'body', state: 'open', comments: 0 });
    if (rest.startsWith('issues?') && m === 'post') return res(201, { number: 999, html_url: 'https://github.com/i/999' });
    if (rest.startsWith('issues?')) return res(200, [{ number: 120, title: 'Phone loop', state: 'open', comments: 3 }]);
    if (rest === 'issues' && m === 'post') { posted.push({ newIssue: body.title }); return res(201, { number: 999, html_url: 'https://github.com/i/999' }); }
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
  return { ctx, props, writes, posted, remoteReceipts, geminiCalls, requests, logs };
}

let failures = 0;
function test(name, fn) { try { fn(); console.log('ok   ' + name); } catch (e) { failures++; console.log('FAIL ' + name + '\n     ' + (e.stack || e).toString().split('\n').slice(0, 12).join('\n     ')); } }

const ownerComment = (body, id = 5001) => [{ id, body, author_association: 'OWNER', user: { login: 'the1mburke-blip' },
  html_url: 'https://github.com/o/r/issues/120#issuecomment-' + id, issue_url: GH + '/issues/120', created_at: '2026-10-28T22:00:00Z' }];

test('poll runs an owner ICARUS_RUN comment end to end: recall, 3-step loop, gate PASS, receipt, reply', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN Say hello and list the last 3 entries in icarus/memory/learned.md.\nVERIFY_FILE: icarus/memory/learned.md'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'read_file', args: { path: 'icarus/memory/learned.md', offset: 0 } } }
      : { answer: 'step ' + n + ' done', tool: null, unverified_claims: ['none'], needs_owner: false, owner_reason: '', lesson: '' } });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(t, 'no receipt written');
  assert.strictEqual(Object.keys(env.writes).length, 0, 'receipt attempted protected-main write');
  assert(/- Execution verdict: PASS - all gates passed/.test(t), 'verdict not PASS:\n' + t.split('\n').filter((l) => /VERDICT|Error/.test(l)).join('\n'));
  assert(/- Recalled: task:/.test(t), 'no recall line');
  assert(/Loop: DISCOVER/.test(t), 'loop not run');
  assert(/read_file\(/.test(t), 'tool call not logged');
  assert(!t.includes(SECRET) && !t.includes(GKEY), 'secret leaked');
  assert.strictEqual(env.posted.filter((p) => p.issue === '120').length, 1, 'no reply on issue 120');
  assert.strictEqual(env.props[CURSOR], '2026-10-28T22:00:00Z');
  assert.strictEqual(attemptOf(env).state, 'ACKNOWLEDGED');
});

test('same comment is not run twice', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN hi'), gemini: () => ({ answer: 'x', tool: null }) });
  env.ctx.athenaPoll();
  const calls = env.geminiCalls.length;
  env.ctx.athenaPoll();
  assert(calls > 0);
  assert.strictEqual(env.geminiCalls.length, calls);
  assert.strictEqual(env.posted.length, 1);
});

test('non-owner and pull-request comments are ignored', () => {
  const c = ownerComment('ICARUS_RUN hi'); c[0].author_association = 'CONTRIBUTOR';
  const p = ownerComment('ICARUS_RUN hi', 5002); p[0].html_url = 'https://github.com/o/r/pull/5#x';
  const env = makeEnv({ comments: c.concat(p), gemini: () => ({ answer: 'x', tool: null }) });
  env.ctx.athenaPoll();
  assert.strictEqual(Object.keys(env.writes).length, 0);
});

test('model cannot claim PASS without gates', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN do something'), gemini: () => ({ answer: 'PASS, all done and verified', tool: null }) });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(/- Execution verdict: FAIL - no evidence gate supplied/.test(t));
});

test('write_file without OWNER_APPROVED is denied; runtime paths always denied', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN write a file\nloop: off'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'write_file', args: { path: 'notes/x.md', content: 'hi' } } } : { answer: 'done', tool: null } });
  env.ctx.athenaPoll();
  assert(!('notes/x.md' in env.writes), 'unapproved write went through');
  const env2 = makeEnv({ comments: ownerComment('ICARUS_RUN write\nOWNER_APPROVED: edit runtime\nloop: off'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'write_file', args: { path: 'icarus/athena-gas/Athena.gs', content: 'x' } } } : { answer: 'done', tool: null } });
  env2.ctx.athenaPoll();
  assert(!('icarus/athena-gas/Athena.gs' in env2.writes), 'runtime self-edit went through');
  const env3 = makeEnv({ comments: ownerComment('ICARUS_RUN write\nOWNER_APPROVED: edit core runtime\nloop: off'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'write_file', args: { path: 'icarus/core/runtime.py', content: 'x' } } } : { answer: 'done', tool: null } });
  env3.ctx.athenaPoll();
  assert(!('icarus/core/runtime.py' in env3.writes), 'core runtime write went through');
});

test('quota 429 fails over to the next approved model', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN hi\nloop: off\nVERIFY_FILE: STATUS.md'),
    gemini: (n) => n === 1 ? { code: 429, text: 'RESOURCE_EXHAUSTED per minute' }
      : n === 2 ? { tool: { name: 'read_file', args: { path: 'STATUS.md' } } } : { answer: 'hello', tool: null } });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(/HTTP 429/.test(t) && /- Execution verdict: PASS/.test(t), t.split('\n').filter((l) => /attempts|VERDICT|Error/.test(l)).join('\n'));
  assert(new Set(env.geminiCalls.map((c) => c.url)).size === 2, 'did not switch model');
  assert(env.geminiCalls.slice(1).every((c) => c.url.includes('gemini-3.1-flash-lite')), 'revisited exhausted primary');
});

test('hourly check uses the configured receipt issue', () => {
  const env = makeEnv({ comments: [], gemini: () => ({ answer: 'all quiet', tool: null }) });
  env.ctx.athenaHourly();
  assert.strictEqual(Object.keys(env.writes).length, 0);
  assert.strictEqual(env.posted.length, 1);
  assert.strictEqual(env.posted[0].issue, '42');
  assert(receiptOf(env).includes('/0/hourly-'));
});

test('installAthenaTriggers and selfTest run', () => {
  const env = makeEnv({ comments: [], gemini: () => ({}) });
  env.ctx.ScriptApp = { getProjectTriggers: () => [], newTrigger: () => ({ timeBased: () => ({ everyMinutes: () => ({ create() {} }), everyHours: () => ({ create() {} }) }) }) };
  vm.runInContext('installAthenaTriggers()', env.ctx);
  const s = JSON.parse(vm.runInContext('athenaSelfTest()', env.ctx));
  assert.strictEqual(s.identityRead, 200); assert(s.approvedRoutes > 0); assert(s.secrets.github && s.secrets.gemini);
});

function receiptOf(env) { return env.posted.find((item) => item.body && item.body.startsWith('# Icarus run receipt v1'))?.body; }
const agentComment = (body, assoc = 'OWNER', id = 6001) => [{ id, body, author_association: assoc, user: { login: 'the1mburke-blip' },
  html_url: 'https://github.com/o/r/issues/140#issuecomment-' + id, issue_url: GH + '/issues/140', created_at: '2026-10-28T23:00:00Z' }];
const SHA = 'c66c0e6a1b2c3d4e5f60718293a4b5c6d7e8f901';

test('completion claim with checkable evidence is adjudicated PASS by gates (file + commit)', () => {
  const env = makeEnv({ comments: agentComment('[SOL] 2026-10-28T23:00Z\nSTATUS: PASS\nACTION: wrote the status file\nEVIDENCE: STATUS.md updated in commit ' + SHA + '\nHANDOFF_TO: OWNER'),
    commits: [SHA], gemini: (n) => n === 1 ? { tool: { name: 'read_file', args: { path: 'STATUS.md' } } }
      : { answer: 'STATUS.md exists; commit found', tool: null } });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(/- Trigger: completion claim/.test(t), 'trigger line missing');
  assert(/- Proposed by: SOL \(via the1mburke-blip\)/.test(t), 'agent not attributed');
  assert(/ok: VERIFY_COMMIT /.test(t), t.split('\n').filter((l) => /VERIFY|VERDICT/.test(l)).join('\n'));
  assert(/- Execution verdict: PASS - all gates passed/.test(t));
  assert.strictEqual(env.posted.filter((p) => p.issue === '140').length, 1, 'no adjudication reply posted');
});

test('claim naming a repo path that exists passes the file gate; a missing one fails', () => {
  const env = makeEnv({ comments: agentComment('[CODEX]\nSTATUS: PASS\nEVIDENCE: icarus/memory/learned.md and docs/not-there.md, commit ' + SHA),
    commits: [], gemini: () => ({ answer: 'done', tool: null }) });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(/ok: VERIFY_FILE icarus\/memory\/learned.md/.test(t) && /FAIL: VERIFY_FILE docs\/not-there.md/.test(t) && /FAIL: VERIFY_COMMIT/.test(t) && /- Execution verdict: FAIL - a gate failed/.test(t), t.split('\n').filter((l) => /VERIFY|VERDICT/.test(l)).join('\n'));
});

test('completion claim with no checkable evidence is FAIL, whatever the model says', () => {
  const env = makeEnv({ comments: agentComment('[STATUS] PASS\nEVIDENCE: it works, trust me, see the chat'), gemini: () => ({ answer: 'PASS, verified', tool: null }) });
  env.ctx.athenaPoll();
  assert(/- Execution verdict: FAIL - the claim names no checkable evidence/.test(receiptOf(env)));
});

test('/evidence AGENT PASS | ... router form is a claim', () => {
  const env = makeEnv({ comments: agentComment('/evidence SOL PASS | STATUS.md readback'), gemini: () => ({ answer: 'ok', tool: null }) });
  env.ctx.athenaPoll();
  const t = receiptOf(env);
  assert(/- Trigger: completion claim/.test(t) && /ok: VERIFY_FILE STATUS.md/.test(t), t.split('\n').filter((l) => /Trigger|VERIFY/.test(l)).join('\n'));
});

test('claims and addresses are read-only even with OWNER_APPROVED in them', () => {
  const env = makeEnv({ comments: agentComment('@Icarus please fix it\nOWNER_APPROVED: anything'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'write_file', args: { path: 'notes/x.md', content: 'hi' } } } : { answer: 'ok', tool: null } });
  env.ctx.athenaPoll();
  assert(!('notes/x.md' in env.writes), 'write went through from a non-ICARUS_RUN trigger');
  assert(/- Trigger: addressed to Icarus \(read-only reply\)/.test(receiptOf(env)));
  assert(!/Athena/.test(receiptOf(env)), 'internal name leaked into a receipt');
  assert(/write_file\(/.test(receiptOf(env)), 'tool attempt not logged');
});

test('addressed comment ([TO] [ICARUS]) gets a reply attributed to the agent', () => {
  const env = makeEnv({ comments: agentComment('[FROM] [LUNA]\n[TO] [ICARUS]\nWhat is blocking #149?'), gemini: () => ({ answer: 'Actions billing', tool: null }) });
  env.ctx.athenaPoll();
  assert(/- Proposed by: LUNA \(via the1mburke-blip\)/.test(receiptOf(env)));
  assert.strictEqual(env.posted.length, 1);
});

test('no loops: Athena receipts, laptop adjudications, wakes and plain chatter never trigger', () => {
  for (const body of ['# Icarus run 2026-10-28\n- Execution verdict: PASS\nSTATUS: PASS\n[TO] [ICARUS]', 'some text\n\n_Receipt: icarus/runs/x.md_\nSTATUS: PASS',
    '[ICARUS ADJUDICATION] 2026-10-28\n[VERDICT] FAIL\n@Icarus', '[TEAMCHAT_WAKE] NEW_TASK #9\n[TO] [ICARUS]', 'Looks good to me, thanks', 'status pass maybe later',
    'email me at x@icarus.dev']) {
    const env = makeEnv({ comments: agentComment(body), gemini: () => ({ answer: 'x', tool: null }) });
    env.ctx.athenaPoll();
    assert.strictEqual(Object.keys(env.writes).length, 0, 'triggered on: ' + body.slice(0, 40));
  }
});

test('non-team accounts are ignored even when they address Icarus', () => {
  const env = makeEnv({ comments: agentComment('@Icarus hello', 'NONE'), gemini: () => ({ answer: 'x', tool: null }) });
  env.ctx.athenaPoll();
  assert.strictEqual(Object.keys(env.writes).length, 0);
});

test('zero-tool hourly narrative cannot earn PASS or acknowledge a task', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md'),
    gemini: () => ({ answer: 'PASS, I read it', tools_executed: 99, tool: null }) });
  env.ctx.athenaPoll();
  assert(receiptOf(env).includes('Execution verdict: FAIL - ZERO_TOOL_EXECUTION_REJECTED'));
  assert(receiptOf(env).includes('tools_executed: 0'));
  assert.strictEqual(attemptOf(env).state, 'FAILED');
});

test('denied tools cannot earn PASS', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md'),
    gemini: (n) => n === 1 ? { tool: { name: 'imaginary', args: {} } } : { answer: 'PASS', tool: null } });
  env.ctx.athenaPoll();
  assert(receiptOf(env).includes('ZERO_TOOL_EXECUTION_REJECTED'));
  assert.strictEqual(attemptOf(env).state, 'FAILED');
});

test('failure is receipted and does not replay when provider recovers', () => {
  let providerRecovered = false;
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md'),
    gemini: () => providerRecovered ? { answer: 'later', tool: null } : { code: 503, text: 'capacity' } });
  env.ctx.athenaPoll();
  const calls = env.geminiCalls.length;
  assert.strictEqual(attemptOf(env).state, 'FAILED');
  providerRecovered = true;
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, calls);
  assert.strictEqual(env.posted.length, 1);
});

test('crash after durable reservation cannot replay and releases the lock', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md'), gemini: () => ({}) });
  const run = env.ctx.runAthena_;
  env.ctx.runAthena_ = () => { throw new Error('simulated timeout'); };
  assert.throws(() => env.ctx.athenaPoll(), /simulated timeout/);
  assert(!env.props[CURSOR]);
  assert.strictEqual(attemptOf(env).state, 'RUNNING');
  env.ctx.runAthena_ = run;
  env.ctx.athenaPoll();
  assert.strictEqual(attemptOf(env).state, 'QUARANTINED_UNCERTAIN');
  assert.strictEqual(env.geminiCalls.length, 0);
  assert.strictEqual(env.posted.length, 0);
});

test('failed reservation readback blocks side effects', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md'), gemini: () => ({}),
    propertyWrite: (key) => !key.startsWith(JOURNAL) });
  assert.throws(() => env.ctx.athenaPoll(), /Durable state readback failed/);
  assert.strictEqual(env.geminiCalls.length, 0);
  assert.strictEqual(env.posted.length, 0);
});

const readStatus = () => ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md');
const successfulRead = (n) => n === 1 ? { tool: { name: 'read_file', args: { path: 'STATUS.md' } } }
  : { answer: 'read', tool: null };

test('overlapping poll cannot dispatch while first poll holds the script lock', () => {
  const env = makeEnv({ comments: readStatus(), gemini: (n) => {
    env.ctx.athenaPoll();
    return successfulRead(n);
  } });
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 2);
  assert.strictEqual(env.posted.length, 1);
});

test('409 and response loss reconcile without a second POST or execution', () => {
  for (const mode of [{ code: 409 }, { throw: true, commit: true }]) {
    const env = makeEnv({ comments: readStatus(), gemini: successfulRead,
      receiptPost: (_c, props) => {
        const a = attemptOf({ props });
        assert.strictEqual(a.state, 'RECEIPT_UNCERTAIN');
        assert.strictEqual(a.digest.length, 64);
        assert(a.receiptKey.endsWith('|v1'));
        return mode;
      } });
    env.ctx.athenaPoll();
    assert.strictEqual(attemptOf(env).state, 'RECEIPT_UNCERTAIN');
    env.ctx.athenaPoll();
    assert.strictEqual(attemptOf(env).state, mode.commit ? 'ACKNOWLEDGED' : 'RECEIPT_UNCERTAIN');
    assert.strictEqual(env.geminiCalls.length, 2);
    assert.strictEqual(env.posted.length, 1);
  }
});

test('a mismatched or edited receipt never acknowledges or triggers another POST', () => {
  const env = makeEnv({ comments: readStatus(), gemini: successfulRead,
    receiptReadback: (c) => ({ code: 200, body: { ...c, body: c.body + '\nchanged' } }) });
  env.ctx.athenaPoll();
  env.ctx.athenaPoll();
  assert.strictEqual(attemptOf(env).state, 'RECEIPT_UNCERTAIN');
  assert.strictEqual(env.posted.length, 1);
  assert.strictEqual(env.geminiCalls.length, 2);
});

test('unreadable destination before first POST prevents publication and replay', () => {
  const env = makeEnv({ comments: readStatus(), gemini: successfulRead, receiptListError: () => true });
  env.ctx.athenaPoll();
  env.ctx.athenaPoll();
  assert.strictEqual(attemptOf(env).state, 'RECEIPT_UNCERTAIN');
  assert.strictEqual(env.posted.length, 0);
  assert.strictEqual(env.geminiCalls.length, 2);
});

test('cutover is fail-closed until observe mode proves old command exclusion', () => {
  const old = { ...readStatus()[0], id: OLD_ID, issue_url: GH + '/issues/6', created_at: '2026-10-27T22:00:00Z' };
  const uncertain = { ...readStatus()[0], id: 5002 };
  const env = makeEnv({ comments: [old, uncertain, ...readStatus()], gemini: successfulRead });
  delete env.props[PROOF];
  delete env.props[QUARANTINE];
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 0);
  env.props[QUARANTINE] = 'QUARANTINED_UNCERTAIN';
  env.props['ATHENA_QUARANTINE_V1|' + REPO.toLowerCase() + '/120/5002'] = 'QUARANTINED_UNCERTAIN';
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 0);
  env.props.ATHENA_CUTOVER_V1 = JSON.stringify({ ...config, mode: 'observe' });
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 0);
  assert.strictEqual(env.props[PROOF], proof(config));
  assert(env.logs.some((line) => line.includes('excluded comment ' + OLD_ID)));
  env.props.ATHENA_CUTOVER_V1 = JSON.stringify(config);
  env.ctx.athenaPoll();
  assert.strictEqual(attemptOf(env).state, 'ACKNOWLEDGED');
  assert.strictEqual(env.posted.length, 1);
  assert(!env.requests.some(({ method, rest }) => method === 'post' && rest === 'issues/6/comments'));
});

test('pagination, timestamp ties and legacy seen-ID eviction cannot replay a command', () => {
  const ignored = Array.from({ length: 101 }, (_, i) => ({ ...readStatus()[0], id: i + 1, body: 'chatter' }));
  const env = makeEnv({ comments: [...ignored, ...readStatus(), { ...readStatus()[0], id: 5002 }],
    gemini: (n) => successfulRead(n % 2 === 1 ? 1 : 2) });
  env.ctx.athenaPoll();
  env.props.ATHENA_DONE_IDS = '[]';
  env.ctx.athenaPoll();
  env.ctx.athenaPoll();
  assert(env.requests.some(({ rest }) => rest.startsWith('issues/comments?') && rest.endsWith('&page=2')));
  assert.strictEqual(attemptOf(env).state, 'ACKNOWLEDGED');
  assert.strictEqual(attemptOf(env, 5002).state, 'ACKNOWLEDGED');
  assert.strictEqual(env.posted.length, 2);
  assert.strictEqual(env.geminiCalls.length, 4);
});

test('two-read incident requires both successful actual reads, independent of file gates', () => {
  const paths = ['icarus/memory/current-state.md', 'icarus/runtime/endpoints.json'];
  const comments = ownerComment('ICARUS_RUN read both files\nloop: off\n' + paths.map((p) => 'VERIFY_FILE: ' + p).join('\n'));
  for (const reads of [[], [paths[0]], [paths[1]], [paths[0], paths[0]], paths]) {
    const env = makeEnv({ comments, gemini: (n) => n <= reads.length
      ? { tool: { name: 'read_file', args: { path: reads[n - 1] } } } : { answer: 'read both', tool: null } });
    env.ctx.athenaPoll();
    assert.strictEqual(attemptOf(env).state, reads === paths ? 'ACKNOWLEDGED' : 'FAILED');
  }
  const failed = makeEnv({ comments, contents: (p) => p === paths[1] ? { code: 403 } : null,
    gemini: (n) => n <= paths.length ? { tool: { name: 'read_file', args: { path: paths[n - 1] } } }
      : { answer: 'read both', tool: null } });
  failed.ctx.athenaPoll();
  assert.strictEqual(attemptOf(failed).state, 'FAILED');
  assert(receiptOf(failed).includes('TOOL_EXECUTION_FAILED'));
});

test('durable daily cap still applies after replacing file receipts', () => {
  const body = 'ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md\nTEST_CAP_RUNS: 1';
  const env = makeEnv({ comments: [...ownerComment(body), ...ownerComment(body, 5002)], gemini: successfulRead });
  env.ctx.athenaPoll();
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 2);
  assert.strictEqual(attemptOf(env).state, 'ACKNOWLEDGED');
  assert.strictEqual(attemptOf(env, 5002).state, 'FAILED');
  assert(env.posted[1].body.includes('daily run cap reached'));
});

test('hourly read subset fails even with valid existence gates', () => {
  const env = makeEnv({ comments: [], gemini: (n) => n === 1 ? { tool: { name: 'read_file', args: { path: 'icarus/runtime/endpoints.json' } } } : { answer: 'all directories checked', tool: null } });
  env.ctx.athenaHourly();
  assert(receiptOf(env).includes('REQUIRED_TOOL_EXECUTION_MISSING'));
});

test('hourly exact required tool trace can pass', () => {
  const required = [['read_file', 'icarus/runtime/endpoints.json'], ['list_dir', 'icarus/memory'],
    ['list_dir', 'icarus/proposals'], ['list_dir', 'icarus/runs'], ['read_file', 'icarus/memory/current-state.md']];
  const env = makeEnv({ comments: [], gemini: (n) => n <= required.length
    ? { tool: { name: required[n - 1][0], args: { path: required[n - 1][1] } } } : { answer: 'checked', tool: null } });
  env.ctx.athenaHourly();
  assert(receiptOf(env).includes('Execution verdict: PASS'), receiptOf(env).slice(-1200));
});

test('429/503 use exactly two authorized routes once, preserve prompt, then BLOCKED', () => {
  for (const code of [429, 503]) {
    const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md'), gemini: () => ({ code, text: 'capacity' }) });
    env.ctx.athenaPoll();
    assert.strictEqual(env.geminiCalls.length, 2);
    assert.strictEqual(new Set(env.geminiCalls.map((c) => c.url)).size, 2);
    assert.deepStrictEqual(env.geminiCalls[0].body, env.geminiCalls[1].body);
    assert(receiptOf(env).includes('BLOCKED:'));
    assert.strictEqual(attemptOf(env).state, 'FAILED');
  }
});

test('authentication errors stop after primary and never use fallback', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off'), gemini: () => ({ code: 401, text: 'unauthorized' }) });
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 1);
  assert.strictEqual(attemptOf(env).state, 'FAILED');
});

test('unapproved or paid route configuration is rejected before any model request', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nVERIFY_FILE: STATUS.md'),
    contents: (rel) => rel === 'icarus/runtime/approved-routes.json' ? { code: 200, body: { type: 'file', content: Buffer.from(JSON.stringify({ routes: [
      { provider: 'openrouter', model: 'paid/model', approved: true, costPolicy: 'verified-zero-cost' }
    ] })).toString('base64') } } : null,
    gemini: () => { throw new Error('unapproved endpoint used'); } });
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 0);
  assert.strictEqual(attemptOf(env).state, 'FAILED');
});

test('runtime budget exhaustion prevents fallback request', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN read STATUS.md\nloop: off\nTEST_CAP_CALLS: 1'), gemini: () => ({ code: 503, text: 'capacity' }) });
  env.ctx.athenaPoll();
  assert.strictEqual(env.geminiCalls.length, 1);
  assert(receiptOf(env).includes('call budget exhausted'));
});

console.log(failures ? failures + ' FAILED' : 'all passed');
process.exitCode = failures ? 1 : 0;
