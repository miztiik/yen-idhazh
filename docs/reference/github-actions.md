# GitHub Actions Workflows

**Last Updated**: 2026-09-30

Which workflows run, when they run, and what they may publish.
The [workflow declarations](../../.github/workflows/) are authoritative.
All schedules and run dates are UTC. Every workflow supports manual dispatch.

## Trigger reference

| File | Display name | Automatic trigger | Purpose |
| --- | --- | --- | --- |
| `ci.yml` | `CI` | Pull request; push to `main` | Code and site checks |
| `digest.yml` | `Content refresh` | `20 2 * * *`, `20 6 * * *`, `20 10 * * *`, `20 14 * * *`, `20 18 * * *` | Digest and production state |
| `llm-council.yml` | `LLM-COUNCIL` | `0 22 * * *` | Model judges' verdicts |
| `pages.yml` | `Pages publication` | Completed `CI` or `Content refresh` run | Static site |
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
- After successful CI, publish its verified commit only if `frontend/`,
  `config/idhazh.json` or `state/` changed. Failed CI does not publish.
- After Content refresh completes, publish the branch tip regardless of the run's
  overall conclusion. Its producer validated the committed day; a sibling failure
  does not invalidate it. The run's starting commit does not contain its new day.
- Manual publication also uses `main`.
- Cancel superseded builds, but let an active deployment finish. Deploy requires
  a successful build and its complete artifact. These are separate job groups.

CI-triggered publication follows verdict arrival, not commit order. An older
commit whose CI finishes last can still publish last.

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

Give each case its own trial state root to prevent filename collisions. Only the
commit job has write permission; validate downloaded rows and config-derived paths
before staging them. Gather only the plan's named UTC day from each declared ledger,
not a trial root's accumulated history. Never write reader-facing payloads. Use
[model evaluation](../how-to/evaluate-new-summarizer-model.md) for adoption decisions.

## Vector backfill

Supply the explicit `days` list and dispatch without `commit` first.
Repair only those closed UTC days, and re-encode a wrong
day in full so old and new vector arithmetic cannot mix. Validate payloads and build
before committing. The weight check follows the commit: excess weight must not
discard a valid repair. See the [publication checks](../architecture/publishing/what-stops-a-broken-day-being-published.md)
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
