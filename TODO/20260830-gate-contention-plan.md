# Gate contention plan - one heavy gate at a time, and a suite that fits the box

**Last Updated**: 2026-08-30
**Level**: 4 (structural, across `backend/utilities/`, `backend/tests/`, `pyproject.toml`, `frontend/` and `docs/`; no persisted contract moves)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 2; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Parallel agents run unbounded heavy gates on one 12-core box, so the same 1,675-test suite that CI finishes in 62.68 s took 630.55 s locally, and three browser suites running at once turned a commit CI had passed into 11 failures. |
| Hard scope - in | A machine-wide lock that serialises `pytest`, `npm run build` and `npm run test:browser` across every worktree; opt-in parallel execution of the backend suite; a per-worktree preview port; the session-scoped setup of the most expensive test file; the gate protocol and every measured number recorded once. |
| Hard scope - out | The CI workflows and job structure (`gates` is 85-104 s and is not the problem). Playwright `workers` above 1 inside one suite. Deleting or thinning any test. Weakening any assertion. VS Code settings and anything outside the repository. New hardware. Any change under `backend/idhazh/contracts/`. |
| ESCALATE triggers | (a) Any row that would move a file under `backend/idhazh/contracts/` or a file in `schemas/` - that is Level 5, stop. (b) A test that passes serially and fails under `-n` and cannot be isolated without weakening its oracle - stop row 2, keep the suite serial. (c) Any proposal to raise a timeout, add a retry, or relax an assertion so a gate survives contention - stop the row and say so; that is the defect this plan exists to remove. (d) A row needing a change to `.github/workflows/` - out of scope, report it. |
| Chosen strategy | Serialise the three CPU-bound gates instead of throttling the work, then give the one gate that is running the whole box. Authority: Carmack (runner and throughput), with Fowler on file ownership. |
| Execution | autonomous orchestrator per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 2. |

### Measured baseline (this box, 2026-08-30, Windows 11, 12 logical CPUs, 31.8 GiB RAM)

| Fact | Value | How it was taken |
| --- | --- | --- |
| CI `gates`, full backend suite | **1,675 passed in 62.68 s** | Run 33309961650, job 99253105379, commit `b78e984` |
| CI `gates` job wall clock | 85, 95, 101, 102, 102, 104 s (n=6) | Six consecutive `main` runs |
| CI `site` job wall clock | 201, 203, 205, 234, 246, 255 s (n=6) | Same six runs |
| Local full backend suite, same 1,675 tests | **630.55 s** | `yi-r10`, redirected pytest log |
| Local full backend suite, all runs that day | 452.13, 493.60, 534.77, 579.07, 630.55, 653.18, 738.97, 1098.04 s (n=8, 7.5 to 18.3 min) | Redirected pytest logs across worktrees |
| Local against CI, same suite | **10.1x slower** | 630.55 / 62.68 |
| Two full backend suites overlapping | **7 min 47 s** | `yi-r15` 14:38:48 to 14:48:23, `yi-r10` 14:40:36 to 14:51:06 |
| Browser suite, running alone | 3.6, 3.8, 4.0 min (n=3) | Redirected suite logs |
| Browser suite, three running at once | **5.3, 5.5, 8.0 min** (n=3) | Same day, overlapping runs |
| The 8.0 min run | **11 failed**, first failure a 3.0 min timeout in `search.spec.ts` | Its failed specs were unchanged against `origin/main` and CI passed that same commit |
| Host during three suites | CPU 98 to 100 percent, disk 0 to 2 percent, RAM free >= 6.3 GiB | Two snapshots |
| Host after they exited | **CPU 30 percent** | Third snapshot |
| Shells alive | 89 `pwsh`, 87 of them children of one VS Code process, oldest 09:12:03 | Process table |
| Processes and worktrees | 501 processes, 14 registered worktrees | Process table, `git worktree list` |

**What the baseline rules out.** Disk stayed at or below 2 percent and free memory never fell below 6.3 GiB, so the box is CPU-bound rather than paging or I/O-bound. `[tool.pytest.ini_options]` is unchanged on `origin/main`, and the only recent manifest change is an optional extra CI does not install, so no configuration regression is in play. CI's own timings did not move.

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A machine-wide lock, so one heavy gate runs at a time | - | A | PENDING | - | - | - |
| 2 | The backend suite uses the cores the box has | 1 | B | PENDING | - | - | - |
| 3 | Two worktrees can never share one preview server | 1 | B | PENDING | - | - | - |
| 4 | The most expensive test file pays for its setup once | 2 | C | PENDING | - | - | - |
| 5 | Closure: re-measure under the lock, record the protocol, delete this plan | 1, 2, 3, 4 | D | PENDING | - | - | - |

**File ownership is exclusive per wave.** `docs/reference/agent-notes.md` belongs to row 1 and to nobody else. `docs/how-to/run-the-gates.md`, `docs/how-to/execute-a-plan.md` and `docs/reference/measurements.md` belong to row 5 and to nobody else; rows 2, 3 and 4 report their numbers in their PR body and row 5 records them.

## 2 - Row #1 - A machine-wide lock, so one heavy gate runs at a time

- **Scope:** A standard-library operator utility that serialises `pytest`, `npm run build` and `npm run test:browser` across every worktree on one machine, and names the current holder while a caller waits.
- **Files touched:**
  - `backend/utilities/gate_lock.py`
  - `backend/tests/test_gate_lock.py`
  - `docs/reference/agent-notes.md`
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, and the utility runs from a fresh clone with no configuration.
- **Oracle:** Start K real subprocesses that each take the lock, append a `(start, end)` monotonic pair to one shared file, and release. Assert all K ran and that no two intervals overlap. Non-overlap under real concurrency is the entire claim; a single-process test proves nothing.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A lock file created with `O_CREAT` plus `O_EXCL` under the user temp directory, carrying pid, worktree path and start time. Standard library only, same behaviour on Windows and Linux, no new dependency (Rule #8). | Carmack |
  | 2 | A lock whose holding pid is gone is reclaimed, and the reclaim is logged. A lock that outlives its holder would stop every gate on the box, which is worse than the contention it prevents. | Carmack |
  | 3 | A waiter prints who holds the lock, from which worktree, and for how long. "What is running" is the question every blocked agent asks, and answering it is why this is a tool and not a convention. | Fowler |
  | 4 | CI never takes the lock. A GitHub runner is one job alone on its own machine, and `gates` at 62.68 s is not the problem this solves. | Carmack |
  | 5 | The lock covers exactly the three gates measured as CPU-bound. `ruff`, `mypy`, `svelte-check`, `shellcheck` and `bundle-gate` stay unlocked, because serialising a cheap gate only adds waiting. | Carmack |
  | 6 | It lives in `backend/utilities/`, which CLAUDE.md section 3 already names as operator tooling that never runs in the pipeline. | Fowler |
  | 7 | The `agent-notes.md` entry states the symptom first - a suite that is 10.1x its CI cost, and a false red under fan-out - because that is what an agent sees before it knows the cause. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A Windows named mutex through `ctypes` | Windows only, and `backend/` is type-checked and tested on the Linux runner as well. | Carmack |
  | 2 | Cutting `Parallel N` to 1 in every plan-doc | It serialises the writing as well as the gates. The writing is not what saturates the box; three simultaneous suites are. | Fowler |
  | 3 | Each agent checks CPU load before starting | A check with no interlock races. Four agents read "idle" in the same second and all four start. | Fowler |
  | 4 | A scheduling daemon | A service on the developer machine to install, keep alive and restart. A lock file has no lifetime of its own. | Carmack |

## 3 - Row #2 - The backend suite uses the cores the box has

- **Scope:** The full backend suite runs in parallel on a developer machine, opt-in and off by default, with parity against the serial run proved rather than assumed.
- **Files touched:**
  - `pyproject.toml`
  - `backend/tests/` (only where a test proves not to be parallel-safe)
- **Acceptance gates:** `ruff`, `mypy --strict`, the contract drift gate, the full suite serially, the full suite under `-n`, and `git status --porcelain` empty after each of the two runs.
- **Oracle:** The set of passing node ids is identical serially and under `-n auto`, and `git status --porcelain` is empty after both. Equal counts are not enough - a parallel run that silently skips a test would pass a count check, and a test that writes into the tracked tree has already happened once in this repository.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `pytest-xdist` enters the `dev` extra, with its installed bytes, its measured effect and its beneficiary named in the same comment the other dev dependencies carry (Rule #8). | Carmack |
  | 2 | `addopts` is not changed. CI runs the suite in 62.68 s on 4 vCPU and gains little from sharding; `-n` stays a local flag, so the gate everybody trusts keeps running the way it runs today. | Carmack |
  | 3 | A test that cannot run in parallel is pinned to a single worker by group. It is never deleted, never skipped and never weakened. | Fowler |
  | 4 | The speedup is measured on this box under the row 1 lock, with hardware, date and spread, or the row does not land (Rule #10). | Carmack |
  | 5 | If the measured gain is under 2x, the row COLLAPSES and the dependency does not ship. A dependency that buys nothing is rent paid forever. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | `-n auto` inside `addopts` | It changes CI, which is already fast, and it would hide a parallel-only failure inside the one gate that is currently authoritative. | Carmack |
  | 2 | Splitting the suite into fast and slow tiers | Two commands to remember and a tier that rots the first time somebody forgets to label a test. Parallel execution needs no taxonomy. | Fowler |
  | 3 | Deleting or thinning tests to buy wall clock | The suite is why a repository merging this fast can be merged at all. The cost is the scheduling, not the coverage. | Fowler |
  | 4 | Running the suite only in CI | CI cannot run before a push, and a red push costs the next agent its merge. | Fowler |

## 4 - Row #3 - Two worktrees can never share one preview server

- **Scope:** The browser suite's preview port derives from the worktree it runs in, so two checkouts cannot silently test one another's build.
- **Files touched:**
  - `frontend/playwright.config.ts`
  - `frontend/tests/preview-port.spec.ts` (new, pure-function)
- **Acceptance gates:** `svelte-check` 0 errors, `npm run build`, the browser suite green, and two worktrees resolving two different ports for the same command.
- **Oracle:** Two different absolute worktree paths derive two different ports; the same path derives the same port on every call; and with `CI` set the port is byte-identical to today's default. Determinism and the CI carve-out are both load-bearing, so both are asserted.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Outside CI the default port derives from a hash of the worktree absolute path, and `PREVIEW_PORT` still overrides it. A derived default removes a step a human currently has to remember per worktree. | Carmack |
  | 2 | Inside CI the port stays 4173, so the runner's behaviour does not move at all. | Carmack |
  | 3 | `reuseExistingServer` keeps its current value. Once the port is per-worktree, the server it may adopt is that worktree's own, which is the case it was written for. | Fowler |
  | 4 | The derivation is a pure function with its own spec, in the pure-function half of the browser suite that runs in Node with no browser. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | `reuseExistingServer: false` | It does not remove the collision. It converts a silent wrong-build pass into a failure to bind. | Carmack |
  | 2 | Requiring `PREVIEW_PORT` and failing when unset | A fresh clone would then fail the command its own gate doc prints. | Fowler |
  | 3 | Raising the suite timeout or the encoder wait | A timeout raised to survive contention hides the contention, and the false red returns at the next fan-out. This is ESCALATE trigger (c). | Andre |

## 5 - Row #4 - The most expensive test file pays for its setup once

- **Scope:** `test_workflows.py` builds its real git and bash fixtures once per session rather than once per test, with every assertion unchanged.
- **Files touched:**
  - `backend/tests/test_workflows.py`
- **Acceptance gates:** `ruff`, `mypy --strict`, full `pytest`, and `--durations=25` captured before and after on the same box under the row 1 lock.
- **Oracle:** The same test node ids pass, none of the bash-backed tests reports as skipped, and the file's total wall clock falls. A speedup bought by a skip is a failed row, which is why the skip count is asserted and not merely read.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Measure per-test durations before changing a line. The file is the largest in the suite at 2,981 lines and 85 test functions with 9 `subprocess.run` sites, which makes it the first suspect and not yet the proven cause. | Carmack |
  | 2 | Shared setup moves to a session-scoped fixture only where no test mutates it. Anything a test writes to keeps its own per-test copy. | Fowler |
  | 3 | `requires_bash` stays. A host with no bash still skips; the oracle asserts that this host is not one of them. | Fowler |
  | 4 | If the measured saving is under 10 percent of the file's wall clock, the row COLLAPSES and the file is left alone. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Mocking git and bash | The file's entire value is that it executes the real commit script that both daily jobs run (Rule #7). | Fowler |
  | 2 | Marking the file slow and excluding it by default | It guards the step that publishes the day. An excluded guard is a deleted guard. | Fowler |
  | 3 | Rewriting the file into a new structure | Its assertions are the asset. Only the setup is being paid for twice. | Fowler |

## 6 - Row #5 - Closure: re-measure under the lock, record the protocol, delete this plan

- **Scope:** The gate docs carry the protocol and every measured number this plan produced, and the plan-doc is removed.
- **Files touched:**
  - `docs/how-to/run-the-gates.md`
  - `docs/how-to/execute-a-plan.md`
  - `docs/reference/measurements.md`
  - `TODO/20260830-gate-contention-plan.md` (deleted)
- **Acceptance gates:** full `pytest`, `ruff`, `mypy --strict`, the ASCII-and-LF check, and every cross-link resolving.
- **Oracle:** The full backend suite and the browser suite are re-measured on the merged tree under the lock on an otherwise idle box, and each recorded figure carries hardware, date and spread (Rule #10). A closure that records the pre-plan numbers has recorded folklore.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `execute-a-plan.md` gains only a domain-neutral sentence - serialise expensive gates when workers share one machine. The tool, the command and the numbers go in `run-the-gates.md`, because CLAUDE.md section 5 keeps process docs copyable between projects. | Fowler |
  | 2 | The protocol is stated as two rules: a worker runs the tests its row touches while it iterates and the full suite once before it reports; the orchestrator does not re-run a full suite the worker already ran on the same tree, it reads the CI `gates` job. | Fowler |
  | 3 | Terminal and preview-server hygiene is recorded where the traps that produce the same symptom already live, next to the process-accumulation entries rather than in a new page. | Fowler |
  | 4 | Every number lands in `measurements.md` once, and the other pages link to it. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A new `docs/how-to/` page for the gate protocol | It belongs beside the gate commands it changes. A separate page is the clutter this repository has already had to delete once. | Fowler |
  | 2 | Keeping the plan-doc as a record | Git history is the ledger, and a stale plan is read as current. | Fowler |
  | 3 | Recording the numbers measured while this plan was authored | They were taken on a box running three suites at once. They are the symptom, not the result. | Carmack |
