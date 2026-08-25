# Agent Notes

**Last Updated**: 2026-08-25

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

`.tmp_*` is gitignored, so the patch file never lands in a commit.

**`origin/main` moves under you.** The scheduled pipeline pushes `plan:` and
`digest:` commits to `main` several times an hour, and the editor auto-fetches.
A branch created "from `origin/main`" and a merge done "against `origin/main`"
minutes apart can disagree on `state/*.csv` purely because the tip moved. Run
`git rev-parse origin/main` immediately before branching and again before
pushing. A `git diff main origin/main` that is non-empty right after a
successful `--ff-only` means it moved again.

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

**Before deleting a leftover branch**, all three legs must hold: the PR reads
`MERGED` from a live `gh pr view` (not a cached `gh pr list`), its `mergeCommit`
is an ancestor of `origin/main`, and the residual `git diff origin/main <branch>`
is stale content only. A branch tip beyond its PR's `headRefOid` is not
automatically orphaned work - the commit was often rebased under a new SHA. Find
it by subject:
`git log origin/main --oneline --diff-filter=A -- <file the commit created>`.
GitHub keeps `refs/pull/<n>/head` for a merged PR forever, so this is recoverable
either way.

**Line endings are pinned, so do not hand-normalise.** `.gitattributes` sets
`text eol=lf` on every authored file type. A tool that writes CRLF is normalised
when git stores the blob. A blanket normalise pass rewrites files you never
touched and produces a phantom diff of hundreds of lines.

## GitHub CLI

**`gh pr checks --watch` and a bare `gh run watch` open an alternate terminal
buffer** and return nothing an agent can read. Pipe through `Out-String`, or read
the state directly:

```powershell
gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" --jq '.check_runs[]|"\(.name)=\(.status)/\(.conclusion // "-")"'
```

**Deprecation warnings are check-run annotations, not log lines.** Grepping the
log finds nothing. Read them, and always capture a baseline count from a
pre-fix run so the fix can be shown to have done something:

```powershell
gh api repos/<owner>/<repo>/check-runs/<jobId>/annotations
```

**`gh pr merge --squash --delete-branch` prints
`fatal: 'main' is already used by worktree` and exits non-zero when any worktree
has `main` checked out - but the server-side merge has already succeeded.**
Verify with `gh pr view <n> --json state` before reacting. Do not retry the
merge. Only `gh`'s local post-merge cleanup was skipped.

## The Actions cache

**The cache key names the weights, so the runtime is frozen to a binary nobody
named.** In `digest.yml` the `work` job caches `backend/models` and
`backend/bin` together under `llm-<MODEL_FILE>-v2`, and the `route` job does the
same under `llm-<ROUTE_FILE>-v2`. The step that asks the GitHub API for the
newest `llama-b<N>-bin-ubuntu-x64` release is guarded by
`if: steps.weights.outputs.cache-hit != 'true'`. On a hit it never runs. The
server that starts is whatever `llama-server` was saved the first time that key
was written, and nothing in the run says which one that is.

The symptom is a step that reads as live code and has not executed for days,
beside a log with no build line in it. Verified 2026-08-25 against runs
`32766098026` and `32772221068`: neither of the eight `runtime-log-*` artifacts
carries a build identifier. Two runs a cache apart may share a binary or may
not, and the workflow gives no way to tell. Do not assert either. The throughput
figures those runs produced are in
[measurements.md](measurements.md).

## PowerShell

- **One line only.** Multi-line commands are mangled before they reach the
  shell. There is no working heredoc.
- **`Select-String` has no `-Recurse`.** Use
  `Get-ChildItem -Recurse | Select-String`, or the editor's own search.
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
  instead.
- **`npm` and `npx` are not on `PATH` in a freshly spawned terminal.** Use the
  absolute `C:\Program Files\nodejs\npx.ps1`.

## The integrated browser

- **`document.visibilityState` is `hidden`, so `requestAnimationFrame` never
  fires.** Anything that runs in a mount-time frame callback looks dead here and
  works correctly under Playwright. Verify that class of behaviour with the
  browser suite, not by hand.
- **`locator.scrollIntoViewIfNeeded()` times out on a page that keeps relaying
  out.** Use `page.evaluate` with `scrollIntoView` instead.
- **`getBoundingClientRect()` returns zero width for every element on the
  console.** Layout is not being driven in a hidden page, so a bar that draws
  perfectly still measures 0. The `style` attribute is still correct and still
  worth asserting; take any real geometry from the Playwright suite, where the
  same elements measure normally.
- **Check that the element you grabbed is the one you meant.** On the digest
  page `[data-band]` matches both the `<article>` and the confidence chip inside
  it, so a height measured off the wrong one is silently wrong. Target
  `span[data-band]`.

## The canary build

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

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the commands these traps interfere with.
- [../how-to/ship-a-pr.md](../how-to/ship-a-pr.md) - the PR lifecycle the git and `gh` entries serve.
- [documentation-structure.md](documentation-structure.md) - the routing rule that sends a lesson here rather than into private memory.
- [../../CLAUDE.md](../../CLAUDE.md) - section 5 (Documentation Discipline).
