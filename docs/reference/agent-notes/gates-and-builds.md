# Agent Notes - Gates and Builds

**Last Updated**: 2026-10-03

Checks before trusting a test or build result. Commands belong in [run-the-gates.md](../../how-to/run-the-gates.md).

## Gate commands

- Inspect `npm --prefix frontend run test:changed -- --list`, then run the selected checks. Keep full-suite checks in CI unless local full coverage is needed.
- Read the first failure and which later checks did not run. A missing tool, interrupted process, cached failure or skipped test is not a pass.
- Inspect an existing run before starting another. Use the launcher's `--status`; use `--fresh` only when an unchanged run must be repeated.

## Running the gates

- Confirm the interpreter and imported package belong to the intended environment and checkout. Use the documented `IDHAZH_PYTHON` setting for frontend commands that invoke Python.
- Keep inputs unchanged during a check. If a test dirties tracked files, fix its output location rather than bypassing the input check.
- Drive migrations and failure states with bounded fixtures. Confirm the fixture reaches the behavior under test; do not skip an assertion because its required control or data is absent.
- A generic file-format test needs a real fixture of that format, not a ledger chosen only because it currently uses it. After a ledger migrates, keep old-format reader coverage explicit and test its current writer through the native persistence API.
- Before moving a document or changing a table, check for tests and tools that read it. Repair those inputs as well as Markdown links.
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

## Two heavy gates on one box

- Let `test:changed` acquire its own lock. Do not wrap it in the same lock, bypass coordination, launch duplicate checks, or stop another worker's run.
- Reproduce a timing failure in isolation before changing code. Do not raise a timeout or weaken an assertion merely to obtain a pass.

## The canary build

- Use the canary, the fixed test-data build, for the browser suite; use the real build for published-site measurements. Verify which build is served.
- Finish one build before starting another that writes the same output directory. Do not rebuild files while a preview or test is reading them.

## Serving a build to measure it

- Use the project's build and preview scripts. Verify a feature of the intended build before measuring, including hydration when the check needs it.
- For paired measurements, keep inputs and build settings equal except for the change being measured, and alternate the cases. Verify the intended difference before comparing results.
- Prove missing-data behavior by removing the input the surface actually reads. For build-time data, rebuild against an isolated fixture; blocking an unused request proves nothing.

## See also

- [../../architecture/contracts/schemas.md](../../architecture/contracts/schemas.md) - payload changes and their fixtures.
- [browser.md](browser.md) - browser verification.
- [git-and-github.md](git-and-github.md) - reading remote checks.
