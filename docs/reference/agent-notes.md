# Agent Notes

**Last Updated**: 2026-08-26

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

**That normalisation happens at `git add`, and the gates run before it.**
`test_repo_text_is_ascii_and_lf` in `backend/tests/test_contracts.py` reads the
WORKING-TREE bytes of every file under `schemas/`, `config/` and the fixture
directories, and asserts `b"\r\n" not in raw`. A new JSON file authored on
Windows lands CRLF, so the test fails on a file you just wrote and the
`.gitattributes` entry that covers it does nothing until the blob is stored.
Write new files LF explicitly:

```powershell
[System.IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
```

The same CRLF also breaks a byte-identical round trip, so the contract drift
gate reports a diff in a file whose content never changed.

## Gate commands

**`ruff format` is not a gate here, and running it rewrites files you never
touched.** CI runs `ruff check .` only. The tree is not `ruff format` clean, so
`ruff format backend` reformatted 24 unrelated files in one pass on 2026-08-26 -
tests, utilities and modules the change had nothing to do with. Run
`ruff check --fix` for the lint autofixes and leave formatting alone. If a
format pass has already happened, `git restore --` the specific unrelated paths
rather than the tree.

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

## The editor's own search tools

**A workspace search reads the folder VS Code has open, not your worktree.**
`grep_search` and `file_search` are scoped to the workspace root. Given an
absolute path into a worktree outside it they return nothing at all - not an
error, an empty result - and an absolute path into the main checkout silently
answers about a different revision of the file you meant. The tell is a symbol
you know exists reported as absent, or a line number tens of lines off. Read the
file by absolute path instead, or search from a terminal in your own worktree.

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

## Running the gates

- **`pyproject.toml` already sets `addopts = "-q"`, so your own `-q` gives
  `-qq`** - and `-qq` removes the `N passed` summary line entirely. The run
  then shows progress dots and an exit code and nothing else, which reads like
  a broken collection. Run `pytest` with no quiet flag. Before concluding that
  a missing summary means something is wrong, check `[tool.pytest.ini_options]`.

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
- **A sync terminal call can return "Command produced no output" without having
  run.** Parallel agents share one shell, so a sibling's interrupt or an
  unfinished input line swallows yours. Re-issue the identical command before
  believing the result. An empty result is not a failed gate.
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
- **`getBoundingClientRect()` returns zero width for every element on the
  console.** Layout is not being driven in a hidden page, so a bar that draws
  perfectly still measures 0. The `style` attribute is still correct and still
  worth asserting; take any real geometry from the Playwright suite, where the
  same elements measure normally.
- **Check that the element you grabbed is the one you meant.** On the digest
  page `[data-band]` matches both the `<article>` and the confidence chip inside
  it, so a height measured off the wrong one is silently wrong. Target
  `span[data-band]`.

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
