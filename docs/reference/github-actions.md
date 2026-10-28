# GitHub Actions Workflows

**Last Updated**: 2026-10-28

Which workflows run, when they run, and what they may publish.
The [workflow declarations](../../.github/workflows/) are authoritative.
All schedules and run dates are UTC. Every workflow supports manual dispatch.

## Trigger reference

| File | Display name | Automatic trigger | Purpose |
| --- | --- | --- | --- |
| `ci.yml` | `CI` | Pull request; push to `main` | Code and site checks |
| `digest.yml` | `Content refresh` | `20 2 * * *`, `20 6 * * *`, `20 10 * * *`, `20 14 * * *`, `20 18 * * *` | Digest and production state |
| `llm-council.yml` | `LLM-COUNCIL` | `0 22 * * *` | Model judges' verdicts |
| `pages.yml` | `Pages publication` | Passing `CI` run on a push to `main`; completed `Content refresh` run | Static site |
| `drift.yml` | `Drift review` | `0 8 * * 0` | Quality drift review |
| `idhazh-gardener.yml` | `Idhazh Gardener` | `40 0 * * *` | Retention and history maintenance |
| `backfill.yml` | `Vector backfill` | none | Repair closed days' vectors |
| `idhazh-pipeline-tests.yaml` | `Pipeline tests` | none | Check a model with real articles |
| `feed-ingest-plan-test.yml` | `Feed ingest plan test` | none | Run the real planner HTTP API and publish its completed planner and host metadata |
| `yen-ai-pipeline.yml` | `Yen-AI-Pipeline` | none | Run the independent summarizer API |
| `ai-pipeline-tests.yml` | `Yen-Summarizers` | none | Run independent TypeScript inference and its existing audit |

Use filenames for dispatch and API calls. `workflow_run.workflows` matches display
names instead: update its callers and the workflow tests when renaming a label.

Both independent inference workflows accept `models_file`. Blank follows
`config/idhazh.json`; a value selects that declaration through the shared
candidate-config action. Both launch through the shared model-server action
and obtain request settings and the committed destination through
`model_runtime.py describe-request`. They expose no independent model-name,
repository, quantization or sampling selection. See
[ci-model-runtime.md](ci-model-runtime.md) for the shared runtime contract.

## Drift review

The [drift review workflow](../../.github/workflows/drift.yml) runs
[`drift_report.py`](../../backend/utilities/drift_report.py) against the saved
evaluation records. The command loads and validates config files from the
committed `config/` directory by default. A direct invocation may pass
`--config <directory>` to select another config root; the same loader validates
it before the report runs. The workflow exposes no config-root input, so its
scheduled and manually dispatched runs keep the committed default.

## Content refresh

Plan once, then distribute that plan across workers. Derive worker counts and job
bounds from config before the work matrix starts. Workers must not plan separately:
they would read changing feeds and could skip or duplicate articles.

Assemble after worker failures if planning succeeded and the run was not cancelled.
Keep successful items and commit failure records; annotate a planned run that
publishes nothing. Overlapping runs use distinct writer identities and the
[commit protocol](../architecture/publishing/committing.md), not a shared queue.

## Manual feed planner

`feed-ingest-plan-test.yml` calls both real HTTP services on its own runner.
The host service uses committed telemetry, placement and task-selected copy
controls. It returns one completed raw host Parquet file, or an explicit
disabled result. The caller validates it and combines it with the current
planner metadata for the [bounded commit adapter](../architecture/publishing/committing.md#design-rationale).
Only the four planner ledgers maintain their existing raw-day indexes.
There is no host index, remote host service or direct collector call. The
workflow records a host fingerprint but does not profile live planner CPU or
RAM.

Three tasks close the collection: commit all verified ledgers and write the
report, upload one prepared run artifact, then check completion and clean up.
Publication may retain completed diagnostics after planner failure; it never
changes the failed result. The artifact contains selected full text for the
next summarizer, the report and delivery receipt, plus exact uncommitted
metadata only when Git delivery was not confirmed. Ledger rows remain
body-free and go to their normal Git locations, not to an archive in Git.
The Markdown summary includes the actual Git delivery result and host
fingerprint facts, with L3 cache and total RAM capacity displayed in MiB.
Failed finalization or upload leaves temporary output untouched. Independent
host-probe checks remain in CI and are not part of this manual workflow.
The [manual workflow guide](../how-to/run-feed-ingest-plan-test.md#saved-output-and-failures)
defines the artifact layout and cleanup conditions.
See [host metrics](host-metrics.md) for the fingerprint and its unavailable reasons.

## Pages publication

- Build committed data only. Do not run the producer or a model during publication.
- [`publish_decision.py`](../../backend/utilities/publish_decision.py) holds the
  rule, one case a trigger, and every publish builds main's tip:
  - A pull request's CI, a failed CI and a manual CI run never publish. A pull
    request publishes when it merges.
  - A push to `main` publishes after its CI passes, when the push changed a path
    the site build reads. The program lists the paths the build never reads;
    every other path counts, so a new build input publishes by default. The
    push's range comes from its check suite, so every commit of the push counts.
  - Content refresh publishes when it landed a change under `frontend/public/`,
    whatever the run's conclusion. Its producer validated the committed day; a
    sibling failure does not invalidate it.
  - A manual publish from `main` always publishes.
  - A diff the program cannot read publishes.
- A push whose CI passes while a newer push has changed site code publishes
  nothing; the newer push's own CI publishes both. Building the tip means a late
  verdict cannot take the site back to an older commit, and a day that landed
  while CI ran stays published.
- Cancel superseded builds, but let an active deployment finish. Deploy requires
  a successful build and its complete artifact. These are separate job groups.

## LLM council permissions

`llm-council.yml` declares permissions per job, not for the whole workflow.
`draw` reads repository contents. `judge` reads contents and Actions artifacts.
Only `save_council_results` writes contents; it also reads Actions artifacts.
All other scopes are disabled by each job's declared block. See the
[council's permission boundary](../architecture/publishing/llm-council.md#design-rationale-nobody-has-to-notice-a-dead-night)
for the reason and its check.

## Pipeline tests

Draw one replayable article plan for all enabled cases in `config/pipeline-tests.json`.
Run the real production stages with a separate model server per runner. Let sibling
runners finish after a failure. The report must fail for an enabled case with no
summary or with an item outside the plan. This tests execution, not model quality
or comparative speed across different runner machines.

Give each case its own trial root named `<case>` to prevent filename
collisions - ledgers land tier-first at `state/raw/pipeline-tests/<case>/` and
`state/compact/pipeline-tests/<case>/`, traces at
`state/raw/traces/pipeline-tests/<case>/`. The case slug is separate from the shared
`run.trial_state_dirname` root. Only the commit job has write permission; validate
downloaded rows and config-derived paths before staging them. Gather only the plan's
named UTC day from each declared ledger, not a trial root's accumulated history.
Every runner names the checked-out commit in its ledger identity, so the commit
job rejects a result made from a different code version.
Never write reader-facing payloads.

## Vector backfill

Enter `days` as a whitespace-separated list of UTC dates in `YYYY-MM-DD` form.
The workflow passes each date as a separate `--day`; no days means no work, and
the job does not discover historical days. Dispatch without `commit` first.
Repair only closed UTC days, and re-encode a wrong day in full so old and new
vector arithmetic cannot mix. Validate payloads and build before committing.
The weight check follows the commit: excess weight must not discard a valid
repair. See the [publication checks](../architecture/publishing/what-stops-a-broken-day-being-published.md)
and [weight rules](site-weight.md).

## Design rationale

- Schedules are best-effort wakes, not proof a run happened or a lock between jobs.
  Separate digest cron lines identify the delayed slot. Inspect actual runs before
  changing cadence; do not infer completed work from cron expressions.
- Only the gardener's `history` job may force-push, under
  [CLAUDE.md section 8](../../CLAUDE.md). It checks whether a rewrite is due, and
  pushes with a lease on the tip it read, so git refuses the push if another run
  pushed meanwhile; it then squashes again on the new tip, up to `push_attempts`
  pushes in all. A quiet cron window cannot replace that lease.
- Share blocks that must agree, but keep different article-selection rules separate.
  Use approved external action versions; local actions use the checked-out commit.

## See also

- [ci-dispatch-inputs.md](ci-dispatch-inputs.md) - accepted inputs and validation.
- [ci-model-runtime.md](ci-model-runtime.md) - runtime pins, downloads and model checks.
- [ci-environment.md](ci-environment.md) - repository settings and platform limits.
- [../architecture/publishing/idhazh-gardener.md](../architecture/publishing/idhazh-gardener.md) - maintenance tasks and history rewrites.
- [../architecture/publishing/llm-council.md](../architecture/publishing/llm-council.md) - the nightly model judges.
- [../how-to/analyze-a-pipeline-artifact.md](../how-to/analyze-a-pipeline-artifact.md) - inspect a run's artifacts.
- [../how-to/run-the-pipeline.md](../how-to/run-the-pipeline.md) - production stages and where they run.
