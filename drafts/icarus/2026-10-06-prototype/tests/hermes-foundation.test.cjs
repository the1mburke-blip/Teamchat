const fs = require('fs');
const path = require('path');

function assert(condition, message) {
  if (!condition) {
    console.error('FAIL:', message);
    process.exit(1);
  }
}

// Resolve file locations relative to this test file
const gsPath = path.join(__dirname, '..', 'server-overlay', 'HermesExecutorAdapter.gs');
const kotlinPath = path.join(__dirname, '..', 'android', 'app', 'src', 'main', 'java', 'com', 'icarus', 'shell', 'HermesExecutorContract.kt');
const mdPath = path.join(__dirname, '..', 'HERMES_MOBILE_FOUNDATION_V01.md');

const gsContent = fs.readFileSync(gsPath, 'utf8');
const kotlinContent = fs.readFileSync(kotlinPath, 'utf8');
const mdContent = fs.readFileSync(mdPath, 'utf8');

// 1. Inertness checks on .gs
assert(!/PASS/.test(gsContent), '.gs file must not contain the token PASS');
assert(!/credential/i.test(gsContent), '.gs file must not contain credential strings');
assert(!/grant/.test(gsContent), '.gs file must not contain grant strings');
assert(/var HermesExecutorAdapter/.test(gsContent), '.gs file should define HermesExecutorAdapter');

// 2. Kotlin contract checks
assert(!/PASS/.test(kotlinContent), 'Kotlin file must not contain the token PASS');
assert(/interface Executor/.test(kotlinContent), 'Kotlin file should declare Executor interface');

// 3. Documentation checks
assert(/Integration Sequence/.test(mdContent), 'Markdown must contain "Integration Sequence" section');

console.log('All Hermes foundation checks passed.');
process.exit(0);
