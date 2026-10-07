const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { context: c, sheets } = require('./runtime.test.cjs');

// Load ChildPool into the synthetic context
vm.runInContext(
  fs.readFileSync(path.join(__dirname, '../server-overlay/ChildPool.gs'), 'utf8'),
  c,
  { filename: 'ChildPool.gs' }
);
const kernel = vm.runInContext('IcarusGovernance', c);

// Helper to create a unique parent task
let seq = 0;
function makeParent(label) {
  const task = c.createTask_(
    'childpool-device',
    'childpool-' + (++seq),
    'Parent objective ' + label
  );
  if (!task || typeof task.task_id === 'undefined') {
    throw new Error('createTask_ did not return a task with task_id');
  }
  return task.task_id;
}

// A – parent binding and governed child identity
test('A parent binding and governed child identity', () => {
  const parentId = makeParent('A');
  const childId = 'alpha';
  const sub = 'subobjective A';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const binding = c.childPoolCreate_(parentId, childId, sub, caps, route);
  assert.ok(binding);
  assert.equal(binding.governanceId, `${parentId}:child:${childId}`);

  const expectedHash = kernel.hash(sub.trim());
  assert.equal(binding.subobjectiveHash, expectedHash);

  // capabilities are canonical (sorted, deduped)
  assert.deepStrictEqual(JSON.parse(JSON.stringify(binding.capabilities)), caps);

  // route preserved
  assert.equal(binding.route, route);

  // No result row should exist yet
  const result = c.childPoolFindResult_(binding.bindingHash);
  assert.equal(result, null);
});

// B – immutable subobjective conflict
test('B immutable subobjective conflict', () => {
  const parentId = makeParent('B');
  const childId = 'beta';
  const sub1 = 'first sub';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const binding1 = c.childPoolCreate_(parentId, childId, sub1, caps, route);
  const binding2 = c.childPoolCreate_(parentId, childId, sub1, caps, route);
  assert.deepStrictEqual(binding1, binding2);

  // Different subobjective should reject
  assert.throws(() => {
    c.childPoolCreate_(parentId, childId, 'different sub', caps, route);
  }, /CHILD_BINDING_CONFLICT/);
});

// C – capability/route non‑escalation
test('C capability/route non‑escalation', () => {
  const parentId = makeParent('C');
  const childId = 'gamma';
  const sub = 'sub C';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const binding = c.childPoolCreate_(parentId, childId, sub, caps, route);
  assert.ok(binding);

  // Attempt to broaden capabilities
  assert.throws(() => {
    c.childPoolCreate_(parentId, childId, sub, ['analysis.read', 'research.read'], route);
  }, /CHILD_BINDING_CONFLICT/);

  // Attempt to change route
  assert.throws(() => {
    c.childPoolCreate_(parentId, childId, sub, caps, 'OPENROUTER_FREE');
  }, /CHILD_BINDING_CONFLICT/);

  // Invalid capability
  assert.throws(() => {
    c.childPoolCreate_(parentId, 'delta', sub, ['unknown.cap'], route);
  }, /CAPABILITY_DENIED/);

  // Invalid route
  assert.throws(() => {
    c.childPoolCreate_(parentId, 'epsilon', sub, caps, 'BAD_ROUTE');
  }, /ROUTE_DENIED/);
});

// D – isolation/no nested delegation
test('D isolation/no nested delegation', () => {
  const parentId = makeParent('D');
  const childId = 'zeta';
  const sub = 'sub D';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const dispatcher = () => {
    // Attempt nested child creation
    c.childPoolCreate_(parentId, 'nested', sub, caps, route);
    return { ok: true };
  };

  assert.throws(() => {
    c.childPoolRun_(parentId, childId, sub, caps, route, dispatcher);
  }, /NESTED_CHILD_DISPATCH_DENIED/);

  // Ensure no result persisted
  const binding = c.childPoolFindBinding_(parentId, childId);
  assert.ok(binding);
  const result = c.childPoolFindResult_(binding.bindingHash);
  assert.equal(result, null);
});

// E – kernel binding/material‑change denial
test('E kernel binding/material‑change denial', () => {
  const parentId = makeParent('E');
  const childId = 'eta';
  const sub = 'sub E';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const binding = c.childPoolCreate_(parentId, childId, sub, caps, route);
  const spec = c.childPoolSpec_(binding);
  const principal = { id: 'ghost:' + childId, role: 'executor' };
  const permit = kernel.prepare(binding.governanceId, spec, principal);

  // Clone spec and tamper with route
  const tamperedSpec = JSON.parse(JSON.stringify(spec));
  tamperedSpec.route = 'OPENROUTER_FREE';

  let effect = 0;
  assert.throws(() => {
    kernel.run(permit, tamperedSpec, principal, () => {
      effect++;
    });
  }, /MATERIAL_CHANGE/);
  assert.equal(effect, 0);
});

// F – executor cannot self‑PASS
test('F executor cannot self‑PASS', () => {
  const parentId = makeParent('F');
  const childId = 'theta';
  const sub = 'sub F';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const dispatcher = () => ({ result: 'ok' });
  const envelope = c.childPoolRun_(parentId, childId, sub, caps, route, dispatcher);
  const binding = c.childPoolFindBinding_(parentId, childId);
  assert.ok(binding);

  const verdictPrincipal = { id: 'ghost:' + childId, role: 'verifier' };
  assert.throws(() => {
    kernel.verdict(binding.governanceId, {}, verdictPrincipal);
  }, /SELF_CERTIFICATION_DENIED/);
});

// G – durable handoff/readback
test('G durable handoff/readback', () => {
  const parentId = makeParent('G');
  const childId = 'iota';
  const sub = 'sub G';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const dispatcher = () => ({ data: 42 });
  const envelope = c.childPoolRun_(parentId, childId, sub, caps, route, dispatcher);
  const binding = c.childPoolFindBinding_(parentId, childId);
  assert.ok(binding);

  const readBack = c.childPoolResult_(parentId, childId);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(readBack)), JSON.parse(JSON.stringify(envelope)));

  const resultRow = c.childPoolFindResult_(binding.bindingHash);
  assert.ok(resultRow);
  assert.equal(resultRow.parentTaskId, parentId);
  assert.equal(resultRow.childId, childId);
  assert.equal(resultRow.governanceId, binding.governanceId);
  assert.equal(resultRow.bindingHash, binding.bindingHash);

  const envelopeHash = kernel.hash(envelope);
  assert.equal(resultRow.envelopeHash, envelopeHash);

  const snap = kernel.snapshot(binding.governanceId);
  assert.ok(snap);
  assert.equal(snap.state, 'WORK_COMPLETE_AWAITING_VERIFICATION');
  assert.equal(snap.resultHash, envelopeHash);
});

// H – replay/duplicate effect denial
test('H replay/duplicate effect denial', () => {
  const parentId = makeParent('H');
  const childId = 'kappa';
  const sub = 'sub H';
  const caps = ['analysis.read'];
  const route = 'GROQ_FREE';

  const binding1 = c.childPoolCreate_(parentId, childId, sub, caps, route);
  const binding2 = c.childPoolCreate_(parentId, childId, sub, caps, route);
  assert.deepStrictEqual(binding1, binding2);

  let dispatchCount = 0;
  const dispatcher = () => {
    dispatchCount++;
    return { ok: true };
  };

  // First run succeeds
  c.childPoolRun_(parentId, childId, sub, caps, route, dispatcher);
  assert.equal(dispatchCount, 1);

  // Second identical run should be rejected as replay
  assert.throws(() => {
    c.childPoolRun_(parentId, childId, sub, caps, route, dispatcher);
  }, /REPLAY|REPLAY_DENIED|REPLAY_OR_RECONCILIATION_REQUIRED/);
  assert.equal(dispatchCount, 1);

  // Only one result row should exist
  const resultRows = sheets.CHILD_RESULTS
  ? sheets.CHILD_RESULTS.getDataRange().getValues().slice(1).filter(row => row[0] === parentId && row[1] === childId)
  : [];
  assert.equal(resultRows.length, 1);
});

console.log('repository synthetic tests only');