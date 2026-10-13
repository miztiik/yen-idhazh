# Every parquet engine call runs on the calling thread, so a short program exits cleanly

**Last Updated**: 2026-10-13

**Level**: 3 ([CLAUDE.md](../CLAUDE.md) section 6) - Row 2 moves engine calls across two subsystems, the ledger's parquet module and the host verifiers.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes. Parallel N = 1 because each row needs the row before it, and Row 1 measures, so it runs alone.

Table A - operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The canary build's score-key step sometimes aborts after it prints a correct answer, which fails the site build at random; a rerun passes and proves nothing (known defect 51) |
| A2 | Hard scope - in | Row 1: reproduce the abort on ubuntu-latest with Python 3.12 and capture its native backtrace, before any code changes. Row 2, structure only: every parquet engine call the host verifiers make goes through `backend/idhazh/ledger/parquet.py`, and the lint rule refuses the engine anywhere else. Row 3: every engine call there runs on the calling thread; ship the thread test and the score-key exit test; remove the blind process-exit assertion; correct `docs/architecture/contracts/persistence.md`; close known defect 51 |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C. Each fires only on its condition and means: stop, report the numbers, wait for a person |
| A5 | Chosen strategy | One door for the engine: every parquet engine call lives in `backend/idhazh/ledger/parquet.py`, the existing lint rule refuses one anywhere else, and every engine call there runs on the thread that made it, held by a test that counts the process's threads - Fowler, 2026-10-12; owner ruling 2026-10-13 chose it over the three smaller options in Table J (J1 to J3) |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1, because each row needs the row before it and Row 1 measures |

Table B - hard scope out

| Id | What is out | What leaving it out costs | What would bring it in |
| --- | --- | --- | --- |
| B1 | A retry or signal tolerance in `frontend/scripts/build-canary.mjs` | Nothing: it would hide the fault from every other short program that reads a ledger | Never as a fix ([CLAUDE.md](../CLAUDE.md) Guardrail #5: a temporary fix is a permanent fix whose note gets lost); known defect 51 rules it out |
| B2 | Removing the separate `--scored-keys` process (the canary day step writes the keys file instead) | One extra Python start and one ledger read per canary site build, about 1 to 2 s (estimate) | A canary-build simplification row. It would hide, not fix, this fault for other programs |
| B3 | Parallel column decode for large ledger reads | Columns decode one at a time. Estimate: no visible change, because turning rows into Python objects and validating them already runs on one thread and costs more | A paired measurement (threads on and off, alternating, one process) on the largest packed file, showing decode costs more than a budget the owner names. The change then lives in `read` and `open_bytes`, next to the rule, and gives the engine memory it owns before it uses threads |
| B4 | Running the canary path on Python 3.14 in CI | None after this plan: no engine thread remains to hang | A hang seen on Python 3.14 after this plan |
| B5 | Pinning pyarrow (`pyarrow>=21` in `pyproject.toml`) | The failing runs' engine version stays unknown; the fix depends on no default, because it sets every flag it relies on | A failure that reproduces on one pyarrow version and not another |
| B6 | A neutral footer description in place of the engine's footer objects that the two host verifiers read | An engine swap still edits the verifiers' footer checks. They check which engine wrote a file, so they change at a swap anyway | The engine swap itself |

Table C - ESCALATE triggers

| Id | Trigger | Report |
| --- | --- | --- |
| C1 | A row would take one of the three smaller options in Table J (J1 to J3) in place of the chosen strategy (A5), which the owner ruled on 2026-10-13 | Which option, and what made the chosen strategy fail |
| C2 | Gate 1 sees no abort on the base within its bounded runs, the busy-CPU loop included; or Gate 4 needs more than 4 jobs | A finding about the instrument ([CLAUDE.md](../CLAUDE.md) section 0d). Do not call the defect reproduced, and do not land Row 3 without the owner |
| C3 | The backtrace shows the abort on the main thread, or lacks `PyGILState_Ensure` called from `arrow::py::PyBuffer::~PyBuffer` beneath the forced unwind (`pthread_exit`, `std::terminate`) | The frames. The fix's property may not cover that mechanism |
| C4 | The thread test's ledger-read case passes on today's behaviour in CI (Gate 2) | The run id. The oracle cannot see what it guards |
| C5 | The thread test fails on the fix | Which call starts the thread; Fowler narrows the count or changes the oracle |
| C6 | Any abort, hang or wrong answer on the fix in Gate 4 | The counts and the backtrace |
| C7 | A change reaches a persisted shape, the bytes a writer produces, `frontend/scripts/build-canary.mjs` or `.github/workflows/ci.yml` | The diff that reaches it |
| C8 | An existing test turns red after Row 2 or Row 3 | Its name. Do not edit its assertion |
| C9 | The new banned-api entry does not report the `parquet.pyarrow` uses before Row 2 removes them | The lint output. The guard cannot see the back door; Fowler changes the guard |
| C10 | A write through the door starts an engine thread on today's engine (Gate 1 step 8, or a write case in Gate 2) | The counts. The rule's write half needs a code change this plan does not have |
| C11 | A thread-test case cannot be driven from a real fixture ([CLAUDE.md](../CLAUDE.md) Guardrail #7: a mock makes a thing look finished without being built) | Which case, and which fixture is missing |

Table D - the fault ruling: causes and claims considered (code read at main 72569d6; reproduced on base c71d17a by Row 1)

| Id | Cause or claim | Ruling | Why |
| --- | --- | --- | --- |
| D1 | An engine worker thread drops the last hold on the caller's bytes during interpreter shutdown. In plain words: the ledger reader hands the engine a block of bytes that Python owns and lets the engine decode it on its own worker threads. If a worker lets go of the last hold on those bytes after the caller has moved on, the release needs Python's lock. During shutdown, Python 3.12 on Linux ends that thread by unwinding its stack; the unwind reaches C++ code that may not be unwound, and the C++ runtime aborts the process with "terminate called without an active exception", after the answer was printed | IN - Row 1's backtrace confirms this chain on a non-main thread: the Python buffer destructor requests the GIL during forced thread unwind. The fix also removes D2 | Same message and signal. The abort came after a complete answer: the answer goes to a pipe, which Python writes out at shutdown. The first abort was on the merge that moved the scores to parquet (#1166). On the `--scored-keys` path the read is the last real work, then one print and exit. A thread waiting for Python's lock asks for a turn after about 5 ms (Python's switch interval), so a program that exits sooner than that after its last read leaves a late worker no turn - the likely reason this is the exposed caller. The upstream core dump (apache/arrow issue 34314) shows this chain. Decode on the engine's threads over Python-owned bytes is the default the code takes (pyarrow 25.0.1 `ParquetFile.read`, `use_threads=True`) |
| D2 | A C++ thread object destroyed while still joinable during exit-time cleanup, the other usual source of this message | OUT - Row 1 shows the aborting worker inside `pthread_exit`'s forced unwind, not the main thread in exit handlers | It would not depend on what runs last, yet only the step whose last act is a read has aborted. The fix starts no engine thread, so it removes this too |
| D3 | The engine's read-ahead I/O pool holds the bytes | LIKELY OUT for this path | For an in-memory source the engine's in-memory reader answers read-ahead itself (its `ReadAsync` override in Arrow's `cpp/src/arrow/io/memory.cc`; signature read, body not read). The read-ahead default also differs between pyarrow 25.0.1's docs (on) and the engine's current source (off). The fix turns read-ahead off anyway |
| D4 | A Python daemon thread alive at exit | OUT | The only one, "host-watch" (`backend/idhazh/telemetry/host.py:604`), starts inside the work stage's `Watch`, never on this path |
| D5 | Another native library's threads | OUT | onnxruntime and tokenizers load only inside `Embedder` (`backend/idhazh/embed.py:108` and `:133`); no backend module imports duckdb |
| D6 | Node killed the child for size or time | OUT | Node kills with SIGTERM and prints no C++ runtime message; the message came from the child |
| D7 | Runner memory pressure | OUT | The kernel's out-of-memory kill is SIGKILL, with no message |
| D8 | A fault in the decode itself | OUT | The printed answer was complete and correct |
| D9 | The `with` block in `parquet.read` as the cure (`docs/architecture/contracts/persistence.md:169-172` says it closes the reader and byte source) | OUT as a fix | The engine's file object closes only a source it opened itself, and the in-memory reader keeps its buffer until the object is freed; neither touches a hold a worker thread still has |

Table E - evidence still missing after Row 1

| Id | Missing fact | Why it matters | Where it comes from | If it cannot be had |
| --- | --- | --- | --- | --- |
| E3 | The pyarrow version on the three failing runs | `pyarrow>=21` is unpinned, so a cause that only one engine version has is not ruled out | The runs' own install logs, if GitHub still serves them; Row 1 records the version it installs | B5 says what a version-only failure would bring in |
| E4 | The specific 2026-10-12 abort log | Confirms the reported step and message | Row 1 checked candidate run 38243267274; it was green and its logs showed no abort | The exact recurrence remains unlocated; its check record stands and no row waits on it |
| E5 | Whether the process-exit regression that `persistence.md:171` names exists, and whether it ran on the 2026-10-12 candidate | If it exists and ran, it passed while the fault was live, so it cannot see this fault | Row 3, by search | Row 3 says so in its pull request |

## 1. Status reckoner

Table F

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Reproduce the exit abort on ubuntu-latest with Python 3.12 and capture its native backtrace | - | A | DONE | ledger-read-exit-ab | - | direct |
| F2 | 2 | Route every parquet engine call through the ledger's parquet module | 1 | B | PENDING | - | - | - |
| F3 | 3 | Run every engine call on the calling thread, so a short program exits cleanly | 2 | C | PENDING | - | - | - |

### Row #1 - Reproduce the exit abort on ubuntu-latest with Python 3.12 and capture its native backtrace

- **Scope:** A throwaway workflow reproduces the abort on the base commit, captures its native backtrace and counts engine threads around each kind of engine call, and the numbers land in known defect 51's entry before any code changes.
- **Files touched:**
  - `TODO/20260823-known-defects-plan.md` - known defect 51's entry: the base SHA; `python -VV`, `pyarrow.__version__`, `uname -r` and `nproc`; per loop the runs, aborts, wrong answers and other exits; the aborting thread's top 15 frames; the step 8 thread counts; the run ids.
  - `TODO/20261012-ledger-read-exit-abort-plan.md` - this row's Reckoner line.
  - `.github/workflows/reproduce-ledger-read-exit-abort.yml` - on the throwaway branch only; never merged; deleted with the branch.
- **Acceptance gates:**
  - **Gate 1 - reproduce first (CI-side, throwaway).** A workflow triggered by a push to an unmerged branch cut from main (record the SHA): ubuntu-latest, `timeout-minutes: 30`, the browser job's steps in `.github/workflows/ci.yml` up to "Build the canary day" without Node, DuckDB and Playwright (Python 3.12, `pip install -e .`), then `sudo apt-get install -y gdb`, `ulimit -c unlimited`, and a core pattern that writes into the workspace.
    1. Record `python -VV`, `pyarrow.__version__`, `uname -r` and `nproc`.
    2. Run `python backend/utilities/build_canary_day.py` (the step "Build the canary day"). Check that the score ledger's raw file starts with `PAR1`.
    3. Run `python backend/utilities/build_canary_day.py --scored-keys --state backend/var/canary/state` once and keep its stdout as the reference; it must hold one key per published canary item.
    4. Pinned loop: 100 runs of step 3's command under `taskset -c 0`, stdout and stderr to a file per run. Pinning puts the program and the engine's threads on one CPU, so a waking caller pre-empts the worker that woke it.
    5. Control loop: the same 100 runs without `taskset`.
    6. If both loops show no abort: one more pinned loop of 100 with a busy loop pinned to the same CPU. Still none -> C2.
    7. For the first abort: `gdb -batch -ex "thread apply all bt" "$(command -v python)" <core>`. Upload the output as an artifact; copy the aborting thread's top 15 frames into the record.
    8. Thread check, each case in its own fresh interpreter: count the entries of `/proc/self/task` after importing `idhazh.ledger.parquet`, then again after one engine call of one kind - the `--scored-keys` read through `build_canary_day.main()`; one read through each host verifier, on the fixture its own tests use; one `ledger.persist` write; one `render_grouped_period` build. Row 3's Gate 2 expects these counts.
    - Record per loop: runs, aborts (exit by the abort signal, SIGABRT), wrong answers, other exits. Pass: at least one abort with the complete answer already on stdout, and a backtrace that shows C3's chain on a thread that is not the main thread.
  - **Local:** `python backend/utilities/doc_load.py` on the two changed Markdown files, before and after. A documentation-only change runs no application suite ([CLAUDE.md](../CLAUDE.md) section 9).
- **Oracle:** the backtrace of one abort: the aborting thread is not the main thread, and its frames show `PyGILState_Ensure` called from `arrow::py::PyBuffer::~PyBuffer` beneath the forced unwind. It cannot settle how often the canary's own runs abort, because the pinned loop raises the rate on purpose; and a loop with no abort is a finding about the instrument, not proof that the fault is absent (C2).
- **Decisions:**

Table G

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Reproduce on ubuntu-latest with Python 3.12, the production target where it failed ([CLAUDE.md](../CLAUDE.md) Guardrail #2: the GitHub runner is production). A thread ended at shutdown is not unwound on Windows, and on Python 3.14 the same race hangs the thread instead | Fowler |
| G2 | The instrument is a throwaway workflow on an unmerged branch, deleted after use, as the 2026-09-02 install measurement in `pyproject.toml` was | Fowler |
| G3 | Pinning to one CPU is the named amplifier; the unpinned loop is the control | Fowler |
| G4 | This row measures, so it runs alone (docs/how-to/execute-a-plan.md, "A row that MEASURES runs alone") | Fowler |
| G5 | The record lives in known defect 51's entry, the page that owns the defect; this plan points at it and does not copy it | Fowler |
| G6 | No code lands before this row passes. A backtrace that shows another chain (C3) changes what Rows 2 and 3 should build, and a refactor with no behavioural change after it is not done | Fowler; known defect 51 |
| G7 | This plan is the home of known defect 51's fix, the defect's entry points at it, and the two land together in one commit to main | Owner ruling 2026-10-12 |

- **Rejected alternatives:**

Table H

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Reproduce on the owner's Windows machine, or by hand under WSL | Windows cannot show it; WSL needs a person and is not the production target | Free on Windows, and it sees nothing; about an hour of a person's time under WSL | Fowler |
| H2 | Keep the pinned loop in the CI suite as a permanent stress test | Row 3's thread test makes it redundant once the fix lands | About 1 to 2 s per run, times the loop count, on every CI run (estimate) | Fowler |
| H3 | Ship the fix on the reasoning alone | A fix whose proof today's code also passes proves nothing; only the backtrace can overturn the mechanism | Saves one throwaway workflow, up to 4 jobs of 30 minutes | Fowler; known defect 51 |

### Row #2 - Route every parquet engine call through the ledger's parquet module

- **Scope:** A structural change with no behaviour change: the three places that open Python-owned bytes on the engine open them through one door function in `backend/idhazh/ledger/parquet.py`, the host verifiers' one other engine call (the zstd page decompress) moves into that module, and the lint rule refuses the engine anywhere else.
- **Files touched:**
  - `backend/idhazh/ledger/parquet.py` - Extract Function: `open_bytes(data, *, max_footer_bytes=None, max_footer_items=None)`, a context manager over the engine's in-memory reader and file object, which `read` uses; it passes the engine's defaults exactly as each call site does today. Move Function: `decompress_zstd_page(body, size)`. Module docstring: the one-file swap claim names what still crosses the door, the engine's footer objects that the two host verifiers read (B6).
  - `backend/idhazh/telemetry/host_output_verify.py` - `_read_parquet` opens through `parquet.open_bytes`; its `engine = parquet.pyarrow` line and the `engine=` argument go.
  - `backend/idhazh/telemetry/host_history_files.py` - `_compact` opens through `parquet.open_bytes`; both `engine = parquet.pyarrow` lines go; the `_decompress` calls lose `engine`.
  - `backend/idhazh/telemetry/host_parquet_admission.py` - `_decompress` calls `parquet.decompress_zstd_page`, imported inside the function as `backend/idhazh/ledger/persist.py` imports the module; Remove Parameter `engine` from `_decompress`, `_data_value` and `admit_host_parquet`.
  - `pyproject.toml` - one banned-api entry, `"idhazh.ledger.parquet.pyarrow"`, with its reason, next to the existing `"pyarrow"` entry.
  - `docs/architecture/contracts/persistence.md` - "Swapping the engine": step 1 says to rewrite every function in `ledger/parquet.py` (today's list names `read_envelope`, which lives in `persist.py`); the one-module rule names the two banned-api entries that hold it. Lines 198 and 251 (at 72569d6) name `backend/tests/ledger/test_single_engine_import.py`: keep the name if a search finds that file, else name the banned-api entries.
  - Every file this row changes among those the search `rg -n "parquet\.pyarrow|engine=|_decompress\(|_data_value\(|admit_host_parquet\(" backend` names, tests included, each listed in the pull request.
  - `TODO/20261012-ledger-read-exit-abort-plan.md` - this row's Reckoner line.
- **Acceptance gates:**
  - **Local, ban first:** add the banned-api entry before any other edit and run `python -m ruff check .`. It must report every `parquet.pyarrow` use under `backend/` outside `backend/tests/` that the search above finds; none reported -> C9. Then make the moves; `python -m ruff check .` is clean.
  - **Local:** `npm --prefix frontend run test:changed -- --list`, then run the selection; `python -m mypy`; `python -m pytest -n 0 backend/tests/ledger` and the host verifier and page-check test modules the search names; `python backend/utilities/doc_load.py docs/architecture/contracts/persistence.md`, before and after.
  - **CI:** `gates`, `site` and `browser` green with no assertion edited (C8).
- **Oracle:** the existing tests of the door's round trip (`backend/tests/ledger`) and of the two host verifiers and the page check (found by search), assertions unchanged, green before and after. This row is a refactor, so its check passes at both ends by design, and what must be able to fail is the behaviour the moves could break (docs/how-to/execute-a-plan.md, check 2); the ban is the part that is red before the moves and clean after. It cannot settle that no caller decodes through the file object `open_bytes` hands out with the engine's default threads; Row 3's thread test holds the two callers that exist.
- **Decisions:**

Table I

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Extract Function is earned: three call sites open Python-owned bytes on the engine today - `parquet.read`, `host_output_verify._read_parquet` and `host_history_files._compact` (`rg -n BufferReader backend/idhazh`) - and three concrete usages earn an abstraction (Fowler worldview #10) | Fowler |
| I2 | The refactor serves the next behavioural change: Row 3 sets the thread rule once, in `open_bytes` and `read`, not at three call sites (make the change easy, then make the easy change) | Fowler |
| I3 | Move Function for the zstd page decompress, so no engine use stays outside the module and the ban can hold. It sits in `parquet.py` because that file is the engine boundary | Fowler |
| I4 | The guard is the existing banned-api rule in `pyproject.toml`, not a test that scans source files ([CLAUDE.md](../CLAUDE.md) Guardrail #12: a read must not grow with the repository) | Fowler |
| I5 | `open_bytes` hands out the engine's own file object. The two verifiers keep `use_threads=False` on their batch decode, written at each call: two callers do not earn a decode function. Row 3's thread test holds both | Fowler |
| I6 | The door function's parameters are named for what they bound - footer bytes and footer items - not for the engine's own option names, so a swap keeps the signature | Fowler |
| I7 | One pull request, structural only. A squash merge makes it one commit, and Row 3's behavioural change is a separate pull request, so the two never share a commit (two-hat rule) | Fowler |
| I8 | No persisted shape, no written byte and no writer changes; this is an internal rewrite behind the same call sites, with no committed-history consequence | Fowler |

- **Rejected alternatives:**

Table J

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | No structural row; set the flags in `parquet.read` only | The two verifiers keep the engine's read-ahead default, which pyarrow 25.0.1 documents as a background I/O thread pool; no test holds them | Nothing now; later, this fault again in whichever short program runs a verifier last, with no test failing first | Fowler; owner ruling 2026-10-13 |
| J2 | No structural row; set the flags at each of the three call sites | Each site is fixed, but the rule lives in three copies: the next reader copies whichever it finds, and an engine upgrade or swap restates it three times | This row's structural pull request is saved; three places kept in step for as long as the code lives | Fowler; owner ruling 2026-10-13 |
| J3 | Extract the door function, but leave the zstd decompress on `parquet.pyarrow` | The back door that produced the three copies stays open and unwatched, and the ban cannot land | One moved call and one lint line fewer | Fowler; owner ruling 2026-10-13 |
| J4 | A wrapper that hands out the file's footer, schema and serial batches, but not its decode methods | It holds the decode rule by construction, but batch decode has two callers today, and two do not earn it | About 15 lines, and the verifiers' page-check signatures change; brought in by a third caller of batch decode through `open_bytes` | Fowler |
| J5 | Replace the engine's zstd decompress with cramjam's, which the page check already uses for snappy | A behaviour change - another decompressor, other errors on a malformed page - inside a structural row | A row of its own with malformed-page tests; it would make the page check engine-free | Fowler |
| J6 | A test that scans source files for `parquet.pyarrow` | A read that grows with the repository (Guardrail #12); the banned-api rule replaced exactly such a scan | One test module, charged on every run as the tree grows | Fowler |

### Row #3 - Run every engine call on the calling thread, so a short program exits cleanly

- **Scope:** `open_bytes` opens with read-ahead off and `read` decodes on the calling thread, so no engine call through the door starts a thread, proven by a test that fails on today's behaviour, by the canary's own command exiting 0 with its answer, and by Row 1's instrument run again on the fix.
- **Files touched:**
  - `backend/idhazh/ledger/parquet.py` - `open_bytes`: `pre_buffer=False`; `read`: `use_threads=False`; module docstring: the rule - every engine call runs on the thread that made it - with its reason in plain words: an engine thread that released the caller's bytes would need Python's lock, and during interpreter shutdown that aborts the process (Linux, Python 3.12) or hangs the thread (Python 3.14).
  - `backend/tests/ledger/test_engine_threads.py` - new, marked `contract` per `backend/tests/test_marks.py`: the thread test (K6, K7).
  - `backend/tests/test_canary_day.py` - the score-key exit test (K8).
  - The fresh-interpreter process-exit test that `persistence.md:171` names: find it by searching `backend/tests` for a test that starts a fresh interpreter to read a file under `tests/fixtures/parquet/`. Remove its exit assertion; keep anything else it guards. If none exists, say so in the pull request (E5).
  - `backend/tests/test_marks.py` - only if the new module carries no mark.
  - `docs/architecture/contracts/persistence.md` - replace lines 169-172 (at 72569d6) with the rule, its reason in plain words and the test that holds it; "Swapping the engine" step 2 gains: keep every engine call on the calling thread - for duckdb, a one-thread connection, because its `threads` setting defaults to the core count.
  - `docs/reference/agent-notes.md` - one entry: this abort cannot show on Windows (a thread ended at shutdown is not unwound there) and turns into a hang on Python 3.14; reproduce it on ubuntu-latest with Python 3.12.
  - `TODO/20260823-known-defects-plan.md` - known defect 51: the Gate 2 and Gate 4 numbers, the run ids, the pull request; status CLOSED in this change.
  - `backend/idhazh/ledger/AGENTS.md` - only if it exists: the new invariant.
  - `TODO/20261012-ledger-read-exit-abort-plan.md` - this row's Reckoner line.
  - Not touched: `backend/utilities/build_canary_day.py` (known defect 51 listed it; the program is where the fault showed, not where it lives), `frontend/scripts/build-canary.mjs`, `.github/workflows/ci.yml`.
- **Acceptance gates:**
  - **Gate 2 - the new test fails on today's behaviour (CI).** Push the tests-only commit alone, and let its run finish before pushing again: a newer push cancels a pull request's running checks. The `gates` job must fail on the thread test's ledger-read case. The verifier cases fail or pass as Gate 1 step 8 counted; the write cases pass (C10 otherwise). Report any other failure; an abort in the score-key exit test counts as one more reproduction. Record the run id.
  - **Gate 3 - the fix (local, then CI).** Local: `npm --prefix frontend run test:changed -- --list`, then run the selection; `python -m ruff check .`; `python -m mypy`; `python -m pytest -n 0 backend/tests/test_canary_day.py backend/tests/ledger/test_engine_threads.py`; `python backend/utilities/doc_load.py` on every changed Markdown file, before and after. On Windows the thread test reports SKIPPED, and a skip is not a pass. CI on the fix: `gates`, `site` and `browser` green; dependants by name: `backend/tests/ledger`, `backend/tests/test_canary_day.py`, the host verifier and page-check tests Row 2's search named, and the compaction and console-payload tests the selector names.
  - **Gate 4 - the fix holds under the same instrument (CI-side, throwaway).** Rerun Gate 1 steps 1-8 on a throwaway branch cut from this pull request's head. Pass: 0 aborts, 0 wrong answers, thread counts unchanged. With a pinned base abort rate p from Row 1, 100 clean runs happen by luck with chance (1-p) to the power 100; that chance is under 1 percent only when p is at least about 4.5 percent. If Row 1's p is lower, raise both loops to about 4.6/p runs, split across jobs of at most 30 minutes; more than 4 jobs -> C2.
- **Oracle:** the thread test's ledger-read case, deterministic both ways: red on today's behaviour on every run, green on the fix on every run; dropping either flag from the door turns it red again. It cannot settle whether another library starts a thread after the call, or what the engine does on a path no case drives; Gate 4's zero count bounds the first and does not prove it.
- **Decisions:**

Table K

| Id | Decision | Authority |
| --- | --- | --- |
| K1 | The property the fix makes true: no engine call through the door starts a thread or leaves one behind, and every engine object that refers to the caller's bytes is made and destroyed on the calling thread before the call returns | Fowler |
| K2 | Remove the engine's threads (`pre_buffer=False`, `use_threads=False`) rather than change who owns the bytes: it is the only option with a test that fails on today's code, and it also removes D2. Upstream, the issue 34314 reporter's `use_threads=False` made the bug disappear | Fowler |
| K3 | This is a fix, not a workaround: it removes a necessary condition of the fault - an engine thread holding Python's bytes - and a test holds that ([CLAUDE.md](../CLAUDE.md) Guardrail #5) | Fowler |
| K4 | Both flags are literals with their reason in the docstring, not config knobs: setting either to True brings the abort back ([CLAUDE.md](../CLAUDE.md) Guardrail #6: a value that can never vary is named, with why) | Fowler |
| K5 | The rule covers every engine call, writes included. Writes need no code change, because pyarrow 25.0.1's parquet writer has no thread option; the write cases hold it. The edit that turns them red: a writer moved to `pyarrow.dataset.write_dataset`, whose `use_threads` defaults to True | Fowler |
| K6 | The thread test has one case per kind of engine call - the ledger read (the fault's path), each host verifier's read, a `ledger.persist` write and a `render_grouped_period` build - each in its own fresh interpreter with a 120 s timeout, because the engine's thread pools belong to the process and keep their threads: a case run after another engine call would reuse them and see no change. Each counts the entries of `/proc/self/task` after importing `idhazh.ledger.parquet` and again after the call; equal counts and the expected rows pass. It skips where `/proc` does not exist, where the abort cannot happen | Fowler |
| K7 | Before the ledger-read case counts, it asserts the filed raw file starts with `PAR1`, so a config change to JSON lines cannot make it vacuous. Its state is a score ledger filed into `tmp_path` by `build_canary_day.file_scores` | Fowler |
| K8 | The score-key exit test runs the command the canary build runs - `sys.executable backend/utilities/build_canary_day.py --scored-keys --state <tmp_path>`, from the repository root, `PYTHONPATH=backend`, 120 s timeout - and requires exit status 0 and `json.loads(stdout) == {row.item_id: row.url_key for row in scored()}`. It is known defect 51's oracle; alone it cannot show the race is gone, because today's code passes it almost every time | Fowler; known defect 51 |
| K9 | Tiers: contract for the thread test, because it pins a rule of the ledger door; integration for the score-key exit test ([CLAUDE.md](../CLAUDE.md) section 13). Real fixtures filed through the door's own writer, real pyarrow, no mocks | Fowler |
| K10 | One pull request: the tests-only commit first (Gate 2), then the fix; the squash makes one behavioural commit that ships with its tests ([CLAUDE.md](../CLAUDE.md) Guardrail #9) | Fowler |
| K11 | Serial decode ships without a gating measurement: low downside, two flags to revert ([CLAUDE.md](../CLAUDE.md) Guardrail #10); B3 names the measurement | Fowler |
| K12 | No design-rationale section: the rule paragraph in `persistence.md` carries its reason, and reversal costs two flags | Fowler |

- **Rejected alternatives:**

Table L

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Retry the step in `build-canary.mjs` | Hides the fault from every other short program | A few lines; every other program stays exposed | Owner; known defect 51 |
| L2 | `os._exit` after printing in `--scored-keys` | Hides the fault for one program and skips shutdown flushes such as logging; a band-aid (Guardrail #5). One unrelated project took this route against issue 34314 | Two lines | Fowler |
| L3 | Copy the bytes into engine-owned memory, keep the threads | No test can fail on today's code, because the race stays a race; engine threads still exist at exit, so D2 stays open | About 3 lines, and memory twice the file size during each read | Fowler |
| L4 | Let the engine open the path itself, keep the threads | The same test gap and D2 exposure as L3; the host verifiers must parse the exact bytes they checked | A signature change; `persist._opened` reads each file twice | Fowler |
| L5 | Shut down the engine's thread pools before exit | pyarrow has no public call that guarantees every finished task is destroyed; every program entry point would need it | A hook in about ten entry points, plus an upstream call that does not exist today | Fowler |
| L6 | `use_threads=False` alone | Keeps read-ahead, which pyarrow 25.0.1 documents as a background I/O thread pool; safety would rest on an undocumented detail | One flag fewer | Fowler |
| L7 | A config knob for the two flags | Setting either to True brings the abort back; a value that must never vary is a named literal (K4) | One config field and its schema, and a way to bring the fault back by config | Fowler |
| L8 | A test that reads `parquet.py` for the flag spelling | It sees the spelling, not the threads; an engine swap or a new path passes it | One small test that gives no signal | Fowler |
