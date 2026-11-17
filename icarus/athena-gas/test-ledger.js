// Offline test of the Athena git-ledger bridge (ICARUS_QUEUE enqueue + outcome relay).
// Apps Script services are stubbed and gh_ is replaced by an in-memory contents API. No network.
// Usage: node test-ledger.js <repo_dir> [<out_dir>]  (out_dir receives the queued file for the Python cross-check)
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const REPO_DIR = process.argv[2], OUT_DIR = process.argv[3];
const SRC = fs.readFileSync(path.join(REPO_DIR, 'icarus/athena-gas/Athena.gs'), 'utf8');

function makeEnv() {
  const props = { GITHUB_PAT: 'ghp_TESTSECRET123456' };
  const files = {}, posts = [];
  const blob = (x) => {
    const buf = Buffer.isBuffer(x) ? x : Array.isArray(x) ? Buffer.from(x.map((b) => b & 255)) : Buffer.from(String(x), 'utf8');
    return { getDataAsString: () => buf.toString('utf8'), getBytes: () => [...buf] };
  };
  const ctx = {
    console: { log: () => {} },
    Utilities: {
      Charset: { UTF_8: 'utf8' },
      base64Encode: (s) => Buffer.from(String(s), 'utf8').toString('base64'),
      base64Decode: (s) => [...Buffer.from(String(s), 'base64')],
      newBlob: blob, getUuid: () => 'uuid-1', formatDate: () => 'x',
    },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    UrlFetchApp: { fetch: () => { throw new Error('network disabled in test'); } },
    ScriptApp: {},
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  ctx.gh_ = (R, method, p, body) => {
    const m = /^contents\/([^?]+)(?:\?.*)?$/.exec(p);
    if (m) {
      const fp = m[1].split('/').map(decodeURIComponent).join('/');
      if (method === 'GET') {
        if (fp in files) return { code: 200, text: JSON.stringify({ type: 'file', sha: 's', content: Buffer.from(files[fp]).toString('base64') }) };
        const kids = Object.keys(files).filter((k) => k.startsWith(fp + '/')).map((k) => ({ name: k.slice(fp.length + 1), type: 'file' }));
        return kids.length ? { code: 200, text: JSON.stringify(kids) } : { code: 404, text: '{}' };
      }
      if (method === 'PUT') {
        const existed = fp in files;
        files[fp] = Buffer.from(body.content, 'base64').toString('utf8');
        return { code: existed ? 200 : 201, text: JSON.stringify({ commit: { sha: 'c0ffee' } }) };
      }
    }
    const c = /^issues\/(\d+)\/comments$/.exec(p);
    if (c && method === 'POST') { posts.push({ issue: Number(c[1]), body: body.body }); return { code: 201, text: JSON.stringify({ id: 900 + posts.length }) }; }
    return { code: 500, text: 'unexpected ' + method + ' ' + p };
  };
  return { ctx, props, files, posts };
}

const job = { job_id: 'T-001', task: { objective: 'write hello' }, verify_spec: { expected_files: ['out.txt'] } };
const owner = { author_association: 'OWNER', html_url: 'https://github.com/x/y/issues/7#c', body: '' };

// 1. classification: only OWNER may queue; others are ignored (not turned into runs)
{
  const { ctx } = makeEnv();
  assert.strictEqual(ctx.classifyComment_({ ...owner, body: 'ICARUS_QUEUE\n{}' }), 'queue');
  assert.strictEqual(ctx.classifyComment_({ ...owner, author_association: 'COLLABORATOR', body: 'ICARUS_QUEUE\n{}' }), null);
  assert.strictEqual(ctx.classifyComment_({ ...owner, body: 'ICARUS_RUN x' }), 'run');
}

// 2. validation: pass criteria must be set at enqueue; bad ids and JSON refused; nothing written
{
  const { ctx, files } = makeEnv();
  const run = (b) => ctx.runAthena_({ kind: 'queue', body: b, id: '1', actor: 'michael', issue: 7 }, 'f');
  for (const bad of ['ICARUS_QUEUE not json',
    'ICARUS_QUEUE ' + JSON.stringify({ ...job, verify_spec: {} }),
    'ICARUS_QUEUE ' + JSON.stringify({ ...job, job_id: '../x' }),
    'ICARUS_QUEUE ' + JSON.stringify({ ...job, max_attempts: 0 })]) {
    assert.strictEqual(run(bad).verdict, 'BLOCKED', bad);
  }
  assert.deepStrictEqual(Object.keys(files), []);
}

// 3. enqueue: fenced JSON accepted, immutable queue file written and read back, never claims PASS
{
  const { ctx, files } = makeEnv();
  const body = 'ICARUS_QUEUE\n```json\n' + JSON.stringify(job) + '\n```';
  const r = ctx.runAthena_({ kind: 'queue', body, id: '1', actor: 'michael', issue: 7 }, 'f');
  assert.strictEqual(r.verdict, 'PARTIAL');
  assert.ok(/QUEUED \(not executed\)/.test(r.payload) && !/\bPASS\b/.test(r.payload), r.payload);
  const q = JSON.parse(files['icarus/ledger/queue/T-001.json']);
  assert.deepStrictEqual(Object.keys(q).sort(), ['author', 'max_attempts', 'task', 'verify_spec']);
  assert.strictEqual(q.task.source_issue, 7);
  assert.strictEqual(q.author, 'owner:michael');
  const again = ctx.runAthena_({ kind: 'queue', body, id: '2', actor: 'michael', issue: 7 }, 'f');
  assert.strictEqual(again.verdict, 'BLOCKED');
  if (OUT_DIR) fs.writeFileSync(path.join(OUT_DIR, 'T-001.json'), files['icarus/ledger/queue/T-001.json']);
}

// 4. relay: only final states, once each, to the source issue, loop-safe prefix
{
  const { ctx, files, posts, props } = makeEnv();
  files['icarus/ledger/queue/T-001.json'] = JSON.stringify({ task: { source_issue: 7 } });
  files['icarus/ledger/state/T-001.json'] = JSON.stringify({ status: 'claimed', attempts: 0 });
  const R = ctx.newRun_({ id: 'poll', actor: 'poll' });
  ctx.relayLedgerResult_(R, ctx.PropertiesService.getScriptProperties());
  assert.strictEqual(posts.length, 0);
  files['icarus/ledger/state/T-001.json'] = JSON.stringify({ status: 'done', attempts: 1 });
  ctx.relayLedgerResult_(ctx.newRun_({ id: 'poll', actor: 'poll' }), ctx.PropertiesService.getScriptProperties());
  ctx.relayLedgerResult_(ctx.newRun_({ id: 'poll', actor: 'poll' }), ctx.PropertiesService.getScriptProperties());
  assert.strictEqual(posts.length, 1);
  assert.strictEqual(posts[0].issue, 7);
  assert.ok(posts[0].body.startsWith('[ICARUS via runtime]'));
  assert.ok(/OWN_OUTPUT|/.test('') && ctx.classifyComment_({ ...owner, body: posts[0].body }) === null, 'relay must not retrigger');
  assert.ok(Object.keys(props).some((k) => k.startsWith('ATHENA_LEDGER_RELAYED_V1|')));
}

console.log('test-ledger: all assertions passed');
