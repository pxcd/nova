const test = require('node:test');
const assert = require('node:assert/strict');
const { handle, validate, parseReceipt, receiptID } = require('./ai-review.cjs');
const HEAD = 'a'.repeat(40), BASE = 'b'.repeat(40), OLD = 'c'.repeat(40);
const report = 'Reviewed the exact final diff and regression checks. No blocking findings remain. Limits: no live device testing.';
function setup() {
  const state = { checks: [], receipts: [], failures: [], run: { event: 'workflow_dispatch', path: '.github/workflows/ai-review.yml', head_branch: 'main', status: 'completed', conclusion: 'success', actor: { login: 'owner' } } };
  const pr = { number: 7, state: 'open', head: { sha: HEAD }, base: { sha: BASE, ref: 'main' } };
  const github = { rest: { pulls: { get: async () => ({ data: pr }), list: () => {} }, checks: { create: async value => { state.checks.push(value); }, listForRef: () => {} }, actions: { getWorkflowRun: async () => ({ data: state.run }) } },
    paginate: async fn => fn === github.rest.pulls.list ? [pr] : state.receipts };
  const context = { repo: { owner: 'owner', repo: 'sample' }, actor: 'owner', ref: 'refs/heads/main', runId: 42, serverUrl: 'https://github.com', eventName: 'pull_request_target', payload: { repository: { default_branch: 'main' }, pull_request: { number: 7 } } };
  const core = { setFailed: message => state.failures.push(message) };
  return { state, pr, github, context, core };
}
const input = extra => ({ pr: '7', head: HEAD, base: BASE, model: 'gpt-6.1-sol', verdict: 'pass', report, ...extra });
const receipt = extra => ({ id: 5, external_id: receiptID(7, HEAD, BASE, 10), app: { slug: 'github-actions' }, conclusion: 'success', html_url: 'https://github.com/owner/sample/checks/5', ...extra });
test('missing receipt blocks merging and a matching trusted receipt passes', async () => {
  const x = setup(); await handle(x); assert.equal(x.state.checks.at(-1).conclusion, 'failure');
  x.state.receipts = [receipt()]; await handle(x); assert.equal(x.state.checks.at(-1).conclusion, 'success');
});
test('stale head/base, foreign PR, fabricated app and malformed receipt cannot satisfy the gate', async () => {
  for (const bad of [receipt({ external_id: receiptID(7, OLD, BASE, 10) }), receipt({ external_id: receiptID(7, HEAD, OLD, 10) }), receipt({ external_id: receiptID(8, HEAD, BASE, 10) }), receipt({ app: { slug: 'other' } }), receipt({ external_id: 'fabricated' })]) {
    const x = setup(); x.state.receipts = [bad]; await handle(x); assert.equal(x.state.checks.at(-1).conclusion, 'failure');
  }
});
test('receipts must originate from completed owner-dispatched default-branch gate runs', async () => {
  for (const bad of [{ event: 'pull_request' }, { path: '.github/workflows/ci.yml' }, { head_branch: 'feature' }, { actor: { login: 'contributor' } }, { status: 'in_progress' }, { conclusion: 'cancelled' }]) {
    const x = setup(); Object.assign(x.state.run, bad); x.state.receipts = [receipt()]; await handle(x); assert.equal(x.state.checks.at(-1).conclusion, 'failure');
  }
});
test('newest explicit failure overrides an older passing review', async () => {
  const x = setup(); x.state.receipts = [receipt(), receipt({ id: 6, conclusion: 'failure' })]; await handle(x);
  assert.equal(x.state.checks.at(-1).conclusion, 'failure');
});
test('owner can record only an open PR with exact reviewed commits from trusted main', async () => {
  const x = setup(); x.context.eventName = 'workflow_dispatch'; x.context.payload.inputs = input(); await handle(x);
  assert.equal(x.state.checks[0].conclusion, 'success'); assert.equal(parseReceipt(x.state.checks[0].external_id).head, HEAD);
  assert.match(x.state.checks[0].output.summary, /explicit maintainer attestation/);
  for (const patch of [{ head: OLD }, { base: OLD }]) {
    const y = setup(); y.context.eventName = 'workflow_dispatch'; y.context.payload.inputs = input(patch); await assert.rejects(handle(y), /changed since review/); assert.equal(y.state.checks.length, 0);
  }
});
test('contributor, feature-branch dispatch, closed PR and wrong target are rejected', async () => {
  for (const kind of ['actor', 'ref', 'state', 'target']) {
    const x = setup(); x.context.eventName = 'workflow_dispatch'; x.context.payload.inputs = input();
    if (kind === 'actor') x.context.actor = 'attacker';
    if (kind === 'ref') x.context.ref = 'refs/heads/feature';
    if (kind === 'state') x.pr.state = 'closed';
    if (kind === 'target') x.pr.base.ref = 'other';
    await assert.rejects(handle(x)); assert.equal(x.state.checks.length, 0);
  }
});
test('model and report validation fail closed; report contents remain inert data', async () => {
  for (const patch of [{ pr: '01' }, { pr: '0' }, { head: 'short' }, { verdict: 'approved' }, { model: 'bad\nidentity' }, { report: 'short' }, { report: 'x'.repeat(20001) }]) assert.throws(() => validate(input(patch)));
  const x = setup(); x.context.eventName = 'workflow_dispatch'; x.context.payload.inputs = input({ report: report + '\n${{ secrets.NEVER_READ }}; process.exit(99)' }); await handle(x);
  assert.match(x.state.checks[0].output.summary, /process.exit\(99\)/); assert.equal(x.state.checks[0].conclusion, 'success');
});
test('explicit failed review remains a blocking check', async () => {
  const x = setup(); x.context.eventName = 'workflow_dispatch'; x.context.payload.inputs = input({ verdict: 'fail' }); await handle(x);
  assert.equal(x.state.checks[0].conclusion, 'failure'); assert.equal(x.state.failures.length, 1);
});
test('base-branch pushes revalidate every open PR', async () => {
  const x = setup(); x.context.eventName = 'push'; await handle(x); assert.equal(x.state.checks.length, 1); assert.equal(x.state.checks[0].conclusion, 'failure');
});
