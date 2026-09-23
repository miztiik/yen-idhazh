# Agent Notes - Git and GitHub

**Last Updated**: 2026-09-23

Traps in `git`, worktrees, merges and the `gh` CLI. Index and scope:
[../agent-notes.md](../agent-notes.md).

## Commit identity

**A guessed GitHub noreply email can credit a stranger.** `noreply@users.noreply.github.com` maps to the real `noreply` account, not an anonymous placeholder. GitHub's contributor list uses author credit; the authenticated pusher is a different fact, available from the repository activity API. Both affected pushes named `miztiik`. Local `user.name` and `user.email` override global settings, and changing either does not change an old commit. Check `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT` before committing; do not replace configured identities with test placeholders. A guessed `yen-idhazh@users.noreply.github.com` address does not reserve that GitHub account either.

**The one-time attribution repair changes commit IDs, not the recorded files.** Under the [owner approval in CLAUDE.md section 8](../../../CLAUDE.md#8-git-hygiene), `b8cd2c41` becomes `b615a0b4` and `83d47ac3` becomes `172e259e`. Their `noreply` fields use `yen-idhazh <yen-idhazh@users.noreply.github.com>` instead. Their descendants receive new IDs too. A complete local Git bundle keeps the original history; the repair checks every affected file tree, message, date, parent mapping and unaffected identity.

**Merging the old history back restores the wrong credit.** Other agents and their worktrees were left running at the owner's request. Before publishing from an old branch, carry only its unmerged changes onto the repaired `main` in a fresh branch and worktree. Do not merge old `main` back into repaired `main`, and do not reset a worktree that holds another agent's work. GitHub's cached contributor display can lag behind the corrected branch history.

## Worktrees

**More than one agent shares this checkout, so a listing from earlier in the session is fiction.** Worktrees appear and disappear mid-task. Read `git worktree list` immediately before you stage, and never `git add.` in a checkout you did not create - it sweeps another branch's work into your commit.

**`git checkout -b` in the shared checkout branches off whatever `HEAD` happens to be.** A parallel agent moves `HEAD` between your commands; a branch was cut while `HEAD` sat on a sibling's work and carried its unmerged commit as the parent. Always name the start-point and take your own worktree:

```powershell
git worktree add <repo>.worktrees/<name> -b <branch> origin/main
```

**Every worktree goes in that one container, never beside the checkout.** They accumulate - dozens on one box - and scattered siblings bury the repository among directories that are copies of it. It may not go inside the checkout either: `ruff check.` and `mypy` walk gitignored paths, `git grep` and the site-weight gate glob the tree, and each worktree carries its own `frontend/node_modules`. Name it for the row it serves, `<plan letter><row number>`.

**Branch before the first edit, not after the work is done.** A 35-file change built uncommitted in the shared checkout survived only by luck: the owner committed underneath it, `origin/main` gained 22 commits, and an earlier `git add` had been undone by another process. `git switch -c <branch>` carries an uncommitted tree onto a new branch, so the recovery is cheap - but it defers the merge to the worst moment.

**A `git worktree add` the terminal kills leaves a directory that is not a worktree.** The checkout can be cut at 69 percent of 697 files: the tree is most of the way there, `git rev-parse` inside says `not a git repository`, and `git worktree list` does not mention it - so there is nothing to remove and the branch name is taken. Clean up all three pieces, then retry from a detached script:

```powershell
Remove-Item -LiteralPath <path> -Recurse -Force; git worktree prune; git branch -D <branch>
```

Check `Test-Path <path>\.git` afterwards; progress lines reaching 100 percent do not mean the `.git` file was written.

**`git worktree remove` can deregister a worktree and still fail to delete it.** On Windows it stops at the first locked path and reports `failed to delete...: Invalid argument` with the administrative entry already gone. Read the exit as "partly done", find the holder, then re-run the filesystem delete - not `git worktree remove`, which has nothing left to deregister.

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*<worktree>*' }
```

**Nothing removes a finished worktree on its own, and `git worktree prune` is not that thing** - it only clears the entry for a directory that has already gone. One sweep found 38 abandoned sibling directories holding 156,482 files, every one a row whose pull request had merged days earlier, because the closing step is the one a worker killed mid-row never reaches. Sweep them, and read the report before removing, because a sibling creates a worktree between any two commands:

```powershell
python backend/utilities/sweep_worktrees.py # report, change nothing
python backend/utilities/sweep_worktrees.py --remove # remove what it named
```

It keeps a tree unless the pull request is `MERGED`, the branch is gone from the remote, and the tree is clean. All three are needed: a squash merge leaves the branch a non-ancestor, so ancestry cannot say whether the row landed, and a branch with no pull request is pending work rather than stale work.

**Two process classes hold a dead tree's files and only one is safe to kill.** An `esbuild` service whose executable is inside the tree keeps running after the row ends - stop it. The editor's **Svelte language server** loads `rollup`, `lightningcss` and `tailwindcss-oxide` `.node` out of every worktree it has indexed (many dead trees at once); it runs as `Code.exe`, so match on the command line (`svelte-language-server/bin/server.js`), never on the name. Stopping it released all 42 files and the editor respawned it untouched. Find any holder by loaded module:

```powershell
Get-Process | ForEach-Object { try { $_.Modules | Where-Object { $_.FileName -like '<worktree>*' } } catch { } }
```

## The moving base

**`origin/main` moves under you without you fetching, because every worktree shares one `.git`.** A sibling's `git fetch` updates the ref for all of them, and the scheduled pipeline pushes several times an hour. A merge can be taken against an eleven-commit `origin/main` and twenty minutes later the range can list twelve, so a cleanly auto-merged file read as though the merge had deleted a paragraph. **Diff against the sha you merged, never against the moving ref**, and re-`fetch` and re-`merge` immediately before you push.

**Your own feature branch can move too, and one of the two causes is benign.** `git reflog -8` tells them apart: `merge origin/main: Fast-forward` is a background process advancing the branch and your commits are still there; `checkout: moving from X to Y` is a parallel agent switching branches in the checkout, so the tree you are about to stage is not the tree you think it is.

**A pull request that reads `CONFLICTING` may have nothing left to resolve.** GitHub judges the head it was pushed, and a worktree handed over mid-row often already holds the merge commit that settles it. A pull request can read `DIRTY`/`CONFLICTING` while its worktree sat on an unpushed merge of `origin/main`; pushing that commit was the whole fix. Ask the two questions before you resolve anything - what GitHub is judging, and whether your own tree still conflicts:

```powershell
gh pr view <n> --repo <owner/repo> --json headRefOid,mergeable,mergeStateStatus
git merge-tree --write-tree --name-only HEAD origin/main   # exit 0 means no conflict
```

`git merge-tree` answers without touching the worktree, so it is also the cheapest way to find out whether a fetch has made a merge you already resolved conflict again.

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

**`git grep` for a conflict marker MISSES one sitting in a working file mid-merge.** It reads the index and the stage entries, not the unmerged file on disk, so `git grep "^<<<<<<<"` reports nothing while a file still carries a marker - and the first thing to notice it is a linter, complaining about a syntax error on a line nobody wrote. Scan the filesystem instead, re-count after every edit pass because a truncated dump of a file hides a hunk, and let the linter be the second opinion rather than the first:

```powershell
Get-ChildItem -Recurse -File -Path backend,config,frontend/src |
  Select-String -Pattern '^<<<<<<< |^>>>>>>> ' -List
```

**Safe pattern when the shared checkout is dirty with work that is not yours.** `.tmp_*` is gitignored, so the patch never lands in a commit:

```powershell
git diff --output=.tmp_mine.patch -- <only your paths>
git worktree add <repo>.worktrees/<name> -b <branch> origin/main
git apply --3way.tmp_mine.patch
```

**A dirty checkout can be a restored checkpoint, not unfinished work.** The agent host commits the whole tree to `refs/agents/<session>/checkpoints/turn/<n>`; a tree restored from one reads as ordinary uncommitted work. The tell is the direction of the diff - the shared checkout added 132 lines and removed 5,240, un-writing a contract field, its validator, its changelog entry and its fixture. Confirm by matching blobs, not by reading the diff:

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

**A fix can read as applied and still never reach the commit.** Reading the file back after an edit confirms the working tree, which is not what a push ships - so the edit, the read-back and the push can all succeed and the pull request carry none of it. Two staging faults produce it, and both exit quietly. Slicing `git status --porcelain` with `$_.Substring(3)` keeps the path on an ordinary `?? ` or ` M ` line and mangles a `DU ` or `D  ` one, and `git add -- <a path already staged as deleted>` errors, which under a single `git add` call for the whole list leaves every remaining path unstaged. **The tell is that both halves have to hold**: `git status --porcelain` empty AND `git show --stat HEAD` listing the files you meant.

```powershell
git status --porcelain; git show --stat HEAD
```

**Before deleting a leftover branch**, all three legs must hold: the pull request reads `MERGED` from a live `gh pr view`, its `mergeCommit` is an ancestor of `origin/main`, and the residual diff is stale content only. A branch tip beyond its `headRefOid` is usually a rebase under a new sha - find it by subject with `git log origin/main --oneline --diff-filter=A -- <file the commit created>`. GitHub keeps `refs/pull/<n>/head` for a merged pull request for ever.

**`git branch --merged` answers "none of them" in a repository that squash-merges**, which is not the same as "none are merged". Ask whether the branch would still change the base:

```bash
main_tree=$(git rev-parse origin/main^{tree})
[ "$(git merge-tree --write-tree origin/main <branch> | head -1)" = "$main_tree" ]
```

**That test has one false negative, and it is the common case for a plan-doc.** If both sides added the same file the merge is an add/add conflict, so the branch reads as unmerged. Compare the blobs before believing it - identical object ids mean the content landed verbatim (`git rev-parse <branch>:<path> <squash>:<path>`, needs `MSYS_NO_PATHCONV=1`). One branch of four flagged this way can be fully merged.

**Merging the tip of a stacked chain lands every branch under it, so the parents' pull requests are closed rather than merged.** A branch cut from another branch carries its parent's commits, and the squash folds all of them into the one entry the tip creates. Three pull requests of a four-deep chain were already on `main` the moment the tip merged, and merging them after that would have re-applied content that was there - a conflict at best, a duplicated row at worst. The tell is not the pull-request state, which still reads `OPEN`: ask whether the branch adds a file `main` does not have.

```powershell
git diff --name-only --diff-filter=A origin/main...origin/<branch> |
  ForEach-Object { git cat-file -e "origin/main:$_" 2>$null; "$_ on main: $($LASTEXITCODE -eq 0)" }
```

Every file already present means the branch is redundant. Close it with a comment naming the pull request that carried it, so the row's history stays readable.

**Merging the BASE of a stacked pair makes the child look catastrophically conflicted, and it is not.** The squash folds A's commits into one new commit on `main`, B still carries A's originals, so every file the two touched conflicts on both sides at once - 40 files on one pair, and each one was A's own content arriving twice. `--ours` is right on every one of them, and a file A deleted takes `git rm` rather than a resolve. The hazard is that the noise hides the only thing in the merge that is not yours: whatever `main` gained that the child has never seen. Count that first, and verify it survived after you resolve.

```powershell
git log --oneline HEAD..origin/main            # usually one squash commit, and it is the one to check
git diff --stat origin/main HEAD -- <path>    # after the merge: only your own edits may remain
```

## Reading the tree with `git grep`

**A hit count says a symbol is everywhere when nothing calls it.** Counting `visual_planner` across this repository named 56 files, which reads as a live subsystem. Three of them were under `backend/idhazh/` and **all three were docstring prose**; the only real import outside `backend/tests/` was an offline harness under `backend/utilities/`. A plan row was dispatched to retire that subsystem on the strength of a replacement that had never been wired to anything, and the count is what made the replacement look live. **"Is it mentioned" and "is it called" can answer 56 and 0**, and only the second one says whether deleting the old thing breaks the site. Ask for import statements, and read the production package on its own:

```powershell
git grep -nE '^\s*(from|import)\s+.*<module>' -- backend/idhazh backend/utilities
```

A module imported only by tests and by `backend/utilities/` is built and unwired, which is indistinguishable from built and shipped in every other reading of the tree. The cheapest confirming tell is the module's own docstring: one that still says a later row will connect it usually has not been connected.

## Ledgers under merge

**A header migration cannot survive a rebase on a path that carries a union merge driver.** Three still do - `state/published/**/*.csv`, `state/visual-prunes/**/*.csv` and `state/seen/**/*.csv` - and every other head under `state/` lost one on 2026-09-19. Union merge keeps every line from both sides - right for an append-only ledger, wrong for a file whose every line changed. One merge produced 4,349 data rows where 2,232 were expected, and the tell was a data row whose `run_id` cell read `run_id`. Do not resolve by hand:

```powershell
git checkout origin/main -- state/scores.csv
<re-run your migration script>
```

Expect to redo it on every rebase. Two guards make the redo safe: refuse to write unless an unmodified read-write round trip is byte-identical, and refuse if the rows are not all one width.

**A MERGE does the same thing and never conflicts, which is worse.** Union merge has no conflict state, so `git merge origin/main` over a rewritten shard exits 0, prints `Auto-merging`, and leaves one file with two headers and two row widths. Any recipe that waits for a conflict marker misses it. Make the repair unconditional after every merge and every rebase.

**A change of grain fails in the directory rather than in the file, so census the directory.** Moving a store from `<YYYY-MM>.csv` to `<YYYY>/<MM>/<DD>.csv` deletes a file the scheduled `digest.yml` run is still appending to: that run is pinned to the sha it started on, so it keeps writing the month shard your branch removed. After the merge the store holds both grains. Nothing reads as corrupt - `day_partition.day_files` refuses a name it cannot place, so every read of that store stops instead. A store can need the same migration twice for this. Restore the store from the trunk and re-run the migration utility; do not resolve by hand, and count the files in the directory afterwards rather than only reading the one you edited.

**`frontend/public/telemetry/*.csv` is the opposite case, and the conflict it raises is the feature.** That path is deliberately not union-merged, so a branch that widens the projection collides loudly. The cause is not another agent: a scheduled `digest.yml` run stages that directory from a checkout pinned to its start sha, so a run in flight while your pull request is open republishes both shards with the **old** publisher. Both sides are machine output, so keep neither:

```powershell
git restore --source=origin/main -- frontend/public/telemetry
python -m idhazh.telemetry.publish.public_telemetry
```

**A publisher takes the DIGEST root, not the published root, and handing it the wrong one writes a directory nobody looks at.** `series.console_root(digest_root)` is `digest_root.parent`, so a re-derivation pointed at `frontend/public` lands in `frontend/machine/` - an untracked tree of plausible files, exit 0, and the conflicted shard still conflicted. The tell is `git status --porcelain` naming a new untracked directory one level above where you expected the write; pass `frontend/public/digest`.

Before merging anything that rewrites `frontend/public/`, check `gh run list --workflow digest.yml --limit 3` for a run in flight and wait it out.

**Waiting it out does not converge when the pipeline appends faster than CI finishes, and that is the usual case rather than the exception.** A pull request that widened `state/item-health` from 29 columns to 42 and rebuilt the projection from it: a full CI cycle takes about eight minutes, with the browser job the pole at 5m12s, and the pipeline appended to `state/item-health/2026-09.csv` three times inside one such window. Each append re-conflicted the branch, so the branch reached green and mergeable at different moments and never both at once. Three repair cycles produced three identical repairs. **The way out is to stop treating the data rows as part of the change under test.** Repair, push, and merge on `MERGEABLE/UNSTABLE` rather than waiting for a fourth cycle: the code was already green on an earlier head, and everything added since came from `main` itself plus a re-derivation a committed utility performs deterministically. Then census the trunk immediately, because the squash merge itself runs the union driver on GitHub's side and can concatenate one last time:

```powershell
python -c "import csv,pathlib,collections;w=collections.Counter();[w.update([len(r)]) for p in pathlib.Path('state/item-health').glob('*.csv') for r in csv.reader(p.open(encoding='utf-8',newline=''))];print(dict(w))"
```

One width for every row and one header per shard, or repair on the trunk. What this costs, stated rather than hidden: a merge on `UNSTABLE` is a merge whose final check set nobody read, so it is right only when the delta since the last green head is data the trunk wrote and a deterministic re-derivation of it. A code change in that delta makes it the wrong call.

**A test that reads the newest committed day is racing the pipeline**, so it goes red in the morning and green by evening. The digest publishes several times a day and appends to the same payload, so the newest date on disk is always the one still being written - one morning sample read 78 stories at 09:00 against 374 to 582 on a finished day. Take the newest day that is **not** the newest date on disk, or better, use a bounded fixture (`CLAUDE.md` Guardrail #12).

## Line endings

**Line endings are pinned, so do not hand-normalise.** `.gitattributes` defaults every path to `text=auto eol=lf`, then marks known binary formats. A blanket normalise pass rewrites files you never touched and produces a phantom diff of hundreds of lines.

**That normalisation happens at `git add`, and the gates run before it.** `test_repo_text_is_ascii_and_lf` reads the WORKING-TREE bytes under `config/` and the fixture directories, so a new JSON file authored on Windows fails on a file you just wrote. The same CRLF also breaks a byte-identical round trip, so a fixture's round-trip test reports a diff in a file whose content never changed. Write new files LF explicitly:

```powershell
[System.IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
```

## The `gh` CLI

**An inherited token can override `gh`'s stored active account.** Verify the
intended actor in the current shell without exporting a stored token:

```powershell
Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
Set-Alias -Name ghm -Value gh -Scope Local
ghm api user --jq .login
```

This loads no profile and changes no saved account. Stop if the returned login
is not the intended actor; do not print or export a token for an account check.

**`gh pr merge`'s exit code says nothing useful.** It exits non-zero with `fatal: 'main' is already used by worktree` when any worktree holds `main`, and with `could not determine current branch: failed to run git: not on any branch` from a detached worktree - and in both the server-side merge and the branch delete have already succeeded. The merge can also be invisible for a few seconds afterwards. `gh pr view <n> --json state,mergeCommit` is the only reliable read, and a second merge attempt is the one action here that is not idempotent.

**Do not detach a row's worktree in order to free its branch - remove the worktree instead.** Detaching throws the branch away, which is the only signal `sweep_worktrees.py` can judge a leftover on, so the tree is kept for ever.

**`gh pr checks --watch` and a bare `gh run watch` open an alternate terminal buffer** and return nothing an agent can read. Pipe through `Out-String`, or read the state directly:

```powershell
gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" --jq '.check_runs[]|.name+"="+.status+"/"+(.conclusion//"-")'
```

**`gh pr checks --watch` answers about the run it already knew about.** Called within seconds of a push it reports the PREVIOUS run's conclusions as `pass` - observed immediately after updating a branch. Bind the question to the head commit (`gh pr view <n> --json headRefOid`), and read an empty result as "not registered yet", which is a different answer from `pass`.

**`gh pr checks` exit codes: 8 while anything is pending, 0 when every check is green, 1 when one failed.** It also prints `no checks reported` for about a minute after a push. A job can report `status: in_progress` with `conclusion: success` while the run is complete, so a settle loop keyed on exit 0 polls for ever - key it on `gh run view <id> --json status,conclusion` instead.

**An empty check list has three causes and only one is worth waiting out.** The head is new and the runner is catching up (wait); the pull request was opened against a base stale enough that no workflow started (rebase and push); or the pull request is `CONFLICTING`, in which case GitHub builds nothing, indefinitely. **Ask `gh pr view <n> --json mergeable` before the first poll, not after it** - a pull request that was green an hour ago goes `CONFLICTING` the moment a sibling merges something that touches one of its files, and the only visible symptom is that the new head registers no checks at all. Two poll loops were spent on a commit whose `mergeable` had already read `CONFLICTING`. Merging `origin/main` in and pushing clears it and starts the run in the same move.

**A `--jq` filter or a `--json` list assembled by PowerShell is silently mangled.** `--json tagName, assets, url` becomes three arguments (`accepts at most 1 arg(s)`), and a filter built with `+` concatenation outside parentheses hands `gh` three operands - it takes the first, ignores the rest, and prints an empty result that reads as "no run has started yet". Quote the whole list, build the string first, or let PowerShell filter:

```powershell
$runs = gh run list --repo <owner/repo> --branch <branch> --limit 10 --json name,status,conclusion,headSha |
 ConvertFrom-Json | Where-Object { $_.headSha -eq $head }
```

**A `workflow_dispatch` cannot reach a workflow that is not on the default branch.** `gh workflow run <file> --ref <my-branch>` answers `HTTP 404: workflow <file> not found on the default branch` even when the file is committed and pushed on that branch, because GitHub resolves the workflow id from `main` first. So a row that ships a new dispatch-only workflow cannot use it before the merge - plan the row around it.

**`gh run list` intermittently answers `error connecting to api.github.com`** on a box with several agents making calls at once. Retry before you go and read CI; two failures in a row on different subcommands is a different signal.

## Reading a run

**A green run conclusion can mean the gate never ran.** The `scope` job decides which jobs start, and a commit touching only data paths gets `browser=skipped` - GitHub folds a skipped job into a `success` conclusion, so the run reads as a full pass. `main`'s browser job was red for about nine hours on 2026-09-20, from `896688ed` at 12:35 UTC to `6c5bccd6` at 21:19 UTC; sixteen commits in that window reported the failure and twenty reported all-green with the browser job skipped, so a reader who arrived between two of them saw a healthy trunk. **The tell is that the conclusion is one word and the job list is not** - a skipped job and a passing job give the same conclusion, and only the list separates them. Read the list, never the conclusion:

```powershell
gh api repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[]|.name+"="+((.conclusion)//"running")'
```

**No log of any kind is readable while the run is going.** `gh run view <runId> --job <jobId> --log` and the run-level form both exit 1 with `logs will be available when it is complete`, even for a job that finished twenty minutes ago - and redirecting makes it worse, because the file is then 82 bytes of that sentence. What IS readable mid-run is the artifacts: `gh run download <runId> --name plan` gives the run plan, and each `items-<n>` appears as its shard finishes.

**A completed run fails the other way round, so keep both commands.** `gh run view <runId> --log` can exit 0 and wrote a zero-byte file while `gh api repos/<owner>/<repo>/actions/jobs/<jobId>/logs` returned the whole log. Neither endpoint is the reliable one; when the first answer is empty, ask the other.

**Filtering that log by a marker string drops the output you asked for**, because the lines worth reading carry no marker - the marker is what your own `echo` printed around them. Find the marker line numbers, then slice between them:

```powershell
$log = Get-Content -LiteralPath $path
$at = (Select-String -Path $path -Pattern 'MYTAG' -SimpleMatch).LineNumber
$log[($at[0])..($at[1] - 2)]
```

**A missing llama-server log line is a verbosity setting, not a fact about the server.** At the default `-lv 3` a start prints twelve lines and the whole model-loader block is absent - no `llama_model_loader:`, no `print_info:`, no `load_tensors:`, no `llama_kv_cache:`, no `sched_reserve:`, and nothing naming flash attention. At `-lv 4` the same start prints about 206. So a grep that finds nothing has three possible answers and only one of them is about the server: **it happened**, **it did not**, and **the verbosity was not raised** - and reading the missing line as "it did not" turns a forgotten flag into a finding about the runtime. `/props` and `/metrics` cannot settle it either; both come back byte-identical whether the server started with `-fa on` or `-fa off`. `-lv` on the summarize entry is 4 in `config/idhazh.json` for this reason. Measured 2026-09-09; the readings are in [benchmarks/what-llama-server-reports-about-itself.md](../benchmarks/what-llama-server-reports-about-itself.md). The project wrote a reader for that three-state answer and deleted it on 2026-09-21 with nothing having called it - the lesson is for a person at a terminal, which is who greps that log.

**A grep for a string the build never writes matches nothing for ever, and reads as a broken step.** `system_info` was grepped from the visuals job's server log on nine consecutive runs and matched zero times: llama.cpp `b10598` writes no line containing it. Before treating a silent grep as a regression, confirm the build emits the string at all.

**`gh run download` can exit 0 on a partial artifact.** One download extracted 25 of 37 items with no warning on either stream; an identical re-run gave all 124 files. Count what landed against what the run declares before computing anything from it - a measurement taken from a silently truncated artifact is wrong in a direction nobody checks:

```powershell
gh api "repos/<owner>/<repo>/actions/runs/<id>/artifacts" --jq '[.artifacts[].name]|length'
(Get-ChildItem <dest> -Directory).Count
```

**Deprecation warnings are check-run annotations, not log lines**, so grepping the log finds nothing. Read `gh api repos/<owner>/<repo>/check-runs/<jobId>/annotations`, and capture a baseline count from a pre-fix run so the fix can be shown to have done something.

**A check-runs poller that treats "none yet" as "all done" prints ALL GREEN on a red commit.** The endpoint returns an empty list for the half-minute after a push, so the first tick sees nothing pending and declares success - with the per-check listing printing nothing at all, which is easy to read as terse output. Require a check to exist:

```powershell
if ($checks.Count -gt 0 -and $pending.Count -eq 0) {... }
```

**"The evidence expired" is usually wrong - check the artifact AND the job log.** A short `retention-days` is not the same as gone: `runtime-log-*` keeps two days, so yesterday's run still hands over the raw bodies, and the job log keeps far longer than any artifact. Get job ids from `gh api "repos/<owner>/<repo>/actions/runs/<run-id>/jobs?per_page=100"`. Use both to recover real `/metrics` bodies; that is why `tests/fixtures/runtime/` holds captures rather than something plausible somebody typed.

**The `items-*` artifacts are the only corpus of real article text.** Nothing commits an article body, so a rule that reads `Article.text` cannot be measured against `frontend/public/digest/` at all; the measurable corpus is a completed run's artifacts. Two things bite: filter on `status == "ok"` (a failed article is a real payload with no text, and deflated every percentage by 24 percent on the measured run), and artifacts expire, so the number carries its run id and not just its date.

**An upstream README can be behind the binary it documents.** llama.cpp `b10598` publishes `llamacpp:prompt_tokens_cached_total` and describes `prompt_tokens_total` as excluding cached tokens; its own `tools/server/README.md` at that exact tag carries neither the extra series nor the four words that decide whether a number is a read rate or a prompt rate. A field's meaning comes from a capture, never from the document about it. Where the instrument publishes a derived value beside its inputs, reproduce it as a free self-check - `prompt_tokens_seconds` is exactly `prompt_tokens_total / prompt_seconds_total`, which proves which definition the counter is using with no second source needed.

**A missing runner fixture can be captured in about three minutes, with no checkout.** Create a ref through the API, `PUT` a one-job workflow onto it as base64 content, read the job log, then `DELETE` the ref. Every trigger here is main-only or dispatch-only, so a branch that exists for forty seconds starts nothing else. Record the run id in the measurement, and say the branch was deleted. **Convert the YAML to LF before you base64 it** - a carriage return inside a `run: |` block reaches bash as part of the command, so the job fails on a line that looks correct in every rendering of it.

## The Actions cache

**A cache key that does not name what it holds freezes that thing silently.** `digest.yml` once cached `backend/models` and `backend/bin` together under a key naming only the weights, while the step that fetched the llama.cpp release was skipped on a cache hit - so the server that started was whatever binary happened to be saved first, and nothing in the run said which one. The symptom is a step that reads as live code and has not executed for days. The shape generalises to any cache key that omits an input the cached bytes depend on.

## The plan queue

**A status an agent is told to write is a status that does not get written.** Thirteen rows had been dispatched and merged and no cell anywhere read `IN-FLIGHT`, so for a whole session the only record of what was being worked was a chat log no later agent can read. The same failure happens at the other end: the first row executed under the execution contract merged in a pull request that touched no Reckoner line, and hours later the row still read `PENDING` with an empty `PR` column while the work was on the trunk. **The instruction to flip it had been written down and read by the agent that did not do it** - which is the finding worth keeping. Wording alone does not hold, so the update moved inside the diff that is reviewed, and the plan-queue reader fails when a merged pull request names a row that never learned it landed.

**A long-lived status table in one plan-doc conflicts on EVERY parallel branch of that plan.** This is the single-plan version of the generated-page failure above, and giving the page one writer does not touch it. Six pull requests of one plan each stamped their own row in one markdown table; adjacent rows sit one to three lines apart, so every merge after the first read `CONFLICTING`. The resolution is always the same and always mechanical - keep each side's own rows - but it is a cycle each: merge `origin/main`, resolve, push, re-poll. **Budget one such cycle per pull request after the first, and merge them one at a time.** Ask `gh pr view <n> --json mergeable` right after any sibling merges, because a `CONFLICTING` pull request registers no check runs and reads exactly like a stuck queue.

**A plan asserting its parallel rows touch different files is making a claim, not stating a fact.** A 33-row plan stated the rule outright and was wrong on its first wave: three rows shared one stylesheet and three components, two more shared one config file, and a sixth needed a component that a row in a later group had not created yet. The evidence was in the plan the whole time, because the rows' own `Files touched` lists disagreed with the sentence above them. Diff the lists; never trust the sentence.

**A plan can be rewritten under the agent executing it, and the copy in your worktree will not say so.** Five rows of a live plan were collapsed into a new plan by a parallel session while three of its pull requests were in flight; the executing agent found out only because merging `origin/main` into a branch raised a conflict in the Reckoner, and the incoming side carried `COLLAPSED` in five status cells. The new plan had also **corrected** the old one - a row said a 900 s readiness wait would drop to 2 s, where the right change was a 2 s check in front of a wait that must not move, because a cold model load legitimately takes 284 to 447 s. An agent that had implemented the row as written would have shipped a benchmark arm that calls a healthy server dead. **Re-read the row from `origin/main` at dispatch, not from the worktree you cut earlier**, and when a row's own numbers disagree with the tree, treat the tree as the authority and say what you corrected.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [gates-and-builds.md](gates-and-builds.md) - merge failures that only a gate finds.
- [shell-and-tools.md](shell-and-tools.md) - the PowerShell and MSYS quoting traps behind several of these commands.
- [../github-actions.md](../github-actions.md) - workflow triggers and platform limits.
- [../../how-to/ship-a-pr.md](../../how-to/ship-a-pr.md) - the pull-request lifecycle these entries serve.
