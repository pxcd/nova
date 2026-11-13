'use strict';
const CHECK = 'AI review';
const PREFIX = 'ai-review-v1:';
const SHA = /^[a-f0-9]{40}$/;
function receiptID(pr, head, base, run) { return `${PREFIX}${pr}:${head}:${base}:${run}`; }
function parseReceipt(value) {
  const m = /^ai-review-v1:([1-9][0-9]*):([a-f0-9]{40}):([a-f0-9]{40}):([1-9][0-9]*)$/.exec(value || '');
  return m && { pr: Number(m[1]), head: m[2], base: m[3], run: Number(m[4]) };
}
function validate(input) {
  if (!/^[1-9][0-9]*$/.test(input.pr || '') || !Number.isSafeInteger(Number(input.pr))) throw new Error('Invalid PR number');
  if (!SHA.test(input.head || '') || !SHA.test(input.base || '')) throw new Error('Full reviewed head and base SHA are required');
  if (!['pass', 'fail'].includes(input.verdict)) throw new Error('Verdict must be pass or fail');
  if (typeof input.model !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:/@ +#-]{0,159}$/.test(input.model)) throw new Error('Reviewer model identity is required');
  if (typeof input.report !== 'string' || input.report.trim().length < 40 || Buffer.byteLength(input.report) > 20000) throw new Error('Supply a substantive review report (40 characters to 20KB)');
  return { ...input, pr: Number(input.pr), report: input.report.trim() };
}
async function handle({ github, context, core }) {
  const { owner, repo } = context.repo;
  if (context.eventName === 'push') {
    const prs = await github.paginate(github.rest.pulls.list, { owner, repo, state: 'open', base: context.payload.repository.default_branch, per_page: 100 });
    for (const pr of prs) await handle({ github, core, context: { ...context, eventName: 'pull_request_target', payload: { ...context.payload, pull_request: { number: pr.number } } } });
    return;
  }
  const record = context.eventName === 'workflow_dispatch';
  let input;
  if (record) {
    const branch = context.payload.repository.default_branch;
    if (context.actor.toLowerCase() !== owner.toLowerCase()) throw new Error('Only the repository owner can record an AI review');
    if (context.ref !== `refs/heads/${branch}`) throw new Error('Record reviews using the trusted default-branch workflow');
    input = validate(context.payload.inputs || {});
  }
  const number = record ? input.pr : context.payload.pull_request?.number;
  if (!Number.isSafeInteger(number)) throw new Error('PR number is missing');
  const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number: number });
  if (pr.base.ref !== context.payload.repository.default_branch || pr.state !== 'open') throw new Error('Review gate requires an open PR targeting the default branch');
  const head = pr.head.sha;
  const base = pr.base.sha;
  if (!SHA.test(head) || !SHA.test(base)) throw new Error('Invalid PR commits');
  const runURL = `${context.serverUrl}/${owner}/${repo}/actions/runs/${context.runId}`;
  if (record) {
    if (input.head !== head || input.base !== base) throw new Error('PR head or base changed since review; perform a new review');
    await github.rest.checks.create({ owner, repo, name: CHECK, head_sha: head,
      status: 'completed', conclusion: input.verdict === 'pass' ? 'success' : 'failure',
      external_id: receiptID(number, head, base, context.runId), details_url: runURL,
      output: { title: `Recorded ${input.verdict.toUpperCase()} — ${input.model}`, summary:
        `Reviewer model: ${input.model}\n\nRecorded by: ${context.actor}\n\nPR: #${number}\n\nReviewed head: ${head}\n\nReviewed base: ${base}\n\n${input.report}\n\nThis is an explicit maintainer attestation of an existing AI review, not a model run performed by this workflow.` } });
    if (input.verdict === 'fail') core.setFailed('AI review recorded blocking findings');
    return;
  }
  const checks = await github.paginate(github.rest.checks.listForRef, { owner, repo, ref: head, check_name: CHECK, per_page: 100, filter: 'all' });
  const candidates = [];
  for (const check of checks) {
    const receipt = parseReceipt(check.external_id);
    if (!receipt || receipt.pr !== number || receipt.head !== head || receipt.base !== base || check.app?.slug !== 'github-actions') continue;
    if (!['success', 'failure'].includes(check.conclusion)) continue;
    // Verify that the receipt came from an owner-dispatched trusted workflow, not a PR workflow with a matching check name.
    const { data: run } = await github.rest.actions.getWorkflowRun({ owner, repo, run_id: receipt.run });
    if (run.status !== 'completed' || (check.conclusion === 'success' && run.conclusion !== 'success') ||
        run.event !== 'workflow_dispatch' || run.path !== '.github/workflows/ai-review.yml' ||
        run.head_branch !== context.payload.repository.default_branch ||
        run.actor?.login?.toLowerCase() !== owner.toLowerCase()) continue;
    candidates.push(check);
  }
  candidates.sort((a, b) => b.id - a.id);
  const receipt = candidates[0];
  const passed = receipt?.conclusion === 'success';
  await github.rest.checks.create({ owner, repo, name: CHECK, head_sha: head,
    status: 'completed', conclusion: passed ? 'success' : 'failure',
    external_id: `ai-review-gate:${number}`, details_url: runURL,
    output: { title: passed ? 'Matching AI review recorded' : 'AI review required for this revision', summary: passed
      ? `A recorded review matches PR #${number}, head ${head} and base ${base}.\n\nReceipt: ${receipt.html_url}`
      : `No passing recorded review matches PR #${number}, head ${head} and base ${base}.\n\nHave Codex or Qwen review this revision, resolve blocking findings, then use scripts/record-ai-review.py to record the result. New commits require a new review.` } });
  if (!passed) core.setFailed('A passing AI review for the exact head/base commits is required');
}
module.exports = { handle, validate, parseReceipt, receiptID };
