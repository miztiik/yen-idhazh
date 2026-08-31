# Agent Notes

**Last Updated**: 2026-08-31

Environment and tool quirks that make a command lie about its result in this
repository. Each entry is a trap that cost real time at least once, the symptom
it shows, and the response.

This page exists so that execution craft has a home inside `docs/`. A lesson
kept only in an agent's private memory is invisible to the next person and to
the next agent (`CLAUDE.md` section 5).

**This is not a place for project knowledge.** A rule about how the pipeline
behaves, what a payload carries, or why a design was chosen belongs in the
living doc that owns it ([documentation-structure.md](documentation-structure.md)).
If an entry here starts explaining the product, it has been filed wrong.

## Git and worktrees

**More than one agent can share this checkout.** Worktrees appear and disappear
mid-task. Run `git worktree list` immediately before you stage, never trust a
listing from earlier in the session, and never `git add .` in a checkout you did
not create - it sweeps another branch's work into your commit.

**Never `git checkout -b` in the shared checkout.** With no start-point it
branches off whatever `HEAD` currently is, and a parallel agent moves `HEAD`
between your commands. On 2026-08-25 a plan branch was cut while `HEAD` sat on
another agent's `plan/console-charts`, so it carried that agent's unmerged
commit as its parent. Always name the start-point and take your own worktree:

```powershell
git worktree add <absolute path> -b <branch> origin/main
```

**`origin/main` moves under you without you fetching, because every worktree
shares one `.git`.** A sibling agent's `git fetch` updates the ref for all of
them. On 2026-08-31 a merge was taken against an `origin/main` of eleven
commits, and twenty minutes later `git log <base>..origin/main` listed twelve -
so a file the merge had auto-merged cleanly now read as though the merge had
DELETED a paragraph `main` holds, which is exactly what a bad merge looks like.
It was not one; the twelfth commit simply arrived afterwards. Re-run
`git rev-parse origin/main` before you diff against it, and re-`fetch` and
re-`merge` immediately before you push rather than assuming the tree you tested
is the tree you are merging into.

**Neither `git status` nor the commit output reveals that contamination**, because
it is in the branch's parent, not in the index. `git status --porcelain` showed
one staged file and `git commit` reported "1 file changed" - both true, both
useless. Three checks that do catch it:

```powershell
git log --oneline origin/main..<branch>          # more commits than you made
git diff --stat origin/main..HEAD                # more files than you touched
gh pr view <n> --repo <owner/repo> --json files --jq '[.files[].path]'
```

Run the `gh pr view` one before every merge; it is the cheapest and it is what
caught the 2026-08-25 case. To recover without a force push (`CLAUDE.md`
section 8): branch again off `origin/main` in a fresh worktree, `git cherry-pick`
your own commit, confirm the diff lists only your files, push the new branch,
open a new PR, close the old one with the reason, then
`git push origin --delete <old-branch>`.

Safe pattern when the shared checkout is dirty with work that is not yours:

```powershell
git diff --output=.tmp_mine.patch -- <only your paths>
git worktree add <absolute path> -b <branch> origin/main
git apply --3way .tmp_mine.patch
```

**A `git worktree add` the terminal kills leaves a directory that is not a
worktree.** On 2026-08-30 the checkout was cut at 69 percent of 697 files. The
directory existed and held most of the tree, `git rev-parse` inside it said
`not a git repository`, and `git worktree list` did not mention it at all - so
the usual `git worktree remove` has nothing to remove and the branch name is
already taken. Clean up all three pieces, then retry from a detached script:

```powershell
Remove-Item -LiteralPath <path> -Recurse -Force
git worktree prune
git branch -D <branch>
```

The checkout is slow enough to hit the idle kill on a repository this size, so
run it the way every other long child is run - `Start-Process pwsh -WindowStyle
Hidden` writing a sentinel (see [PowerShell](#powershell)). Check
`Test-Path <path>\.git` afterwards; the progress lines reaching 100 percent do
not mean the `.git` file was written.

**Branch first, before the first edit - not after the work is done.** A session
on 2026-08-28/29 built a 35-file change entirely uncommitted in the shared
checkout. Nothing was lost, but three things happened while it sat there: the
owner committed to `main` underneath it, `origin/main` gained 22 commits touching
94 files, and the index was reset by another process so a `git add` from earlier
in the session had silently come undone. The recovery is cheap and worth
knowing - `git switch -c <branch>` carries an uncommitted working tree onto a new
branch, so committing there and then `git switch main` leaves the shared checkout
clean - but the cost is that the merge is deferred to the worst possible moment,
when the change is largest and the divergence widest. Commit to a branch inside
the first few edits.

`.tmp_*` is gitignored, so the patch file never lands in a commit.

**A `git push -u` that the terminal kills can land the push and skip the `-u`.**
On 2026-08-29 the tool cut the command with no output and exit 1, which reads
like a failed push. The branch was on the remote at the right SHA, and only the
upstream config had not been written - so `git rev-parse --abbrev-ref '@{u}'`
still answered `origin/main` and a retry would have looked like a second push of
the same commits. Read the remote before concluding anything:

```powershell
git ls-remote --heads origin <branch>
```

If it names your SHA the push is done; `git fetch origin <branch>` then
`git branch --set-upstream-to=origin/<branch>` finishes the job. Setting the
upstream before the fetch fails with `does not exist`, because the push wrote
the remote branch and not the remote-tracking ref.

**The venv tests the checkout it was installed from, not your worktree.**
`pip install -e .` writes `_editable_impl_idhazh.pth` into
`.venv/Lib/site-packages`, and that file holds the ABSOLUTE path of the checkout
you installed from. Run the shared venv from a worktree and `pytest` collects
your tests while `import idhazh` silently resolves to the other tree, so a green
run says nothing about your change. `PYTHONPATH` is searched before a `.pth`
entry, so one variable fixes it:

```powershell
$env:PYTHONPATH='<absolute path to your worktree>\backend'
& <shared venv>\Scripts\python.exe -c "import idhazh; print(idhazh.__file__)"
```

Print that path before every gate run. If it does not name your worktree, every
result after it is about somebody else's code. Verified 2026-08-25 across ten
worktrees.

**And the same variable is what breaks the NEXT worktree.** `PYTHONPATH` leaks
into every terminal the editor opens afterwards, and it beats a correct `.pth`
just as reliably as it beats a wrong one. A worktree with its own venv, its own
`pip install -e .` and its own correct `_editable_impl_idhazh.pth` still imported
a sibling worktree's `idhazh`, so `python -m idhazh.contracts.export` wrote
`schemas/` into the OTHER tree and `git status` here stayed clean - which reads
exactly like the exporter ignoring a new contract. Clear it first, then print the
path:

```powershell
$env:PYTHONPATH=''
& .\.venv\Scripts\python.exe -c "import idhazh; print(idhazh.__file__)"
```

Set the variable only when you are deliberately borrowing another checkout's
venv. Observed 2026-08-27.

**A header migration cannot survive a rebase, because `state/*.csv` is
`merge=union`.** Union merge keeps every line from both sides, which is exactly
right for an append-only ledger and exactly wrong for a file whose every line
changed. Rebase a branch that widened `state/scores.csv` and git hands back both
copies concatenated - main's 2,232 narrow rows, then your header again as row
2,233, then your 2,232 wide rows. Measured 2026-08-27: 4,349 data rows where
2,232 were expected, and the tell was a data row whose `run_id` cell read
`run_id`.

Do not resolve it by hand. Take the tip's copy and redo the migration on top:

```powershell
git checkout origin/main -- state/scores.csv
<re-run your migration script>
```

Migrate in the commit you push and expect to redo it on every rebase. Two
guards make the redo safe: refuse to write unless an unmodified read-write
round trip is byte-identical, and refuse if the rows are not all one width -
the second one is what catches the doubled file.

**`origin/main` moves under you.** The scheduled pipeline pushes `plan:` and
`digest:` commits to `main` several times an hour, and the editor auto-fetches.
A branch created "from `origin/main`" and a merge done "against `origin/main`"
minutes apart can disagree on `state/*.csv` purely because the tip moved. Run
`git rev-parse origin/main` immediately before branching and again before
pushing. A `git diff main origin/main` that is non-empty right after a
successful `--ff-only` means it moved again.

**Your own feature branch can move under you too, and one of the two causes is
benign.** Observed 2026-08-24: `git worktree list` named a commit nobody in the
session had authored. `git reflog -8` is what tells the cases apart. An entry
reading `merge origin/main: Fast-forward` is the harmless one - a background
process advanced the branch and your commits are still there. An entry reading
`checkout: moving from X to Y` is the dangerous one - a parallel agent switched
branches in the checkout, so the tree you are about to stage is not the tree you
think it is. Commit as soon as the gates are green, so there is a SHA of your
own to compare everything against.

**Local `main` is often behind on purpose.** When the shared checkout carries
dirty files that overlap incoming commits, `git merge --ff-only` aborts. That is
correct. Do not force it.

**Reconciling an abandoned dirty checkout** - the sequence that loses nothing:

1. Classify before touching anything. `git diff origin/main -- <paths>` compares
   the working tree against upstream directly. Most "conflicting" files usually
   turn out byte-identical to `origin/main` because someone already merged them.
2. Snapshot. `git switch -c wip/snapshot-<date>`, stage explicit paths, commit.
   Now nothing can be lost.
3. Let git merge. `git merge origin/main` on the snapshot branch. Disjoint hunks
   auto-resolve.
4. Verify by symbol, not by eye. Grep that upstream's added and removed symbols
   survived and yours are present. An auto-merge can silently revert an upstream
   deletion.
5. Curate onto a fresh branch off current `origin/main`, one themed commit at a
   time.
6. Prove zero loss: `git diff wip/snapshot-<date> HEAD -- <changed paths>` must
   be empty.

**A dirty checkout can be a restored checkpoint, not unfinished work.** The agent
host commits the whole tree at the start of a turn to
`refs/agents/<session>/checkpoints/turn/<n>`. Those refs are reachable but sit on
no branch, and a tree restored from one reads in `git status` as ordinary
uncommitted work. The tell is the direction of the diff. Measured 2026-08-28, the
shared checkout held 21 changed files that added 132 lines and removed 5,240 -
it deleted about 40 times what it added, because yesterday's content was lying
over today's branch. It was un-writing committed work: a contract field, its
validator, its changelog entry and its fixture, all still on the branch.

Confirm by matching blobs, not by reading the diff. A file that is byte-identical
to a checkpoint is that checkpoint, whatever the timestamps say:

```powershell
git for-each-ref --sort=-committerdate --format='%(committerdate:iso) %(refname)' refs/agents/
git diff <checkpoint-sha> -- .      # empty across the tracked paths means the tree IS that checkpoint
git hash-object <path>              # for untracked files, which the line above ignores
```

Then restore by explicit path. Never `git restore .` (section 8). Discarding
costs nothing here, because the checkpoint ref holds every byte and stays
reachable. Check the untracked files by hash too: the same 2026-08-28 tree
carried a 441 KB `search.ts` at the repo root that was byte-identical to
`state/published.csv`, and a plan-doc that #112 had closed and deleted on
purpose.

**Before deleting a leftover branch**, all three legs must hold: the PR reads
`MERGED` from a live `gh pr view` (not a cached `gh pr list`), its `mergeCommit`
is an ancestor of `origin/main`, and the residual `git diff origin/main <branch>`
is stale content only. A branch tip beyond its PR's `headRefOid` is not
automatically orphaned work - the commit was often rebased under a new SHA. Find
it by subject:
`git log origin/main --oneline --diff-filter=A -- <file the commit created>`.
GitHub keeps `refs/pull/<n>/head` for a merged PR forever, so this is recoverable
either way.

**`git branch --merged` answers "none of them" in a repository that squash-merges,
and that is not the same as "none of them are merged".** A squash rewrites the
branch's commits into one new commit, so no branch tip is ever an ancestor of the
base. Ask whether the branch would still change the base instead. When the merge
result equals the base's tree, the branch contributes nothing:

```bash
main_tree=$(git rev-parse origin/main^{tree})
[ "$(git merge-tree --write-tree origin/main <branch> | head -1)" = "$main_tree" ]
```

**That test has one false negative, and it is the common case for a plan-doc.**
If the branch added a file and the squash added the same file, the merge is an
add/add conflict, so the result tree differs from the base and the branch reads
as unmerged. Compare the blobs before believing it. Identical object ids on both
sides means the content landed verbatim and the branch is stale, not unmerged:

```bash
git rev-parse <branch>:<path> <squash commit>:<path>     # needs MSYS_NO_PATHCONV=1
```

Observed 2026-08-28: one branch of four flagged this way was fully merged and
three genuinely held work. Do not delete on the `merge-tree` verdict alone.

**`git worktree remove` can deregister a worktree and still fail to delete it.**
On Windows the removal stops at the first locked path and reports
`failed to delete ...: Invalid argument`, but the administrative entry is already
gone - so `git worktree list` no longer shows it while thousands of files remain
on disk. The usual holder is a build or watch process started inside that
worktree, which keeps running after its own executable is unlinked. Find the
holder by path rather than guessing:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*<worktree>*' }
```

Read the exit as "partly done" and re-run the filesystem delete after the holder
is gone. Do not re-run `git worktree remove`; it has nothing left to deregister.

**A file you can see in the editor may not be in the repository at all.** The
editor's workspace is the shared checkout, and `TODO/` there collects untracked
plan-docs that were authored but never committed. In a worktree cut from
`origin/main` the file simply is not present, and every git question about it
answers as though it never existed: `git log --all -- <path>` prints nothing,
`git grep <name> origin/main` finds no inbound link, and `git rm <path>` fails.
That reads exactly like "somebody already distilled and deleted this", which is
a different conclusion with a different response. On 2026-08-26 a whole
plan-doc, five sibling plan-docs and every cross-reference between them turned
out to be untracked. Ask before you plan the work:

```powershell
git ls-files --error-unmatch <path>          # "did you forget to git add" = untracked
git -C <the shared checkout> status --porcelain -- TODO/
```

An untracked plan-doc cannot be deleted by a pull request, and there is nothing
to repoint - but its findings still have to reach `docs/`, which is the half
that matters.

**Line endings are pinned, so do not hand-normalise.** `.gitattributes` defaults
every path to `text=auto eol=lf`, then marks known binary formats explicitly.
Future text types therefore use LF without another extension rule, while binary
bytes stay untouched. A blanket normalise pass rewrites files you never touched
and produces a phantom diff of hundreds of lines.

**That normalisation happens at `git add`, and the gates run before it.**
`test_repo_text_is_ascii_and_lf` in `backend/tests/test_contracts.py` reads the
WORKING-TREE bytes of every file under `schemas/`, `config/` and the fixture
directories, and asserts `b"\r\n" not in raw`. A new JSON file authored on
Windows lands CRLF, so the test fails on a file you just wrote and the
`.gitattributes` rule does nothing until the blob is stored. The shared VS Code
setting and `.editorconfig` make normal editor writes LF. File tools, generated
output and PowerShell can bypass both, so write new files LF explicitly before
the first test:

```powershell
[System.IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
```

The same CRLF also breaks a byte-identical round trip, so the contract drift
gate reports a diff in a file whose content never changed.

## Gate commands

**A test's `print()` never reaches you on the default `pytest` run, and `-s`
does not bring it back.** `addopts` is `-q -n auto`, so every run is distributed
and a passing worker's output is dropped. A gate that prints the measurement it
just took reads as a gate that printed nothing - `test_the_ranking_clears_its_bar`
prints the whole retrieval report, and on 2026-08-31 it took three attempts to
see it. Ask for one worker:

```powershell
python -m pytest backend/tests/test_retrieval_eval.py -n0 -s -k clears_its_bar
```

`-p no:xdist` is the wrong reflex. `-n auto` is still in `addopts`, so pytest
exits **4** on an unrecognised argument - and a usage error with no test output
looks like a broken suite rather than a bad flag.

**`ruff` will rewrite a cross-check into the expression it was checking.** A
test that recomputes a value a second way only works while the two expressions
differ. On 2026-08-31 a check written as `zip(stamps, stamps[1:])` against an
implementation using `itertools.pairwise` tripped `RUF007`, whose fix is
`pairwise` - two copies of one expression, a test that passes, and nothing
checked. The lint error is the warning; taking its suggestion is the trap. Write
the second expression in a third form the rule does not name - an indexed
`range(len(x) - 1)` loop here - and say in the docstring why it is not the
obvious one, or the next reader applies the fix.

**`ruff format` is not a gate here, and running it rewrites files you never
touched.** CI runs `ruff check .` only. The tree is not `ruff format` clean, so
`ruff format backend` reformatted 24 unrelated files in one pass on 2026-08-26 -
tests, utilities and modules the change had nothing to do with. Run
`ruff check --fix` for the lint autofixes and leave formatting alone. If a
format pass has already happened, `git restore --` the specific unrelated paths
rather than the tree.

**`npm run bundle-gate` no longer weighs a route against a recorded number.**
Until 2026-08-30 it held every route's first-load JavaScript within 64 bytes of
a hand-maintained record, and about a hundred lines of this page were about
telling that gate's toolchain noise apart from a real change: node 22 against
node 24, a local Windows build against CI's Linux one, a control build of
`origin/main` before drawing any conclusion, and the rule that a locally
measured number must never be recorded. All of it is gone with the gate and with
`frontend/bundle-baseline.json`. What remains has no machine offset: the gate
refuses an encoder on the first-load path, and holds each capped page under its
ceiling in `config/idhazh.json`, which is an absolute limit rather than a
comparison against another build.

**Two builds of the same source disagree on a fifth of `frontend/build/`, and
the cause is a timestamp.** `kit.version.name` defaults to `Date.now()`. It
lands in `_app/version.json`, in the `__sveltekit_<id>` global every prerendered
document names, and through that in the content hash of every chunk filename -
so a byte-identity oracle over `build/` reads as a regression across every dated
page when nothing changed. Measured 2026-08-31 over 380 files: 83 of them
differed between two builds of one tree, and the byte total was identical to the
byte, which is the tell. Normalising the string out before hashing does not
rescue it - only two files carry the literal timestamp, because the rest inherit
it through filenames that moved.

Pin the version for both arms instead, and revert the pin before you commit:

```javascript
version: { name: process.env.BUILD_VERSION ?? Date.now().toString() },
```

With `BUILD_VERSION` set to one constant, the same pair came out 380 files and
158,564,941 bytes with zero differing hashes. The control arm is your own
changed files `git checkout --`'d in place and copied back afterwards, in the
worktree that just built - not a fresh extract of `origin/main`, which brings
its own byte offset from whatever gitignored state differs between the two
trees.

**A `DONE.txt` sentinel beside a `done.txt` output file is the same file.**
Windows filenames are case-insensitive, so a gate script that writes
`ruff check` output to `$out\ruff.txt` and then a sentinel to `$out\RUFF.txt`
silently overwrites the result with the word `RUFF-DONE`. The run looks like it
passed - the sentinel is there, the file exists, and nothing errored - and the
exit code you needed is gone. On 2026-08-26 this destroyed the ruff and mypy
output of a full gate run and cost a second one. Give a sentinel a name that is
not the stem of any output file, such as `SENTINEL.txt`.

**A new pipeline CLI flag may not be named after a llama-server flag.**
`test_every_job_that_starts_a_server_reaches_the_one_argv_builder` reads every
`run:` body in every workflow and fails on any whole-token match against
`llama_server_flags()`, so that the server's argv is built once from `config/`
and never spelled by hand. A stage that wants to be handed the scraped
`/metrics` body therefore takes `--counters-file` and not `--metrics`. The
failure names the step and the flag, so it is quick to read - but only if you
know the guard is about the server's namespace rather than about your stage.

**A path added to `commit-and-push.sh` must already exist in a fresh checkout.**
The script runs `git add "$@"` under `set -euo pipefail` with every path a job
owns in one call, so a file that only appears once its producer has succeeded
turns a producer failure into a failure of the whole commit step - and the other
ledgers staged beside it are lost with it. Ship a new row ledger with its header
committed, and assert the committed header equals the contract's column list.

**A test that runs the real `commit-and-push.sh` will edit your own `state/`
unless every command it hands the script is substituted.** The harness in
`backend/tests/test_workflows.py` executes the shipped script against a
`tmp_path` repository, and any step the script runs as `python -m idhazh <verb>`
resolves its paths off `config.REPO_ROOT`, which is derived from the installed
package rather than from the working directory. So a seven-shard fan-out test
settles the developer's committed ledgers seven times, silently, and the damage
shows up as a dirty tree long after the suite is green. Substitute the command
with a script that takes the tree as an argument - `backend/utilities/settle_ledger.py`
and `backend/utilities/rebuild_day.py` exist for exactly this - and check
`git status --porcelain` after any suite run that exercised the commit step.

## GitHub CLI

**A `workflow_dispatch` cannot reach a workflow that is not on the default
branch.** `gh workflow run <file> --ref <my-branch>` answers
`HTTP 404: workflow <file> not found on the default branch`, even when the file
is committed and pushed on that branch and its `on:` block is correct. GitHub
resolves the workflow id from `main` and only then applies `--ref`. So a row
that ships a new dispatch-only workflow cannot use it to produce anything for
its own pull request; the first dispatch is possible only after the merge.
Measured 2026-08-26 on `backfill.yml`. Plan the row around it rather than
debugging the YAML.

**`gh pr checks --watch` and a bare `gh run watch` open an alternate terminal
buffer** and return nothing an agent can read. Pipe through `Out-String`, or read
the state directly:

```powershell
gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" --jq '.check_runs[]|"\(.name)=\(.status)/\(.conclusion // "-")"'
```

**`gh pr checks --watch` answers about the run it already knew about.** Called
within a few seconds of a push it reports the PREVIOUS run's conclusions, in
full, as `pass` - so a branch that has not been built yet reads green. Observed
2026-08-25 on PR #94 immediately after updating the branch. Bind the question to
the commit instead:

```powershell
$head = gh pr view <n> --repo <owner/repo> --json headRefOid --jq .headRefOid
gh api "repos/<owner>/<repo>/commits/$head/check-runs" --jq '.check_runs[]|"\(.name)=\(.status)/\(.conclusion // "-")"'
```

An empty result means CI has not registered the new head yet, which is a
different answer from `pass` and the one you actually needed.

**"No checks reported" can mean CI never triggered at all, and waiting will not
fix it.** That is a different cause from the empty check-run list above, where
the head is new and the runner is catching up. Here the pull request was opened
against a base stale enough that no workflow ever started for it, so the answer
stays empty for as long as you watch it. Rebase onto current `origin/main` and
push; the push is what starts the run.

Expect that rebase to conflict on `backend/idhazh/contracts/app_config.py`,
because both sides appended to its `changelog` array. Resolve by keeping both
entries, newest first, then regenerate:

```powershell
& <shared venv>\Scripts\python.exe -m idhazh.contracts.export
```

Do not hand-merge `schemas/app-config.schema.json`. It is generated, so editing
it is the anti-pattern the contract drift gate exists to catch, and the export
is one command.

**Deprecation warnings are check-run annotations, not log lines.** Grepping the
log finds nothing. Read them, and always capture a baseline count from a
pre-fix run so the fix can be shown to have done something:

```powershell
gh api repos/<owner>/<repo>/check-runs/<jobId>/annotations
```

**`gh api repos/<owner>/<repo>/actions/jobs/<id>/logs` exits 1 and prints
nothing.** It reads like the job kept no log. The job did; the endpoint answers
with a redirect `gh api` does not follow. Ask through the run instead:

```powershell
gh run view <runId> --repo <owner/repo> --job <jobId> --log
```

**No log of any kind is readable while the run is still going.** The command
above exits 1 with `run <id> is still in progress; logs will be available when
it is complete`, and so does the run-level `gh run view <runId> --log` - even for
a job that finished twenty minutes ago. Redirecting to a file makes this worse,
because the file is then 82 bytes of that sentence and reads like an empty log.
What IS readable mid-run is the artifacts: `gh run download <runId> --name plan`
gives the run plan, and each `items-<n>` and `runtime-log-<n>` appears as its
shard finishes. So to answer "how many items is this run doing?" while it runs,
read `plan.json` rather than the `plan` job's log.

**`gh run download` can exit 0 on a partial artifact.** One download extracted
25 of 37 items and returned success; a second attempt gave all 124 files. Count
what you got against what you expected before you compute anything from it - a
measurement taken from a silently truncated artifact is wrong in a direction
nobody checks.

**`gh pr merge --squash --delete-branch` prints
`fatal: 'main' is already used by worktree` and exits non-zero when any worktree
has `main` checked out - but the server-side merge has already succeeded.**
Verify with `gh pr view <n> --json state` before reacting. Do not retry the
merge. Only `gh`'s local post-merge cleanup was skipped.

**The same command from a DETACHED worktree exits 1 with
`could not determine current branch: failed to run git: not on any branch`, and
both the merge and the branch delete succeeded.** Seen three times on
2026-08-31. Detaching before merging is still right - it is what stops the
branch delete failing - so this exit code is the normal outcome of doing the
right thing, not a fault.

**And the merge can be invisible for a few seconds after it lands.** Also
2026-08-31: `gh pr merge` exited 0, and `gh pr view <n> --json state,mergeCommit`
run immediately afterwards still answered `OPEN` with a null merge commit.
Re-query after doing something else rather than retrying the merge; a second
merge attempt on a merged PR is the one action here that is not idempotent.

**The rule under all three: `gh pr merge`'s exit code says nothing useful.**
`gh pr view <n> --json state,mergeCommit` is the only reliable read, and it needs
a pause before it is reliable either.

**`gh run download` exits 0 on a partial download.** Observed 2026-08-25: one
invocation extracted 25 of 37 items and returned a clean exit code, with no
warning on either stream; an identical re-run gave all 124 files. Nothing in
the output distinguishes the two. Count what landed against what the run
declares before reading any of it:

```powershell
gh api "repos/<owner>/<repo>/actions/runs/<id>/artifacts" --jq '[.artifacts[].name]|length'
(Get-ChildItem <dest> -Directory).Count
```

A count that disagrees is a truncated download, not a missing artifact.
Re-run the download; do not conclude the run produced less than it did.

### The `items-*` artifacts are the only corpus of real article text

Nothing commits an article body - we publish a link and our own summary, never
the source text - so a rule that reads `Article.text` cannot be measured against
`frontend/public/digest/` at all. The measurable corpus is a completed pipeline
run's artifacts:

```powershell
gh run list --repo <owner>/<repo> --workflow digest.yml --limit 5 --json databaseId,conclusion
foreach ($n in 0,1,2,3) { gh run download <run-id> --repo <owner>/<repo> --name "items-$n" --dir "$env:TEMP\corpus\items-$n" }
(Get-ChildItem "$env:TEMP\corpus" -Recurse -Filter '*.article.json').Count
```

Two things bite. **Filter on `status == "ok"`**: a failed article is a real
payload with no `text`, and it deflates every percentage silently - 160 files
were 121 usable articles on the run measured 2026-08-26, a 24 percent
difference. And **artifacts expire**, so a number measured this way carries its
run id, not just its date, or nobody can reproduce it.

Used on 2026-08-26 to tune the lens and event vocabularies before wiring them.
It changed the answer: a candidate list that looked reasonable put one event on
34.7 percent of articles.

### "The evidence expired" is usually wrong - check the artifact AND the job log

A short `retention-days` is not the same as gone. Two independent recoveries,
and it is worth trying both before writing a fixture by hand (Rule #7 wants a
real capture, and a hand-typed one is not):

- **The artifact, if the run is still inside its window.** `runtime-log-*`
  keeps two days, so yesterday's run still hands over the raw bodies:
  `gh run download <run-id> --repo <owner>/<repo> --name runtime-log-3 --dir "$env:TEMP\rt3"`.
- **The job log, which GitHub keeps far longer than any of these artifacts.**
  Anything a step printed is still there:
  `gh run view --repo <owner>/<repo> --job <job-id> --log | Select-String 'llamacpp:'`.
  Get the job ids from
  `gh api "repos/<owner>/<repo>/actions/runs/<run-id>/jobs?per_page=100" --jq '.jobs[]|"\(.id) \(.name)"'`.
  Note the shape: `gh api .../actions/jobs/<id>/logs` returns nothing at all,
  because it redirects to a blob `gh` will not follow. Use `gh run view --job`.

Used on 2026-08-27 to recover four real `/metrics` bodies for the prefill
reconciliation, which is why `tests/fixtures/runtime/` holds captures rather
than something plausible somebody typed.

### An upstream README can be behind the binary

llama.cpp `b10598` publishes `llamacpp:prompt_tokens_cached_total` and describes
`llamacpp:prompt_tokens_total` as "Number of prompt tokens processed, excluding
cached tokens". Its own `tools/server/README.md` at that exact tag carries
neither: not the extra series, and not the four words that decide whether a
number is a read rate or a prompt rate. A field's meaning comes from a capture,
never from the document about it.

When the instrument publishes a derived value beside its inputs, use it as a
free self-check: `llamacpp:prompt_tokens_seconds` is exactly
`prompt_tokens_total / prompt_seconds_total`, so reproducing the gauge from the
counters proves which definition the counter is using, with no second source
needed.

## The Actions cache

**A cache key that does not name what it holds freezes that thing silently.**
`digest.yml` used to cache `backend/models` and `backend/bin` together under
`llm-<MODEL_FILE>-v2`, while the step that fetched the llama.cpp release was
guarded by `if: steps.weights.outputs.cache-hit != 'true'`. On a hit it never
ran, so the server that started was whatever binary happened to be saved the
first time that key was written, and nothing in the run said which one.

The symptom is a step that reads as live code and has not executed for days,
beside a log with no build line in it. Verified 2026-08-25 against runs
`32766098026` and `32772221068`: neither of the eight `runtime-log-*` artifacts
carries a build identifier, so the throughput figures those runs produced (in
[measurements.md](measurements.md)) cannot be attributed to a binary.

**Closed 2026-08-25.** The key now carries `${{ env.LLAMA_CPP_BUILD }}`, the
release is pinned and digest-checked, and each inference job prints the sha256
of its binary and its weights. Kept here because the shape generalises: any
cache key that omits an input the cached bytes depend on turns a fetch step
into dead code and the artifact into an unnamed one.

## The Python environment

**An install on an unsupported interpreter does not fail - it stops
answering.** `pip install -e ".[dev]"` prints no error and no traceback, and
`site-packages` holds `pip` and nothing else. Observed 2026-08-25 on Windows:
the documented `python -m venv .venv` took whatever `python` resolved to, which
was 3.14, and ten minutes later `site-packages` still held only `pip`. Nothing
about it reads as a version problem.

It is deceptive because pip writes nothing into `site-packages` until it has
resolved and built every distribution. A large download, a resolver that keeps
backtracking and a source build all look the same from outside: a venv with only
`pip` in it. The symptom cannot point at a cause.

**A missing wheel is the cause that never resolves itself.** A compiled
dependency ships one wheel per CPython minor. When the minor is missing, pip
falls back to the source distribution and starts a build - `pydantic-core` then
wants a Rust toolchain and `lxml` wants libxml2, and neither prints a line for
minutes. One command tells you which interpreter you are on:

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.version)"
```

**Closed 2026-08-26 at the top end.** `pyproject.toml` now declares
`requires-python = ">=3.12,<3.15.0a0"`, so pip refuses an interpreter it cannot
resolve for, up front, with a message that names the version. The ceiling is
`onnxruntime==1.29.0`: pinned exactly, cp311 through cp314, and no source
distribution at all, so 3.15 cannot install at any price.

**The 3.14 hang was not a missing wheel, whatever it looked like.** Every
per-minor compiled dependency in the resolved set publishes a cp314 wheel for
Windows, the oldest of them uploaded 2026-05-06 - read from the package index on
2026-08-26, after the observation. By elimination a 3.14 install that never
returns is a download or a resolve that is not finishing, and this page already
records a TLS handshake failure against `files.pythonhosted.org`. Do not repeat
the wheel diagnosis without checking the index first.

**On a machine whose only interpreter is outside the bound**, do not fight the
venv. Use the shared checkout's interpreter with `PYTHONPATH` set to your own
worktree's `backend` - the same escape as the `.pth` trap above, and it needs
the same `import idhazh` check before any result is worth reading.

**`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'` in the
shared `.venv` is an ABI mismatch, not a broken install.** Observed 2026-08-28:
`.venv\Scripts\python.exe -V` said 3.14.2 while
`.venv\Lib\site-packages\pydantic_core\` held `_pydantic_core.cp312-win_amd64.pyd`
and 268 other cp312 binaries. The venv had been built against a 3.12 that was
later removed from the machine, so the launcher now runs 3.14 against wheels
compiled for 3.12. Nothing reinstalls or repairs it, because pip sees the
distributions as already present. The one command that names it:

```powershell
Get-ChildItem .\.venv\Lib\site-packages -Recurse -Filter *.pyd |
  Group-Object { ($_.Name -split '\.')[-2] } | Select-Object Name, Count
```

A count under `cp312-win_amd64` while `python -V` says anything else IS the
diagnosis. Build a fresh venv rather than reinstalling into the broken one, and
build it somewhere `git status` cannot see:

```powershell
py -3.14 -m venv "$env:TEMP\yi-venv314"
& "$env:TEMP\yi-venv314\Scripts\python.exe" -m pip install -e ".[dev]" > "$env:TEMP\pip.txt" 2>&1
```

**Redirect that install to a file. Do not pipe it.** `pip install ... | Select-Object -Last 8`
hangs exactly the way piped `pytest` does (recorded under "PowerShell" below), at
low CPU, with the shell prompt never returning - and on a fresh venv it looks
precisely like the resolver stall documented above it.

**From a detached script, the install is not usable when its log says it
finished.** `Start-Process pwsh -WindowStyle Hidden` running `pip install -e
".[dev]"` writes `Successfully installed ...` and then `import idhazh` keeps
failing for minutes, because the redirected log is buffered and the last lines
arrive well before the process exits. Observed 2026-08-31. Only the sentinel the
script writes after the install is the truth, and the cheapest confirmation is
the import itself:

```powershell
& .\.venv\Scripts\python.exe -c "import idhazh; print(idhazh.__file__)"
```

Run that before any schema regeneration, for a second reason as well: it prints
which checkout the editable install points at, and an editable install left over
from the shared checkout answers about a different revision of the package.

## The editor's own search tools

**A workspace search reads the folder VS Code has open, not your worktree.**
`grep_search` and `file_search` are scoped to the workspace root. Given an
absolute path into a worktree outside it they return nothing at all - not an
error, an empty result - and an absolute path into the main checkout silently
answers about a different revision of the file you meant. The tell is a symbol
you know exists reported as absent, or a line number tens of lines off. Read the
file by absolute path instead, or search from a terminal in your own worktree.

**It is unreliable in BOTH directions, and the false positive is newer.** On
2026-08-31 one session got an empty result for a function that was in the file it
named, and, minutes earlier, real matches from a sibling worktree nobody had
asked about. So neither answer is evidence outside the workspace root: an empty
result does not mean absent, and a hit does not mean yours. `git grep -n` from
your own worktree answers both questions and cannot be confused about which tree
it read.

**It can also return a line of code that no longer exists anywhere.** That is a
different failure from the one above: not the wrong revision of a file, but
content that was deleted and is still being served from an index nobody
refreshed. On 2026-08-29 `grep_search` reported
`backend/tests/test_corpus.py:275: assert SummarizeConfig().bands[-1].min_source_words > CAP_WORDS`
- an assertion a merged pull request had already removed. Line 275 of that file
was blank. A worker read it as a live test contradicting the new ladder and
nearly "fixed" a line that was not there.

**The tell is that two search tools disagree**, and the one reading the bytes
wins. `Select-String` found no such line, and `Select-String` was right. Before
editing anything a workspace search pointed you at, confirm the line from the
file:

```powershell
Get-Content <path> | Select-Object -Skip 274 -First 3
```

A hit you cannot reproduce with `Select-String` or `Get-Content` is not there.

**The editor's replace tool deletes whatever the old text held and the new text
drops, and reports success.** It is a literal swap, so a line that sits inside
the matched block and is missing from the replacement is gone with no warning
and no diff to read. On 2026-08-29 a worker matched a block of workflow YAML to
change two steps, omitted an `actions/setup-python` step that happened to sit
between them, and the tool reported a clean edit. Nothing failed until the job
ran. The block was long enough that the omission was invisible in the call.

The cheap catch is one command after every structural edit, before the gates:

```powershell
git diff --stat -- <path>
```

A line count that moved by more than the change you meant is the whole signal.
Prefer a match tight enough to hold only the lines you are changing; a wide
match to "give the tool context" is the thing that makes this possible.

**Inserting a heading can orphan the paragraphs after it, and the diff of what
you inserted looks perfect.** Markdown has no closing tag, so a new `###` takes
ownership of everything below it until the next heading. On 2026-08-31 a new
subsection swallowed the two closing paragraphs of the topic above it; the
inserted text was exactly right and the page had quietly changed what those two
paragraphs were about. Re-read the whole region after any heading insert, not
only the lines you added.

## Hugging Face

**The `ETag` on a weights download is not the SHA-256, and it looks exactly
like one.** Pinning the two configured models on 2026-08-26 meant proving the
bytes at a commit still matched the `sha256` in `config/idhazh.json`. A `HEAD`
on `https://huggingface.co/<repo>/resolve/<commit>/<file>` answers with a
64-character hex `ETag` and the right `Content-Length` - and that hex disagrees
with the recorded digest, because repositories on Xet-backed storage return a
Xet content hash there. Read as a mismatch it says the weights moved, which
would stop a change that is fine.

Ask the pointer instead. `/raw/` at a commit returns the git-LFS pointer text,
and `oid sha256:` in it is the digest of the bytes that URL serves:

```powershell
curl.exe -sS "https://huggingface.co/<repo>/raw/<commit>/<file>"
```

The repository-scoped API answers the same question for the default branch -
`https://huggingface.co/api/models/<repo>?blobs=true` carries `sha` (the head
commit) and each file's `lfs.oid`. **Its revision-scoped form does not**:
`/api/models/<repo>/revision/<commit>?blobs=true` returns `lfs.size` with
`lfs.oid` null, so a check written against it silently compares against
`None`.

## npm

**`npm ci` in a fresh worktree can stop making progress after the tree is
complete.** Observed 2026-08-26 with five agents on one machine: the dependency
tree finished extracting, then the process sat at a constant CPU time for ten
minutes and never wrote its summary. The install is usable long before it exits.
Check before you wait any longer:

```powershell
Test-Path frontend\node_modules\.package-lock.json
(Get-ChildItem frontend\node_modules -Recurse -File | Measure-Object).Count
```

A `.package-lock.json` on disk and a file count at or above the main checkout's
means reification finished. Every tool then runs through `node`
`node_modules/<pkg>/<entry>.js` directly, which needs nothing from `npm`. Do not
conclude the environment is broken, and do not re-run `npm ci` - a second one
contends with the first.

**The inverse also happens: `npm ci` exits 0 and the bins are not resolvable
yet.** Observed 2026-08-29 under parallel load, with `NPMCICODE=0` recorded and
`Test-Path frontend\node_modules\.bin` returning true. The script launched
immediately after died with `'svelte-kit' is not recognized`, and `npm run
check`, `npm run build` and `npm run bundle-gate` all returned 1 in one round -
which reads exactly like a broken lockfile. The identical script passed all
three a minute later. The `.cmd` shims are on disk before a new process can
resolve them. Gate on the specific shim, and never diagnose a toolchain from the
first run after an install:

```powershell
Test-Path frontend\node_modules\.bin\svelte-kit.cmd
```

**`npm ci` can also exit 0 with one package only partly extracted.** The same
day, `aria-query/lib/index.js` was missing from an install that reported success
and surfaced twenty minutes later as `MODULE_NOT_FOUND` inside `vite build`,
reading exactly like a code fault. A second `npm ci` fixed it. Suspect the
install before the source whenever a missing module belongs to a transitive
dependency nothing in the change touched.

## Running the gates

- **A `page.route` answering 500 does not simulate a failed download here.**
  transformers.js only treats a *404* from a same-origin path as a miss. Any
  other status is read as the file: it takes the error body as the model, fires
  its own `done` event for it, and fails about 200 ms later inside the ONNX
  runtime with `protobuf parsing failed`. So the failure is neither where the
  route is nor in the library the route names. Two things follow for any test
  that fakes a model failure. The route is not total - `tokenizer.json`,
  `config.json`, `tokenizer_config.json` and the 21.6 MB ONNX runtime wasm all
  still load, because the pattern matches only `.onnx` - and the file still
  arriving is what made `search.spec.ts`'s retry test flaky, because it reported
  progress after the failure. Fixed in the component on 2026-08-27; the test now
  holds that file back on purpose, so the order is decided instead of raced.
- **Each Playwright test gets its own CacheStorage, so a sibling test cannot
  leave the encoder behind for the next one.** The `page` fixture is a fresh
  browser context, and `caches.keys()` read at the start of a mid-file test on
  2026-08-27 returned `[]`. transformers.js also caches only a 200, so a faked
  error response is never written. When a download-failure test misbehaves, the
  cache and the test order are the wrong suspects - read the trace's network
  list instead, and if the request is in it with the status you faked, the route
  fired and the cache was not consulted.

- **A test that skips itself when it cannot find a control is a gate that turns
  off silently.** `canaries.spec.ts` looked for the old search offer button and
  called `test.skip` when the count was zero, so renaming that control switched
  off an injection canary and the suite still reported green - `2 skipped` in a
  125-line pass list that nobody reads to the end. Observed 2026-08-27. Two
  rules fall out: read the skip count on every suite run and account for each
  one, and write the guard as `await expect(locator, 'why this matters')
  .toHaveCount(1)` rather than a skip whenever the fixture is supposed to
  provide the thing. A skip is right only when the environment genuinely varies;
  it is never right for a selector you control.
- **A CSS length read back off `style` is the browser's serialisation, not the
  string you wrote.** A bar drawn at `inline-size: 100.0000%` reads back as
  `100%`, because the engine drops trailing zeros; every other row in the same
  list, at `52.9412%`, round-trips unchanged. So a Playwright assertion
  comparing the style STRING fails on exactly one row - the full bar - which
  reads like a bug in the one case the arithmetic cannot get wrong. Observed
  2026-08-30 on the console's ranked bars. Compare the number:
  `parseFloat(node.style.inlineSize)` against `Number(expected.toFixed(4))`.
- **`pyproject.toml` already sets `addopts = "-q"`, so your own `-q` gives
  `-qq`** - and `-qq` removes the `N passed` summary line entirely. The run
  then shows progress dots and an exit code and nothing else, which reads like
  a broken collection. Run `pytest` with no quiet flag. Before concluding that
  a missing summary means something is wrong, check `[tool.pytest.ini_options]`.

  **The same `-qq` also changes what `--collect-only` prints, from node ids to
  one count a file.** Measured 2026-08-29 on pytest 9.1.1:
  `pytest --collect-only -q backend/tests/test_evals.py` answers
  `backend/tests/test_evals.py: 57` and nothing else, while the same command
  without the flag lists all 57 node ids. So grepping that output for the test
  you just added finds nothing, and the natural reading - "my test was not
  collected" - is wrong. Either drop your `-q` and grep the node ids, or prove
  it by the count moving by one.
- **A launch that reported nothing still launched.** `Start-Process -Wait`
  returned `Command produced no output` and exit 1 three times on 2026-08-26
  while starting the script every time, so three builds wrote `frontend/build`
  and one output directory at once. Nothing errored. `npm run bundle-gate` then
  measured a half-written tree and put `/console/` at 52,127 B against a real
  130,396 - a number that was one paste away from being recorded as a ceiling.
  Two tells: a page weight that moved by tens of kilobytes with no change to
  match it, and `The process cannot access the file` when you read the output
  back. Before trusting any byte measurement, look for the second build:

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Select-Object ProcessId,CommandLine
  ```

  This is the sharp edge of the "re-issue a command that produced no output"
  rule below: re-issue it only after checking whether the first one is running.
  `frontend/build` is one shared directory, so two builds in it is not a slow
  gate - it is a wrong number that looks like a right one.
- **A page-weight failure is often not yours.** `/archive/` and `/console/` grow
  every time the pipeline publishes, so a red bundle gate on your branch may be
  red on `origin/main` too. Check before you change a number:

  ```powershell
  gh api "repos/miztiik/yen-idhazh/commits/$(git rev-parse origin/main)/check-runs" --jq '.check_runs[]|"\(.name)=\(.conclusion)"'
  ```

  And when the number really is yours, a raise needs a control build of the old
  payload under the new source. See
  [../how-to/run-the-gates.md](../how-to/run-the-gates.md).
- **A Playwright spec cannot import a module that imports `$app/anything`.**
  Playwright's pure-function specs run in Node with no SvelteKit resolver, so a
  spec that reaches into `frontend/src/lib/` fails the *whole suite* at load
  time with `Error: Cannot find package '$app' imported from ...` - not one
  test, all of them, before a single browser opens. Measured 2026-08-27, when
  `assist-guard.spec.ts` started importing the month-index parser and that
  parser lived beside the `fetch` that needs `base`. The fix is a module split:
  the pure half in its own file with no `$app` import, the fetching half
  re-exporting it. The tell is that the error names a *package* rather than a
  test.
- **Run the browser suite through `npm run test:browser` and nothing else.**
  Calling Playwright's own entry point by hand -
  `node node_modules/@playwright/test/cli.js test` - makes every spec fail with
  `Playwright Test did not expect test() to be called here`, followed by
  `No tests found`. It reads exactly like two installed copies of the package,
  and it is not: the `.cmd` shim runs that same file, and `npm run test:browser`
  passes on the identical tree seconds later. Observed 2026-08-31. This is the
  **inverse** of the rule elsewhere on this page about calling a bin with `node`
  rather than through `npx`; that rule is about long-lived servers, and it does
  not extend to the test runner.
- **A new chart component that draws a `<path>` fails a spec about icons.**
  `frontend/tests/icons.spec.ts::no component holds a path of its own` keeps the
  icon set closed by forbidding path data anywhere outside
  `frontend/src/lib/icons/`, and its exemption for chart components is a **name**
  regex. So a component called `WriteTimeHistogram` fails until the name is added
  to that regex, while the existing chart components pass because they draw with
  `line`, `rect` and `polyline` and never needed the carve-out. The failure names
  the icon rule, which is nowhere near the row that caused it.
- **A test that drives the console's window control must wait for hydration
  first.** Every `[data-window-preset]` input is `disabled` in the prerendered
  document and enabled on mount, so a click issued before that lands times out at
  about 15 s with no useful message. `frontend/tests/console-window.spec.ts`'s
  `hydrated()` helper is the pattern:

  ```ts
  await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
  ```
- **Widening a Svelte action's node type to a union breaks its listeners, and
  `svelte-check` reports it far from the change.** `addEventListener` overload
  sets do not merge across element types, so changing
  `action(node: SVGSVGElement)` to `SVGSVGElement | HTMLElement` produced eight
  errors on lines that were not edited. The fix is also the better code: keep one
  `[type, handler]` list and attach it through a single `const events: EventTarget
  = node`, so the add and the remove halves cannot drift apart.
- **A transitioned paint property read straight after `hover()` or `focus()`
  returns an interpolation, not the value it is going to.** A card whose
  `box-shadow` and `border-color` ease over `--dur-fast` reported
  `rgb(86, 78, 230)` against an accent of `rgb(79, 70, 229)`, which reads as the
  wrong colour rather than as the right colour arriving. One
  `requestAnimationFrame` is not enough either - that lands mid-ease. Poll for
  the final value and let the poll be the assertion:

  ```ts
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.querySelector('article.item')!).boxShadow))
    .toBe(resolvedShadowToken);
  ```

  Resolve the token through a throwaway element - set `style.boxShadow` to the
  custom property's value, read the computed string back, remove it - so the
  comparison is against the token rather than against a string somebody typed.
- **`locator.hover()` scrolls the element into view, so a viewport-relative rect
  taken before it and after it says the element moved.** A card asserting "no
  lift on hover" failed with `top` 332 before and 18 after, which reads as a 314px
  jump the CSS does not contain. Take `rect.top + window.scrollY` and
  `rect.left + window.scrollX`, and call `scrollIntoViewIfNeeded()` before the
  rest reading as well. Measured 2026-08-31.

## Git Bash on Windows

**MSYS rewrites any argument that looks like a POSIX path list, so a
`<rev>:<path>` argument never reaches the program.** Git Bash converts `:` to
`;` and `/` to `\` before the process starts. `git show "origin/main:docs/a.md"`
is delivered as `origin\main;docs\a.md`, and git answers
`fatal: Not a valid object name`. Every `<rev>:<path>` form is affected -
`git show`, `git cat-file`, `git rev-parse`, `git diff <rev>:<a> <rev>:<b>` -
and so is any other tool taking a colon-joined argument, such as
`docker run -v <host>:<container>`.

**The damage is done by the quiet version, not the loud one.** With `2>/dev/null`
on the call, the fatal goes nowhere and the command simply writes nothing to
stdout. A comparison built on it then reads the empty stream as content:

```bash
git show "origin/main:$rel" 2>/dev/null | diff -q - "$file"   # always "differs"
git cat-file -e "origin/main:$rel" 2>/dev/null                # always "absent"
```

Observed 2026-08-28 while deciding whether three leftover directories held
unsaved work. Every file was reported as differing from `main` or missing from
it. Both answers were the shell, not the repository; the files were byte-
identical to commits already in history. The failure mode is indistinguishable
from the honest negative answer, which is what makes it expensive.

Two responses, and prefer the second:

```bash
export MSYS_NO_PATHCONV=1                    # disables the rewrite for the shell
git ls-tree <rev> -- <path>                  # no colon, so nothing to rewrite
git hash-object <file>                       # then: git cat-file -e <40-hex sha>
```

**The general rule: when a check decides whether something can be deleted, build
it on an argument the shell cannot rewrite.** A 40-character object id has no
`:` and no `/` in it, so `git hash-object <file>` followed by
`git cat-file -e <sha>` answers "is this content in the repository" through a
path MSYS never touches. That is why it stayed correct on 2026-08-28 while the
`<rev>:<path>` comparison beside it was wrong about 22 files. Reach for the
colon-free form first and the environment variable only as a fallback, because
the variable protects the shell you remember to set it in and nothing else.

## PowerShell

- **One line only.** Multi-line commands are mangled before they reach the
  shell. There is no working heredoc.
- **A mangled here-string leaves the variable holding the PREVIOUS script.** The
  line above says the heredoc does not work; what it does next is the trap. In a
  persistent shell `$s = @'...'@` failing leaves `$s` at whatever the last script
  put there, so `Set-Content new.ps1 -Value $s` writes an old script under a new
  name and runs it successfully, doing the wrong thing. Observed 2026-08-29,
  found only because the launcher printed a `PWD=` line from the previous run.
  Write launcher scripts with the editor's file tool, never from a here-string.
- **`python -c` with a multi-line string is the same trap, and it fails
  silently.** `& python -c "` followed by several lines of Python exits 1 and
  writes a zero-byte file even with `*> out.txt` on it, so it reads exactly like
  the interpreter crashing on the import you were checking. Observed twice on
  2026-08-30 introspecting an installed package. Write the snippet to a `.py`
  file with the editor's file tool and run the file; a single-line `python -c`
  with semicolons works but stops being readable at about three statements.
- **`Start-Process -ArgumentList` splits an element that holds spaces into
  several arguments.** The detached-script pattern below is the right way to run
  `gh`, and passing the command's own arguments through `-ArgumentList` is not.
  Observed 2026-08-31 opening a pull request: a seven-word `--title` came back as
  `unknown arguments ["the" "archive-search" "recall" ...]; please quote all
  values that have spaces`, which reads like a wrong flag rather than a shell
  fault. Do not answer it by adding quotes to the element - the script is already
  detached, so call the program directly inside it and redirect there:

  ```powershell
  & gh pr create --base main --title $title --body-file $body 1> $out 2> $err
  "EXIT=$LASTEXITCODE" | Set-Content -LiteralPath $done
  ```

  Separate `1>` and `2>` rather than `*>`, and read the two files. First try, PR
  URL on stdout.
- **A command that IDLES is killed at 16 to 45 seconds, exit 1, no output.**
  `Start-Sleep`, `Wait-Process -Timeout` and any `while` loop that sleeps between
  probes all return instantly with an empty result. A loop that PRINTS something
  every second or two survives longer, and is still cut eventually. Reported
  independently by four agents on 2026-08-29. The trigger is idleness rather than
  duration, which is why a long `pytest` streaming dots outlives a short sleep.
  The only pattern that holds: a `Start-Process pwsh -WindowStyle Hidden` child
  writing a sentinel file, polled by many separate short calls.
- **A killed redirect leaves the output file present and EMPTY.** `mypy > file
  2>&1` cut at the idle limit exits 1 with a zero-byte file, so `Test-Path` says
  true and `Get-Content` says nothing - which reads exactly like a gate that
  passed silently. Always write `$LASTEXITCODE` into a separately-named `-DONE`
  sentinel and read the sentinel; never infer a pass from an empty log. For the
  same reason, do not chain two long redirects in one call (`ruff > a; mypy > b`
  returned no output and neither file existed afterwards). One long child a call.
- **A log that stops growing is NOT a stalled process.** `*>> $log` from a
  detached script buffers, so the file sits at the same size for minutes while
  the child works. On 2026-08-30 a healthy `pytest` run was killed twice for
  looking frozen at 94 percent; the whole suite is 1,599 tests and 579 s, and
  `backend/tests/test_workflows.py` alone spends minutes in `git` subprocesses
  with nothing to print. Ask the process, not the file:

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object CommandLine -like '*<your worktree>*' |
    Select-Object ProcessId, UserModeTime
  ```

  `UserModeTime` is in 100-ns units, so it climbing between two samples means
  work is happening. Only a value that does not move is a stall.
- **A killed command is indeterminate in both directions.** The same kill left
  `gh pr create` having done nothing at all, and left `git push -u` having pushed
  the branch and skipped only the `--set-upstream`. Neither the exit code nor the
  empty output separates the two. Ask the server: `git ls-remote --heads origin
  <branch>` and `gh pr list --state all --head <branch>`.
- **`Select-String` matches case-insensitively unless you say otherwise**, so a
  search for a constant finds the helper that replaced it. Hunting a merge
  failure on 2026-08-27, `Select-String -Pattern 'INDEX_ROOT'` reported five
  hits in a file whose real content was five `_index_root()` calls, which read
  as "the constant is still there" and pointed the diagnosis at the wrong side
  of the merge for ten minutes. Pass `-CaseSensitive` whenever the question is
  about an identifier.
- **`Select-String` has no `-Recurse`.** Use
  `Get-ChildItem -Recurse | Select-String`, or the editor's own search.
- **`-like` treats `?` as a wildcard, so `-like '??*'` matches everything.**
  Filtering `git status --porcelain` for untracked files with
  `Where-Object { $_ -like '??*' }` returns the modified files too, because `?`
  means "any one character" and not a literal question mark. Observed
  2026-08-28, where it made a staged file read as untracked inside a list that
  was really the whole status. Ask git the question instead -
  `git ls-files --others --exclude-standard` for untracked and
  `git ls-files -- <path>` for tracked - or match with `.StartsWith('??')`,
  which has no wildcard grammar at all.
- **A relative path inside a `[System.IO.File]` call does not follow
  `Push-Location`.** .NET resolves against the process working directory, which
  `Push-Location` does not change. Pass an absolute path, or use
  `Resolve-Path`.
- **A multi-paragraph commit message goes through a file.** Write
  `.tmp_commit_msg.txt` (gitignored), then `git commit -F`. Prefer
  `[System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))`
  over `Set-Content -Encoding utf8`, which prepends a BOM that `git commit -F`
  treats as message content.
- **`git show <ref>:<path> | Set-Content` writes CRLF**, so a following
  `git diff --no-index` reports every line as changed. Compare in memory
  instead. Adding `-NoNewline` is worse, not better: PowerShell splits the git
  output into an array of lines and `-NoNewline` joins them with nothing, so a
  Python file arrives as one line and fails to import while the copy still
  reports success. To put a path back to another revision byte for byte, use
  `git restore --source=<ref> --worktree -- <path>`, which touches no encoding
  and leaves the index alone.
- **`git add -- $paths` with a PowerShell array stages nothing and does not
  say so.** The following `git commit` then lands one file instead of twelve.
  Spell the paths out as separate arguments, and read
  `git diff --cached --name-status` before committing - `git status --short`
  puts a staged change in column 1 and an unstaged one in column 2, and the
  two are one space apart.
- **`npm` and `npx` are not on `PATH` in a freshly spawned terminal.** Use the
  absolute `C:\Program Files\nodejs\npx.ps1`.
- **A sync terminal call can return "Command produced no output" without having
  run.** Parallel agents share one shell, so a sibling's interrupt or an
  unfinished input line swallows yours. Re-issue the identical command before
  believing the result. An empty result is not a failed gate.
- **It can also return another worktree's output, and that is worse than an
  empty one.** An empty result announces itself; a plausible one does not.
  Observed repeatedly on 2026-08-28 and 2026-08-29 with several agents running
  at once - a `git grep`, a pytest tail, a `Get-Process` table - each result
  well formed, each about a sibling's tree. Reasoning about which tree you got
  does not work, because a correct answer about the wrong tree is
  indistinguishable from a correct answer about yours. Tag every command and
  discard anything that does not carry your tag:

  ```powershell
  Write-Host 'MYTAG-014'; Set-Location -LiteralPath '<abs>'; $PWD.Path; <command>
  ```

  Increment the number on every call. Refuse any result whose first line is not
  the tag you just sent, and re-run rather than interpret it. Printing
  `$PWD.Path` catches the same fault a second way.
- **`Set-Location -LiteralPath` to a path that does not exist fails, and every
  command after the semicolon still runs - in the previous directory.** Under
  parallel agents that previous directory is often a sibling's worktree. The tag
  above does not catch it, because the tag is printed before the `Set-Location`
  and so the first line looks right. Observed 2026-08-31 re-verifying a row: the
  worktree had never been created, and `git status` answered about another
  agent's 27 staged files as if they were mine. Gate on the directory rather than
  trusting the change:

  ```powershell
  Write-Host 'MYTAG-015'; $t = '<abs>'; Set-Location -LiteralPath $t; if ($PWD.Path -ne $t) { exit 9 }; <command>
  ```

  Exit code 9 is then unambiguous: the command never ran, rather than running
  somewhere else.
- **A queued command can execute long after you sent it, on top of live work.**
  On 2026-08-29 a `Remove-Item -Recurse -Force .venv` ran about 25 minutes after
  it was issued and deleted `site-packages` under a `pytest` that had started in
  the meantime. The suite froze at a fixed percentage, `python -m pytest
  --version` answered `No module named pytest`, and `import pydantic` still
  worked - a half-deleted environment, which reads exactly like a broken
  toolchain. Never queue a destructive command against a path a later command
  needs. When a suite stalls, check that its interpreter still has its packages
  before you start debugging tests.
- **A foreground `pytest` can be killed mid-run**, with the tool reporting exit
  code 1 and an empty output file - the same shape as a collection error.
  `--collect-only` tells the two apart: a suite that collects cleanly and then
  dies partway through was interrupted, not broken. Run long suites detached and
  poll, which also survives the tool timing out:

  ```powershell
  Start-Process pwsh -WindowStyle Hidden -ArgumentList '-NoProfile','-File','<abs>.ps1'
  ```

  Have that script write its output to one file and its exit code to a
  **second, differently named** sentinel, then poll for the sentinel. Names that
  share a prefix defeat the poll: `Select-String` matches substrings, so a
  pattern written for `PIP_EXIT` also fires on `ENSUREPIP_EXIT` and the run
  reads as finished while it is still going. Anchor the pattern and pick names
  that are not substrings of each other.
- **The launch itself can silently not happen.** On 2026-08-30 a
  `Start-Process pwsh -WindowStyle Hidden ...` returned with no error, no child
  appeared, and the missing gate read as a slow one for two polls. `Test-Path`
  the log file before reading it: false means the script never started, and the
  answer is to send the launch again rather than to keep polling.
- **Write every long gate to a uniquely named file and read the file back.**
  `... *> "$env:TEMP\yi_<row>_pytest.txt"`, then read that file. The terminal
  pane shows whoever spoke last, which may not be you.
- **Read that file through the shell, not through the editor's file reader.**
  The editor serves a cached copy of a path a detached process is still
  writing. On 2026-08-26 a `mypy.txt` the directory listing gave as 160 bytes
  read back as empty three times, which looks exactly like a gate that has not
  finished. Poll for completion by listing the directory for a sentinel the
  script writes last, then `Get-Content <absolute path>`.
- **`pwsh -NoProfile -File <script>.ps1` can exit 1 and do nothing at all** - no
  output, no side effects, no file written. Invoke the script as
  `& '<absolute path>.ps1'` instead.
- **A PowerShell pipe appends CRLF, so a piped `sha256sum --check` manifest
  cannot find its file.** The error names the file with a trailing `$'\r'`.
  Write the manifest LF-only with `[System.IO.File]::WriteAllText` and pass the
  path as an argument. The workflow's own `echo | sha256sum --check` is correct;
  only the local rehearsal of it needs this.

## The integrated browser

- **`document.visibilityState` is `hidden`, so `requestAnimationFrame` never
  fires.** Anything that runs in a mount-time frame callback looks dead here and
  works correctly under Playwright. Verify that class of behaviour with the
  browser suite, not by hand.
- **`locator.scrollIntoViewIfNeeded()` times out on a page that keeps relaying
  out.** Use `page.evaluate` with `scrollIntoView` instead.
- **`locator.click()` cannot succeed here at all**, for the same reason: layout
  is never driven, so Playwright's actionability check waits for an element that
  never becomes stable and then reports `Element is outside of the viewport`.
  Observed 2026-08-27 on the archive's Search button, which renders correctly and
  reads correctly in the snapshot. `{ force: true }` does not help - it fails on
  the viewport check instead of the stability one. Drive it from the DOM, which
  sends the same event a reader does:

  ```js
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Search');
    button.click();
  });
  ```

  Read the error before rewriting the selector: `outside of the viewport` and
  `waiting for element to be visible, enabled and stable` on an element the
  snapshot shows are this quirk, not a broken locator.
- **`getBoundingClientRect()` returns zero width for every element on the
  console.** Layout is not being driven in a hidden page, so a bar that draws
  perfectly still measures 0. The `style` attribute is still correct and still
  worth asserting; take any real geometry from the Playwright suite, where the
  same elements measure normally.
- **Check that the element you grabbed is the one you meant.** On the digest
  page `[data-band]` matches both the `<article>` and the confidence chip inside
  it, so a height measured off the wrong one is silently wrong. Target
  `span[data-band]`.
- **A zero-width rect does not only measure wrong - it makes correct code look
  broken.** The entry above is about a number you read. This is about a number
  the page reads: any guard that returns early on a zero or negative
  `getBoundingClientRect().width` - a chart that will not draw without a frame,
  a readout that will not place itself - takes that branch every time here. The
  feature then does nothing at all, which reads as a bug in the feature rather
  than a property of the host. Confirm it in the Playwright suite before
  changing the guard.
- **The host swallows a real `Escape` keypress**, so
  `page.keyboard.press('Escape')` closes nothing and a dismiss handler reads as
  unwired. Dispatch it inside the page, where it reaches the same listener a
  reader's key does:

  ```js
  await page.evaluate(() =>
    document.activeElement.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    )
  );
  ```

- **Under load from parallel workers the integrated browser may refuse to
  connect at all.** `open_browser_page` times out at 30 s and every following
  `read_page` or `run_playwright_code` fails with
  `browserType.connectOverCDP: Timeout 30000ms exceeded`, repeatedly - which
  reads as a broken build rather than a busy host. Do not keep retrying. Drive
  Chromium through Playwright yourself for the same evidence section 12 asks
  for: console errors, any response at status 400 or above, `route.abort()` for
  the degraded case, and element screenshots. That path also drives layout, so
  every quirk above stops applying. Note a script written to `TEMP` resolves
  modules from `TEMP`, so `require()` Playwright by its absolute path inside the
  worktree's `node_modules` or it fails `MODULE_NOT_FOUND`.

## Serving a build to measure it

- **`python -m http.server` serves `.js` with the Windows registry MIME type**,
  which is often `text/plain`. The browser refuses the module, SvelteKit never
  hydrates, and the page still looks right and still logs zero errors. Every
  post-hydration measurement then reports the prerendered value: on 2026-08-25 a
  chart's `viewBox` read back as the SSR fallback and looked 373 px wrong. If
  you use it, assert hydration first - `Object.keys(window).some(k => k.startsWith('__sveltekit'))`
  must be true before any measured number is worth reading.
- **`vite preview` can take about a minute to bind when several agents are
  building at once, and sometimes never binds at all.** It prints its `Local:`
  line only once it is listening, so poll for that line rather than assuming a
  silent process has failed. Playwright's own `webServer` starts it fine.
- **Playwright's preview port comes from `PREVIEW_PORT`, default 4173.** Set it
  per worktree before running the browser suite. Two agents on one port do not
  collide loudly: `reuseExistingServer` is on outside CI, so the second one
  silently tests the first one's bytes.
- **A killed Playwright run leaves that server behind, and it poisons the next
  run.** `reuseExistingServer` then adopts a server whose asset map predates your
  rebuild, so the page loads and every hashed asset 404s. Observed 2026-08-31:
  39 failures in 74 tests, across specs the change never touched, **every one of
  them a timeout at the same 15.6 s**. That identical duration across unrelated
  specs is the tell - a real regression fails in different ways at different
  points. One spec re-run on a fresh `PREVIEW_PORT` passed 7 of 7 in 11.9 s.
  Always take a fresh port before diagnosing a wide, uniform failure.
- **`vite preview --outDir build` still serves static assets out of
  `.svelte-kit/output/client`.** So the section 12 step-5 check - delete the
  page's data file and confirm it degrades - fails to prove anything if you only
  remove the file from `build/`: the page loads it anyway and the smoke reads as
  a pass. On 2026-08-27 that took two attempts to spot, because the served copy
  came back HTTP 200 with the directory renamed. Hide every copy -
  `build/`, `.svelte-kit/output/client/` and `static/` - and clear the browser
  cache through CDP (`Network.clearBrowserCache` plus
  `Network.setCacheDisabled`), or the second reload is served from memory.
  Expect `vite preview` to die with an unhandled `ENOENT` when a file it is
  streaming disappears; that is the server, not the page.
- **`vite build --outDir <other>` does NOT move the site. `adapter-static`
  writes `build/` whatever vite is told**, so a second arm built "somewhere
  else" silently overwrites the arm you were about to measure. On 2026-08-31 an
  empty-ledger control asked for `build-empty`, and `build-empty` was never
  created while `build/` quietly became the control - which is only visible if
  you check the output rather than the exit code. Rebuild the real site straight
  afterwards, and never take a bundle-gate reading on a tree you did not build
  in that same step.
- **A `route.abort()` or `route.fulfill(404)` arm that intercepted NOTHING is a
  null result, not a pass.** The console routes inline their whole seed and
  fetch nothing at runtime but a font, so on 2026-08-31 a degraded arm over
  `**/telemetry/**` reported zero errors with an intercept count of zero on all
  three routes - a clean pass that tested nothing. Print the count and refuse to
  read the arm at zero. The honest degraded arm for a build-time surface is the
  root-override one: copy `state/` and `frontend/public/` to `TEMP`, truncate
  every CSV to its header line, point `STATE_ROOT`, `TELEMETRY_ROOT` and
  `DIGEST_ROOT` at the copy, and rebuild. With an empty seed the runtime fetch
  then does fire, and the intercept count comes back at one.

## Measuring with the committed encoder

- **The committed `tokenizer.json` bakes in truncation and padding, so every
  length you measure off it is the same number.**
  `frontend/static/assist/models/.../tokenizer.json` carries
  `"truncation": {"max_length": 128}` and a fixed `"padding": {"Fixed": 128}` as
  top-level keys in the file. `Tokenizer.from_file(path).encode(text)` therefore
  returns exactly 128 ids for a six-word headline and for a two-thousand-word
  article alike. Nothing errors, and a p50, a p95 and a max that are all the same
  power of two look like a narrow distribution rather than a broken instrument.
  `backend/idhazh/embed.py` already overrides both, which is why no committed
  vector was ever affected - but a measurement that builds its own tokenizer
  inherits them. Switch both off first:

  ```python
  tok.no_truncation()
  tok.no_padding()
  ```

  Diagnose in one line with
  `json.loads(Path(f).read_text())["truncation"]`.

- **The unknown-token share does not detect text the encoder cannot read.** The
  vocabulary holds single Devanagari, Arabic and Cyrillic characters as subword
  pieces, so a Hindi sentence tokenises to an `[UNK]` share of 0.008 and an
  Arabic one to 0.000 - each spelled out one character at a time. What the
  vocabulary lacks is the words, not the letters, so the share reads as a clean
  bill of health for an item no query will ever retrieve. Measure the share of
  `str.isalpha()` characters whose `unicodedata.name` begins `LATIN` instead;
  that is what `assist.min_readable_letter_share` gates on. Measured 2026-08-26
  over 1889 committed items the result is two points with nothing between them:
  3 items at 0.0 and the next lowest at 0.9975.

## Building a page of a chosen length

- **`trafilatura` drops a paragraph it has already seen, so a fixture built from
  one repeated sentence is not the length the test believes.** A synthetic page
  of 320 copies of one sentence extracts to about 150 words, and it does that
  whether the page holds 30 copies or 3000. Nothing errors, and the test then
  asserts a length band the article never reached. Give every copy its own
  ordinal - `f"Item {index}. {SENTENCE}"` - and the count tracks: measured
  2026-08-26, 320 unique sentences of 12 words extracted to 3783 words against
  3840 asked for, while the identical-sentence version of the same page gave
  121.

- **Count the prefix.** A sentence of ten words plus an `Item N.` ordinal is
  twelve words, and sizing on ten undershoots every fixture by a fifth.

## The canary build

- **`npm run build:canary` does not build the canary day, and the browser suite
  dies at COLLECTION without it.** On a fresh worktree the whole suite fails
  before a single test runs, with
  `Error: ENOENT: no such file or directory, scandir '<worktree>\backend\var\canary\digest'`
  attributed to `console.spec.ts:33` - three specs read the canary tree at module
  scope, so it reads like three broken tests and is one missing directory.
  `npm run build:canary` exits 1 and prints five words of hint. Two commands, in
  this order, and the first needs the venv's Python on `PATH`:

  ```powershell
  & .\.venv\Scripts\python.exe backend/utilities/build_canary_day.py
  cd frontend; npm run build:canary
  ```

  Run it before the suite, not after a red one. `backend/var/` is gitignored, so
  every fresh worktree pays this and CI pays it on every run - which is why
  `ci.yml` runs `build:canary` immediately before `test:browser`.

- **There are two builds and they are for different questions. Do not swap
  them.** `npm run build` makes the real site, and that is the tree a page-weight
  ceiling is measured on. `npm run build:canary` makes the fixture site, and that
  is the tree the browser suite asserts against - `ci.yml` runs
  `build_canary_day.py`, then `build:canary`, then `test:browser`, in that order.
  Running the suite against a real build fails about sixteen canary tests for
  reasons that have nothing to do with your change, and reading a ceiling off a
  canary build measures a fixture. They share one output directory, so whichever
  ran last is what is on disk: rebuild the real site before any byte reading, and
  rebuild the canary before any suite run.

- **`build_canary_day.py` used to append to the canary ledgers instead of
  replacing them.** Running it a second time doubled every feed-health row, and
  by the fifth run `canary-gone` had five failures, crossed
  `collect.quarantine_after_failures`, and failed the unrelated "marked rested"
  browser test - a red suite on a developer machine, in code nobody had touched,
  while CI stayed green because its `backend/var/` is empty every run.
  **Fixed 2026-08-24**: the builder clears `--state` before writing, so the
  canary day is a function of that file rather than of how many times somebody
  has run it. Nothing needs deleting by hand any more. Kept here because the
  shape of the trap generalises - a fixture builder that is not idempotent turns
  every later gate into a coin toss.

- **A route that reads a ledger the canary does not write can only be tested
  empty, and an all-green suite hides it.** Seen 2026-08-31 building the Machine
  route: `build-canary.mjs` wrote no `runtime-counters.csv`, so every panel of
  the new route rendered its empty state, every browser assertion passed, and
  the suite proved nothing about the nine panels. An empty state passing is a
  **null result**, not a pass. Before writing a browser spec for a new route,
  open `frontend/scripts/build-canary.mjs` and confirm it writes the ledger the
  route reads; if it does not, add a writer there first. Make the fixture
  contain the case you are claiming - the counters canary deliberately gives
  shard 0 every host cell and shard 1 none, so both the instrumented and the
  silent path are asserted.

- **Keep the canary's column list and the contract in the same test.**
  `build-canary.mjs` hardcodes `const COUNTER_COLUMNS = [...]`, which drifts
  silently from `RuntimeCountersRow.csv_columns()` and only shows up as a route
  that renders empty for no visible reason. `backend/tests/test_contracts.py`
  now reads that array out of the `.mjs` with a regex and compares it to the
  model.

## A clean merge is not a working merge

- **A branch that deletes a name, merged with a `main` that added callers of
  it, merges without a single conflict and fails at import time.** Seen
  2026-08-27: `feat/search-reads-the-index` replaced the module constant
  `cli.INDEX_ROOT` with `cli._index_root()`, derived from `PUBLIC_ROOT`, and
  removed every test that patched the constant. `main` then added eleven tests
  that patch it. Git took the branch's `cli.py` and main's tests, reported
  "Merge made by the 'ort' strategy", and eleven tests failed with
  `AttributeError: module 'idhazh.cli' has no attribute 'INDEX_ROOT'`. Nothing
  in the merge output hinted at it.
- **Read the failure before blaming your own change.** All eleven named one
  attribute and none of them touched the surface the row was about. A whole
  file of failures with one identical `AttributeError` is a rename that crossed
  a branch, not a bug you wrote.
- **Whoever merges owns the semantic conflict, not the branch author.** The fix
  belongs in the merge commit, and it has to be checked rather than assumed:
  here every site already patched `PUBLIC_ROOT` at `tmp/public/digest` on the
  line above, and `_index_root()` returns `PUBLIC_ROOT.parent / "assist" /
  "index"`, so deleting the line preserved the identical isolation. Confirm the
  replacement resolves to the same value before removing anything.
- **Delete repeated identical lines with a script that asserts the count**, not
  with an edit tool. Four sites carried byte-identical text, so an editor match
  is ambiguous and a silent partial edit looks like a fix. Assert the expected
  count before and `not in` after.
- The cheap early warning: after any merge into a long-lived feature branch,
  `git grep` the names that branch deleted. `git diff --name-only main...HEAD`
  tells you which files to look in.
- **GitHub can do this to you when nobody ran a merge at all.** Seen 2026-08-27
  on `main` itself: #186 deleted `assets_in_day` from `render/write.py`,
  correctly, because it had no remaining caller. #166 then landed
  `tests/test_published_assets.py`, which imports it. Neither pull request
  touched a line the other did, both were green, both merged, and the result
  could not collect its test suite - an ImportError at collection aborts the
  run, so zero of the 1,288 tests executed. Two green checks, one red `main`,
  and no merge conflict anywhere.
- **A green check on a pull request is not a statement about `main`.** GitHub
  does not re-run a pull request's checks when the base moves under it, so the
  result you are reading describes a base that may no longer exist. That gap is
  the whole hazard: #186 landed in it, between the run that passed on #166 and
  the press that merged #166.
- The check that closes the gap, before merging anything into a base that has
  moved: merge `origin/main` into the branch locally and run the suite on the
  merged tree. It is the only thing that tests the tree the merge will actually
  produce. When that is too slow to do per pull request, the narrow version is
  `git log --oneline -S '<name>' origin/main` for each symbol the branch newly
  imports - if the newest commit named there is the one that deleted it, the
  green check is already stale.

## Two heavy gates on one box turn a green commit red

- **The symptom arrives long before the cause: a backend suite that costs 10.1x
  what CI charges for it, and a browser suite that fails on a commit CI has
  already passed.** Measured 2026-08-30 on one Windows 11 developer machine, 12
  logical CPUs, 31.8 GiB RAM. The same 1,675 tests ran in 62.68 s in CI and
  630.55 s here, and eight local runs that day spanned 452.13 to 1,098.04 s.
  Three browser suites started at once took 5.3, 5.5 and 8.0 min against 3.6 to
  4.0 min alone, and the 8.0 min run reported 11 failures, the first of them a
  three-minute timeout in `search.spec.ts` - on specs byte-identical to
  `origin/main`, on a commit CI had passed. Nothing was broken.
- **The cause is that nothing coordinates the gates.** Several agents work in
  their own worktrees on one machine and each starts `pytest`, `npm run build`
  or `npm run test:browser` the moment it is ready. During the three overlapping
  suites the host sat at 98 to 100 percent CPU with the disk at or below 2
  percent and at least 6.3 GiB of memory free, and fell to 30 percent as soon as
  they exited. It is the cores. It is not paging and it is not the disk.
- **`backend/utilities/gate_lock.py` runs one of those three at a time.** It
  takes a lock file in the user temp directory, runs the command you gave it,
  and releases. Wrap the gate itself, not the shell around it:

  ```powershell
  python backend/utilities/gate_lock.py -- python -m pytest
  python backend/utilities/gate_lock.py -- npm run build
  python backend/utilities/gate_lock.py -- npm run test:browser
  ```

  It imports nothing from `idhazh` and reads no configuration, so any supported
  Python runs it from a fresh clone. `ruff`, `mypy`, `svelte-check`,
  `shellcheck` and `bundle-gate` stay unwrapped - serialising a gate that
  finishes in seconds only adds waiting. A blocked caller prints the holder's
  pid, worktree, command and held-for seconds every 30 s, so "what is running?"
  is answered without asking anybody. **The held-for figure counts from the
  second the lock was won.** Until 2026-08-30 the record carried the second the
  caller started, so a caller that had queued five minutes for the lock was
  reported to the next waiter as having held it for five minutes - one worktree
  read another's one-second-old lock as "held for 324 s".
- **It cannot fail your gate, by design.** A lock whose pid is gone is
  reclaimed and the reclaim is logged; a lock past `--stale-after` (7,200 s,
  which is 6.6x the longest gate measured here) is reclaimed whatever its pid
  says; and a caller that waits out `--timeout` runs the command unlocked rather
  than returning an error. A scheduling aid that can manufacture a red gate is
  worse than the contention it removes. **A create the operating system refuses
  is part of that promise, and was not until 2026-08-30.** On Windows a name
  whose last handle is closing is "delete pending", and every create on it is
  refused with access denied rather than with "it already exists" - measured
  that day, 36 of 50 rounds at 20 callers on one lock had a caller die with a
  traceback out of the create and a non-zero exit, 61 callers of 1,000. A lost
  create is now a lost create, whichever of the two the operating system says.
- **CI never takes it.** The tool reads the `CI` variable a GitHub runner sets
  and runs the command straight through, so a runner - one job alone on its own
  machine - behaves exactly as it did before. Any test that drives the tool must
  clear `CI` from the child environment, or it measures the carve-out instead of
  the lock.
- **`os.kill(pid, 0)` is not a liveness probe on Windows.** CPython routes every
  signal except the two console events to `TerminateProcess`, so the textbook
  probe can kill the process it was only asking about. Measured 2026-08-30 on
  CPython 3.14.2 the child did survive it - but this repository supports 3.12
  through 3.14 and a tool that guards other people's test runs may not rest on
  which one somebody installed. `gate_lock.pid_alive` calls `OpenProcess` and
  then `WaitForSingleObject` on Windows instead, and there is a second trap
  inside that one: **`OpenProcess` still opens a handle for a process that has
  already exited**, for as long as anything holds a handle to it, so the open on
  its own reads a dead process as alive. Only the wait separates them - 258
  (`WAIT_TIMEOUT`) is running, 0 is exited.
- **Windows will not start `npm` from a bare name.** `subprocess.run(["npm",
  ...])` raises `FileNotFoundError`, because the loader appends `.exe` and never
  `.CMD`, while the identical call runs from the full path `shutil.which("npm")`
  returns (`C:\Program Files\nodejs\npm.CMD` here). Measured 2026-08-30.
  Resolving with `shutil.which` also keeps the run off a shell, so nothing in
  the command line is ever read as a shell operator.
- **`mypy` only checks the platform branch you are standing on, so a green local
  type gate says nothing about the other one.** It skips a block guarded by
  `if sys.platform == "win32":` when it is not running on Windows, and CI runs
  on Linux - so the Windows half of any platform split is checked by your
  machine alone, and the POSIX half by CI alone. Worse, the narrowing is
  statement-only: `os.O_BINARY if sys.platform == "win32" else 0` passed on
  Windows and failed CI with `Module has no attribute "O_BINARY"`, while the
  same test written as an `if`/`else` block passes both. Run
  `mypy --platform linux` before you push anything with a `sys.platform` in it -
  it reproduced the CI failure exactly, in one command, and it needs a separate
  `--cache-dir` or it fights the ordinary run for the cache.

- **A new CLI flag anywhere under `backend/` can fail a test in a file you have
  never opened, and only the full suite finds it.**
  `test_summarize.py::test_exactly_one_function_spells_a_llama_server_flag`
  holds a closed-world set of the files allowed to spell an inference-server
  flag, and it searches every `backend/**/*.py` for the quoted flag string. A
  `--poll` on this lock - a name the server also uses - failed it at 84 percent
  of the suite after `ruff`, `mypy`, the targeted file and the whole first CI
  round had all passed. Rename off that namespace (`--retry-every` here); a
  longer flag with the same prefix does not match, because the test looks for
  the closing quote too. Before adding any flag, run
  `git grep -n '"--<your flag>"' -- backend`.
- **Killing a queued `gate_lock` build leaves the tree unservable, and the next
  error names the wrong thing.** The waiter and the build it wraps are one
  process tree, so killing the wrapper can land after `vite build` has already
  cleared `.svelte-kit/output/`. `vite preview` then exits with
  `Server files not found at ...\.svelte-kit\output\server, did you run build
  first?`, which reads as a broken install on a checkout that built cleanly
  minutes earlier - and `frontend/build/` is still there and still looks
  complete, which is what makes it convincing. The fix is one more
  `npm run build`. Measured 2026-08-31. Prefer letting a queued gate finish;
  if you do kill one, rebuild before serving anything.

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the commands these traps interfere with.
- [../how-to/ship-a-pr.md](../how-to/ship-a-pr.md) - the PR lifecycle the git and `gh` entries serve.
- [documentation-structure.md](documentation-structure.md) - the routing rule that sends a lesson here rather than into private memory.
- [../../CLAUDE.md](../../CLAUDE.md) - section 5 (Documentation Discipline).
