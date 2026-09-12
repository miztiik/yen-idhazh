# Agent Notes - Git and GitHub

**Last Updated**: 2026-09-12

Traps in `git`, worktrees, merges and the `gh` CLI. Index and scope:
[../agent-notes.md](../agent-notes.md).

## Worktrees

**More than one agent shares this checkout, so a listing from earlier in the session is fiction.** Worktrees appear and disappear mid-task. Read `git worktree list` immediately before you stage, and never `git add.` in a checkout you did not create - it sweeps another branch's work into your commit.

**`git checkout -b` in the shared checkout branches off whatever `HEAD` happens to be.** A parallel agent moves `HEAD` between your commands; on 2026-08-25 a branch was cut while `HEAD` sat on a sibling's work and carried its unmerged commit as the parent. Always name the start-point and take your own worktree:

```powershell
git worktree add <repo>.worktrees/<name> -b <branch> origin/main
```

**Every worktree goes in that one container, never beside the checkout.** They accumulate - 38 on one box by 2026-09-02 - and scattered siblings bury the repository among directories that are copies of it. It may not go inside the checkout either: `ruff check.` and `mypy` walk gitignored paths, `git grep` and the site-weight gate glob the tree, and each worktree carries its own `frontend/node_modules`. Name it for the row it serves, `<plan letter><row number>`.

**Branch before the first edit, not after the work is done.** A 35-file change built uncommitted in the shared checkout on 2026-08-28 survived only by luck: the owner committed underneath it, `origin/main` gained 22 commits, and an earlier `git add` had been undone by another process. `git switch -c <branch>` carries an uncommitted tree onto a new branch, so the recovery is cheap - but it defers the merge to the worst moment.

**A `git worktree add` the terminal kills leaves a directory that is not a worktree.** On 2026-08-30 the checkout was cut at 69 percent of 697 files: the tree is most of the way there, `git rev-parse` inside says `not a git repository`, and `git worktree list` does not mention it - so there is nothing to remove and the branch name is taken. Clean up all three pieces, then retry from a detached script:

```powershell
Remove-Item -LiteralPath <path> -Recurse -Force; git worktree prune; git branch -D <branch>
```

Check `Test-Path <path>\.git` afterwards; progress lines reaching 100 percent do not mean the `.git` file was written.

**`git worktree remove` can deregister a worktree and still fail to delete it.** On Windows it stops at the first locked path and reports `failed to delete...: Invalid argument` with the administrative entry already gone. Read the exit as "partly done", find the holder, then re-run the filesystem delete - not `git worktree remove`, which has nothing left to deregister.

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*<worktree>*' }
```

**Nothing removes a finished worktree on its own, and `git worktree prune` is not that thing** - it only clears the entry for a directory that has already gone. Measured 2026-09-02: 38 abandoned sibling directories holding 156,482 files, every one a row whose pull request had merged days earlier, because the closing step is the one a worker killed mid-row never reaches. Sweep them, and read the report before removing, because a sibling creates a worktree between any two commands:

```powershell
python backend/utilities/sweep_worktrees.py # report, change nothing
python backend/utilities/sweep_worktrees.py --remove # remove what it named
```

It keeps a tree unless the pull request is `MERGED`, the branch is gone from the remote, and the tree is clean. All three are needed: a squash merge leaves the branch a non-ancestor, so ancestry cannot say whether the row landed, and a branch with no pull request is pending work rather than stale work.

**Two process classes hold a dead tree's files and only one is safe to kill.** An `esbuild` service whose executable is inside the tree keeps running after the row ends - stop it. The editor's **Svelte language server** loads `rollup`, `lightningcss` and `tailwindcss-oxide` `.node` out of every worktree it has indexed (14 dead trees at once on 2026-09-02); it runs as `Code.exe`, so match on the command line (`svelte-language-server/bin/server.js`), never on the name. Stopping it released all 42 files and the editor respawned it untouched. Find any holder by loaded module:

```powershell
Get-Process | ForEach-Object { try { $_.Modules | Where-Object { $_.FileName -like '<worktree>*' } } catch { } }
```

## The moving base

**`origin/main` moves under you without you fetching, because every worktree shares one `.git`.** A sibling's `git fetch` updates the ref for all of them, and the scheduled pipeline pushes several times an hour. On 2026-08-31 a merge was taken against an eleven-commit `origin/main` and twenty minutes later the range listed twelve, so a cleanly auto-merged file read as though the merge had deleted a paragraph. **Diff against the sha you merged, never against the moving ref**, and re-`fetch` and re-`merge` immediately before you push.

**Your own feature branch can move too, and one of the two causes is benign.** `git reflog -8` tells them apart: `merge origin/main: Fast-forward` is a background process advancing the branch and your commits are still there; `checkout: moving from X to Y` is a parallel agent switching branches in the checkout, so the tree you are about to stage is not the tree you think it is.

**Local `main` is often behind on purpose.** When the shared checkout is dirty with work that overlaps incoming commits, `git merge --ff-only` aborts. That is correct. Do not force it.

**A killed `git push -u` can land the push and skip the `-u`.** The tool cuts the command with no output and exit 1, which reads like a failed push, while the branch is on the remote at the right sha and only the upstream config is missing. Read the remote before concluding anything:

```powershell
git ls-remote --heads origin <branch>
```

If it names your sha the push is done; `git fetch origin <branch>` then `git branch --set-upstream-to=origin/<branch>` finishes it. Setting the upstream before the fetch fails, because the push wrote the remote branch and not the remote-tracking ref.

## Contamination and recovery

**Neither `git status` nor the commit output reveals a contaminated parent**, because it is in the branch's history, not in the index. Three checks do:

```powershell
git log --oneline origin/main..<branch> # more commits than you made
git diff --stat origin/main..HEAD # more files than you touched
gh pr view <n> --repo <owner/repo> --json files --jq '[.files[].path]'
```

Run the `gh pr view` one before every merge. To recover without a force push (`CLAUDE.md` section 8): branch again off `origin/main` in a fresh worktree, `git cherry-pick` your own commit, confirm the diff lists only your files, push, open a new pull request, close the old one, then `git push origin --delete <old-branch>`.

**Safe pattern when the shared checkout is dirty with work that is not yours.** `.tmp_*` is gitignored, so the patch never lands in a commit:

```powershell
git diff --output=.tmp_mine.patch -- <only your paths>
git worktree add <repo>.worktrees/<name> -b <branch> origin/main
git apply --3way.tmp_mine.patch
```

**A dirty checkout can be a restored checkpoint, not unfinished work.** The agent host commits the whole tree to `refs/agents/<session>/checkpoints/turn/<n>`; a tree restored from one reads as ordinary uncommitted work. The tell is the direction of the diff - on 2026-08-28 the shared checkout added 132 lines and removed 5,240, un-writing a contract field, its validator, its changelog entry and its fixture. Confirm by matching blobs, not by reading the diff:

```powershell
git for-each-ref --sort=-committerdate --format='%(committerdate:iso) %(refname)' refs/agents/
git diff <checkpoint-sha> --. # empty across tracked paths means the tree IS that checkpoint
git hash-object <path> # untracked files, which the line above ignores
```

Restore by explicit path; never `git restore.` (section 8). Discarding costs nothing, because the checkpoint ref holds every byte.

**Reconciling an abandoned dirty checkout, the sequence that loses nothing.** Classify first (`git diff origin/main -- <paths>`; most "conflicting" files turn out byte-identical to upstream), snapshot onto `wip/snapshot-<date>`, let `git merge origin/main` resolve the disjoint hunks, verify by symbol rather than by eye, curate onto a fresh branch off current `origin/main` one themed commit at a time, then prove zero loss with an empty `git diff wip/snapshot-<date> HEAD -- <changed paths>`.

**A file you can see in the editor may not be in the repository at all.** `TODO/` in the shared checkout collects untracked plan-docs, and in a worktree cut from `origin/main` every git question answers as though the file never existed - which reads exactly like "somebody already distilled and deleted this".

```powershell
git ls-files --error-unmatch <path> # "did you forget to git add" = untracked
```

**Before deleting a leftover branch**, all three legs must hold: the pull request reads `MERGED` from a live `gh pr view`, its `mergeCommit` is an ancestor of `origin/main`, and the residual diff is stale content only. A branch tip beyond its `headRefOid` is usually a rebase under a new sha - find it by subject with `git log origin/main --oneline --diff-filter=A -- <file the commit created>`. GitHub keeps `refs/pull/<n>/head` for a merged pull request for ever.

**`git branch --merged` answers "none of them" in a repository that squash-merges**, which is not the same as "none are merged". Ask whether the branch would still change the base:

```bash
main_tree=$(git rev-parse origin/main^{tree})
[ "$(git merge-tree --write-tree origin/main <branch> | head -1)" = "$main_tree" ]
```

**That test has one false negative, and it is the common case for a plan-doc.** If both sides added the same file the merge is an add/add conflict, so the branch reads as unmerged. Compare the blobs before believing it - identical object ids mean the content landed verbatim (`git rev-parse <branch>:<path> <squash>:<path>`, needs `MSYS_NO_PATHCONV=1`). Observed 2026-08-28: one branch of four flagged this way was fully merged.

## Reading the tree with `git grep`

**A hit count says a symbol is everywhere when nothing calls it.** Counting `visual_planner` across this repository on 2026-09-12 named 56 files, which reads as a live subsystem. Three of them were under `backend/idhazh/` and **all three were docstring prose**; the only real import outside `backend/tests/` was an offline harness under `backend/utilities/`. A plan row was dispatched to retire that subsystem on the strength of a replacement that had never been wired to anything, and the count is what made the replacement look live. **"Is it mentioned" and "is it called" can answer 56 and 0**, and only the second one says whether deleting the old thing breaks the site. Ask for import statements, and read the production package on its own:

```powershell
git grep -nE '^\s*(from|import)\s+.*<module>' -- backend/idhazh backend/utilities
```

A module imported only by tests and by `backend/utilities/` is built and unwired, which is indistinguishable from built and shipped in every other reading of the tree. The cheapest confirming tell is the module's own docstring: one that still says a later row will connect it usually has not been connected.

## Ledgers under merge

**A header migration cannot survive a rebase, because `state/*.csv` is `merge=union`.** Union merge keeps every line from both sides - right for an append-only ledger, wrong for a file whose every line changed. Measured 2026-08-27: 4,349 data rows where 2,232 were expected, and the tell was a data row whose `run_id` cell read `run_id`. Do not resolve by hand:

```powershell
git checkout origin/main -- state/scores.csv
<re-run your migration script>
```

Expect to redo it on every rebase. Two guards make the redo safe: refuse to write unless an unmodified read-write round trip is byte-identical, and refuse if the rows are not all one width.

**A MERGE does the same thing and never conflicts, which is worse.** Union merge has no conflict state, so `git merge origin/main` over a rewritten shard exits 0, prints `Auto-merging`, and leaves one file with two headers and two row widths. Any recipe that waits for a conflict marker misses it. Make the repair unconditional after every merge and every rebase.

**`frontend/public/telemetry/*.csv` is the opposite case, and the conflict it raises is the feature.** That path is deliberately not union-merged, so a branch that widens the projection collides loudly. The cause is not another agent: a scheduled `digest.yml` run stages that directory from a checkout pinned to its start sha, so a run in flight while your pull request is open republishes both shards with the **old** publisher. Both sides are machine output, so keep neither:

```powershell
git restore --source=origin/main -- frontend/public/telemetry
python -m idhazh.publish_telemetry
```

Before merging anything that rewrites `frontend/public/`, check `gh run list --workflow digest.yml --limit 3` for a run in flight and wait it out.

**Waiting it out does not converge when the pipeline appends faster than CI finishes, and that is the usual case rather than the exception.** Measured 2026-09-12 on pull request #636, which widened `state/item-health` from 29 columns to 42 and rebuilt the projection from it: a full CI cycle takes about eight minutes, with the browser job the pole at 5m12s, and the pipeline appended to `state/item-health/2026-09.csv` three times inside one such window. Each append re-conflicted the branch, so the branch reached green and mergeable at different moments and never both at once. Three repair cycles produced three identical repairs. **The way out is to stop treating the data rows as part of the change under test.** Repair, push, and merge on `MERGEABLE/UNSTABLE` rather than waiting for a fourth cycle: the code was already green on an earlier head, and everything added since came from `main` itself plus a re-derivation a committed utility performs deterministically. Then census the trunk immediately, because the squash merge itself runs the union driver on GitHub's side and can concatenate one last time:

```powershell
python -c "import csv,pathlib,collections;w=collections.Counter();[w.update([len(r)]) for p in pathlib.Path('state/item-health').glob('*.csv') for r in csv.reader(p.open(encoding='utf-8',newline=''))];print(dict(w))"
```

One width for every row and one header per shard, or repair on the trunk. What this costs, stated rather than hidden: a merge on `UNSTABLE` is a merge whose final check set nobody read, so it is right only when the delta since the last green head is data the trunk wrote and a deterministic re-derivation of it. A code change in that delta makes it the wrong call.

**A test that reads the newest committed day is racing the pipeline**, so it goes red in the morning and green by evening. The digest publishes several times a day and appends to the same payload, so the newest date on disk is always the one still being written - measured 2026-09-06, 78 stories at 09:00 against 374 to 582 on a finished day. Take the newest day that is **not** the newest date on disk, or better, use a bounded fixture (`CLAUDE.md` Guardrail #12).

## Line endings

**Line endings are pinned, so do not hand-normalise.** `.gitattributes` defaults every path to `text=auto eol=lf`, then marks known binary formats. A blanket normalise pass rewrites files you never touched and produces a phantom diff of hundreds of lines.

**That normalisation happens at `git add`, and the gates run before it.** `test_repo_text_is_ascii_and_lf` reads the WORKING-TREE bytes under `schemas/`, `config/` and the fixture directories, so a new JSON file authored on Windows fails on a file you just wrote. The same CRLF also breaks a byte-identical round trip, so the drift gate reports a diff in a file whose content never changed. Write new files LF explicitly:

```powershell
[System.IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
```

## The `gh` CLI

**`gh pr merge`'s exit code says nothing useful.** It exits non-zero with `fatal: 'main' is already used by worktree` when any worktree holds `main`, and with `could not determine current branch: failed to run git: not on any branch` from a detached worktree - and in both the server-side merge and the branch delete have already succeeded. The merge can also be invisible for a few seconds afterwards. `gh pr view <n> --json state,mergeCommit` is the only reliable read, and a second merge attempt is the one action here that is not idempotent.

**Do not detach a row's worktree in order to free its branch - remove the worktree instead.** Detaching throws the branch away, which is the only signal `sweep_worktrees.py` can judge a leftover on, so the tree is kept for ever.

**`gh pr checks --watch` and a bare `gh run watch` open an alternate terminal buffer** and return nothing an agent can read. Pipe through `Out-String`, or read the state directly:

```powershell
gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" --jq '.check_runs[]|.name+"="+.status+"/"+(.conclusion//"-")'
```

**`gh pr checks --watch` answers about the run it already knew about.** Called within seconds of a push it reports the PREVIOUS run's conclusions as `pass` - observed 2026-08-25 on PR #94, immediately after updating the branch. Bind the question to the head commit (`gh pr view <n> --json headRefOid`), and read an empty result as "not registered yet", which is a different answer from `pass`.

**`gh pr checks` exit codes: 8 while anything is pending, 0 when every check is green, 1 when one failed.** It also prints `no checks reported` for about a minute after a push. A job can report `status: in_progress` with `conclusion: success` while the run is complete, so a settle loop keyed on exit 0 polls for ever - key it on `gh run view <id> --json status,conclusion` instead.

**An empty check list has three causes and only one is worth waiting out.** The head is new and the runner is catching up (wait); the pull request was opened against a base stale enough that no workflow started (rebase and push); or the pull request is `CONFLICTING`, in which case GitHub builds nothing, indefinitely. Ask `gh pr view <n> --json mergeable` before touching a workflow file.

**A `--jq` filter or a `--json` list assembled by PowerShell is silently mangled.** `--json tagName, assets, url` becomes three arguments (`accepts at most 1 arg(s)`), and a filter built with `+` concatenation outside parentheses hands `gh` three operands - it takes the first, ignores the rest, and prints an empty result that reads as "no run has started yet". Quote the whole list, build the string first, or let PowerShell filter:

```powershell
$runs = gh run list --repo <owner/repo> --branch <branch> --limit 10 --json name,status,conclusion,headSha |
 ConvertFrom-Json | Where-Object { $_.headSha -eq $head }
```

**A `workflow_dispatch` cannot reach a workflow that is not on the default branch.** `gh workflow run <file> --ref <my-branch>` answers `HTTP 404: workflow <file> not found on the default branch` even when the file is committed and pushed on that branch, because GitHub resolves the workflow id from `main` first. So a row that ships a new dispatch-only workflow cannot use it before the merge - plan the row around it.

**`gh run list` intermittently answers `error connecting to api.github.com`** on a box with several agents making calls at once. Retry before you go and read CI; two failures in a row on different subcommands is a different signal.

## Reading a run

**No log of any kind is readable while the run is going.** `gh run view <runId> --job <jobId> --log` and the run-level form both exit 1 with `logs will be available when it is complete`, even for a job that finished twenty minutes ago - and redirecting makes it worse, because the file is then 82 bytes of that sentence. What IS readable mid-run is the artifacts: `gh run download <runId> --name plan` gives the run plan, and each `items-<n>` appears as its shard finishes.

**A completed run fails the other way round, so keep both commands.** On 2026-09-02 `gh run view <runId> --log` exited 0 and wrote a zero-byte file while `gh api repos/<owner>/<repo>/actions/jobs/<jobId>/logs` returned the whole log. Neither endpoint is the reliable one; when the first answer is empty, ask the other.

**Filtering that log by a marker string drops the output you asked for**, because the lines worth reading carry no marker - the marker is what your own `echo` printed around them. Find the marker line numbers, then slice between them:

```powershell
$log = Get-Content -LiteralPath $path
$at = (Select-String -Path $path -Pattern 'MYTAG' -SimpleMatch).LineNumber
$log[($at[0])..($at[1] - 2)]
```

**A missing llama-server log line is a verbosity setting, not a fact about the server.** At the default `-lv 3` a start prints twelve lines and the whole model-loader block is absent - no `llama_model_loader:`, no `print_info:`, no `load_tensors:`, no `llama_kv_cache:`, no `sched_reserve:`, and nothing naming flash attention. At `-lv 4` the same start prints about 206. So a grep that finds nothing has three possible answers and only one of them is about the server, which is why a reader of that log needs three states rather than two: **active**, **refused**, and **the verbosity was not raised** - and a check that reads the missing line as "off" turns a forgotten flag into a finding about attention. `/props` and `/metrics` cannot settle it either; both come back byte-identical whether the server started with `-fa on` or `-fa off`. `models.summarize.inference.log_verbosity` is 4 in `config/idhazh.json` for this reason. Measured 2026-09-09; the readings are in [../measurements.md](../measurements.md#what-llama-server-reports-about-its-own-runtime-settings-2026-09-09).

**A grep for a string the build never writes matches nothing for ever, and reads as a broken step.** `system_info` was grepped from the visuals job's server log on nine consecutive runs and matched zero times: llama.cpp `b10598` writes no line containing it. Before treating a silent grep as a regression, confirm the build emits the string at all.

**`gh run download` can exit 0 on a partial artifact.** On 2026-08-25 one download extracted 25 of 37 items with no warning on either stream; an identical re-run gave all 124 files. Count what landed against what the run declares before computing anything from it - a measurement taken from a silently truncated artifact is wrong in a direction nobody checks:

```powershell
gh api "repos/<owner>/<repo>/actions/runs/<id>/artifacts" --jq '[.artifacts[].name]|length'
(Get-ChildItem <dest> -Directory).Count
```

**Deprecation warnings are check-run annotations, not log lines**, so grepping the log finds nothing. Read `gh api repos/<owner>/<repo>/check-runs/<jobId>/annotations`, and capture a baseline count from a pre-fix run so the fix can be shown to have done something.

**A check-runs poller that treats "none yet" as "all done" prints ALL GREEN on a red commit.** The endpoint returns an empty list for the half-minute after a push, so the first tick sees nothing pending and declares success - with the per-check listing printing nothing at all, which is easy to read as terse output. Require a check to exist:

```powershell
if ($checks.Count -gt 0 -and $pending.Count -eq 0) {... }
```

**"The evidence expired" is usually wrong - check the artifact AND the job log.** A short `retention-days` is not the same as gone: `runtime-log-*` keeps two days, so yesterday's run still hands over the raw bodies, and the job log keeps far longer than any artifact. Get job ids from `gh api "repos/<owner>/<repo>/actions/runs/<run-id>/jobs?per_page=100"`. Used on 2026-08-27 to recover four real `/metrics` bodies, which is why `tests/fixtures/runtime/` holds captures rather than something plausible somebody typed.

**The `items-*` artifacts are the only corpus of real article text.** Nothing commits an article body, so a rule that reads `Article.text` cannot be measured against `frontend/public/digest/` at all; the measurable corpus is a completed run's artifacts. Two things bite: filter on `status == "ok"` (a failed article is a real payload with no text, and deflated every percentage by 24 percent on the run measured 2026-08-26), and artifacts expire, so the number carries its run id and not just its date.

**An upstream README can be behind the binary it documents.** llama.cpp `b10598` publishes `llamacpp:prompt_tokens_cached_total` and describes `prompt_tokens_total` as excluding cached tokens; its own `tools/server/README.md` at that exact tag carries neither the extra series nor the four words that decide whether a number is a read rate or a prompt rate. A field's meaning comes from a capture, never from the document about it. Where the instrument publishes a derived value beside its inputs, reproduce it as a free self-check - `prompt_tokens_seconds` is exactly `prompt_tokens_total / prompt_seconds_total`, which proves which definition the counter is using with no second source needed.

**A missing runner fixture can be captured in about three minutes, with no checkout.** Create a ref through the API, `PUT` a one-job workflow onto it as base64 content, read the job log, then `DELETE` the ref. Every trigger here is main-only or dispatch-only, so a branch that exists for forty seconds starts nothing else. Record the run id in the measurement, and say the branch was deleted. **Convert the YAML to LF before you base64 it** - a carriage return inside a `run: |` block reaches bash as part of the command, so the job fails on a line that looks correct in every rendering of it.

## The Actions cache

**A cache key that does not name what it holds freezes that thing silently.** `digest.yml` once cached `backend/models` and `backend/bin` together under a key naming only the weights, while the step that fetched the llama.cpp release was skipped on a cache hit - so the server that started was whatever binary happened to be saved first, and nothing in the run said which one. The symptom is a step that reads as live code and has not executed for days. Closed 2026-08-25 by putting the build id in the key; kept because the shape generalises to any cache key that omits an input the cached bytes depend on.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [gates-and-builds.md](gates-and-builds.md) - merge failures that only a gate finds.
- [shell-and-tools.md](shell-and-tools.md) - the PowerShell and MSYS quoting traps behind several of these commands.
- [../github-actions.md](../github-actions.md) - workflow triggers and platform limits.
- [../../how-to/ship-a-pr.md](../../how-to/ship-a-pr.md) - the pull-request lifecycle these entries serve.
