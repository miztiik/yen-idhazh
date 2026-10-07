# Agent Notes - Gates and Builds

**Last Updated**: 2026-10-07

Checks before trusting a test or build result. Commands belong in [run-the-gates.md](../../how-to/run-the-gates.md).

## Gate commands

- Inspect `npm --prefix frontend run test:changed -- --list`, then run the selected checks. Keep full-suite checks in CI unless local full coverage is needed.
- Read the first failure and which later checks did not run. A missing tool, interrupted process, cached failure or skipped test is not a pass.
- Inspect an existing run before starting another. Use the launcher's `--status`; use `--fresh` only when an unchanged run must be repeated.
- `node scripts/build-state.ts --complete` took 112.5 s on the shared Windows machine on 2026-10-03, so wait for it rather than calling it hung.
- A fresh worktree has no `.venv` and no `frontend/node_modules`, and setting both up is the slowest step: on 2026-10-07, on the shared Windows machine, `npm ci` took 513 s and `pip install -e ".[dev]"` took 1,583 s after one package-feed timeout and a retry (plan 62's row L19), and 114 s and 991 s in another worktree the same day. Start both before the first check needs them, and wait rather than calling either hung.
- **`pytest -m contract -q` ends on a `FAILED` line with no count after it, which reads as a run that stopped; it finished, and the extra `-q` hid the count.**
  `addopts` in `pyproject.toml` already carries `-q`, so one more is `-qq`, and
  pytest 9.1.1 then drops the `N passed, M failed` line (2026-10-06). The tell
  is the short test summary as the last output, with nothing after it. Leave
  `-q` off:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -m contract
  ```

## Running the gates

- Confirm the interpreter and imported package belong to the intended environment and checkout. Use the documented `IDHAZH_PYTHON` setting for frontend commands that invoke Python.
- Keep inputs unchanged during a check. If a test dirties tracked files, fix its output location rather than bypassing the input check.
- Drive migrations and failure states with bounded fixtures. Confirm the fixture reaches the behavior under test; do not skip an assertion because its required control or data is absent.
- A generic file-format test needs a real fixture of that format, not a ledger chosen only because it currently uses it. After a ledger migrates, keep old-format reader coverage explicit and test its current writer through the native persistence API.
- Before moving a document or changing a table, check for tests and tools that read it. Repair those inputs as well as Markdown links.
- Adding a persisted contract or retiring a task changes named test inputs too. Update the explicit fixture-path list, task declaration and module lists, and transitive-import lists beside the implementation. A committed fixture that the named fixture list omits is still untested.
- Check platform-specific Python APIs with mypy's CI target platform. Guard Windows-only code directly with `sys.platform == "win32"`; an intermediate boolean can prevent the checker from excluding that branch on Linux. Include the shared fixture module when checking a test file in isolation.
- A passing race test must reproduce the production changes: file additions and deletions, changing content-addressed paths, and competing push timing. A stable-path fixture or a test that retains superseded nodes does not prove a content-addressed replacement retry works.
- Before and after splitting tests, compare the collected test cases, allowing only the intended module-path changes. A passing remainder does not prove that no tests were lost.
- For a structural contract move, compare its on-demand schema before and after, then run import and type checks. Preserve class docstrings: Pydantic includes them in schema descriptions.
- Use the complete project build command. For byte comparisons, use one fixed `BUILD_VERSION` across both builds so generated identifiers do not change. Never measure output from a failed build.
- Compare CI's actual candidate and failure with your local tree before attributing a regression. A conflict-free merge does not prove that the combined changes work.
- **A compaction test or profile reads as a code regression; it is a slow
  Windows machine.** On a shared Windows box, every small-file open or atomic
  rename the compaction code performs can cost around 30 ms, almost
  certainly from antivirus scanning the worktree and the system temp folder.
  The same profile on a stock GitHub `ubuntu-latest` runner took the same
  file operations well under a millisecond each - see "Where the remaining
  time goes" in
  [what-a-compaction-pass-costs.md](../benchmarks/what-a-compaction-pass-costs.md).
  Before suspecting the code, compare against that Linux reading. Excluding
  the worktree and temp folders from the Windows antivirus scanner is the
  person's own machine choice; an agent does not change machine settings to
  fix this.

- **A logic spec fails with `ERR_MODULE_NOT_FOUND` in a fresh worktree; the
  spec is fine, the worktree has no `node_modules`.** `npx playwright` then
  loads a cached global copy that cannot import the config. The tell is an
  `npm-cache\_npx` path in the stack. The logic group needs no build, so link
  a sibling checkout's install with the same lockfile instead of running
  `npm ci`. A junction needs an absolute target. Remove it with `rmdir`:
  `Remove-Item -Recurse` follows the link and deletes the sibling's install.
  ```powershell
  New-Item -ItemType Junction -Path frontend\node_modules -Target (Resolve-Path <sibling>\frontend\node_modules).Path
  cmd /c rmdir frontend\node_modules
  ```

- **A build through a linked `node_modules` fails on a missing package; the
  code is fine, the linked install changed under you.** Its owner can run
  `npm ci` or switch branches while you use it. On 2026-10-07, on this Windows
  machine with Node 24.12.0, vite failed with `Rollup failed to resolve import
  "@duckdb/duckdb-wasm"` after two builds through the same link had passed.
  The tell is that package missing from the sibling's folder. Remove the link,
  run your own `npm ci` (134 s in one run here), then build again:
  ```powershell
  cmd /c rmdir frontend\node_modules
  npm --prefix frontend ci
  ```

- **A logic spec that renders a component fails with `Cannot find package '$lib'` on its first run in a fresh worktree or a copy of a commit, then passes; the spec is fine, `.svelte-kit/` did not exist yet.**
  `frontend/tsconfig.json` takes `$lib` from `.svelte-kit/tsconfig.json`, which
  `npm ci` does not write. Playwright reads the paths when it starts; the run's
  own `vitePreprocess` writes the file after that (2026-10-06, Node 24.12.0:
  `console-data-explorer-shape.spec.ts` 1 failed and 7 did not run, then 25
  passed). The tell is a `.svelte-kit` folder created during the failed run.
  Write it first, from `frontend/`, where the Svelte config is:
  ```powershell
  npx svelte-kit sync
  ```

- **An older index-ceiling check fails locally while CI passes; it used a
  different compressor from the deployment gate.** Windows Python can use
  zlib-ng rather than the gate's Node zlib. The current `test_page_ceilings`
  helper uses Node gzip, matching `bundle-gate.mjs`, without raising ceilings
  or reducing the required margin. A check on an older commit may still differ;
  compare its generated index with the deployment gate's compressor first.

- **A logic spec that writes Parquet prints `Assertion failed: !(handle->flags & UV_HANDLE_CLOSING)`, which reads as a crash; its tests passed.**
  On 2026-10-05, on Windows with Node 24.12.0 and DuckDB-Wasm 1.33.1-dev57.0,
  a Playwright worker that had written files with `COPY ... TO` printed this
  libuv line while it shut down, after every result was reported, and the run
  still ended `N passed` with exit 0. The door specs, which only read, print
  nothing. The tell is the line arriving between results or at a worker
  restart, never inside a test. Read the summary and the exit code:
  ```powershell
  node node_modules/@playwright/test/cli.js test --config playwright.logic.config.ts tests/ledger-lifecycle.spec.ts; "exit $LASTEXITCODE"
  ```

- **`test:changed` stops with `The selected Python executable does not exist.` in a worktree with no `.venv`; the Python is there, and the launcher refused the name it chose itself.**
  With no `.venv`, `frontend/scripts/run-checks.ts` falls back to the bare
  name `python` and hands that name to the run inside its lock as
  `IDHAZH_PYTHON`, which that run refuses because no file has that path
  ([defect 62](../../../TODO/20260823-known-defects-plan.md)). Plan 62's row
  L20 met it on 2026-10-07. The tell is the message right after
  `[checks] waiting for the test slot` and a second copy of the selection.
  Set up `.venv` as
  [run-the-gates.md](../../how-to/run-the-gates.md#set-up-the-backend-environment)
  says, or hand the launcher a full path:
  ```powershell
  $env:IDHAZH_PYTHON = (Get-Command python).Source
  ```

- **A copied `bundle-gate.mjs` fails with a `SyntaxError` on an `import`; the
  script is fine, it has no `package.json` beside it.**
  `frontend/package.json` sets `"type": "module"`, which is what tells Node to
  read `frontend/asset-base.js` as an ES module. Copy `bundle-gate.mjs` alone
  into a bare folder and Node falls back to CommonJS, where `import` is a
  syntax error. Plan 62's row L24 met it on 2026-10-07. The tell is the error
  naming the `import` line itself, not a missing module. Copy the commit's
  `frontend/package.json` beside the script, or run it from a full checkout
  of `frontend/`:
  ```powershell
  Copy-Item frontend\package.json <bare-folder>\package.json
  ```

## Two heavy gates on one box

- **The unlocked gate control reports a missing interval, not a failed child.**
  On Windows with Python 3.14.2 on 2026-10-07,
  `test_ci_runs_the_gate_unlocked_and_the_same_workers_then_overlap` failed in
  the full suite and in an isolated retry. All children exited successfully,
  but their shared append file lacked an interval. A recorder race is a
  suspect, not a proven production lock failure. Do not weaken the assertion;
  compare separate per-worker records before changing the lock implementation.
- Let `test:changed` acquire its own lock. Do not wrap it in the same lock, bypass coordination, launch duplicate checks, or stop another worker's run.
- Reproduce a timing failure in isolation before changing code. Do not raise a timeout or weaken an assertion merely to obtain a pass.
- **A Playwright run sits still after its last result, or between `--repeat-each` repeats, then ends exit 1 with every test passed; it is Playwright waiting for a worker to exit, then killing it.**
  The wait is `PWTEST_CHILD_PROCESS_TIMEOUT`, 5 minutes by default. On
  2026-10-06, on Windows with Node 24.12.0 and Playwright 1.62.1, workers of
  one `ledger-ranges.spec.ts` test outlived it 1 time in 2; with it at 20
  seconds, 16 times in 30 and then 4 in 30. It is not only a `--repeat-each`
  effect: on 2026-10-07 a single run of one spec, from a config with no
  `webServer`, stalled the full 5 minutes (plan 62's row L19), and 11 console
  specs run directly with `--no-deps` ended 179 passed and 0 failed, exit 1,
  when their last worker was killed (row L27). Only the worker and its esbuild
  service process stay alive; the cause is unknown, and CI shows no stall.
  The tell is `force-killed it` between or after the results, and at the end
  `errors were not a part of any test`, with no test failed and none that did
  not run. Every test passed, and the exit code reports the kill. Read the
  counts; shorten the wait only as the next note says.

- **A run with `PWTEST_CHILD_PROCESS_TIMEOUT` set ends with a few tests passed and the rest "did not run"; the setting killed a project that another project depends on.**
  A shorter wait helps where no project depends on another: at 20 seconds,
  row L19's single run waited 20 seconds instead of 5 minutes. It breaks a run
  where one does: in `frontend/playwright.config.ts` the `reader` and
  `console` projects depend on `offline`. At 20 seconds Playwright killed the
  `offline` worker as it exited, counted the kill as that project's error, and
  ran no test of the project that depends on it: row L27's run through
  `test:changed` ended "9 passed, 179 did not run" (2026-10-07). To tell which
  case you are in before the run, read the config it uses: a project with
  `dependencies` means leave the wait at its default. After the run, the tell
  is `did not run` with nothing failed. For a spec that never contacts the
  preview server, use a config with no `webServer` and one project,
  `playwright.logic.config.ts`, and shorten the wait there:
  ```powershell
  $env:PWTEST_CHILD_PROCESS_TIMEOUT = '20000'
  node node_modules/@playwright/test/cli.js test --config playwright.logic.config.ts tests/<spec>.spec.ts
  Remove-Item Env:PWTEST_CHILD_PROCESS_TIMEOUT
  ```

- **Some cases of a parallel run fail with `EPERM` on a path under `.svelte-kit/types`; the tests are fine, several workers wrote that folder at once.**
  A spec that renders a component through `serverCompiler` in
  `frontend/tests/support/server-render.ts` compiles Svelte in its own
  worker. On 2026-10-07, on Windows, plan 62's row L27 ran such specs on three
  workers at once: 6 cases failed with `EPERM` in `.svelte-kit/types`, and on
  one worker the same 6 gave their real results. The tell is `EPERM` naming a
  path under `.svelte-kit/types`. Keep one worker, the default while
  `PLAYWRIGHT_WORKERS` is unset, or run the failed cases again on one:
  ```powershell
  node node_modules/@playwright/test/cli.js test --config <config> tests/<spec>.spec.ts --workers=1
  ```

## The canary build

- Use the canary, the fixed test-data build, for the browser suite; use the real build for published-site measurements. Verify which build is served.
- Finish one build before starting another that writes the same output directory. Do not rebuild files while a preview or test is reading them.
- **A browser run ends `Timed out waiting 120000ms from config.webServer` and runs no test; the build was refused as stale.**
  The build record fingerprints Git's committed tree, the working diff and
  untracked files, so any edit after `build:canary`, a doc or a plan
  included, makes `verified-preview.ts` refuse the build, and Playwright
  pipes that refusal away. The tell is the timeout with no test line before
  it. Commit or revert the edit, then build again before the run:
  ```powershell
  git status --porcelain
  npm run build:canary
  ```
- **The preview refuses a build your change never touched, after a browser tool ran in the worktree; the tool's files are inputs.**
  Every untracked file that `.gitignore` does not cover is fingerprinted. The
  Playwright MCP browser saves page snapshots and screenshots to
  `.playwright-mcp/` in the worktree root; on 2026-10-07 one snapshot there
  made `verified-preview.ts` refuse a fresh canary build, until `.gitignore`
  listed the folder. The tell is `git status` naming a folder no change of
  yours wrote. Ignore that folder in `.gitignore`; deleting its files before
  each build only moves the trap:
  ```powershell
  git status --porcelain --untracked-files=all
  ```
- **The same timeout from a fresh build reads as a stale one; the box was too busy to start the preview in 120 s.**
  `verified-preview.ts` checks the build's inputs and output before it
  serves. On this Windows box at 90 to 100 percent CPU on 2026-10-06, it
  printed nothing for over 100 s from a clean tree, and once printed its
  address just after the limit; the same build served on the next try. The
  tell is an empty `git status --porcelain` since the build. Do not rebuild;
  run the same command again when the load drops:
  ```powershell
  (Get-CimInstance Win32_Processor).LoadPercentage
  ```

## Serving a build to measure it

- Use the project's build and preview scripts. Verify a feature of the intended build before measuring, including hydration when the check needs it.
- For paired measurements, keep inputs and build settings equal except for the change being measured, and alternate the cases. Verify the intended difference before comparing results.
- Prove missing-data behavior by removing the input the surface actually reads. For build-time data, rebuild against an isolated fixture; blocking an unused request proves nothing.

## See also

- [../../architecture/contracts/schemas.md](../../architecture/contracts/schemas.md) - payload changes and their fixtures.
- [browser.md](browser.md) - browser verification.
- [git-and-github.md](git-and-github.md) - reading remote checks.
