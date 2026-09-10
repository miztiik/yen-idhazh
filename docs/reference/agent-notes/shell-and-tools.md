# Agent Notes - Shell and Tools

**Last Updated**: 2026-09-10

Traps in PowerShell, MSYS, the editor's own file and search tools, the Python
environment, npm and the libraries that lie about what they returned. Index and
scope: [../agent-notes.md](../agent-notes.md).

## PowerShell

**Send one line.** The terminal tool takes a single command; a multi-line block is not reliably delivered. Chain with `;`, and write anything longer to a `.ps1` with the file-creation tool and run the file. There is no heredoc: a multi-line here-string sent as one command arrives mangled, and the variable then holds the PREVIOUS script - which runs happily and answers the previous question. The same applies to `python -c` with a multi-line string; it fails silently or runs something else.

**`[System.IO.File]` resolves a relative path against the process directory, not the shell's.** `Set-Location` and `Push-Location` move the PowerShell location only, so `WriteAllText('docs/x.md', ...)` lands in whatever directory the host started in - usually the shared checkout, so an edit meant for a worktree silently modifies `main`. Always pass an absolute path, or use `Set-Content` / `Out-File`, which do follow the shell.

**A function that logs with `Write-Output` returns the log as part of its value.** Every uncaptured expression joins the return value, so a caller doing `if (Test-Thing) { }` tests a non-empty array and always takes the true branch. Log with `Write-Host`, and let the function return exactly one object.

**`Start-Process -Wait` does not set `$LASTEXITCODE`.** It stays at whatever the last native command left, so a failing child reads as success. Capture the process:

```powershell
$p = Start-Process -FilePath pwsh -ArgumentList '-File','x.ps1' -Wait -PassThru; $p.ExitCode
```

**`Start-Process -ArgumentList` splits an element that holds spaces.** `-ArgumentList @('-c', 'import x; print(1)')` reaches Python as several arguments. Pass a single pre-quoted string, or write the script to a file and pass its path.

**A command that goes IDLE is killed at 16 to 45 seconds** and reported as "may be waiting for input", even with `-NonInteractive`. Anything long must be detached with `Start-Process -WindowStyle Hidden` writing to a file, then read the file. Never `Start-Sleep`.

**Redirecting both streams of one command to the SAME file runs nothing.** `> out.txt 2> out.txt` returns instantly with two empty files and no error. Use `*>&1 > out.txt`, or two different files.

**A killed redirect leaves the output file present and empty**, which reads as "the command produced nothing" rather than "the command was cut off". Check the exit code and the file size together.

**A long command PIPED into a filter prints nothing until it finishes**, and the tool backgrounds it first. `pytest ... | Select-String FAILED` looks like a hang. Redirect the whole stream to a file, then filter the file. `| Select-Object -Last N | Out-File` is worse: on a 42-minute browser run it wrote nothing at all, because the pipeline never got to run.

**A double-quoted string carrying a backtick escape can leave the shell on a `>>` continuation prompt**, after which every later command is swallowed as more input - so a later failure gets blamed on the wrong command. Prefer single quotes; when a literal newline or backtick is needed, put it in a `.ps1`.

**`-like '??*'` treats `?` as a wildcard**, so a filter meant to find literal question marks matches every string of two or more characters. Use `-match '\?'` or `.Contains('?')`.

**`-match` against an ARRAY filters it instead of answering yes or no.** `if ($lines -notmatch 'x')` is true whenever ANY line fails to match, so a guard written that way never fires. Reduce first: `if (($lines | Where-Object { $_ -match 'x' }).Count -eq 0)`.

**`Select-String` matches case-insensitively unless you pass `-CaseSensitive`**, so a search for an uppercase marker reports hits from ordinary prose. It also has no `-Recurse`; feed it `Get-ChildItem -Recurse` output through `-Path`.

**A git revision carrying `@{` is eaten before git sees it.** `HEAD@{1}` and `main@{u}` are PowerShell splatting syntax. Single-quote the whole argument.

**A multi-paragraph commit message goes through a file.** Write it with `[System.IO.File]::WriteAllText` (not `Set-Content`, which adds a BOM that lands in the message), then `git commit -F .tmp_commit_msg.txt`. `.tmp_*` is gitignored.

**`git show <ref>:<path> | Set-Content` writes CRLF** and produces a phantom whole-file diff; `-NoNewline` then strips the trailing newline and produces a different phantom diff. Use `git restore --source=<ref> -- <path>`.

**`git add -- $paths` with a PowerShell array stages nothing** and exits 0. Pass the paths as separate literal arguments.

**A scratch directory under `$env:TEMP` outlives the session, so the next run reads the last run's files.** Prefix every scratch file with the row tag, and clear the directory before the first write rather than after the last read - a killed run never gets to the cleanup.

**`DONE.txt` beside `done.txt` is the same file.** Windows paths are case-insensitive, so a "finished" sentinel and a "started" sentinel that differ only in case overwrite each other and the wait returns immediately. Make sentinel names differ by more than case.

**A log that stops growing is not a stalled process.** A gate can spend twenty minutes inside one step with no output. Check CPU before concluding anything:

```powershell
(Get-Process -Id <pid>).UserProcessorTime
```

**A killed command is indeterminate in BOTH directions** - it may have done nothing, or everything. Verify by side effect (the file it writes, the remote ref it pushes), never by exit code.

## The terminal tool itself

**A sync call can return "Command produced no output" without having run**, and it can also return ANOTHER worktree's output. Tag every command with something only that invocation prints:

```powershell
"TAG=<row> PWD=$($PWD.Path)"; <command>
```

**`Set-Location -LiteralPath` to a path that does not exist fails, and the rest of the line still runs** - in the previous directory. Gate on `$PWD` in the same line.

**A queued command can execute long after you sent it**, so its output arrives attached to a later question. The tag above is the only defence.

**A foreground `pytest` can be killed mid-run and reported as though it finished.** `--collect-only` tells the two apart: if collection alone takes minutes, the run was cut. Run long suites detached with two sentinels - one written before the command, one after - and anchor any pattern you grep for, because `PASSED` also matches `XPASSED`.

**The launch itself can silently not happen.** `Start-Process` returns, and no log file is ever created. `Test-Path <log>` immediately afterwards is the check.

**`Start-Process pwsh -Wait` can report exit 1 while the child succeeded and is still running.** Believe the child's own sentinel file, not the parent's code.

**`pwsh -NoProfile -File <script>.ps1` can exit 1 having done nothing**, with no error text. Dot-source or call the absolute path instead: `& 'C:\...\script.ps1'`.

**A PowerShell pipe appends CRLF**, so a manifest written that way and fed to `sha256sum --check` reports the file as missing rather than as changed.

## Git Bash on Windows

**MSYS rewrites any argument that looks like a path, including `<rev>:<path>`.** `git show 'origin/main:docs/x.md'` becomes `origin/main;C:/Program Files/Git/docs/x.md` - and the quiet version does the damage: `git rev-parse main:file` silently answers about the wrong path. Either disable the rewrite or use a colon-free form:

```bash
MSYS_NO_PATHCONV=1 git show 'origin/main:docs/x.md'
git --no-pager show origin/main -- docs/x.md
```

`git grep` has no `-CaseSensitive` flag (it is case-sensitive by default, `-i` makes it not), and it exits 1 when it finds nothing - which a `&&` chain reads as a failure.

## The editor's own file and search tools

**A workspace search reads the folder VS Code has open, never your worktree.** `includePattern` is resolved against the workspace root, so a pattern prefixed with the worktree directory matches nothing and the same pattern without it happily searches the SHARED checkout and returns its stale copy. Both failure modes are silent and the second is worse - you read `main`'s text and conclude your edit did not apply. In a worktree, use `Select-String -Path` with absolute paths, or `read_file` with an absolute path.

**The search index is unreliable in both directions**, even inside the open folder: a term that exists returns nothing, and a hit can be a line of code that no longer exists. When two tools disagree, the byte reader wins - `Select-String` and `git grep` read the file.

**The file-reading tool can hand back a file's previous contents** after a detached script rewrote it, for minutes. Read anything a script just wrote with `Get-Content`. Copying to a fresh filename defeats the cache - unless the file is still being appended to, in which case even that stops working and you must track progress by side effect (the row count, the sentinel) instead.

**The replace tool deletes whatever the old text held and the new text drops.** Two edits to a tab-indented TypeScript file dropped a comment header and a closing brace, and the type-checker then reported 37 errors in 12 files, none of them about the change. Match the file's existing indentation character exactly, and run `git diff --stat` after EVERY structural edit - an unexpected line count is the only early warning. Inserting a heading is the same hazard: it can orphan the paragraphs that followed it.

## The Python environment

**An install on an unsupported interpreter does not fail, it stops answering.** `pip install -e .` on Python 3.14 produced no output for 45 seconds and was killed, with nothing on either stream saying why. `pyproject.toml` bounds the interpreter (`requires-python`), and the environment picker will happily hand you one outside it. Print the version before trusting an install:

```powershell
& <python> -c "import sys; print(sys.version)"
```

**On a machine outside the bound, do not build a venv - borrow the shared one.** Set `PYTHONPATH` to the worktree's `backend` and run the shared interpreter, so the code under test is yours and the dependencies are the ones already installed. Two follow-on traps: the venv's `.pth` file points at the checkout it was installed from, so without `PYTHONPATH` you are testing the SHARED tree while reading your own; and `PYTHONPATH` leaks into the next command, including into the browser suite, where a spec that shells out to a backend CLI then fails with `ModuleNotFoundError`. Print `idhazh.__file__` to prove which tree ran, and clear the variable before switching worktrees.

**`ModuleNotFoundError: pydantic_core._pydantic_core` is an ABI mismatch, not a missing package.** A venv built for one minor version and run by another finds the package and cannot load its extension. Diagnose by counting the interpreter tags on the `.pyd`, and fix by building a fresh venv under `$env:TEMP` - never by reinstalling into the broken one. Redirect that install to a file rather than piping it, and when it runs from a detached script, confirm with an actual import: the log says `Successfully installed` before the environment can be used.

**The shared venv can simply be missing a declared dependency.** `pip install --dry-run -e .` separates the two cases: it lists what would be installed (stale venv, install it) or reports everything satisfied (the tree is the problem).

## Pydantic

**`model_copy(update=...)` accepts a key the model does not have.** It sets the attribute without validating, so a config key renamed everywhere except here leaves a test silently running on the committed default. One occurrence held a 22-minute timeout where the test wanted 0.01, and CI's own 15-minute bound killed the job - `cancelled`, no failing assertion anywhere. After renaming a field, grep `model_copy(update=` as well as the attribute path, and assert the field took.

## npm

**`npm ci` can stop making progress after the tree looks complete**, and it can exit 0 with a package only partly extracted, and it can report every binary present while the next process cannot resolve one. Gate on the specific shim you are about to run, not on the exit code:

```powershell
Test-Path frontend/node_modules/.bin/vite.cmd
```

`.package-lock.json` plus a plausible file count means the install is effectively done. A brand-new worktree has no `node_modules` at all, and `npm run build` gets a surprising distance before failing on a missing binary.

**From a detached hidden shell, `& npm ci` resolves nothing and leaves `$LASTEXITCODE` unset.** `npm` and `npx` are batch shims that are not on `PATH` in a freshly spawned terminal. Call the script directly:

```powershell
& node "$env:APPDATA\npm\node_modules\npm\bin\npm-cli.js" ci
```

## Hugging Face

**The ETag on a weights download is not the SHA-256.** Large files are LFS pointers, so the ETag is the pointer's hash. Ask the pointer for the real digest, or take the two cheaper reads - the `X-Linked-ETag` header on the 302, or the recursive tree listing, which gives every file's `lfs.oid` in one call:

```
GET https://huggingface.co/<repo>/raw/<rev>/<file>
GET https://huggingface.co/api/models/<repo>/tree/<commit>?recursive=1
```

The revision-scoped file API returns `lfs.oid` as null, so it cannot answer this. And a file's digests do not identify one commit - the same blob appears in every revision that did not change it - so pin the revision explicitly. A `resolve/<40-hex-sha>/` URL redirects to the CDN where `resolve/main/` does not.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [git-and-github.md](git-and-github.md) - the git commands these quoting traps break.
- [gates-and-builds.md](gates-and-builds.md) - running a gate through a detached script.
- [browser.md](browser.md) - the integrated browser, which fails in its own ways.
