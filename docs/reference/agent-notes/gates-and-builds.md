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
$env:IDHAZH_PYTHON = '<abs path to python.exe>'; npm --prefix frontend run test:changed
```

The same variable is needed for any Playwright spec that runs a backend command (`malformed-day.spec.ts` shells out to `idhazh validate-days`). Without it the suite returns `1 failed, 1008 passed` and the message reads as a broken validator, not a `PATH` problem.

**`test:changed` REUSES a cached failed run.** A re-run prints `Reusing completed run <hash>: exit 1. Use --fresh to rerun unchanged inputs.` and exits 1 in two seconds, which reads as "still broken" when nothing ran. The record is keyed on the input tree, so an environmental flake stays cached until the tree changes. Pass `--fresh`; a green re-run then overwrites the record.

**`test:changed` can exit 1 with every test green.** `malformed-day.spec.ts` runs `idhazh validate-days` at the repository root, which appends a row to the tracked `state/day-validations.csv` for any day lacking a receipt under the current rules. That file is inside the fingerprint the selector re-checks after the browser groups, so the run ends `The canary build has stale inputs` under a list where all 1,009 tests passed. The tell is a modified `state/day-validations.csv` you never touched. Confirm the rules did not move, and do not commit the row:

```powershell
python -c "from idhazh.cli import _validator_identity; print(_validator_identity())"
```

**`npm run bundle-gate` no longer weighs a route against a recorded number.** Until 2026-08-30 it held each route's first-load JavaScript within 64 bytes of a hand-maintained record, and telling that gate's toolchain noise apart from a real change took a control build every time. That comparison and `frontend/bundle-baseline.json` are both gone. What remains has no machine offset and is still live: the gate REFUSES an encoder on the first-load path, and holds each capped page under its ceiling in `config/idhazh.json`.

**A new backend test module fails CI unless a registered `pytestmark` or the exemption list names it.** `test_marks.py` requires every module under `backend/tests/` to carry a mark or appear in `UNMARKED_MODULES`, and the failure names the marker registry rather than your file. Add the module in the same commit that creates it.

**A pytest harness that runs inside CI inherits `$GITHUB_OUTPUT`.** A test spawning a script that appends to it writes into the job's real output file and can overwrite a downstream job's inputs. Point the variable at a temporary file in the fixture.

**A test's `print()` never reaches you on the default run.** `pyproject.toml` sets `addopts = -q -n auto`, so output is captured and xdist swallows it. Use `-n0 -s -k <name>`; `-p no:xdist` exits 4. That same committed `-q` also means your own `-q` gives `-qq`, which removes the summary line - and changes `--collect-only` from a list of ids to a bare count, so a search for a renamed parametrized id finds nothing and reads as broken collection. Drop `-q` to list ids. `-k` cannot select a hyphenated id at all, because it splits on Python-identifier rules; run the node by its full id.

**A length test written with two-letter words is graded by the character rail, not the length rule.** `summarize.output_schema` puts `minLength` and `maxLength` on the summary field, and Pydantic checks those while PARSING the reply - before anything counts a word. So `"y " * 100` is 100 words and 200 characters, the rail throws it out as `bad_shape`, the length rule never runs, and the failure claims the verdict is `None`, which sends you into the verdict function. Build the fixture from realistic words (`"deliberation " * 100` is 100 words and 1,300 characters); the schema assumes roughly 5 characters per word at the floor and 13 at the ceiling. An over-length fixture has to stay under the character ceiling for the same reason. Seen 2026-09-10.

**ruff rewrites a cross-check into the expression it was checking.** RUF007 turned a hand-written pairwise walk into `itertools.pairwise`, which is what the assertion existed to verify. When a test checks an implementation, write the check in a third form the linter will not fold. Two more: B018 rejects a bare attribute used as a parse guard (assign it, `_ = parts.port`), and renaming a module makes ruff report I001 on files you never opened, because the import ordering changed under them.

**`ruff format` is NOT a gate here.** Running it rewrites unrelated files - 14 on 2026-08-24, 38 on 2026-08-29, 73 on 2026-09-08, which is a magnitude rather than a figure. `ruff check` is the gate.

**mypy only checks the platform branch you are standing on.** A `sys.platform` guard hides the other arm entirely, so CI fails on code that type-checked locally. Run `mypy --platform linux` before pushing from Windows.

**A new CLI flag anywhere under `backend/` can fail a test in a file you have never opened**, because a test asserts the flag set. Run the backend suite after any CLI change, however small.

## Contracts and schemas

**`git status --porcelain -- schemas/` straight after `python -m idhazh.contracts.export` looks like every schema changed.** The exporter prints the path of every file it wrote, so the two commands' output runs together and reads as twenty-nine modified files; `git diff --stat -- schemas/` is the question you meant, and empty is the pass. And `git diff --exit-code -- schemas/` is not the drift gate until you have committed - the gate is `test_committed_schemas_match_the_models`, which exports into a temporary directory and compares against the committed bytes, so it does not care what `HEAD` holds.

**The schema export CLI needs an absolute `--out` path.** A relative one resolves against the process directory, so the files land outside the worktree.

**Round-tripping a committed config through its model puts back fields you deleted.** A model with defaults re-serialises them, so a config edit becomes a config restore. Read the diff before staging.

**The opposite rule applies to `tests/fixtures/contracts/`.** One new field breaks four fixtures at once; re-serialise them through `BY_STEM` rather than editing them by hand.

**A hand-written CSV line needs `version` first.** A row one cell short raises `AttributeError` deep inside the reader, where nothing catches it and the message names neither the file nor the row.

**`Sources` refuses two feeds at one URL**, so a fixture with a duplicate fails at config load - before any test body runs, with a message about configuration.

## Running the gates

**A guard that enumerates hazards is wrong the day after it is written.** `test_archive_readers.py` held twelve approved paths and covered two collections out of nineteen; its own maintenance cost grew with the number of collections, which is the defect it existed to catch. It was deleted (`CLAUDE.md` Rule #12). State a rule as a property and enforce it in review.

**A stopwatch cannot prove a cost stopped growing on this box.** Scheduler noise on a shared developer machine swamps the difference between an O(1) read and a small O(n) one, so a wall-clock comparison "proving" a fix is measuring the machine. Assert the property instead - count what the code opened, or bound the input.

**`vite build` alone is not the build.** The full gate produces a bundle around 200 bytes heavier, and the spread between repeated runs of the same command is 8 bytes against 173 bytes across the two forms, so the difference is real and the wrong command reports a number that will not reproduce in CI. Use the gate command in [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md).

**Two builds of one unchanged tree do not agree on about 20 percent of `build/`.** SvelteKit defaults `kit.version.name` to `Date.now()` and stamps it into the manifest and the service worker, so a byte comparison between two builds is measuring the clock. Pin it. That pin is then a live grenade when the variable is unset: two ids reach the page, nothing hydrates, and every interaction test fails for a reason that is not in the diff.

```powershell
$env:BUILD_VERSION = 'measure'; npm --prefix frontend run build
```

**Two builds back to back can fail with `EPERM` on `.svelte-kit/output`** when the previous process still holds it. Retry once before treating it as a real failure. Windows also will not start `npm` from a bare name inside a script - use the full shim path.

**The browser suite goes quiet for minutes and is still working.** Check that the log file's `LastWriteTime` is advancing, and check CPU - and check the right process, because during the longest quiet stretch the busy one is `node`, not `chrome-headless-shell`. Run the suite through `npm run test:browser` and nothing else; `npx playwright test <group>` piped into a filter prints nothing until the whole group finishes.

**A green local `svelte-check` says nothing about the site job**, because CI type-checks the MERGE of your branch and `main`. A branch that deletes a name merges cleanly and fails at import there.

**A callback option in `svelte.config.js` needs a JSDoc `@param`**, or `svelte-check` reports an implicit `any` in a config file that has no types of its own.

**A test that skips itself when it cannot find a control is a gate that turns off silently.** Assert the control exists, then assert what it does.

**Never build a fixture object by spreading `Partial<T>`** - the missing fields do not fail the type check and the test asserts on `undefined`.

**Write every long gate to a UNIQUELY named file.** Two detached launches sharing one log path interleave into a transcript that belongs to neither run, and the second launch is easy to make because the first printed nothing. Put the row tag and a timestamp in the name, and check for a live copy before starting a second.

**A launch that reported nothing still launched.** Two builds running at once produce a byte number belonging to neither. Check for a live copy before starting a second.

**A page-weight failure is often not yours.** Read `main`'s check-runs for the same gate before investigating your diff.

## Two heavy gates on one box

**Symptom: a gate costs ten times its usual wall clock and the browser suite fails on a commit CI passed.** Nothing coordinates two agents' gates, and the box has four cores. It is contention, not a regression.

`backend/utilities/gate_lock.py` serialises the heavy gates, one of three at a time. Chain every heavy gate into ONE locked script rather than taking the lock repeatedly - the second acquisition queues behind whoever got in first. By design it cannot fail your gate: if the lock cannot be taken it runs anyway. CI never takes it, because each job has its own runner.

**Killing a queued build under the lock leaves the tree unservable**, with a half-written `build/`. Rebuild before measuring anything.

`os.kill(pid, 0)` is not a liveness probe on Windows, so a stale lock file needs a different check.

**Raising the Playwright worker count measured slower locally and faster in CI**, because the two machines have different core counts. Put concurrency knobs behind environment variables and take the number in CI.

## The canary build

**`npm run build:canary` does not build the canary day.** Two commands, in order - one writes the fixture day, one builds the site against it:

```powershell
python backend/utilities/build_canary_day.py     # from the repository root only
npm --prefix frontend run build:canary
```

The script resolves its paths against the repository root; run from `backend/` it writes the day into the wrong tree and reports success.

**The canary and the committed digest are two builds for two questions - do not swap them.** The canary is fixed in size, so it is what a per-item rule and any screenshot should run against; the committed digest is what a whole-archive question needs. A screenshot of the reading page built from the committed digest times out.

**The canary's `day-metrics` record is written before the ledgers it reduces**, so a route that reads one of those ledgers can only be tested empty on the canary. Keep the canary's column list and the contract assertion in the same test, so a new column cannot land in one and not the other. The generator once appended instead of rewriting, which made every run's fixture different from the last; the shape generalises to any fixture builder that opens its output for append.

## Serving a build to measure it

**A commit made after the build turns the next browser run red**, because the fingerprint no longer matches. Build last, or rebuild.

**Use `npm run preview`, not a hand-started `vite preview`.** A hand-started server cannot tell a real hydration failure from its own, and `--outDir build` still serves static assets out of `.svelte-kit/output/client` - `--outDir` names a directory `vite preview` does not read. To serve a specific tree, build that tree. `vite preview` also serves through `sirv` with `dev: true`, and renders the SPA fallback per request, so smoke `/404.html` explicitly. It can take a minute to bind under load.

**A killed Playwright run leaves its preview server behind and poisons the next run** - the symptom is uniform timeouts at the same duration for every spec. Playwright takes the port from `PREVIEW_PORT` (default 4173); kill whatever holds it before re-running. Killing the shell that STARTED a detached server does not stop the server.

**Two navigations to URLs differing only in a fragment navigate nothing**, and the same URL after a rebuild is served from the browser cache. Change the path or bypass the cache.

**`git checkout HEAD -- <paths>` restores the file from BEFORE your change**, so commit first if you are proving that a change bites. The control arm of an A/B also deletes uncommitted edits on those paths. `git diff --numstat` is not a restore check - take SHA-256 of the file, because a restore written inside a long script can quietly not have happened.

**An arm that intercepted nothing is a null result, not a pass.** Print the count of intercepted or aborted requests and require it to be non-zero; an abort arm that never fired proves only that the pattern was wrong.

**`python -m http.server` serves `.js` with the registry MIME type**, which on Windows is often `text/plain`, so modules do not load. Serve through the project's own preview.

## Measurement recipes

**Timing a `$lib/server/` module in plain Node** needs the alias resolved; import the built file or point the loader at the alias explicitly, or the timing is of an import failure.

**The committed `tokenizer.json` bakes in truncation and padding**, so every encode returns 128 tokens whatever you feed it. Disable both before counting. And the unknown-token share does not detect text the encoder cannot read - measure the Latin share instead.

**`trafilatura` drops a repeated paragraph**, so a page built to a chosen length by repetition comes out short. Give each copy an ordinal, and count the prefix you added.

**Every performance number carries the hardware, the date and the spread** (`CLAUDE.md` Rule #10). Where the working matters, it lives in [../measurements.md](../measurements.md), not here.

## A clean merge is not a working merge

**A branch that deletes a name merges without conflict and fails at import.** Git compares text; nothing checks that the symbol another branch started calling still exists. Whoever merges second owns the semantic conflict, whichever branch introduced it.

**The dangerous half is often the part git calls clean.** Two rows that both read one ledger merge silently into a reader that agrees with neither writer. The cheap early warning before merging: `git grep` the names your branch deletes. It exits 1 when it finds nothing, which a `&&` chain reads as failure.

**Read the failure before blaming your own change.** A red gate on a merge commit is as likely to be the other branch's.

**GitHub can produce a red `main` when nobody ran a merge.** Two pull requests, each green against its own base, land in sequence and the second breaks the first. A green check on a pull request is not a statement about `main`; the check that closes the gap is merging `origin/main` locally and running the gate on the result. A local red against a green CI on the same commit is usually a stale base.

**A test that asserts the producer has not run yet is a time bomb** - it counts unmigrated rows and goes red on the day the last one ages out, taking every open pull request with it. Prove a read-side migration by removing the key from a fixture.

**A whitespace-sensitive "did I lose a line" check reports false losses.** Compare normalised text, or compare the set of leads. After a base/override inversion in a token file, grep every other file that emits the same custom property.

## The commit-and-push script

**A path added to `.github/scripts/commit-and-push.sh` must already exist in a fresh checkout**, or the workflow fails on a clone where nothing has written it yet.

**A test that runs the real script will edit your own `state/` unless every command it hands the script is substituted.** The harness runs the shipped script against a temporary repository, but any step spelled `python -m idhazh <verb>` resolves its paths off the INSTALLED package, so a fan-out test settles this checkout's committed ledgers once per shard, silently. Substitute with a helper that takes the tree as an argument (`backend/tests/settle_ledger.py`), and check `git status --porcelain` after any run that exercised the commit step. Adding one settlement command to the workflow arms four of those tests at once.

**A new pipeline CLI flag may not be named after a `llama-server` flag.** The server's argv is built once from `config/` by `llama_server_flags()`, and a guard refuses a stage flag in that namespace - so a stage wanting the scraped `/metrics` body takes `--counters-file`, not `--metrics`. The failure names the step and the flag, which is quick to read only if you know the guard is about the server's namespace and not about your stage.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the gate commands themselves.
- [browser.md](browser.md) - the browser suite's own failure modes.
- [git-and-github.md](git-and-github.md) - reading a CI run and merging.
- [../measurements.md](../measurements.md) - the numbers and their working.
