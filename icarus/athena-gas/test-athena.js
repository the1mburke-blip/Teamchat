// Offline test of Athena.gs: Apps Script services are stubbed, GitHub contents are served from the local
// Teamchat checkout, Gemini answers are scripted. No network, no credentials.
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const REPO_DIR = process.argv[2];
const SRC = fs.readFileSync(path.join(REPO_DIR, 'icarus/athena-gas/Athena.gs'), 'utf8');
const SECRET = 'ghp_TESTSECRET123456', GKEY = 'AIzaTESTKEY';

function fmt(d, f) {
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return f.replace(/'([^']*)'/g, '\u0001$1\u0001').replace(/yyyy|MM|dd|HH|mm|ss/g, (t) => ({
    yyyy: d.getUTCFullYear(), MM: p(d.getUTCMonth() + 1), dd: p(d.getUTCDate()), HH: p(d.getUTCHours()), mm: p(d.getUTCMinutes()), ss: p(d.getUTCSeconds()) }[t])).replace(/\u0001([^\u0001]*)\u0001/g, '$1');
}

function makeEnv(scenario) {
  const props = { GITHUB_PAT: SECRET, GEMINI_API_KEY: GKEY, ATHENA_SEEN_SINCE: '2026-10-28T00:00:00Z' };
  const writes = {}, comments = [], posted = [], geminiCalls = [];
  const blob = (x) => {
    const buf = Buffer.isBuffer(x) ? x : Array.isArray(x) ? Buffer.from(x.map((b) => b & 255)) : Buffer.from(String(x), 'utf8');
    return { getDataAsString: () => buf.toString('utf8'), getBytes: () => [...buf] };
  };
  const res = (code, obj) => ({ getResponseCode: () => code, getContentText: () => typeof obj === 'string' ? obj : JSON.stringify(obj) });
  function contents(rel, method, body) {
    const full = path.join(REPO_DIR, rel);
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
    if (rest.startsWith('contents/')) return contents(decodeURIComponent(rest.slice(9).split('?')[0]), m, body);
    if (rest.startsWith('contents?')) return contents('', m, body);
    if (rest.startsWith('issues/comments?')) return res(200, scenario.comments);
    if (/^issues\/\d+\/comments/.test(rest) && m === 'post') { posted.push({ issue: rest.split('/')[1], body: body.body }); return res(201, { url: 'https://api.github.com/x', html_url: 'https://github.com/x' }); }
    if (/^issues\/\d+\/comments/.test(rest)) return res(200, []);
    if (/^issues\/\d+$/.test(rest)) return res(200, { number: Number(rest.split('/')[1]), title: 'Test issue', body: 'body', state: 'open', comments: 0 });
    if (rest.startsWith('issues?') && m === 'post') return res(201, { number: 999, html_url: 'https://github.com/i/999' });
    if (rest.startsWith('issues?')) return res(200, [{ number: 120, title: 'Phone loop', state: 'open', comments: 3 }]);
    if (rest === 'issues' && m === 'post') { posted.push({ newIssue: body.title }); return res(201, { number: 999, html_url: 'https://github.com/i/999' }); }
    return res(404, 'no stub for ' + rest);
  } };
  const ctx = {
    console, JSON, Math, Date, Array, Object, String, Number, RegExp, Error,
    encodeURIComponent, decodeURIComponent, parseInt, isNaN,
    UrlFetchApp,
    Utilities: { base64Decode: (s) => [...Buffer.from(s, 'base64')], base64Encode: (s) => Buffer.from(s, 'utf8').toString('base64'),
      newBlob: blob, formatDate: (d, tz, f) => fmt(d, f), sleep: () => {}, Charset: { UTF_8: 'UTF-8' } },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    ScriptApp: { getProjectTriggers: () => [] }
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx, { filename: 'Athena.gs' });
  return { ctx, props, writes, posted, geminiCalls };
}

let failures = 0;
function test(name, fn) { try { fn(); console.log('ok   ' + name); } catch (e) { failures++; console.log('FAIL ' + name + '\n     ' + (e.stack || e).toString().split('\n').slice(0, 3).join('\n     ')); } }

const ownerComment = (body, id = 5001) => [{ id, body, author_association: 'OWNER', user: { login: 'the1mburke-blip' },
  html_url: 'https://github.com/o/r/issues/120#issuecomment-' + id, issue_url: 'https://api.github.com/repos/o/r/issues/120', created_at: '2026-10-28T22:00:00Z' }];

test('poll runs an owner ICARUS_RUN comment end to end: recall, 3-step loop, gate PASS, receipt, reply', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN Say hello and list the last 3 entries in icarus/memory/learned.md.\nVERIFY_FILE: icarus/memory/learned.md'),
    gemini: (n) => n === 1 ? { answer: '', tool: { name: 'read_file', args: { path: 'icarus/memory/learned.md', offset: 0 } } }
      : { answer: 'step ' + n + ' done', tool: null, unverified_claims: ['none'], needs_owner: false, owner_reason: '', lesson: '' } });
  env.ctx.athenaPoll();
  const receipt = Object.keys(env.writes).find((k) => k.startsWith('icarus/runs/'));
  assert(receipt, 'no receipt written');
  const t = env.writes[receipt];
  assert(/- VERDICT: PASS - all gates passed/.test(t), 'verdict not PASS:\n' + t.split('\n').filter((l) => /VERDICT|Error/.test(l)).join('\n'));
  assert(/- Recalled: task:/.test(t), 'no recall line');
  assert(/Loop: DISCOVER/.test(t), 'loop not run');
  assert(/read_file\(/.test(t), 'tool call not logged');
  assert(!t.includes(SECRET) && !t.includes(GKEY), 'secret leaked');
  assert.strictEqual(env.posted.filter((p) => p.issue === '120').length, 1, 'no reply on issue 120');
  assert.strictEqual(env.props.ATHENA_SEEN_SINCE, '2026-10-28T22:00:00Z');
  assert(JSON.parse(env.props.ATHENA_DONE_IDS).includes('5001'));
});

test('same comment is not run twice', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN hi'), gemini: () => ({ answer: 'x', tool: null }) });
  env.props.ATHENA_DONE_IDS = JSON.stringify(['5001']);
  env.ctx.athenaPoll();
  assert.strictEqual(Object.keys(env.writes).length, 0);
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
  const t = env.writes[Object.keys(env.writes).find((k) => k.startsWith('icarus/runs/'))];
  assert(/- VERDICT: FAIL - no evidence gate supplied/.test(t));
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
});

test('quota 429 fails over to the next approved model', () => {
  const env = makeEnv({ comments: ownerComment('ICARUS_RUN hi\nloop: off\nVERIFY_FILE: STATUS.md'),
    gemini: (n) => n <= 2 ? { code: 429, text: 'RESOURCE_EXHAUSTED per minute' } : { answer: 'hello', tool: null } });
  env.ctx.athenaPoll();
  const t = env.writes[Object.keys(env.writes).find((k) => k.startsWith('icarus/runs/'))];
  assert(/HTTP 429/.test(t) && /- VERDICT: PASS/.test(t), t.split('\n').filter((l) => /attempts|VERDICT|Error/.test(l)).join('\n'));
  assert(new Set(env.geminiCalls.map((c) => c.url)).size >= 2, 'did not switch model');
});

test('hourly check writes a receipt and posts no reply', () => {
  const env = makeEnv({ comments: [], gemini: () => ({ answer: 'all quiet', tool: null }) });
  env.ctx.athenaHourly();
  assert(Object.keys(env.writes).some((k) => k.startsWith('icarus/runs/') && k.includes('hourly-')));
  assert.strictEqual(env.posted.length, 0);
});

test('installAthenaTriggers and selfTest run', () => {
  const env = makeEnv({ comments: [], gemini: () => ({}) });
  env.ctx.ScriptApp = { getProjectTriggers: () => [], newTrigger: () => ({ timeBased: () => ({ everyMinutes: () => ({ create() {} }), everyHours: () => ({ create() {} }) }) }) };
  vm.runInContext('installAthenaTriggers()', env.ctx);
  const s = JSON.parse(vm.runInContext('athenaSelfTest()', env.ctx));
  assert.strictEqual(s.identityRead, 200); assert(s.approvedRoutes > 0); assert(s.secrets.github && s.secrets.gemini);
});

console.log(failures ? failures + ' FAILED' : 'all passed');
process.exitCode = failures ? 1 : 0;
