// Offline tests run the real relay/parser with a strict transport stub.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../scripts/grace_drive_relay.gs'), 'utf8');
const good = { task_id: 'MORNING-001', chair: 'DEEPSEEK', command: 'Read the board and return verified findings',
  expected_artifacts: ['logs/morning-findings.md'], cost_limit_eur: 0 };
const handoff = (body, ready = 'YES') => `HANDOFF_ID: MORNING-001\nREADY: ${ready}\nBODY_BEGIN\n${body}\nBODY_END\n`;

function env(text) {
  const props = { GITHUB_PAT: 'TEST-ONLY' }, requests = [];
  let posted;
  const ctx = { console, DocumentApp: { openById: () => ({ getBody: () => ({ getText: () => text }) }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => props[k], setProperty: (k,v) => { props[k] = v; } }) },
    UrlFetchApp: { fetch(url, opts) {
      requests.push({ url, opts });
      let value = [];
      if (opts.method === 'post') { posted = JSON.parse(opts.payload).body; value = { id: 12, body: posted }; }
      if (url.endsWith('/issues/comments/12')) value = { id: 12, body: posted, html_url: 'https://github.com/test/12' };
      return { getResponseCode: () => opts.method === 'post' ? 201 : 200, getContentText: () => JSON.stringify(value) };
    } } };
  vm.createContext(ctx); vm.runInContext(source, ctx);
  return { ctx, props, requests, posted: () => posted };
}

for (const key of Object.keys(good)) {
  const bad = { ...good }; delete bad[key];
  const e = env(handoff(JSON.stringify(bad)));
  assert.throws(() => e.ctx.relayPrimeHandoff(), /GRACE_PACKET_REJECTED/);
  assert.equal(e.requests.length, 0, 'invalid packet reached GitHub');
  assert.equal(e.props.LAST_RELAYED_HANDOFF_ID, undefined);
}
for (const bad of ['[object Object]', 'not JSON', '{}', 'null', '[]',
    JSON.stringify({ ...good, cost_limit_eur: 1 }), JSON.stringify({ ...good, cost_limit_eur: '0' }),
    JSON.stringify({ ...good, chair: 'UNKNOWN' }), JSON.stringify({ ...good, command: {} }),
    JSON.stringify({ ...good, command: ' ' }), JSON.stringify({ ...good, expected_artifacts: [] }),
    JSON.stringify({ ...good, expected_artifacts: ['[object Object]'] }),
    JSON.stringify({ ...good, extra: 'reject' }), JSON.stringify({ ...good, task_id: 'other' })]) {
  const e = env(handoff(bad));
  assert.throws(() => e.ctx.relayPrimeHandoff(), /GRACE_PACKET_REJECTED/);
  assert.equal(e.requests.length, 0);
}
const e = env(handoff(JSON.stringify(good)));
e.ctx.relayPrimeHandoff();
assert.equal(e.requests.filter((r) => r.opts.method === 'post').length, 1);
assert(e.posted().includes('```json\n'));
assert(!e.posted().includes('[object Object]'));
assert.deepEqual(JSON.parse(e.posted().split('```json\n')[1].split('\n```')[0]), good);
assert.equal(e.props.LAST_RELAYED_HANDOFF_ID, good.task_id);
const pending = env(handoff('placeholder', 'NO'));
pending.ctx.relayPrimeHandoff();
assert.equal(pending.requests.length, 0);
console.log('Grace packet regressions passed: required fields, types, EUR0, rejection before transport, JSON rendering, readback');
