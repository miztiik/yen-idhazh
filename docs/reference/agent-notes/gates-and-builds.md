# Agent Notes - Gates and Builds

**Last Updated**: 2026-09-10

Traps in the commands that decide whether a change is done: the test selector,
pytest, ruff, mypy, the schema drift gate, the build, the canary day, and the
measurement recipes that run on top of them. Index and scope:
[../agent-notes.md](../agent-notes.md).

The gates themselves are in
[../../how-to/run-the-gates.md](../../how-to/run-the-gates.md); this page is only
where they lie about their result.

## Gate commands

**`npm run test:changed --python <interp>` does not reach the canary build.** The flag routes the checks runner's own Python calls; `frontend/scripts/build-canary.mjs` resolves its interpreter separately and shells out to `build_canary_day.py --console-payloads-only`, so in a worktree borrowing a sibling's venv the step prints `wrote 0 console payload file(s)` and the build dies with a bare Node `Error: Command failed` and no Python traceback. It reads as a build regression; it is an interpreter that was never named. Set both:

```powershell
$env:IDHAZH_PYTHON = '<abs path to python.exe>'
npm --prefix frontend run test:changed -- --fresh --python '<abs path to python.exe>'
```

The same variable is needed for any Playwright spec that runs a backend command. `malformed-day.spec.ts` shells out to `idhazh validate-days` and resolves `$IDHAZH_PYTHON`, then a `.venv` at the repository root, then bare `python` - so a borrowing worktree misses the last two and the suite returns `1 failed, 1008 passed` with `No module named idhazh`, which reads as a broken validator rather than a `PATH` problem.

**`test:changed` REUSES a cached failed run.** A re-run prints `Reusing completed run <hash>: exit 1. Use --fresh to rerun unchanged inputs.` and exits 1 in two seconds, which reads as "still broken" when nothing ran. The record is keyed on the input tree, so an environmental flake stays cached until the tree changes. Pass `--fresh`; a green re-run then overwrites the record.

**`test:changed` can exit 1 with every test green.** `malformed-day.spec.ts` runs `idhazh validate-days` at the repository root, which appends a row to the tracked `state/day-validations.csv` for any day lacking a receipt under the current rules. That file is inside the fingerprint the selector re-checks after the browser groups, so the run ends `The canary build has stale inputs` under a list where all 1,009 tests passed. The tell is a modified `state/day-validations.csv` you never touched. Compare the identity in your worktree and in clean `main` - identical means the rules did not move and the receipt was missing before you started. Do not commit the row; every historical one came from a `digest:` commit, and CI is unaffected because `ci.yml` calls `npm run test:browser` directly. Seen 2026-09-09.

```powershell
python -c "from idhazh.cli import _validator_identity; print(_validator_identity)"
```

**A new backend test module fails CI unless a registered `pytestmark` or the exemption list names it.** `test_marks.py` requires every module under `backend/tests/` to carry a mark or appear in `UNMARKED_MODULES`, and the failure names the marker registry rather than your file. The registered marks are `contract`, `visual`, `slow` and `workflow`, under `--strict-markers` - **there is no `unit` mark**, so a plain unit-test module must go in the exemption list. That module is in no focused selection, so it is green on your box and red on the first CI run. Cost one CI round each on `test_rank.py` (2026-09-06) and `test_prompt_loop.py` (2026-09-07).

**A pytest harness that runs inside CI inherits `$GITHUB_OUTPUT`.** The harness in `test_workflows.py` builds the subprocess environment from `os.environ`, so on a runner it carries the `gates` step's own output file and any line the script under test writes lands in that step's outputs. The sharper cost is the test: a case asserting the script survives with the variable UNSET passes locally, where no shell has one, and asserts nothing on the only machine that ever does. Drop `GITHUB_OUTPUT` from the inherited copy and let a test that wants one hand over a file of its own. Closed 2026-09-09; the rule generalises to every `GITHUB_*` variable a runner sets.

**A test's `print` never reaches you on the default run.** `pyproject.toml` sets `addopts = -q -n auto`, so output is captured and xdist swallows it. Use `-n0 -s -k <name>`; `-p no:xdist` exits **4**, because `-n auto` is still in `addopts` and a usage error with no test output looks like a broken suite rather than a bad flag. That same committed `-q` also means your own `-q` gives `-qq`, which removes the summary line - and changes `--collect-only` from a list of ids to a bare count, so a search for a renamed parametrized id finds nothing and reads as broken collection. Drop `-q` to list ids. `-k` cannot select a hyphenated id at all, because it splits on Python-identifier rules; run the node by its full id.

**A length test written with two-letter words is graded by the character rail, not the length rule.** `summarize.output_schema` puts `minLength` and `maxLength` on the summary field, and Pydantic checks those while PARSING the reply - before anything counts a word. So `"y " * 100` is 100 words and 200 characters, the rail throws it out as `bad_shape`, the length rule never runs, and the failure claims the verdict is `None`, which sends you into the verdict function. Build the fixture from realistic words (`"deliberation " * 100` is 100 words and 1,300 characters); the schema assumes roughly 5 characters per word at the floor and 13 at the ceiling. An over-length fixture has to stay under the character ceiling for the same reason. Seen 2026-09-10.

**ruff rewrites a cross-check into the expression it was checking.** RUF007 turned a hand-written `zip(stamps, stamps[1:])` into `itertools.pairwise`, which is what the assertion existed to verify - two copies of one expression, a passing test, and nothing checked. The lint error is the warning; taking its fix is the trap. Write the check in a third form the rule does not name, and say in the docstring why it is not the obvious one. Two more: B018 rejects a bare attribute used as a parse guard (assign it, `_ = parts.port`), and renaming a module makes ruff report I001 on files you never opened, because an import of a module that no longer exists sorts as third-party - 18 errors across 11 files on one rename, 7 of them tests the change never touched (2026-09-05). Repoint the imports rather than reaching for `--fix`, which sorts the stale name into its new wrong place.

**`ruff format` is NOT a gate here.** Running it rewrites unrelated files - 14 on 2026-08-24, 38 on 2026-08-29, 73 on 2026-09-08, which is a magnitude rather than a figure. `ruff check` is the gate.

**mypy only checks the platform branch you are standing on.** A `sys.platform` guard hides the other arm entirely, and the narrowing is statement-only: `os.O_BINARY if sys.platform == "win32" else 0` passed on Windows and failed CI with `Module has no attribute "O_BINARY"`, while the same code written as an `if`/`else` block passes both. Run `mypy --platform linux` before pushing from Windows, with its own `--cache-dir` or it fights the ordinary run for the cache.

**A new CLI flag anywhere under `backend/` can fail a test in a file you have never opened**, and only the full suite finds it. `test_exactly_one_function_spells_a_llama_server_flag` searches every `backend/**/*.py` for a quoted inference-server flag; one `--poll` failed it at 84 percent of the suite, after `ruff`, `mypy`, the targeted file and a whole CI round had passed. Check the namespace before you add the flag:

```powershell
git grep -n '"--<your flag>"' -- backend
```

## Contracts and schemas

**`git status --porcelain -- schemas/` straight after `python -m idhazh.contracts.export` looks like every schema changed.** The exporter prints the path of every file it wrote, so the two commands' output runs together and reads as twenty-nine modified files; `git diff --stat -- schemas/` is the question you meant, and empty is the pass. And `git diff --exit-code -- schemas/` is not the drift gate until you have committed - on a branch whose only schema change is the one it exists to make it returns 1, which reads exactly like a hand-edited schema. The gate is `test_committed_schemas_match_the_models`, which exports into a temporary directory, so it does not care what `HEAD` holds.

**The schema export CLI needs an absolute `--out` path.** A relative one lets the export write its files and then fails when the CLI prints each path relative to the repository root, which is not schema drift. Use `--out (Join-Path $PWD 'backend/var/schemas')`. Observed 2026-09-08.

**Round-tripping a committed config through its model puts back fields you deleted.** `to_json` writes every defaulted field, so a two-line config edit arrives as a three-line diff with a resurrection in it - `digest.items_per_topic`, retired on purpose, came back that way on 2026-09-01. Read the diff line by line rather than for the lines you meant to add.

**The opposite rule applies to `tests/fixtures/contracts/`, where the model IS the right writer.** `test_fixture_round_trips_byte_identically` demands the file bytes equal `to_json`, and the serializer sorts keys, so one new field on a nested model breaks every fixture carrying it - four at once on 2026-09-02. Re-serialise through `BY_STEM[<folder>].from_json(text).to_json` rather than editing by hand.

**The one `app-config` fixture asks for a second thing, and its name is the only place that says so.** `every-knob-differs-from-the-committed-config.json` holds a value the committed `config/idhazh.json` does not, knob by knob, so a reader that ignored the file and fell back to a default would fail rather than pass. Re-serialising a new field into it therefore is not enough: it arrives carrying the default, which is exactly the value the fixture exists not to hold. Set it to something else first, then re-serialise. Observed 2026-09-10 adding `summarize.key_point_words_max`.

**An argparse option in `backend/utilities/` may not be spelled like a llama-server flag.** `test_summarize.test_exactly_one_function_spells_a_llama_server_flag` globs `backend/**/*.py` for any quoted flag `server_argv` emits and compares the file set by equality, so `parser.add_argument("--port", ...)` puts your tool in that set and fails a test about the inference server. `--server-port` passes, because the guard searches for the literal `"--port"` including its quotes. Observed 2026-09-10.

**A hand-written CSV line needs `version` first.** `csv_columns` is `tuple(cls.model_fields)` and `version` is declared on `Contract`, so it is column 0 on every ledger here. A row one cell short gives `DictReader` a `None` and the contract then raises `AttributeError`, which `load_health` and `load_retirements` do not catch because they catch `KeyError` and `ValueError`. The row is malformed, not truncated.

**`Sources` refuses two feeds at one URL**, so a fixture built by copying a feed fails at config load - several frames above the line under test, with a message about configuration. Give the copy an address of its own out of `BODIES`.

## Running the gates

**A guard that enumerates hazards is wrong the day after it is written.** `test_archive_readers.py` held twelve approved paths and covered two collections out of nineteen; its own maintenance cost grew with the number of collections, which is the defect it existed to catch. It shipped and was deleted the same day, 2026-09-06 (`CLAUDE.md` Rule #12). State a rule as a property and enforce it in review.

**A stopwatch cannot prove a cost stopped growing on this box.** The same bounded reads over the same 410-day fixture took 2,657.8 ms and then 3,099.3 ms a few minutes later, nine passes each - 16.6 percent apart on work that opened exactly the same files. It is the page cache, and every growth arm makes the tree bigger, which is the confound. Run the two arms ALTERNATELY in one process, and take the oracle on what the code opens rather than how long it took: a count of files and a sum of `statSync.size` came out 195 files and 53,328,670 bytes at both 420 and 430 published days, where the clock said plus 20 percent. Measured 2026-09-09 on a developer machine.

**`vite build` alone is not the build.** `npm run build` runs `build-icons.mjs`, `build-frame-css.mjs`, `build-worker-switch.mjs` and `copy-visuals.mjs` first, and skipping them uses whatever the last build left in `static/`. Measured 2026-09-03 on `/console/`: three runs through the full chain gave 163,494 / 163,493 / 163,486 bytes, a spread of 8; three `vite build` runs on the same tree gave 163,284 / 163,286 / 163,457, a spread of 173 and about 200 bytes light. Neither number looks wrong on its own, which is the hazard - a ceiling recorded from the second set is recorded from a tree nobody ships.

**Two builds of one unchanged tree do not agree on about 20 percent of `build/`.** SvelteKit defaults `kit.version.name` to `Date.now`, which reaches `_app/version.json`, the `__sveltekit_<id>` global every prerendered document names, and through that the content hash of every chunk filename. Measured 2026-08-31 over 380 files: 83 differed between two builds of one tree and the byte total was identical to the byte, which is the tell. Normalising the timestamp out does not rescue it, because the moved bytes are filenames. Pinned, the same pair came out 380 files and 158,564,941 bytes with zero differing hashes.

```powershell
$env:BUILD_VERSION = '1788285804815' # 13 characters, or it moves the bytes it was set to hold still
npm --prefix frontend run build
```

Leave it unset for any measurement that has to match a CI build, which is every page ceiling. **The pin is a live grenade when the variable is unset**, and the fallback reads as a no-op because SvelteKit's own default is also `Date.now`. It is not the same thing: SvelteKit takes one timestamp when its options module loads, while `svelte.config.js` is evaluated once per Vite pass - so the document names `__sveltekit_184943e`, the client chunk names `__sveltekit_1kal9sg`, and every route throws `TypeError: Cannot read properties of undefined (reading 'data')` on hydration. Nothing else says so: the build is clean, the pages render from their prerendered markup, and the canary build does not split its chunks, so the browser suite stays green. More than one line out of this probe is the defect:

```powershell
Get-ChildItem build -Recurse -Include *.html,*.js |
 Select-String -Pattern '__sveltekit_[a-z0-9]+' -AllMatches |
 ForEach-Object { $_.Matches.Value } | Sort-Object -Unique
```

**Two builds back to back can fail with `EPERM` on `.svelte-kit/output`** when the previous process still holds it. The message names a permission and reads like a broken checkout - and the second build then wrote nothing, so a script that hashes the output afterwards hashes the FIRST build's file and reports two arms that agree. Delete the directory before each build, retry until it is gone, and refuse to read the output when the exit code is not zero. Seen 2026-09-09.

**The browser suite goes quiet for minutes and is still working.** Check that the log file's `LastWriteTime` is advancing, and check CPU - and check the right process, because during the longest quiet stretch the busy one is `node`, not `chrome-headless-shell`. Measured 2026-09-05 across a three-and-a-half-minute gap: the busiest headless shell moved 0.1 CPU-seconds while the runner's `node` moved 52 in 44 seconds, because the tail specs read and parse committed days rather than driving a browser. Killing the run costs another eight minutes and proves nothing. Run the suite through `npm run test:browser` and nothing else; `npx playwright test <group>` piped into a filter prints nothing until the whole group finishes, and calling Playwright's own entry point by hand (`node node_modules/@playwright/test/cli.js test`) fails every spec with `Playwright Test did not expect test to be called here` and then `No tests found` - which reads like two installed copies of the package and is not, since the `.cmd` shim runs that same file (2026-08-31).

**A green local `svelte-check` says nothing about the site job**, because CI type-checks the MERGE of your branch and `main`. An error naming a symbol your working tree does not contain means you are reading the wrong tree, not the wrong code - four consecutive red `site` jobs against a clean local check on 2026-09-06. `git merge origin/main` into the branch and re-run before believing it.

**A callback option in `svelte.config.js` needs a JSDoc `@param`**, or `svelte-check` reports an implicit `any` against the config rather than any source file, which reads like a broken toolchain.

**A test that skips itself when it cannot find a control is a gate that turns off silently.** Read the skip count on every run and account for each one - `2 skipped` at the end of a 125-line pass list is what a disabled injection canary looks like (2026-08-27). Write the guard as `await expect(locator, 'why this matters').toHaveCount(1)` whenever the fixture is supposed to provide the thing.

**Never build a fixture object by spreading `Partial<T>`** - every field is optional, so the spread widens the result and the target type refuses it. Because the error only appears once `T` grows a field, it arrives on somebody else's commit.

**Write every long gate to a UNIQUELY named file.** Two detached launches sharing one log path interleave into a transcript that belongs to neither run, and the second launch is easy to make because the first printed nothing. A sentinel written by appending holds its line twice, which is the tell. Put the row tag in the name, and check for a live copy before starting a second.

**A launch that reported nothing still launched.** Three launches each reported nothing and all three ran, so three builds wrote one shared output directory and the gate measured a half-written tree at 52,127 B against a real 130,396 - one paste away from being recorded as a ceiling (2026-08-26). Before trusting any byte measurement, look for the second build.

**A page-weight failure is often not yours.** `/archive/` and `/console/` grow every time the pipeline publishes, so read `main`'s check-runs for the same gate before investigating your diff.

## Two heavy gates on one box

**Symptom: a gate costs ten times its usual wall clock and the browser suite fails on a commit CI passed.** Measured 2026-08-30 on one developer machine: the same 1,675 tests ran in 62.68 s in CI and 630.55 s here, and eight local runs that day spanned 452.13 to 1,098.04 s. Three browser suites started at once took 5.3, 5.5 and 8.0 min against 3.6 to 4.0 min alone, and the 8.0 min run reported 11 failures on specs byte-identical to `origin/main`. The host sat at 98 to 100 percent CPU with the disk under 2 percent and at least 6.3 GiB free. It is the cores; it is not paging and it is not the disk.

`backend/utilities/gate_lock.py` serialises the heavy gates, one of three at a time. Chain every heavy gate into ONE locked script rather than taking the lock repeatedly - a single wait was measured at 25 to 50 minutes with siblings running, so five separately wrapped gates pay it five times. By design it cannot fail your gate: if the lock cannot be taken it runs anyway. CI never takes it, because each job has its own runner (Rule #2).

**Killing a queued build under the lock leaves the tree unservable.** The waiter and the build it wraps are one process tree, so the kill can land after `vite build` has cleared `.svelte-kit/output/` - `vite preview` then reports `Server files not found` on a checkout that built cleanly minutes earlier, while `frontend/build/` is still there and still looks complete. The fix is one more `npm run build`.

`os.kill(pid, 0)` is not a liveness probe on Windows: CPython routes every signal but the two console events to `TerminateProcess`, so the textbook probe can kill the process it was only asking about. `OpenProcess` alone is not enough either - it still opens a handle for an exited process while anything holds one - so only the wait separates them, 258 (`WAIT_TIMEOUT`) running against 0 exited.

**Raising the Playwright worker count measured slower locally and faster in CI.** One worker to four measured 233.7 s against 135.5 s on an a developer machine with six other checkouts building - 72 percent SLOWER, both arms passing the same 268 tests - and took the runner's browser step from 344 s to 207 s, 40 percent faster (2026-09-05). Two performance cores shared with seven agents is not four dedicated vCPU, so no number of local repetitions fixes it. Put concurrency knobs behind environment variables and take the number from `gh api repos/OWNER/REPO/actions/runs/<id>/jobs`.

## The canary build

**`npm run build:canary` does not build the canary day.** Without it the whole browser suite fails at COLLECTION with `ENOENT: no such file or directory, scandir '<worktree>\backend\var\canary\digest'` attributed to a spec line, because three specs read the canary tree at module scope - which reads like three broken tests and is one missing directory. Two commands, in order:

```powershell
python backend/utilities/build_canary_day.py # from the repository root only
npm --prefix frontend run build:canary
```

Every path the script holds is relative, so run from `frontend/` it finds no injection fixtures and dies on `ValueError: zip argument 2 is longer than argument 1` several frames inside `published_items` - which reads as a deleted fixture. It also writes an untracked `frontend/backend/var/canary/` tree of about 60 files on the way down, and the `build:canary` after it exits **0** on the canary the previous run left behind, so the suite goes green against a tree the failed command was supposed to replace. Count the fixtures before believing the message: `tests/fixtures/canaries/*.json` plus `browser/*.json` must equal `SCORED`. Seen 2026-09-05.

**The canary and the committed digest are two builds for two questions - do not swap them.** They share one output directory, so whichever ran last is on disk. The canary is fixed in size and carries a planted instance of every state the page draws, so it is what a per-item rule and any screenshot run against; a screenshot of the reading page built from the committed digest times out in every form. Running the suite against a real build fails about sixteen canary tests for reasons unrelated to your change.

**The canary's `day-metrics` record is written before the ledgers it reduces**, so every panel fed from those ledgers shows its empty state on the canary and nowhere else - which reads exactly like a panel that fails to render its data. To see the loaded state, patch the block into `backend/var/canary/state/day-metrics/<Y>/<M>/<D>.json`, rebuild, and put the file back; the tree is gitignored, so nothing can be committed by accident. **An empty state passing is a null result, not a pass**: before writing a spec for a new route, confirm `build-canary.mjs` writes the ledger that route reads. Keep the canary's column list and the contract assertion in the same test, because that builder hardcodes its own list. The generator once appended instead of rewriting, so by the fifth run a feed crossed the quarantine threshold and failed an unrelated browser test on developer machines while CI stayed green; fixed 2026-08-24, and the shape generalises to any fixture builder that opens its output for append.

## Serving a build to measure it

**A commit made after the build turns the next browser run red**, before a test runs, with `The real build has stale inputs` and `Process from config.webServer was not able to start. Exit code: 1` - which reads like a broken preview server. A two-line edit to a backend test invalidated a build taken twenty minutes earlier (2026-09-05). The guard only checks the fingerprint, so it says nothing about whether the tree is the real site or the canary.

**Use `npm run preview`, not a hand-started `vite preview`.** A hand-started server serves the directory raw rather than through SvelteKit's preview middleware, so it cannot tell a real hydration failure from its own. `--outDir build` still serves static assets and prerendered documents out of `.svelte-kit/output/` - `--outDir` names a directory `vite preview` does not read, so it serves whatever the LAST build produced whatever `build/` now holds. Measured 2026-09-05: a document 262,022 bytes on disk was served at 216,280, the other arm, on two fresh ports in a row, so two builds of one tree read as identical. **To serve a specific tree, build that tree**, in the order build, serve, measure, build, serve, measure. `sirv` also builds its file map once at startup, so renaming a directory under a running server proves nothing, and `frontend/public/` is Vite's `publicDir` and is served too - the section 12 "delete the data file" check has to hide all three copies. The server renders the SPA fallback per request, so smoke `/404.html` explicitly. It can take a minute to bind under load, and prints its `Local:` line only once it is listening.

**A killed Playwright run leaves its preview server behind and poisons the next run.** `reuseExistingServer` is on outside CI, so the run adopts a server whose asset map predates your rebuild and every hashed asset 404s: 39 failures in 74 tests on 2026-08-31, across specs the change never touched, **every one a timeout at the same 15.6 s**. That identical duration across unrelated specs is the tell; a real regression fails in different ways at different points. Take a fresh `PREVIEW_PORT` (default 4173) before diagnosing a wide, uniform failure - one spec re-run on a fresh port passed 7 of 7 in 11.9 s. Killing the shell that STARTED a detached server does not stop the server; match `node` on its command line.

**Two navigations to URLs differing only in a fragment navigate nothing**, and the same URL after a rebuild is served from the browser cache - three times on one port on 2026-09-05, where the served byte count and the measured DOM disagreed and only the DOM was read. Give every navigation its own query string, and check a number the two builds must differ on before trusting anything else on the page.

**`git checkout HEAD -- <paths>` restores the file from BEFORE your change**, so commit first if you are proving that a change bites; otherwise both arms build the old file and the "with my fix" arm fails. The control arm of an A/B also DELETES uncommitted edits on those paths, and `git status --porcelain` comes out empty afterwards, which is exactly what a clean restore looks like - it took four uncommitted string fixes on 2026-09-03 and nothing failed for two hours. `git diff --numstat` is not a restore check for a file your own change modified, because it compares against `HEAD` and is non-empty by design. Take a SHA-256 before you patch and compare from a separate process.

**An arm that intercepted nothing is a null result, not a pass.** Print the count of intercepted or aborted requests and require it to be non-zero; an abort arm that never fired proves only that the pattern was wrong. The honest degraded arm for a build-time surface is a root override: copy `state/` and `frontend/public/` to `TEMP`, truncate every CSV to its header, point `STATE_ROOT`, `TELEMETRY_ROOT` and `DIGEST_ROOT` at the copy, and rebuild.

**`python -m http.server` serves `.js` with the registry MIME type**, which on Windows is often `text/plain`, so the browser refuses the module and SvelteKit never hydrates - while the page still looks right and logs zero errors, and every post-hydration measurement reports the prerendered value. Assert `Object.keys(window).some(k => k.startsWith('__sveltekit'))` before reading a number, or serve through the project's own preview.

## Measurement recipes

**Timing a `$lib/server/` module in plain Node** needs the alias resolved. Bundle it with the local esbuild and import the bundle, which works because the only `$lib` import in `payload.ts` is `import type` and esbuild erases that before resolving the alias. Two traps in the harness rather than the bundle: the environment variable holding the module path must be a `file://` URI or Node reads a Windows drive letter as a protocol, and `DIGEST_ROOT`, `STATE_ROOT` and `TELEMETRY_ROOT` must be set BEFORE the dynamic `import`, since the module reads them at evaluation. The one warning it prints about a missing base tsconfig is harmless.

```pwsh
node_modules\.bin\esbuild.cmd src/lib/server/payload.ts --bundle --format=esm --platform=node --packages=external --outfile=$out
```

A throwaway spec under `frontend/tests/` would be swept up by the shared selector on the next run, which is the reason to bundle instead.

**The committed `tokenizer.json` bakes in truncation and padding**, so every encode returns exactly 128 ids whatever you feed it - a six-word headline and a two-thousand-word article alike, and a p50, p95 and max that agree read as a narrow distribution rather than a broken instrument. Call `no_truncation` and `no_padding` first; diagnose with `json.loads(Path(f).read_text)["truncation"]`. And the unknown-token share does not detect text the encoder cannot read - the vocabulary holds single Devanagari, Arabic and Cyrillic characters, so Hindi scores 0.008 and Arabic 0.000 while no query will ever retrieve them. Measure the Latin share instead: over 1,889 committed items on 2026-08-26 that gave two points with nothing between them, 3 items at 0.0 and the next lowest at 0.9975.

**`trafilatura` drops a repeated paragraph**, so a page built to a chosen length by repetition comes out short - about 150 words whether the page holds 30 copies or 3,000, and nothing errors. Give each copy an ordinal, and count the prefix you added: 320 unique 12-word sentences extracted to 3,783 words against 3,840 asked for, where the identical-sentence version of the same page gave 121 (2026-08-26).

**Every performance number carries the hardware, the date and the spread** (`CLAUDE.md` Rule #10). Where the working matters, it lives in [../measurements.md](../measurements.md), not here.

## A clean merge is not a working merge

**A branch that deletes a name merges without conflict and fails at import.** Git compares text; nothing checks that the symbol another branch started calling still exists. On 2026-08-27 a branch replaced `cli.INDEX_ROOT` with a function and `main` added eleven tests that patch the constant - a clean `ort` merge, then eleven failures naming one attribute. Whoever merges second owns the semantic conflict, whichever branch introduced it, and the replacement has to be checked rather than assumed to resolve to the same value.

**The dangerous half is often the part git calls clean**, and it need not be a name. Two rows that both auto-merged one route page on 2026-09-01 - one narrowing bars to a window, one adding a strip above them - produced a file drawing windowed bars over a strip that still read the whole ledger. Every symbol resolved and the suite passed. The cheap early warning before merging: `git grep` the names your branch deletes, from `git diff --name-only main...HEAD`. It exits 1 when it finds nothing, which a `&&` chain reads as failure.

**Read the failure before blaming your own change.** A whole file of failures sharing one identical `AttributeError` or `ImportError`, on a surface your row never touched, is a rename that crossed a branch.

**GitHub can produce a red `main` when nobody ran a merge.** On 2026-08-27 #186 deleted a function with no remaining caller and #166 landed a test importing it; neither touched a line the other did, both were green, both merged, and an ImportError at collection meant zero of 1,288 tests ran. A green check on a pull request is not a statement about `main`, because GitHub does not re-run checks when the base moves. The check that closes the gap is merging `origin/main` locally and running the gate on the result; the narrow version is `git log --oneline -S '<name>' origin/main` for each symbol the branch newly imports. A local red against a green CI on the same commit is usually a stale base - 47 backend tests red locally on 2026-09-09, all cascading from one defect the next commit on `main` had already fixed.

**A test that asserts the producer has not run yet is a time bomb** - it counts unmigrated rows and goes red on the day the last one ages out, taking every open pull request with it, which reads as an infrastructure fault rather than one stale assertion. A pipeline push carries the job's own token and starts no workflow, so nothing goes red at the moment it breaks. Prove a read-side migration by removing the key from a fixture, which cannot age out.

**A whitespace-sensitive "did I lose a line" check reports false losses.** A resolution that re-nests a block changes the leading spaces on every line, so a set difference over raw lines lists the whole block as dropped. Compare normalised text. After a base/override inversion in a token file, grep every other file that emits the same custom property: a generated stylesheet still emitting the light value under `:root` put the default document at 2.99:1 against a 4.5:1 bound, with no conflict anywhere and every theme test green because each names a theme explicitly. A test that splits a stylesheet at a selector inverts with it, so split at the OVERRIDE selector.

## The commit-and-push script

**A path added to `.github/scripts/commit-and-push.sh` must already exist in a fresh checkout.** The script runs `git add "$@"` under `set -euo pipefail` with every path a job owns in one call, so a file that appears only once its producer succeeded turns a producer failure into a failure of the whole commit step, and the other ledgers staged beside it are lost with it. Ship a new ledger with its header committed.

**A test that runs the real script will edit your own `state/` unless every command it hands the script is substituted.** The harness runs the shipped script against a temporary repository, but any step spelled `python -m idhazh <verb>` resolves its paths off the INSTALLED package, so a seven-shard fan-out test settles this checkout's committed ledgers seven times, silently. Substitute with a helper that takes the tree as an argument (`backend/tests/settle_ledger.py`, `rebuild_day.py`), and check `git status --porcelain` after any run that exercised the commit step. Adding one settlement command to the workflow armed four of those tests at once on 2026-09-02; `_settled_in_the_clone` now refuses an unsubstituted command by name, so the failure is readable rather than silent.

**A new pipeline CLI flag may not be named after a `llama-server` flag.** The server's argv is built once from `config/` by `llama_server_flags`, and `test_every_job_that_starts_a_server_reaches_the_one_argv_builder` reads every `run:` body in every workflow and fails on any whole-token match - so a stage wanting the scraped `/metrics` body takes `--counters-file`, not `--metrics`. The failure names the step and the flag, which is quick to read only if you know the guard is about the server's namespace and not about your stage.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the gate commands themselves.
- [browser.md](browser.md) - the browser suite's own failure modes.
- [git-and-github.md](git-and-github.md) - reading a CI run and merging.
- [../measurements.md](../measurements.md) - the numbers and their working.
