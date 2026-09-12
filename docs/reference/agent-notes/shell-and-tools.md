# Agent Notes - Shell and Tools

**Last Updated**: 2026-09-12

Traps in PowerShell, MSYS, the editor's own file and search tools, the Python
environment, npm and the libraries that lie about what they returned. Index and
scope: [../agent-notes.md](../agent-notes.md).

## PowerShell

**Send one line.** The terminal tool takes a single command; a multi-line block is not reliably delivered. Chain with `;`, and write anything longer to a `.ps1` with the file-creation tool and run the file. There is no heredoc: a multi-line here-string sent as one command arrives mangled, and the variable then holds the PREVIOUS script - which runs happily and answers the previous question, found on 2026-08-29 only because the launcher printed a `PWD=` line from the run before. The same applies to `python -c` with a multi-line string; it exits 1 and writes a zero-byte file even with `*> out.txt` on it, which reads exactly like the interpreter crashing on the import you were checking.

**`[System.IO.File]` resolves a relative path against the process directory, not the shell's.** `Set-Location` and `Push-Location` move the PowerShell location only, so `WriteAllText('docs/x.md',...)` lands in whatever directory the host started in - usually the shared checkout, so an edit meant for a worktree silently modifies `main`. Two tells: a size that matches the file before your edit, and a `git status` that is dirty in the OTHER checkout. `Get-Content` and `Select-String` are unaffected, because PowerShell resolves their paths itself. Always pass an absolute path, or call `[IO.Directory]::SetCurrentDirectory($w)` right after the `Set-Location`. Fourth sighting 2026-09-10, on a READ rather than a write: `ReadAllText` on a relative path returned the shared checkout's copy of a file just edited in the worktree, which reads as an edit that did not apply and cost 20 minutes.

**A function that logs with `Write-Output` returns the log as part of its value.** Every uncaptured expression joins the return value, so a caller doing `if (Test-Thing) { }` tests a non-empty array and always takes the true branch. On 2026-09-09 a build-hash oracle printed `IDENTICAL=` with nothing after it for that reason, and the two arms agreed only because the second build had failed and the helper hashed the first build's leftover file. Log with `Write-Host`, return exactly one object, and return an explicit sentinel on failure rather than falling through.

**`Start-Process -Wait` does not set `$LASTEXITCODE`.** It stays at whatever the last native command left, so a failing child reads as success and a timed-out wait looks like a finished one. Capture the process:

```powershell
$p = Start-Process -FilePath pwsh -ArgumentList '-NoProfile','-File','x.ps1' -Wait -PassThru; $p.ExitCode
```

**`Start-Process pwsh -Wait` can also report exit 1 while the child succeeded and is still running** - six times in one row on 2026-09-02, every time on a child that finished cleanly. Re-launching on that code starts a second copy of the work against the same output files, which is the real damage. Believe the child's own sentinel, not the parent's code.

**`Start-Process -ArgumentList` splits an element that holds spaces.** A seven-word `--title` came back from `gh` as `unknown arguments [...]`, which reads like a wrong flag rather than a shell fault. Inside a detached script, call the program directly and redirect there rather than passing its arguments through `-ArgumentList`.

**A command that goes IDLE is killed at 16 to 45 seconds** and reported as "may be waiting for input", even with `-NonInteractive`. The trigger is idleness rather than duration, which is why a long `pytest` streaming dots outlives a short sleep. Anything long must be detached with `Start-Process -WindowStyle Hidden` writing to a file, then read the file. Never `Start-Sleep`. Reported independently by four agents on 2026-08-29.

**Redirecting both streams of one command to the SAME file runs nothing.** The file is opened twice, the second open fails, and under `$ErrorActionPreference = 'Continue'` the whole call is skipped in silence - so a detached gate script steps over every step and the sentinel reads `RUFF= MYPY= EXPORT=` beside an 83-byte log. **An empty exit code is a shell fault; a non-zero one is your gate.** Give each command its own `1> <step>.out 2> <step>.err` pair, and never use `2>&1` in a detached script when you also want the exit code. Seen twice on 2026-09-02.

**`python` redirected to a file writes nothing until it exits.** Redirection makes stdout a pipe, so Python block-buffers it, and a long run shows only whatever it flushed - a measurement that printed its first line with `flush=True` and its results without looked hung for 25 minutes on 2026-09-10 while it was working the whole time. Pass `-u`, or `flush=True` on every print you intend to poll. `Get-Process <name> | Select-Object CPU` tells you it is alive; it cannot tell you where it is.

**A killed redirect leaves the output file present and empty**, which reads as "the command produced nothing" rather than "the command was cut off". Always write `$LASTEXITCODE` into a separately named sentinel and read that; never infer a pass from an empty log, and run one long child per call.

**A long command PIPED into a filter prints nothing until it finishes**, and the tool backgrounds it first, so a working command and a hung one look identical. `Select-String` and `Select-Object` read their input to the end before writing anything. Three recorded victims of the one fault: `pytest | Select-String` (2026-09-09), `npm run test:browser | Select-Object -Last 45 | Out-File`, which left a zero-byte log beside exit 0 after a nine-minute run (2026-09-01), and `pip install | Select-Object` on a fresh venv, where it looks exactly like a resolver stall. Redirect the whole stream to a file, then filter the file.

**A double-quoted string carrying a backtick escape can leave the shell on a `>>` continuation prompt**, after which every later command is swallowed as more input - so a later failure gets blamed on the wrong command. No output appears at all, which is how it differs from the idle kill. Prefer single quotes; where a literal control character is needed, `[char]13` and `[Environment]::NewLine` have no escape grammar to survive the trip.

**`-like '??*'` treats `?` as a wildcard**, so a filter meant to find untracked lines in `git status --porcelain` matches every line of two or more characters and returns the whole status. Ask git instead (`git ls-files --others --exclude-standard`), or use `.StartsWith('??')`.

**`-match` against an ARRAY filters it instead of answering yes or no.** `if ($lines -notmatch 'x')` is true whenever ANY line fails to match, so a check-run poller broke on its first tick and wrote its "done" sentinel over a log reading `browser=in_progress... gates=in_progress` (2026-09-06). Nothing errors and the exit code is 0. Join before you match - `if (($r -join ' ') -notmatch 'in_progress|queued')` - and remember `-eq`, `-like` and `-ne` filter an array too.

**`Select-String` matches case-insensitively unless you pass `-CaseSensitive`.** Hunting a merge failure on 2026-08-27, a search for `INDEX_ROOT` reported five hits in a file whose real content was five `_index_root` calls, which read as "the constant is still there" and pointed the diagnosis at the wrong side of the merge. It also has no `-Recurse`; feed it `Get-ChildItem -Recurse` output.

**A git revision carrying `@{` is eaten before git sees it.** `git diff HEAD@{1} HEAD` answers `fatal: ambiguous argument 'HEAD@'` - one character short of what you typed, because PowerShell reads `@{` as a hashtable literal - which reads as a repository with no reflog. Single-quote the whole argument, or name the two shas from `git log --oneline -3`.

**A multi-paragraph commit message goes through a file.** Write it with `[System.IO.File]::WriteAllText` (not `Set-Content`, which adds a BOM that lands in the message), then `git commit -F.tmp_commit_msg.txt`. `.tmp_*` is gitignored.

**`git show <ref>:<path> | Set-Content` writes CRLF** and produces a phantom whole-file diff; `-NoNewline` is worse, because PowerShell splits the output into lines and joins them with nothing, so a Python file arrives as one line and fails to import while the copy still reports success. Use `git restore --source=<ref> --worktree -- <path>`, which touches no encoding and leaves the index alone. The same pipe defeats `sha256sum --check`, whose error then names the file with a trailing `$'\r'`.

**`git add -- $paths` with a PowerShell array stages nothing** and exits 0, so the following commit lands one file instead of twelve. Pass the paths as separate literal arguments and read `git diff --cached --name-status` before committing.

**A scratch directory under `$env:TEMP` outlives the session, so the next run reads the last run's files.** A refusal to overwrite is the lucky case; a reader that opens a stale output and reports its number as a result is the dangerous one. Prefix every scratch file with the row tag - `r15-smoke.cjs`, not `smoke.cjs` - and clear the directory before the first write rather than after the last read, because a killed run never reaches the cleanup.

**`DONE.txt` beside `done.txt` is the same file.** Windows paths are case-insensitive, so a gate script writing `$out\ruff.txt` and then `$out\RUFF.txt` silently overwrites the result with the word `RUFF-DONE` - the run looks like it passed and the exit code you needed is gone (2026-08-26). Give a sentinel a name that is not the stem of any output file, and anchor the pattern you poll for, because `PIP_EXIT` also matches `ENSUREPIP_EXIT`.

**A log that stops growing is not a stalled process.** A detached script's redirect buffers, so the file sits at one size for minutes while the child works: a healthy `pytest` run was killed twice on 2026-08-30 for looking frozen at 94 percent, when the suite is 1,599 tests and 579 s and `test_workflows.py` alone spends minutes inside `git` subprocesses with nothing to print. Ask the process, not the file - `UserModeTime` is in 100-ns units, so a value climbing between two samples is work and only a value that does not move is a stall:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
 Where-Object CommandLine -like '*<your worktree>*' | Select-Object ProcessId, UserModeTime
```

**A killed command is indeterminate in BOTH directions** - the same kill left `gh pr create` having done nothing and left `git push -u` having pushed the branch and skipped only the upstream write. Verify by side effect (the file it writes, the remote ref it pushes), never by exit code.

**`Set-Location` does not move .NET's idea of the current directory, so a `[IO.File]` call on a relative path reads another worktree.** The shell was at `...p23-r6`, `Get-Content .\tests\fixtures\...` worked, and `[IO.File]::ReadAllBytes('tests\fixtures\...')` failed naming `...p23-r3\frontend\tests\fixtures\...` - a path in a different agent's checkout that this run had never touched. The shell's location and `[Environment]::CurrentDirectory` are two variables, and only cmdlets read the first. Worse than the error is the success: the same call on a path that happens to exist in the stale directory returns another worktree's bytes and reads like your own file. **Pass `[IO.File]` an absolute path, always** - `[IO.File]::ReadAllText("$w\backend\tests\test_rank.py")`. Seen 2026-09-12.

## The terminal tool itself

**A sync call can return "Command produced no output" without having run**, about one call in four under load, and it can also return ANOTHER worktree's output. An empty result announces itself; a plausible one does not, and a correct answer about the wrong tree is indistinguishable from a correct answer about yours. Tag every command, increment the tag, and discard anything that does not carry it:

```powershell
"TAG=<row> PWD=$($PWD.Path)"; <command>
```

**Re-issue only after checking whether the first copy is running.** On 2026-08-26 three launches each reported nothing and all three ran, so three builds wrote one shared output directory and the byte gate measured a half-written tree.

**`Set-Location -LiteralPath` to a path that does not exist fails, and the rest of the line still runs** - in the previous directory, which under parallel agents is often a sibling's worktree, and the tag above does not catch it because the tag prints first. Gate on `$PWD` in the same line, so exit 9 means the command never ran rather than ran somewhere else:

```powershell
$t='<abs>'; Set-Location -LiteralPath $t; if ($PWD.Path -ne $t) { exit 9 }; <command>
```

**A queued command can execute long after you sent it**, on top of live work. A `Remove-Item -Recurse -Force.venv` ran about 25 minutes after it was issued, under a `pytest` that had started in the meantime: the suite froze at a fixed percentage, `pytest --version` answered `No module named pytest`, and `import pydantic` still worked - a half-deleted environment that reads exactly like a broken toolchain (2026-08-29). Never queue a destructive command against a path a later command needs.

**A foreground `pytest` can be killed mid-run and reported as though it finished** - exit 1 and an empty output file, the same shape as a collection error. `--collect-only` tells the two apart: a suite that collects cleanly and then dies partway through was interrupted. Run long suites detached with two sentinels, and anchor any pattern you grep for, because `PASSED` also matches `XPASSED`.

**The launch itself can silently not happen.** `Start-Process` returns, no child appears, and no log file is ever created, so the missing gate reads as a slow one. `Test-Path <log>` immediately afterwards is the check; false means send the launch again rather than keep polling.

**A sleeping poll loop is sometimes detached rather than killed**, and re-reading that terminal returns the command line followed by empty lines - so the sentinel arrives on time and the poll cannot say so. Print one line per iteration, which keeps the call in the foreground and shows the log growing.

**`pwsh -NoProfile -File <script>.ps1` can exit 1 having done nothing**, with no error text. Call the absolute path instead: `& 'C:\...\script.ps1'`.

## Git Bash on Windows

**MSYS rewrites any argument that looks like a path, including `<rev>:<path>`.** `git show "origin/main:docs/a.md"` is delivered as `origin\main;docs\a.md` and git answers `fatal: Not a valid object name` - and the quiet version does the damage: with `2>/dev/null` on the call the fatal goes nowhere, the command writes nothing, and a comparison reads the empty stream as content. On 2026-08-28 that reported 22 files as differing from `main` or missing from it; every one was byte-identical to a commit already in history, and the failure is indistinguishable from the honest negative answer.

Build any check that decides whether something can be deleted on an argument the shell cannot rewrite. A 40-character object id has no `:` and no `/`:

```bash
git hash-object <file> # then: git cat-file -e <40-hex sha>
git ls-tree <rev> -- <path> # no colon, so nothing to rewrite
MSYS_NO_PATHCONV=1 git show 'origin/main:docs/a.md' # the fallback, per shell
```

`git grep` is case-sensitive by default (`-i` makes it not) and exits 1 when it finds nothing, which a `&&` chain reads as a failure. It also reads anything after the pattern as a revision until it meets `--`, so a context flag placed the way ripgrep takes it becomes a commit-ish: `git grep -n -A 20 'pattern' -- <path>`.

**A path holding `[` or `]` reads as an empty directory to every PowerShell cmdlet that takes `-Path`.** The brackets are a wildcard character class, so `Get-ChildItem -Name 'frontend/src/routes/[date]/[vertical]/'` matches nothing and returns nothing - no error, no warning, just the same output a genuinely empty folder gives. On 2026-09-12 a worker concluded that route directory did not exist and reported the plan-doc wrong; `git ls-files` showed four files in it. Every SvelteKit dynamic route in this repository is such a path. Use `-LiteralPath`, which takes the string as written, or ask git. The same applies to `Test-Path`, `Remove-Item`, `Copy-Item` and `Select-String`, each of which has its own `-LiteralPath`.

## The editor's own file and search tools

**A workspace search reads the folder VS Code has open, never your worktree.** `includePattern` is resolved against the workspace root, so a pattern prefixed with the worktree directory matches nothing and the same pattern without it happily searches the SHARED checkout and returns its stale copy. Both failure modes are silent and the second is worse - you read `main`'s text and conclude your edit did not apply. **The third failure mode is the quietest: the hit is real and its line number is not.** On 2026-09-12 a worker editing a file in a worktree got line numbers from the shared checkout's copy of the same file, three hundred lines out, and one edit anchored on them silently went to the wrong place. In a worktree, use `Select-String -Path` with absolute paths, or read the file by absolute path.

**The search index is unreliable in both directions**, even inside the open folder: on 2026-08-31 one session got an empty result for a function that was in the file it named, and minutes earlier real matches from a sibling worktree nobody had asked about. It can also return a line of code that no longer exists anywhere - a 2026-08-29 hit quoted an assertion a merged pull request had removed, at a line number that was blank, and a worker nearly restored the deleted rule. When two tools disagree, the byte reader wins; a hit you cannot reproduce with `Select-String` or `Get-Content` is not there.

**The file-reading tool can hand back a file's previous contents** after a detached script rewrote it, for minutes - including a sentinel format that no longer exists on disk, which reads as "the script did not run" and sends you after a launcher bug that is not there. Read anything a script just wrote with `Get-Content`. The editing tool reads the same stale copy, so it refuses to match text that `Get-Content` and a byte dump both show is in the file - and the refusal reads as a whitespace problem in your search string rather than as a cache (2026-09-12, on a module a slice script had just written). Re-run the script with the edit folded into it rather than hand-editing afterwards. Copying to a fresh filename defeats the cache, unless the file is still being appended to: a poll returned test 907 twice while the run had reached 967, because the copy is only as fresh as the read it was made from. Track a long run by a side effect the child finishes with, never by how far its log appears to have got.

**The replace tool deletes whatever the old text held and the new text drops.** It is a literal swap and it reports success, so a line inside the matched block that is missing from the replacement is gone with no warning - a 2026-08-29 workflow edit silently dropped an `actions/setup-python` step sitting between the two steps being changed, and nothing failed until the job ran. Two edits to a tab-indented TypeScript file written with space-indented replacement text dropped a closing brace, and `svelte-check` then reported 37 errors in 12 files, none of them about the change; the one real error is the `'}' expected.` line. Match tightly, match the file's indentation character exactly, and run `git diff --stat` after EVERY structural edit - an unexpected line count is the only early warning. Inserting a heading is the same hazard: markdown has no closing tag, so a new `###` takes ownership of everything below it until the next one.

## Nested subagents

**A worker cannot delegate until the harness is configured to let it, and the failure is silent refusal rather than an error.** In VS Code, enable `chat.subagents.allowInvocationsFromSubagents` in the active user or workspace settings. Every custom agent that delegates must include `agent` in its `tools` list; a prompt carrying its own `tools` list must include it too, because that list takes precedence. If an `agents` list is present it must allow the requested delegate. Verify with one real, read-only nested invocation before relying on it - see [VS Code's nested-subagent documentation](https://code.visualstudio.com/docs/agents/run/subagents#_nested-subagents).

## The Python environment

**An install on an unsupported interpreter does not fail, it stops answering.** pip writes nothing into `site-packages` until it has resolved and built every distribution, so a large download, a backtracking resolver and a source build all look identical from outside - on 2026-08-25 `python -m venv.venv` took a 3.14 that `python` happened to resolve to, and ten minutes later `site-packages` held `pip` and nothing else. `pyproject.toml` now bounds the interpreter (`requires-python = ">=3.12,<3.15.0a0"`), so pip refuses one it cannot resolve for with a message that names the version. Print it before trusting an install:

```powershell
& <python> -c "import sys; print(sys.version)"
```

**On a machine outside the bound, do not build a venv - borrow the shared one.** Set `PYTHONPATH` to the worktree's `backend` and run the shared interpreter, so the code under test is yours and the dependencies are the ones already installed. Three follow-on traps. The venv's `.pth` holds the ABSOLUTE path of the checkout it was installed from, so without the variable `pytest` collects your tests while `import idhazh` resolves to the other tree and a green run says nothing (verified 2026-08-25 across ten worktrees). The variable then leaks into every later terminal and beats a CORRECT `.pth` just as reliably, so `python -m idhazh.contracts.export` writes `schemas/` into the other tree while `git status` here stays clean (2026-08-27). And it reaches the browser suite through a spec that shells out to `python`, where the system interpreter finds your package and dies on `ModuleNotFoundError: No module named 'feedparser'` - one spec of 989 inside a 14-minute suite, naming a dependency rather than a path (2026-09-06). Print the resolved path before every gate run, and clear the variable before switching worktrees:

```powershell
$env:PYTHONPATH = '<abs path to your worktree>\backend' # or '' when not borrowing
& <shared venv>\Scripts\python.exe -c "import idhazh; print(idhazh.__file__)"
```

`npm run test:changed` deletes `DIGEST_ROOT`, `STATE_ROOT`, `TELEMETRY_ROOT` and `PYTHONPATH` from each check's environment, so this never bites through the launcher - only through a hand-rolled script that sets the variable and then runs a browser gate in the same process.

**`ModuleNotFoundError: pydantic_core._pydantic_core` is an ABI mismatch, not a missing package.** A venv built for one minor version and run by another finds the package and cannot load its extension, and nothing reinstalls or repairs it because pip sees the distributions as present. Diagnose by counting interpreter tags on the `.pyd` files - a count under `cp312-win_amd64` while `python -V` says anything else IS the diagnosis (2026-08-28, 269 of them beside a 3.14.2 launcher) - and fix by building a fresh venv under `$env:TEMP`, never by reinstalling into the broken one. Redirect that install to a file rather than piping it, and when it runs from a detached script confirm with an actual import: the log says `Successfully installed` before the environment can be used.

```powershell
Get-ChildItem.\.venv\Lib\site-packages -Recurse -Filter *.pyd |
 Group-Object { ($_.Name -split '\.')[-2] } | Select-Object Name, Count
```

**The shared venv can simply be missing a declared dependency**, which reads as a broken tree rather than a stale environment: `mypy` names a source file and `pytest` dies loading `conftest.py`, for a distribution declared in `pyproject.toml` for weeks (2026-09-02, `protego`). `pip install --dry-run` separates the two cases and costs a download of nothing. One distribution and nothing else moving means a plain install repairs the venv for every sibling sharing it; a version something else pins means stop and build a separate venv.

## Pydantic

**`model_copy(update=...)` accepts a key the model does not have.** It sets the attribute without validating - no exception, no warning, no type error - so a config key renamed everywhere except here leaves a test silently running on the committed default. One occurrence held a 22-minute timeout where the test wanted 0.01, and CI's own 15-minute bound killed the job: `gates: cancelled`, every sibling green, no failing assertion anywhere, twice before the cause was found (2026-09-09). After renaming a field, grep `model_copy(update=` as well as the attribute path, and put one `assert copy.<field> == <value>` after the copy.

## npm

**`npm ci` can stop making progress after the tree looks complete**, and it can exit 0 with a package only partly extracted, and it can report every binary present while the next process cannot resolve one. Gate on the specific shim you are about to run, not on the exit code:

```powershell
Test-Path frontend/node_modules/.bin/svelte-kit.cmd
```

`.package-lock.json` plus a plausible file count means the install is effectively done; do not re-run `npm ci`, which contends with the first. **Never diagnose a toolchain from the first run after an install** - on 2026-08-29 `npm run check`, `npm run build` and `npm run bundle-gate` all returned 1 with `'svelte-kit' is not recognized`, and the identical script passed a minute later. A missing module belonging to a transitive dependency nothing in the change touched is a partial extraction, not a code fault. A brand-new worktree has no `node_modules` at all, and `npm run build` gets a surprising distance before failing, because its first three steps are plain `node`: four lines of success and then `'vite' is not recognized`.

**From a detached hidden shell, `& npm ci` resolves nothing and leaves `$LASTEXITCODE` unset.** `npm` and `npx` are batch shims that are not on `PATH` in a freshly spawned terminal, and the empty exit code is the tell - it looks exactly like a broken lockfile. Call the script directly and redirect the two streams separately:

```powershell
& node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" ci 1> $out 2> $err
```

## Hugging Face

**The ETag on a weights download is not the SHA-256, and it looks exactly like one.** A `HEAD` on `/resolve/<commit>/<file>` returns a 64-character hex ETag that disagrees with the recorded digest, because Xet-backed storage returns a content hash there - read as a mismatch it says the weights moved, which would stop a change that is fine. Take one of the two cheap reads: the `X-Linked-ETag` header on the **302** is the file's SHA-256, so `curl -sI` without `-L` settles it, and the recursive tree listing gives every file's `lfs.oid` for a whole revision in one call.

```
GET https://huggingface.co/api/models/<repo>/tree/<commit>?recursive=1
GET https://huggingface.co/<repo>/raw/<rev>/<file> # the LFS pointer, oid sha256:
```

The revision-scoped `?blobs=true` API returns `lfs.oid` as null, so a check written against it silently compares against `None`. And a file's digests do not identify one commit - walking `Xenova/all-MiniLM-L6-v2` on 2026-09-09, the head and its parent carried the same five digests because the head added other variants - so pin the revision explicitly and say you picked the branch head at the fetch date. A `resolve/<40-hex-sha>/` URL redirects where `resolve/main/` does not, and the small files answer `307` on `huggingface.co` while the model answers `302` to the CDN, so a hop count or a CSP source list has to allow for both.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [git-and-github.md](git-and-github.md) - the git commands these quoting traps break.
- [gates-and-builds.md](gates-and-builds.md) - running a gate through a detached script.
- [browser.md](browser.md) - the integrated browser, which fails in its own ways.
