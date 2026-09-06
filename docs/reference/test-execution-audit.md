# Test Execution Audit

**Last Updated**: 2026-09-06

Historical test executions and the current selection controls, checked against
`main` at `3b425be8`. This records an investigation, not a change to the testing
policy. The commands and policy remain in
[../how-to/run-the-gates.md](../how-to/run-the-gates.md).

The follow-up implementation adds named frontend groups, a no-server logic
configuration, shared dependency selection, verified build modes and reusable
run records. It also removes the collection-time canary reads and the
worker/orchestrator instruction conflict recorded below. The tables remain the
audit of `3b425be8`, not a description of the corrected code. Current commands
are in the gate guide above.

The follow-up also makes tooling tests conditional, requires lock ownership
for automated runs, checks build inputs before and after compilation, and
includes nested specs in the group inventory. Cached successful test steps
must carry complete executed-test counts. These controls address unnecessary
work and false passes separately; no claim is made that every historical full
suite was redundant.

## Evidence scope

| Source | Coverage |
| --- | --- |
| Claude Code project histories | Six main session files, four worktree sessions and nine subagent logs for this repository, dated 2026-08-22 through 2026-08-28. No newer Claude Code execution was available in those folders. |
| Copilot session index | 31 repository sessions updated from 2026-08-29 through 2026-09-05. The index located relevant conversations; it was not used to count executed commands. |
| Copilot raw conversations | Five execution sessions were examined in detail, including nested worker calls: the reading-page, console-chart-craft and source-health plans, a documentation closure, and a ledger repair. The cases below occurred on 2026-09-01 through 2026-09-03. |
| Preserved test output | The exact local output files named by the historical calls corroborated the recent result counts and durations. No historical command was executed again. |

The Claude Code records live under `.claude/projects/` relative to the Windows
user profile. The Copilot records used here live under
`AppData/Roaming/Code/User/workspaceStorage/6d333b2e3df8b6c99b456864443327d4/chatSessions/`
relative to that profile, with a session UUID as the filename. The named
Copilot debug logs contained session-start records rather than the execution
detail, so the raw chat-session records were needed.

Repeated snapshots of the same tool-call ID count once. A script being written,
a command quoted in a plan, and a worker's summary do not count as executions.
An incomplete result does not count as a pass. Session duration is not test
duration.

## Confirmed cases

These are individual historical local Windows observations. The test outputs
do not stamp the CPU model, resource load or complete toolchain per run. Each
listed outcome is one observation, not a repeated controlled benchmark; no
performance spread or overall percentage saving is inferred. Queue time is
separate from the test runner's reported duration. Dates identify the session
activity; local output timestamps can cross the next calendar day.

| Session and date | What actually ran | Result | Assessment |
| --- | --- | --- | --- |
| Claude Code `4c86403e-6bb5-471e-a071-7cb6498d024e`, 2026-08-27 | `python -m pytest` after the helper was already tested and only the agent-notes document changed | 1,288 passed, 20 skipped in 175.39 seconds | An unchanged code suite was rerun for a documentation edit. |
| Copilot `aeca5368-62ba-4603-b7dc-8ab1570d6385`, 2026-09-02 | Full backend suite through `gate_lock` for documentation and agent-Markdown closure | First attempt waited at least 602 seconds, then failed at import because `protego` was absent. Retry: 2 failed, 2,048 passed in 517.67 seconds. Both failures were gate-lock tests. | Unnecessary local breadth and a missing-dependency check performed after an expensive queue wait. |
| Copilot `c9db2d5d-bf25-4bc2-a48c-723a5be5bd3e`, 2026-09-03 | `python -m pytest` after 35 focused ledger tests had passed | 1 failed, 2,133 passed in 429.61 seconds; the failure was the gate-lock worker-overlap test | Likely unnecessary locally under the targeted-local policy. Full CI validation remains useful for a shared ledger change. |
| Copilot `01093de7-123a-48fd-b76b-98c698fc0fef`, 2026-09-01 | The three console specs below, first against the real build, then against the canary build | Wrong build: 25 failed, 54 passed in 10.0 minutes. Correct build: 79 passed in 59.9 seconds. | A targeted selection still wasted a run because its fixture build was wrong. These were not full-suite runs or a controlled speed comparison. |
| Copilot `a6261527-cf57-4fe0-a41d-0e18137921a4`, 2026-09-02/03 | Two full browser launches for the same source-health worker, with no intervening application edit | Both: 957 passed, 11 skipped. First: 14.0 minutes. Duplicate: 20.8 minutes, after at least 751 seconds waiting behind the first run. | Confirmed duplicate execution. The lock prevented overlap but did not prevent doing the same work twice. |

The three-spec selection was:

```text
npx playwright test tests/console.spec.ts tests/console-run-health.spec.ts tests/console-frame.spec.ts
```

The duplicate browser command, from the worker's frontend directory, was:

```text
python ../backend/utilities/gate_lock.py -- node node_modules/@playwright/test/cli.js test
```

These are historical commands, not recommended launch instructions. The first
browser launch piped output through `Select-Object -Last 40`; a second launcher
then started before the first result had been recovered.

| Evidence | Tool-call IDs in the corresponding Copilot session |
| --- | --- |
| Documentation closure, first and retry | `toolu_0187kxq22TKTXq3tbpNXGsr8`, `toolu_01XJqiCnDnx4PfucUNEHkeAu` |
| Ledger full suite | `toolu_01SHkWKgpm9EXCLvobR1JSsc` |
| Console wrong-build and corrected runs | `toolu_01U1T3GKmUzq6LvaxJ9JQrDS`, `toolu_01CS4ZMNasJZEN2Lxd9Ls3Ha` |
| Duplicate browser launches | `toolu_01Ds7uBGHj9RdPhBCnymAyeL`, `toolu_01CyaehrtWZLH8qecwMiWLS4` |

The reading-page session `47006e97-4249-4e16-b9ac-49eec54d65aa` also ran a full
backend check after resolving a shared appearance-schema merge. That is not
classified as redundant: the candidate changed after the worker's focused
checks. Deliberate measurement builds and tests proving that an injected defect
fails were likewise not classified as wasted work.

## Current selection controls

| Control | Verified state | Consequence |
| --- | --- | --- |
| [../../frontend/package.json](../../frontend/package.json) | `test:browser` is `playwright test`. Native file selection works. | Local runs without selectors execute the whole discovered suite. |
| [../../frontend/playwright.config.ts](../../frontend/playwright.config.ts) | One `chromium` project; one worker; zero retries; 180-second test timeout; global preview server; optional `SKIP_CONSOLE_SUITE`. | No named feature projects or separate no-server logic configuration exist. Pure tests do not request a browser, but still share the configured server prerequisite when executed. |
| Frontend inventory | 73 spec files: 32 whose names start with `console`, and 41 others. These are file counts, not collected test counts. | The 411-test comment in the config is historical, not a current inventory. |
| [../../pyproject.toml](../../pyproject.toml) | `addopts = "-q -n auto"`; no custom marker list. | Even a focused pytest call inherits worker startup. The gate guide's description of parallelism as opt-in is stale. |
| [../how-to/execute-a-plan.md](../how-to/execute-a-plan.md) | Workers run every acceptance gate locally; the orchestrator then runs the Definition of Done. | This wording invites duplicate work and conflicts with the targeted-local default when a row explicitly assigns a full suite to CI. It is not proof that every orchestrator repeated every worker check. |
| [../../backend/utilities/gate_lock.py](../../backend/utilities/gate_lock.py) | One lock across worktrees; default wait is 3,600 seconds, then execution proceeds unlocked. | The lock limits overlap, not scope, duplicate requests or total waiting. It is a scheduling aid, not a test-result cache. |
| [../../.github/workflows/ci.yml](../../.github/workflows/ci.yml) | Backend, site and two Python-version robots jobs run on every PR. Browser runs conditionally; console selection is separate. Main runs the full browser suite. | CI already has some selection. Local commands do not automatically reuse it. Cross-version robots checks have a distinct purpose and are not duplicate coverage merely because they run one test file twice. |

### Collection is coupled to generated data

On the audit checkout, this discovery-only command failed before listing any
tests:

```text
npm run test:browser -- --list --reporter=list
```

[../../frontend/tests/console-machine-data.spec.ts](../../frontend/tests/console-machine-data.spec.ts)
read the absent `backend/var/canary/state/runtime-counters.csv` during module
collection. The runner's `Total: 0 tests in 0 files` therefore describes a
collection failure, not an empty suite. No fixture build was started to hide
that failure.

File selection excluded that dependency and listed seven tests successfully:

```text
npm run test:browser -- tests/prerender-guard.spec.ts --list --reporter=list
```

Neither command executed tests or started a preview server. The full current
test-case count remains unverified.

### The CI path filter is not a complete dependency map

The literal patterns in
[../../.github/scripts/browser-suite-needed.sh](../../.github/scripts/browser-suite-needed.sh)
give these results for a PR containing only the named path:

| Changed path | Browser pattern | Console pattern |
| --- | --- | --- |
| `frontend/src/lib/components/KpiCard.svelte` | true | true |
| `frontend/src/styles/tokens.css` | true | false |
| `frontend/src/routes/+layout.svelte` | true | false |
| `frontend/package.json` | true | false |
| `backend/idhazh/render/write.py` | false | false |
| An unknown path outside the listed prefixes | false | false |

These are evaluations of the script's own pattern strings, not new CI runs.
Shared styles, layouts and frontend dependencies can affect the console. The
script's comment says unknown paths run tests, but its unmatched branch prints
false. The full main-branch run is a later safeguard; it does not make the PR
selection complete.

Some checks legitimately cross the language boundary.
[../../frontend/tests/malformed-day.spec.ts](../../frontend/tests/malformed-day.spec.ts)
runs the Python `validate-days` command and then exercises the browser loader.
Canary generation also uses the backend contracts and producer. A directory
split alone cannot decide which tests a change needs.

## Existing planned work

Row 5 of
[../../TODO/20260905-01-visible-chart-plan.md](../../TODO/20260905-01-visible-chart-plan.md)
already proposes backend marks named `contract`, `visual`, `slow` and
`workflow`, with full CI retained. Its collected-set check detects tests left
out of every subset. It is pending on the audit commit.

That row does not yet cover frontend groups, change-to-test dependency
selection, build-mode verification or duplicate-run prevention. The union of
test groups can be complete while the mapping from a changed source file to
those groups is still wrong. Neither the row nor the testing policy was
modified by this audit.

## What the audit turned into, 2026-09-06

Two of the questions above were answered, and the answer to the second was not
the one the audit expected.

**Selection.** `ciAnswer` in `frontend/scripts/test-scope.ts` is now the one
place that decides, and it returns three answers rather than one: whether to run
the browser groups, whether to run the operator console's specs, and whether to
open every committed day. The console's specs are 584 of the browser suite's 997
tests and a pull request runs them only when the change is the console's own or
the harness that chooses; `main` runs every group, which is what the deferral
leans on. There is no nightly job, because a second copy of the browser job is a
second thing to keep correct.

**The bigger cost was not selection.** It was that a test may re-read the whole
committed archive, so its cost grows with every day the pipeline publishes while
its coverage does not. That became Rule #12 and three paragraphs of
[../../CLAUDE.md](../../CLAUDE.md) section 13, with an owner ruling attached: a
test checks code functionality rather than data hygiene, and it is driven with a
built parameter rather than a loop over what the archive happens to hold. A
hygiene check has three legal fates - delete it where a fixture already covers
the rule, move it into the producer that writes the data, or make it an operator
surface `pytest` does not run. `backend/tests/test_archive_readers.py` holds the
list of tests that still read the tree; it went from 22 entries to 12 and may
only shrink.

The numbers behind both are in
[measurements.md](measurements.md#what-the-suite-paid-to-re-read-the-archive-2026-09-06).
The one that reframed the work: the `browser` job was 462 s and the entire
backend suite was 63 s, so deleting backend tests buys about zero wall clock.
None of this was done for speed on the day; it was done because the cost
compounds and the coverage does not.

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - current local and CI commands.
- [../how-to/execute-a-plan.md](../how-to/execute-a-plan.md) - worker and orchestrator responsibilities.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - build-time and browser-time readers.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - stage boundaries and fixture-based integration.
- [agent-notes.md](agent-notes.md) - known environment and command-output traps.
