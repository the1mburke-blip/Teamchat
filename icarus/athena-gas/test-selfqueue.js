// Offline test of Athena cloud-4.6 self-queue (Icarus originates ledger jobs). No network.
// Usage: node test-selfqueue.js <repo_dir> [<out_dir>]
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const REPO_DIR = process.argv[2], OUT_DIR = process.argv[3];
const SRC = fs.readFileSync(path.join(REPO_DIR, 'icarus/athena-gas/Athena.gs'), 'utf8');

function makeEnv(opts) {
  opts = opts || {};
  const props = Object.assign({ GITHUB_PAT: 'ghp_TESTSECRET123456' }, opts.props || {});
  const files = Object.assign({}, opts.files || {}), posts = [], refs = [], modelCalls = [];
  const blob = (x) => {
    const buf = Buffer.isBuffer(x) ? x : Array.isArray(x) ? Buffer.from(x.map((b) => b & 255)) : Buffer.from(String(x), 'utf8');
    return { getDataAsString: () => buf.toString('utf8'), getBytes: () => [...buf] };
  };
  const ctx = {
    console: { log: () => {} },
    Utilities: { Charset: { UTF_8: 'utf8' }, base64Encode: (s) => Buffer.from(String(s), 'utf8').toString('base64'),
      base64Decode: (s) => [...Buffer.from(String(s), 'base64')], newBlob: blob, getUuid: () => 'uuid-1', formatDate: () => '202611181000' },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    UrlFetchApp: { fetch: () => { throw new Error('network disabled in test'); } }, ScriptApp: {},
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  const board = opts.board || [
    { number: 50, title: '[T1] [REQUESTED] Draft a Reddit outreach checklist', body: 'Write the checklist', state: 'open' },
    { number: 227, title: '[RECEIPT LOG] Claude scheduled-run receipts', body: '', state: 'open' },
    { number: 61, title: 'PR thing', body: '', pull_request: {} },
  ];
  ctx.gh_ = (R, method, p, body) => {
    const m = /^contents\/([^?]+)(?:\?.*)?$/.exec(p);
    if (m) {
      const fp = m[1].split('/').map(decodeURIComponent).join('/');
      const q = /[?&]ref=([^&]+)/.exec(p);
      refs.push({ method, fp, ref: q ? decodeURIComponent(q[1]) : (body && body.branch) || null });
      if (method === 'GET') {
        if (fp in files) return { code: 200, text: JSON.stringify({ type: 'file', sha: 's', content: Buffer.from(files[fp]).toString('base64') }) };
        const kids = Object.keys(files).filter((k) => k.startsWith(fp + '/')).map((k) => ({ name: k.slice(fp.length + 1), type: 'file' }));
        return kids.length ? { code: 200, text: JSON.stringify(kids) } : { code: 404, text: '{}' };
      }
      if (method === 'PUT') { const ex = fp in files; files[fp] = Buffer.from(body.content, 'base64').toString('utf8'); return { code: ex ? 200 : 201, text: JSON.stringify({ commit: { sha: 'c0ffee' } }) }; }
    }
    if (/^issues\?state=open/.test(p)) return { code: 200, text: JSON.stringify(board) };
    const c = /^issues\/(\d+)\/comments$/.exec(p);
    if (c && method === 'POST') { posts.push({ issue: Number(c[1]), body: body.body }); return { code: 201, text: JSON.stringify({ id: 900 + posts.length }) }; }
    return { code: 500, text: 'unexpected ' + method + ' ' + p };
  };
  ctx.loadCfg_ = () => JSON.parse(JSON.stringify(ctx.DEFAULT_CFG));
  ctx.usageToday_ = () => ({});
  ctx.approved_ = (R) => { R.provider['gemini-3.5-flash-lite'] = 'google'; return { models: ['gemini-3.5-flash-lite'], err: '' }; };
  ctx.pool_ = (R, system, user) => { modelCalls.push({ system, user }); return { ans: opts.answer === undefined ? GOOD : opts.answer, used: 'gemini-3.5-flash-lite', err: '' }; };
  const R = ctx.newRun_({ id: 'poll', actor: 'poll' });
  return { ctx, R, props, files, posts, refs, modelCalls };
}
const GOOD = { decision: 'QUEUE', source_issue: 50, title: 'Reddit outreach checklist',
  objective: 'Write checklist.md: a 10-step value-first Reddit outreach checklist for the Niche Blueprint, no links, no numbers.',
  expected_files: ['checklist.md'], reason: 'drafting task, sandbox-safe' };
let n = 0; const ok = (name) => { n++; console.log('ok   ' + name); };

{ // 1. idle and due: Icarus writes the job himself, pulse-authored pass criteria, announcement on the item
  const e = makeEnv();
  const out = e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties());
  assert.strictEqual(out, 'queued auto-202611181000-50', out);
  const q = JSON.parse(e.files['icarus/ledger/queue/auto-202611181000-50.json']);
  assert.strictEqual(q.author, 'icarus:pulse-self-queue');
  assert.deepStrictEqual(q.verify_spec.expected_files, ['checklist.md']);
  assert(q.verify_spec.forbidden_patterns.includes('GH_TOKEN') && q.verify_spec.allowed_commands.includes('sh'));
  assert.strictEqual(q.task.source_issue, 50);
  assert(e.refs.filter((r) => r.method === 'PUT').every((r) => r.ref === 'icarus-ledger'), 'writes must hit icarus-ledger');
  assert.strictEqual(e.posts.length, 1); assert.strictEqual(e.posts[0].issue, 50);
  assert(e.ctx.OWN_OUTPUT.test(e.posts[0].body), 'announcement must not retrigger the pulse');
  assert(!/RECEIPT LOG/.test(e.modelCalls[0].user) && !/PR thing/.test(e.modelCalls[0].user), 'receipt logs and PRs excluded from board');
  assert.deepStrictEqual(JSON.parse(e.props.ATHENA_SELF_QUEUE_PICKED_V1), [50]);
  assert.strictEqual(e.R.branch, 'main', 'branch restored');
  if (OUT_DIR) fs.writeFileSync(path.join(OUT_DIR, 'auto-job.json'), e.files['icarus/ledger/queue/auto-202611181000-50.json']);
  // 2. second tick in the same window does nothing
  assert.strictEqual(e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties()), 'not due');
  assert.strictEqual(e.modelCalls.length, 1);
  ok('idle poll: Icarus self-queues one job, criteria set by pulse, announced, rate-limited');
}
{ // 3. unfinished ledger job: no model call, no write
  const e = makeEnv({ files: { 'icarus/ledger/queue/hv-fb-001.json': '{}' } });
  const out = e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties());
  assert(/^ledger busy: hv-fb-001/.test(out), out);
  assert.strictEqual(e.modelCalls.length, 0); assert.strictEqual(e.posts.length, 0);
  ok('ledger busy: no pile-up while the laptop is off');
}
{ // 4. finished jobs do not block
  const e = makeEnv({ files: { 'icarus/ledger/queue/canary-004.json': '{}', 'icarus/ledger/state/canary-004.json': '{"status":"done"}' } });
  assert(/^queued /.test(e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties())));
  ok('finished ledger jobs do not block self-queue');
}
{ // 5. picks off the board or with unsafe paths are rejected; nothing written
  for (const bad of [Object.assign({}, GOOD, { source_issue: 227 }), Object.assign({}, GOOD, { expected_files: ['../x'] }),
    Object.assign({}, GOOD, { expected_files: [] }), Object.assign({}, GOOD, { objective: 'short' })]) {
    const e = makeEnv({ answer: bad });
    const out = e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties());
    assert(/^rejected pick/.test(out), out);
    assert(!Object.keys(e.files).some((k) => k.startsWith('icarus/ledger/queue/')));
  }
  ok('invalid picks rejected without writes');
}
{ // 6. NOTHING_TO_DO and kill switch
  const e = makeEnv({ answer: { decision: 'NOTHING_TO_DO', reason: 'all items need credentials' } });
  assert(/^nothing to do/.test(e.ctx.selfQueueTick_(e.R, e.ctx.PropertiesService.getScriptProperties())));
  const k = makeEnv({ props: { ATHENA_SELF_QUEUE_V1: 'off' } });
  assert.strictEqual(k.ctx.selfQueueTick_(k.R, k.ctx.PropertiesService.getScriptProperties()), 'off');
  assert.strictEqual(k.modelCalls.length, 0);
  ok('NOTHING_TO_DO and kill switch write nothing');
}
{ // 7. version string
  const e = makeEnv();
  assert(/^cloud-4\.6/.test(e.ctx.ATHENA_VERSION));
  ok('version cloud-4.6');
}
console.log('all ' + n + ' passed');
