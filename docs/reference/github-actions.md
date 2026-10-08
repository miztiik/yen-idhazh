# GitHub Actions Workflows

**Last Updated**: 2026-10-04

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
| `validate.yml` | `Model validation` | none | Candidate quality verdict |
| `measure.yml` | `Measurements` | none | Runtime, corpus and budget measurements |
| `idhazh-gardener.yml` | `Idhazh Gardener` | `40 0 * * *` | Retention and history maintenance |
| `backfill.yml` | `Vector backfill` | none | Repair closed days' vectors |
| `idhazh-pipeline-tests.yaml` | `Pipeline tests` | none | Check a model with real articles |

Use filenames for dispatch and API calls. `workflow_run.workflows` matches display
names instead: update its callers and the workflow tests when renaming a label.

## Content refresh

Plan once, then distribute that plan across workers. Derive worker counts and job
bounds from config before the work matrix starts. Workers must not plan separately:
they would read changing feeds and could skip or duplicate articles.

Assemble after worker failures if planning succeeded and the run was not cancelled.
Keep successful items and commit failure records; annotate a planned run that
publishes nothing. Overlapping runs use distinct writer identities and the
[commit protocol](../architecture/publishing/committing.md), not a shared queue.

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

## Candidate runs

Select a candidate through `candidate_models_file`, not copied model fields.
Use the shared candidate-config and model-server actions where their contracts fit.
Every candidate stage must read its scratch config, including planning and verdict
writing, so it cannot alter production's seen records or published data.
Prompts are shipped code, never dispatch text, paths or overrides.

Validation writes verdicts under `state/pipeline-tests/`. Measurements commits
only the `runtime` job's host record there; other measurement outputs are artifacts.
Keep write permissions on the jobs that need them. Do not treat expiring artifacts
as durable records; their retention is declared by each upload step.

## Pipeline tests

Draw one replayable article plan for all enabled cases in `config/pipeline-tests.json`.
Run the real production stages with a separate model server per runner. Let sibling
runners finish after a failure. The report must fail for an enabled case with no
summary or with an item outside the plan. This tests execution, not model quality
or comparative speed across different runner machines.

Give each case its own state root at `state/pipeline-tests/<case>` to prevent
filename collisions. The case slug is separate from the shared
`run.trial_state_dirname` root. Only the commit job has write permission; validate
downloaded rows and config-derived paths before staging them. Gather only the plan's
named UTC day from each declared ledger, not a trial root's accumulated history.
Never write reader-facing payloads. Use
[model evaluation](../how-to/evaluate-new-summarizer-model.md) for adoption decisions.

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
- The gardener still wakes at 00:40 so that the force push lands in the quiet
  time, 01:23 to 07:23: the council's runs of 2026-09-19 to 28 had ended by
  01:23, and none of the digest runs of 2026-09-16 to 28 was created before 07:23.
  A scheduled wake is estimated to start 112 to 334 minutes late, the delays
  measured on the two nearest cron lines, and the three jobs' time limits add
  55 minutes, so the push lands between 02:32 and 07:09. The first scheduled
  wake, on 2026-09-30, started 315 minutes late, inside that estimate.
  `backend/tests/workflows/test_triggers.py` holds these readings and fails when
  a cron line they were read under changes.
- A skipped speed case must not skip the remaining measurement jobs. A failed one
  still blocks dependent runtime work. Label missing results; do not emit a complete
  model dossier from partial evidence. Skipping also moves the weight download cost.
- Share blocks that must agree, but keep different article-selection rules separate.
  Use approved external action versions; local actions use the checked-out commit.

## See also

- [ci-dispatch-inputs.md](ci-dispatch-inputs.md) - accepted inputs and validation.
- [ci-model-runtime.md](ci-model-runtime.md) - runtime pins, downloads and model checks.
- [ci-environment.md](ci-environment.md) - repository settings and platform limits.
- [../architecture/publishing/idhazh-gardener.md](../architecture/publishing/idhazh-gardener.md) - maintenance tasks and history rewrites.
- [../architecture/publishing/llm-council.md](../architecture/publishing/llm-council.md) - the nightly model judges.
- [../how-to/analyze-a-pipeline-artifact.md](../how-to/analyze-a-pipeline-artifact.md) - inspect a run's artifacts.
- [../how-to/run-the-pipeline.md](../how-to/run-the-pipeline.md) - run production stages locally.
