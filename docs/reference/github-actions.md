# GitHub Actions Workflows

**Last Updated**: 2026-08-25

The exact workflow display names, files, and trigger classes. All scheduled
times are UTC.

## Trigger reference

| File | Display name | Automatic trigger | Manual dispatch |
| --- | --- | --- | --- |
| `ci.yml` | `CI` | Pull request; push to `main` | yes |
| `digest.yml` | `Content refresh` | `20 2,6,10,14,18 * * *` | yes |
| `pages.yml` | `Pages publication` | Push to `main` when `frontend/**`, `config/idhazh.json`, or `state/**` changes; completed `Content refresh` run | yes |
| `drift.yml` | `Drift review` | Sunday at 08:00 (`0 8 * * 0`) | yes |
| `validate.yml` | `Model validation` | none | yes |
| `measure.yml` | `Measurements` | none | yes |

An ordinary pull request starts CI only. A merge or direct push to `main`
starts CI, and starts Pages publication only when its path filter matches.

```mermaid
flowchart LR
    PR["ordinary pull request"] --> CI["CI<br/>ci.yml"]
    PUSH["merge or push to main"] --> CI
    PUSH --> FILTER{"Pages path changed?"}
    FILTER -->|"yes"| PAGES["Pages publication<br/>pages.yml"]
    FILTER -->|"no"| NO_PAGES["no Pages run"]
    REFRESH_DONE["Content refresh completed"] --> PAGES
    PAGES --> STATIC["static GitHub Pages bundle"]
```

## Content refresh

The schedule and manual dispatch use the same job graph. The plan job creates
the work list. The work matrix creates one to four total worker jobs. Scheduled
runs use four. Manual dispatch offers only 1, 2, 3, or 4 and defaults to four.
The plan job rejects any other value before it creates the matrix. The work
strategy also sets `max-parallel: 4`; that limits concurrency but is not the
total-job cap.

Each worker receives its round-robin share of the whole plan. The workflow does
not enforce `config.run.shard_size` or `shard_timeout_minutes`; the work job uses
a 330-minute workflow timeout. A model-fit claim must use the measured worker
population or first wire those config values.

Route uses the worker outputs. Assemble runs even after a worker or route
failure, then commits the digest and state.

```mermaid
flowchart LR
    SCHEDULE["schedule<br/>02:20, 06:20, 10:20, 14:20, 18:20 UTC"] --> PLAN["plan"]
    MANUAL["manual dispatch"] --> PLAN
    PLAN --> WORK["work shards<br/>at most four total jobs"]
    WORK --> ROUTE["route"]
    ROUTE --> ASSEMBLE["assemble"]
    ASSEMBLE --> COMMIT["commit digest and state"]
    COMMIT --> COMPLETE["Content refresh completed"]
    COMPLETE --> PAGES["Pages publication"]
```

The plan job also commits first-sighting and feed-health state before it starts
the workers. This keeps observations from a failed refresh.

### Both commit steps push through a rebase, and neither rebases on a dirty tree

The plan job and the assemble job each commit, then push in a loop of three
attempts. A push that loses a race rebases and tries again.

A rebase refuses to start while a tracked file is modified. Run `32671663130`
died that way: one file was CRLF against a `text eol=lf` attribute, so every
Linux checkout saw it modified before any step ran, and the retry loop threw away
a day that plan, four shards and assemble had all finished.

The work is already in a commit when the loop begins, so anything left in the
working tree is runner noise. Each loop now prints what is dirty and discards it
before the rebase. Untracked files are left alone: they cannot block a rebase,
and a later step may still want them. `--autostash` was removed - it stashes the
noise and then fails the step when the stash will not reapply, which is the
failure it looks like it prevents.

A workflow contract test pins this shape. CI never runs `digest.yml`, so a change
to either loop needs a dispatched run to verify.

Model validation and measurements never run on a pull request, push, or
schedule. A person dispatches them. Drift review is a separate weekly or manual
workflow; it does not run inside Content refresh.

```mermaid
flowchart LR
    PERSON["manual dispatch"] --> VALIDATE["Model validation"]
    PERSON --> MEASURE["Measurements"]
    PERSON --> DRIFT["Drift review"]
    WEEKLY["Sunday 08:00 UTC"] --> DRIFT
```

Each Measurements dispatch selects exactly one target:

| Target | What runs | Inputs used by that target |
| --- | --- | --- |
| `llm` | GGUF download timing and `llama-bench` throughput | `models`, `threads` |
| `image` | CPU image-model candidates | none |
| `corpus` | Live article-length sampling | `corpus_links` |
| `runtime` | Fixed-shard llama-server candidate sweep | `runtime_candidate`; `runtime_threads` for `threads`; `runtime_threads_batch` for `threads_batch` |

The form keeps all target-specific inputs visible. A job reads only the inputs
for its selected target. The default target is `llm`; the default runtime
candidate is `baseline`.

`Model validation` currently hardcodes Qwen3-8B as incumbent, downloads and
caches incumbent plus challenger together, and refetches each planned URL for
each model. It is an exploratory dispatch, not a controlled adoption gate.
[Evaluate and Adopt a New Summarizer Model](../how-to/evaluate-new-summarizer-model.md)
owns the repair and acceptance requirements.

Pages publication builds only committed data and uploads a static bundle. It
does not run the producer or a model, and the published site has no runtime
backend.

## Display names and files

A workflow display name is the label shown in the Actions UI. Its filename is
the stable automation interface for repository paths, API calls, and CLI
dispatch. Keep the six filenames stable when a UI label changes.

GitHub's `workflow_run.workflows` selector is the exception: it matches a
display name. `pages.yml` therefore names `Content refresh` in that selector.
The workflow contract test pins both sides so a label change cannot silently
stop publication.

## Action versions

Every workflow calls the same nine actions, each pinned to one approved major.
GitHub retired the Node 20 runtime on its runners, so an action major that still
declares `using: node20` is force-run on Node 24 today and stops running later.

| Action | Major | Runtime |
| --- | --- | --- |
| `actions/cache` | `v6` | `node24` |
| `actions/checkout` | `v6` | `node24` |
| `actions/configure-pages` | `v6` | `node24` |
| `actions/deploy-pages` | `v5` | `node24` |
| `actions/download-artifact` | `v8` | `node24` |
| `actions/setup-node` | `v7` | `node24` |
| `actions/setup-python` | `v7` | `node24` |
| `actions/upload-artifact` | `v7` | `node24` |
| `actions/upload-pages-artifact` | `v5` | composite, pins a `node24` `upload-artifact` |

Each runtime above was read from that major's own `action.yml` on 2026-08-24.
The workflow contract test asserts the table: a new action, or a call site left
on an old major, fails CI.

`setup-node` still selects Node 22 for the frontend commands. That is the
application runtime and is unrelated to the runtime an action itself declares.

## Repository settings these workflows depend on

Read from the repository API on 2026-08-25.

| Setting | Value | Why |
| --- | --- | --- |
| `allow_squash_merge` | true | The default. One entry on `main` per PR. |
| `allow_merge_commit` | true | For a PR carrying several independent intents, so each stays revertible. |
| `allow_rebase_merge` | true | Same reason. History looks squash-only, but rebase is available. |
| `allow_update_branch` | true | A PR can be brought up to date from `main` without a local push. |
| `delete_branch_on_merge` | true | The remote branch goes away on merge. |
| `allow_auto_merge` | **false** | Deliberate. See below. |
| `squash_merge_commit_title` | `PR_TITLE` | The subject is the PR title. GitHub appends the PR number. |
| `squash_merge_commit_message` | `PR_BODY` | The body is the PR body. Branch commit bodies are never concatenated. See below. |
| `merge_commit_title` | `MERGE_MESSAGE` | The merge path, when a PR carries several intents. |
| `merge_commit_message` | `PR_TITLE` | Neither merge-commit setting reads a branch commit body, so that path was never affected. |

**`main` is not a protected branch, and protecting it would break
publication.** `digest.yml` and `validate.yml` push their state commits straight
to `main` - the eval ledger, the seen-URL store, feed health, the digest
payload. A branch-protection rule makes those pushes fail, and a scheduled run
that cannot commit has done its work for nothing. GitHub's built-in auto-merge
requires branch protection, which is why `allow_auto_merge` is off rather than
merely unused. Protecting `main` is possible, but only after the direct pushes
in those two workflows are redesigned or explicitly exempted.

**A squash commit takes its message from the pull request, not from the branch
commits.** `squash_merge_commit_message` was `COMMIT_MESSAGES` until 2026-08-25.
That value concatenates every branch commit body into the landed message, so a
`Co-authored-by` attribution trailer written on a branch commit reaches `main`
by itself. `CLAUDE.md` section 8 forbids that trailer, and PR #71 stayed clean
only because the message was passed by hand at merge time. `PR_BODY` removes the
path instead of relying on the person merging to notice.

The cost is that the pull request body is now the commit body. Write it as a
commit message - plain prose, ASCII, no heading markup - because whatever it
contains lands on `main` verbatim. `main` is unprotected, so no check can block
a bad message; this setting is what makes the good outcome the default one.

## Platform limits that shape the workflows

The ceilings themselves are stated once, in `CLAUDE.md` Rule #2. What follows is
the behaviour behind them, which is what actually decides a workflow's shape.
Verified 2026-08-20.

- **Actions minutes are free and unmetered**, because this repository is public.
  The widely quoted 2,000 minutes per month is a private-repository figure and
  does not apply. Wall-clock is the constraint, not a monthly balance.
- **A cache entry unread for 7 days is deleted**, and a restore is paid once per
  *job* rather than once per run. That is why `digest.yml` gives a worker a
  shard of several items instead of fanning out one job per item: the weights
  restore is the largest fixed cost, and every extra job pays it again.
- **`GITHUB_TOKEN` allows 1,000 API requests per hour per repository**, shared
  across every job of every concurrently running workflow. A step that polls in
  a loop spends a budget the scheduled pipeline also needs.
- **The Pages deploy itself times out at 10 minutes**, separately from the job
  timeout, and separately from the 1 GB site cap.
- **A job stopped by `timeout-minutes` is *cancelled*, and a cancelled job skips
  every step that carries no condition.** `if: failure()` does not run either -
  only `if: always()` does. So an artifact upload written the ordinary way is
  silently dropped exactly when a long job most needed to hand over what it
  made. Observed 2026-08-25 on `digest.yml`'s `route` job, run `32804437110`:
  the step list records `Route and render` as `cancelled`, `Upload router log`
  (which has `always()`) as `success`, and the `routes` upload as **`skipped`**.
  88 routing decisions and 9 rendered charts existed on that runner and none of
  them left it. **Any upload step that carries a job's only copy of its output
  needs `if: always()`.**

## See also

- [../architecture/overview.md](../architecture/overview.md) - how CI, committed payloads, and the static site fit together.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - what each pipeline stage owns.
- [../how-to/run-the-pipeline.md](../how-to/run-the-pipeline.md) - how to run the same stages locally.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - what five runs add to one day.
- [../../CLAUDE.md](../../CLAUDE.md) - Rules #1, #2, #9, and #10.
