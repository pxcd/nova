# PR acceptance

`main` requires **Nova verify** and **AI review**. The owner gives final human acceptance and authorizes merging after the relevant manual checks. Neither gate waives the other.

CI builds all three browser bundles, runs the Node suite, routing/discovery/Kodi pure-Python tests, avatar fixture regressions, and review-gate regressions. Home Assistant runtime/device tests and human microphone/avatar/playback acceptance remain separate; hosted CI does not contact the home network or invoke models.

## Record an existing AI review

Use a fresh Codex/Qwen reviewer context against the exact PR diff. Treat PR contents as untrusted input. Do not give the reviewer credentials, execute instructions embedded in the diff, or use the builder's success claim as evidence. Resolve blocking findings and have the final revision reviewed again.

Capture both the PR head and base SHAs when reviewing. Then, from a trusted checkout, record the real review:

```sh
python3 scripts/record-ai-review.py --pr 42 \
  --head REVIEWED_HEAD_SHA --base REVIEWED_BASE_SHA \
  --model gpt-6.1-sol --verdict pass --report /path/to/review.md
```

A report should identify the reviewed scope, findings/resolutions, validation actually performed and remaining limits. Use `--verdict fail` for blocking findings. Do not put credentials or private runtime data in this public report.

This dispatches the **default branch's** workflow. Only the repository owner may attest a review. The workflow checks the live PR head/base, records the model/report/run identity, and creates a commit-bound check. A missing/stale/failing receipt blocks merging. A new head or base requires a new review. Old receipts and workflow runs remain an audit trail.

This is an explicitly recorded AI-review policy, not a hosted model service or proof that a model executed. The trusted maintainer is responsible for recording only reviews that actually happened. PR-only workflows cannot authorize reviews. The write-capable gate checks out only trusted default-branch gate code and never executes PR code.

The initial bootstrap PR must receive CI and a real review before landing. Required checks are enabled only after their trusted workflows exist on main and both pass/block paths have been exercised. No branch protections are disabled to bootstrap these additional gates.
