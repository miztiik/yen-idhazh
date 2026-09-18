# What CI depends on outside its own files

**Last Updated**: 2026-09-18

The settings this repository has to carry and the platform behaviour nobody here
controls. Both decide how a workflow behaves, and neither is visible in a
workflow file - which is why a change that reads correctly in YAML can still
fail. The workflow files themselves are in
[github-actions.md](github-actions.md).

## Repository settings these workflows depend on

Read from the repository API on 2026-08-25.

| Setting | Value | Why |
| --- | --- | --- |
| `allow_squash_merge` | true | The default. One entry on `main` per PR. |
| `allow_merge_commit` | true | For a PR carrying several independent intents, so each stays revertible. |
| `allow_rebase_merge` | true | Same reason. History looks squash-only, but rebase is available. |
| `allow_update_branch` | true | A PR can be brought up to date from `main` without a local push. |
| `delete_branch_on_merge` | true | The remote branch goes away on merge. |
| `allow_auto_merge` | true | Turned on 2026-08-31. See below. |
| `squash_merge_commit_title` | `PR_TITLE` | The subject is the PR title. GitHub appends the PR number. |
| `squash_merge_commit_message` | `PR_BODY` | The body is the PR body. Branch commit bodies are never concatenated. See below. |
| `merge_commit_title` | `MERGE_MESSAGE` | The merge path, when a PR carries several intents. |
| `merge_commit_message` | `PR_TITLE` | Neither merge-commit setting reads a branch commit body, so that path was never affected. |

**`main` is not a protected branch, and protecting it would break
publication.** `digest.yml` and `validate.yml` push their state commits straight
to `main` - the eval ledger, the seen-URL store, feed health, the digest
payload. A branch-protection rule makes those pushes fail, and a scheduled run
that cannot commit has done its work for nothing. Protecting `main` is possible,
but only after the direct pushes in those two workflows are redesigned or
explicitly exempted.

**`allow_auto_merge` was turned on on 2026-08-31, and on its own it buys
nothing. Measured, not assumed.** The setting was off on the argument that
GitHub's auto-merge needs branch protection, and that argument is right.
`gh pr merge 303 --squash --delete-branch --auto` was run against a pull request
whose four checks were still in flight: it **exited 0 and queued nothing**.
`autoMergeRequest` read `null` and `mergeStateStatus` read `UNSTABLE`, with
`rulesets` empty and `branches/main/protection` answering 404. A zero exit code
is not evidence here - read `autoMergeRequest` through the GraphQL API instead.

The reason is that auto-merge queues a merge behind something that BLOCKS it.
With no required status check nothing blocks, so there is nothing to queue
behind, and GitHub declines rather than waiting for checks it was never told to
care about.

**What would make it work, and what that costs.** A repository ruleset on `main`
requiring the `gates` and `site` checks, with `github-actions[bot]` on its
bypass list. The bypass is load-bearing: `digest.yml` and `validate.yml` push
state commits straight to `main` with the job's own token - the eval ledger, the
seen-URL store, feed health, the digest payload - and a ruleset that forgets it
stops the digest publishing that night. The setting stays on because it is free
and is the half that cannot break anything; the ruleset is written here as the
next step rather than taken quietly.

**A squash commit takes its message from the pull request, not from the branch
commits.** `squash_merge_commit_message` was `COMMIT_MESSAGES` until 2026-08-25.
That value concatenates every branch commit body into the landed message, so a
`Co-authored-by` attribution trailer written on a branch commit reaches `main`
by itself. `CLAUDE.md` section 8 forbids that trailer, and PR #71 stayed clean
only because the message was passed by hand at merge time. `PR_BODY` removes the
path instead of relying on the person merging to notice.

The cost is that the pull request body is now the commit body. Write it as a
commit message - plain prose, ASCII, no heading markup - because whatever it
contains lands on `main`. Wrap it at 72 columns. GitHub re-wraps a wider body
and leaves an orphan word on its own line: PR #72 was written at 80 columns and
landed with a longest line of 72, measured 2026-08-25. `main` is unprotected, so
no check can block a bad message; this setting is what makes the good outcome
the default one.

## Platform limits that shape the workflows

The ceilings themselves are stated once, in `CLAUDE.md` Guardrail #2. What follows is
the behaviour behind them, which is what actually decides a workflow's shape.
Verified 2026-08-20.

- **Actions minutes and artifact storage are free and unmetered**, because this
 repository is public. The widely quoted 2,000 minutes and 500 MB are GitHub
 Free *account* figures - the 500 MB shared with Packages - and both meter
 private repositories only. Wall-clock is the constraint, not a monthly
 balance, and no artifact total here is charged for. Artifacts expire on their
 retention window and never under storage pressure, so the only reason to keep
 the count down is that a person reading a run has to find the one they want.
- **A cache entry unread for 7 days is deleted**, and a restore is paid once per
 *job* rather than once per run. That is why `digest.yml` gives a worker a
 shard of several items instead of fanning out one job per item: the weights
 restore is the largest fixed cost, and every extra job pays it again. It is
 also why a workflow that runs a few times a month earns no cache of its own -
 the entry is cold on every dispatch - unless the reader is a sibling job in
 the same run, which is what `validate.yml` `qualify` and `measure.yml`'s bench
 both rely on.
- **The 10 GB cache limit is ours; the eviction is GitHub's.** 10 GB is the
 default, a repository administrator can raise it - to 10 TB on a user-owned
 repository - and storage above 10 GB is billed only where it has been raised.
 At the default nothing can be billed and no save can fail: past the limit
 GitHub saves the new entry and deletes others by oldest last-access until the
 total is under, so a full cache costs a re-download. On 2026-09-18 two entries
 totalling 9.97 GB, both read two days earlier, had gone while five older but
 smaller ones remained - size pressure rather than the 7-day rule, which is the
 evidence the limit here is the default.
- **A cache is scoped to a branch.** A run restores entries from its own branch,
 from the default branch, and - for a pull request - from the base branch. An
 entry written by a `pull_request` run lives on the merge ref, so only re-runs
 of that pull request restore it.
- **`GITHUB_TOKEN` allows 1,000 API requests per hour per repository**, shared
 across every job of every concurrently running workflow. A step that polls in
 a loop spends a budget the scheduled pipeline also needs.
- **The Pages deploy itself times out at 10 minutes**, separately from the job
 timeout, and separately from the 1 GB site cap.
- **A job stopped by `timeout-minutes` is *cancelled*, and a cancelled job skips
 every step that carries no condition.** `if: failure` does not run either -
 only `if: always` does. So an artifact upload written the ordinary way is
 silently dropped exactly when a long job most needed to hand over what it
  made. Observed 2026-08-25 on the since-retired `visuals` job in `digest.yml`, run
 `32804437110`: the step list records the render step as `cancelled`, the log
 upload (which has `always`) as `success`, and the decisions upload as
 **`skipped`**.
 88 planning decisions and 9 rendered charts existed on that runner and none of
 them left it. **Any upload step that carries a job's only copy of its output
 needs `if: always`.** The rule was written and three sibling steps in the same
 file never got it: on 2026-09-14, run `34852763827`, the `work` job's three
 uploads still carried no condition, three of four shards were cancelled at
 `run.shard_timeout_minutes`, and 33 items their ledger steps had already
 recorded as published never reached `assemble`. **Fixing one step in a file is
 not fixing the file.**
- **Every `digest.yml` artifact a re-render needs is gone within one day, so "re-render the day from its decisions" is not a repair option for any day older than 24 hours.** Read off `digest.yml` on 2026-09-15, it keeps seven: `plan` 1 day, `shard-visuals-<shard>` 1 - that one
 carries this run's rendered charts - `runtime-log-<shard>` 2, `items-<shard>`
 7, `review` 7, `evidence-<shard>` 14, and `captures-<shard>` 90. **The re-render window is set by the
 shortest of those and never by the longest**, which is the trap in reading the
 list: `assemble` downloads `plan`, `items-*` and `shard-visuals-*` and needs
 all three, so a week-old `items-*` repairs nothing once the other two have
 gone - and a 90-day `captures-*` repairs nothing at all, because it holds what the model was asked rather than what the day published. Nothing under `backend/var/` is committed either: `.gitignore` line 52
 is `backend/var/`, and `git ls-files backend/var` returns no files. **The
 committed record of a run is the digest under `frontend/public/digest/` plus
 the rows under `state/`, and never the intermediates.** Repairing an older day
 therefore means reading its articles again and paying the whole work stage
 again - there is no cheaper path, and a
 plan that assumes one is proposing something that cannot be done. Job *logs*
 are the exception: they outlive every artifact here, which is why a question
 about what a past run did is asked with `gh run view --job <id> --log`. **`captures-<shard>` is the one artifact that outlives the day it describes**, and it is the odd one on purpose: a regression is found by comparing today with a run from weeks ago, so a window shorter than the comparison is a window that closes exactly when it is wanted. It holds each call's rendered prompt and raw reply behind `logging.capture_prompts` and `logging.capture_replies`; with both off the directory is empty and the upload is a green no-op. It is never committed and is named in no `commit-and-push.sh` call, because a rendered prompt carries the article body inside it ([../../CLAUDE.md](../../CLAUDE.md) section 0a).

 **A capture is not read by hand.** One file is a single JSON object holding a 15,000-character prompt on one line. [../how-to/analyze-a-pipeline-artifact.md](../how-to/analyze-a-pipeline-artifact.md) is the procedure: what to download, what to run, and what the document it writes holds.
- **A re-run is per job, never per step, and it reuses the original commit.**
 `gh run rerun <id> --failed` and `gh run rerun --job <id>` start the failed job
 again from its first step; there is no way to resume at the step that failed.
 That is survivable here only because the expensive jobs are separate: a failed
 `assemble` re-runs alone - 82 s in run `33270983446` - while `plan` and the
 `work` shards keep their results and are not repeated. It works
 for one day, because `plan` and `shard-visuals-*`, two of the three artifacts
 `assemble` downloads, carry
 `retention-days: 1`. **The re-run uses the same `GITHUB_SHA` and the same
 workflow file as the original event**, so it cannot pick up a fix that landed
 afterwards, and a job that failed against a `main` which has since moved will
 re-measure the tree it started from rather than the one that is published now.
 A re-run that goes green for that reason has laundered the failure rather than
 answered it.

## See also

- [github-actions.md](github-actions.md) - which workflows exist, when each runs, and what each does.
- [../how-to/analyze-a-pipeline-artifact.md](../how-to/analyze-a-pipeline-artifact.md) - how to read the one artifact that outlives the day it describes.
- [../architecture/publishing/retention.md](../architecture/publishing/retention.md) - what the committed record keeps once the artifacts are gone.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2, which states the ceilings this page explains the behaviour behind.
