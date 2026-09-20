# The machine, honestly: steal, evicted weights, and a console that names its questions

**Last Updated**: 2026-09-20
**Level**: 5 (a persisted contract, a published payload, and the operator's primary surface)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The console reports hypervisor theft as our own compute, publishes a column that has never held a value, draws a memory mark that falls when its instrument cannot fall, and titles its panels after subsystems instead of the operator's question. |
| Hard scope - in | The sampler separates what the machine gave us from what a neighbour took. The one failure mode nothing can currently see - the kernel reclaiming the model's own weight pages - gets an instrument and a name. Every machine column on the item row either has a reader or is deleted. Every panel on the Hardware route states the question it answers in plain English, sits in a group named for an operator's decision, and no panel survives on the grounds that it already exists. |
| Hard scope - out | See table 0a. |
| ESCALATE triggers | See table 0b. |
| Chosen strategy | Correct the instruments before redrawing the surface that reads them. Carmack ruled which machine readings are reachable and which are noise; Fowler ruled the grain, the seam and what to delete; Susan ruled the page. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. |
| Rollback | None. Git is the backup. A row that replaces a thing deletes that thing in the same commit. |
| The price, stated here rather than discovered at row ten | Fourteen rows name `frontend/src/routes/console/machine/+page.svelte`, measured at 72,099 bytes. Plan 33 group I already paid this as a serial chain and priced the alternative in its Row #27 without taking it. This plan takes it: Row #7 extracts the panels into a file each, which converts a fourteen-link chain into a fan-out and is the reason the console half is not the critical path a second time. Row #7's own cost is one Level 3 refactor that must change no rendered byte. |

### The correction this plan is built on

`_CPU_IDLE` in `backend/idhazh/telemetry/host.py` treats `idle` and `iowait` as not-busy and nothing else, so `steal` is counted as our work. Every busy figure this project has ever published is our compute plus whatever the host gave another tenant, unlabelled and unbounded. Measured 2026-09-20 over the committed `state/item-health/` tree, exact counts over committed files and therefore carrying no spread: `cpu_busy_pct` holds 1,174 rows at min 96.33, median 98.92, max 99.77. None of those figures is what its own column description claims.

A drawn figure that changes meaning says so on the surface that drew it. Row #10 carries that sentence to the page; it is not optional decoration on the row.

### The standing rule: nothing is keyed to how many calls the pipeline makes

**No column, no panel, no track and no title in this plan is shaped by the number of model calls an item makes.** Owner ruling, 2026-09-20, and it is the rule two plan-docs have already broken.

The count is not a property of the pipeline. It is a config value. `_ask_the_model` in `backend/idhazh/stages/common.py` runs `_two_spans` when `turns.thinks` is true and a single request otherwise, `thinks` is true exactly when the model's `turns.thinking_close` is set, and both call sites in `backend/idhazh/stages/two_calls.py` pass the same `model.turns`. The active model sets that marker, so **every logical call is two requests today and an item is four requests - eight alternating read-and-write phases.** Clear one config value and it is four phases, with no code changed.

So every fixed count written about this pipeline has been wrong. Plan 33 said four phases. This plan's first draft said six. The ledger's own `model_calls` says two, and it is right about logical calls and says nothing about phases. **A design that needs the number is a design that breaks on a config edit**, which is why the rule is stated here rather than discovered at a row.

What is allowed: phases, because read-then-write is a property of a transformer; totals over whatever calls happened; and distributions whose track count comes from the data. What is not: a column named for a call, a panel with one track per call, or any arithmetic that assumes a number.

### Table 0a - out of scope

| id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| 0a1 | L3 cache utilization as a column - hit rate, miss rate, occupancy | The explanation for a throughput gap between two machines reporting the same processor. `docs/reference/host-metrics.md` records four EPYC 7763 draws differing 8.8 percent on decode, and neither the instruction-set flags nor the bandwidth probe explains it. | Row #1's probe returning a populated `/sys/bus/event_source/devices/cpu/events/`. That is the only evidence that would move this line, and it is why Row #1 exists. |
| 0a2 | The memory split by prefill and decode - plan 33 Row #8 | The operator cannot say which half of the model call holds the peak, so a context cut and an output-length cut cannot be told apart on evidence. | A within-call memory sample. Row #2 must settle the existing peak column first; until it does, a second memory instrument would inherit a disputed one. Row #18 corrects plan 33's stated reason, which is wrong on two counts. |
| 0a3 | Scheduler thrashing columns - `/proc/stat` `ctxt`, `procs_running` | Nothing measured. `load_1m` at a median 5.50 on 4 vCPU is four spinning ggml threads plus the python worker, the watch thread and the sampler - the expected signature of `n_threads=4, n_parallel=1`, not a pathology to discover. `procs_running` is a gauge and a barrier spike is microseconds, so a 30 s tick cannot see it. | A direct `--threads` experiment showing the queue depth changes the answer. `measure.yml` already runs one, and a within-run comparison cancels the box, so a passive proxy does not beat it. |
| 0a4 | A cache-resident against memory-resident bandwidth probe pair | The ability to say a machine's cache is slow relative to its memory. For a decode loop streaming a multi-GB weight file past a 32 MiB cache, that sentence has no consequence. | A model small enough to be cache-resident. None is on the table. |
| 0a5 | `/proc/vmstat` swap counters - `pswpin`, `pswpout`, `pgmajfault` | Nothing. Swap is consumed - 3.22 GB total with free dipping to 2.53 GB, so about 690 MB - but against 4.33 GB of `MemAvailable` at the worst item that is opportunistic housekeeping at the distribution's default swappiness, not pressure. Weight-page eviction touches no swap counter at all, which is why Row #4 reads major faults on the process instead. | A run where `MemAvailable` approaches zero. Row #14's memory board is what would show it. |
| 0a6 | An `iowait` column | Nothing. The busy figure counts `iowait` as idle, so a median of 98.92 bounds `iowait` at 1.08 percent and the worst item bounds it at 3.67. The ceiling is already known without the column. | A busy figure that drops materially below its 96.33 floor. |
| 0a7 | A bandwidth-against-read-rate scatter panel | After steal, memory bandwidth is the most likely physical explanation for the spread between machines, and nothing plots it against the rate it would explain. | It is a fourteenth panel and Susan ruled it displaces the platform-mix count rather than joining it. That trade is a separate decision, not a row here. |
| 0a8 | Finish reasons and recovery flags as panels - `label_finish_reason`, `summary_finish_reason`, `recovered` | A decode stopping on length rather than on a stop token is a budget that no longer fits, and nothing draws it. | It is a content-quality signal, so it belongs to Editor and Jony on the Pipeline route, not to the Hardware route this plan owns. |
| 0a9 | The page width - `chart.width_px` 760 inside `frame.console_max_px` 1600 | Every panel uses 47.5 percent of the frame it sits in. | A real reading at 1440 and at 1920. Susan refused to pick a width from a config file, and an estimate here would ship as a literal in a theme token. |

### Table 0b - ESCALATE triggers

An escalation STOPS that row and reports. It does not stop the plan; other rows keep running.

| id | Trigger | Why a person decides |
| --- | --- | --- |
| 0b1 | Row #1's probe finds a working hardware PMU on the runner. | The whole of 0a1 was priced on the assumption there is none. A positive result opens scope this plan did not size. |
| 0b2 | Row #2 finds the falling peak is a collection defect that makes committed rows wrong rather than merely mis-described. | Correcting a description is Level 2. Deciding what happens to history a run already wrote is not an agent's call. |
| 0b3 | `cpu_steal_pct` reads zero on every row of the first committed day after Row #4 ships. | Then the reading cannot disagree with anything and Row #10's panel is refused on the same ground that retired `busy_slots_per_decode` in plan 33. One query against one day settles it, and Row #10 states the answer before it draws. |
| 0b4 | Row #7's extraction changes any rendered byte. | It is a pure move. A move that changes output is a rewrite nobody reviewed. |
| 0b5 | A console row cannot be built without raising the route's byte budget. | The design is costed at fewer bytes than the page ships today. If that is false, the premise the ordering rests on is false. |
| 0b6 | Any row needs a second memory instrument on `ItemHealthRow` before Row #2 closes. | A new memory column beside a disputed one inherits the dispute, and the reader cannot tell which figure to believe. |
| 0b7 | A row needs a column, a track, a title or an arithmetic step keyed to the number of model calls. | The standing rule above. The count is a config value, so a design that needs it breaks on a config edit rather than on a code change, and nothing will fail to warn the person who makes it. |

Everything else: dispatch the personas in DEBATE per docs/how-to/execute-a-plan.md, converge to one written ruling, bake it into the row, move on.

## 1 - Status Reckoner

**Part A corrects the instruments. Part B redraws the surface. Part C closes.** Part B's panel rows depend on Part A only where a panel draws a column Part A creates - Rows #10 and #11 - so the two halves overlap rather than queue.

**Row #7 is the row that makes the rest parallel.** Fourteen rows name one Svelte route of 72,099 bytes. Extracting the panels into a file each is what turns that chain into a fan-out, and it must change no rendered byte.

**Three `Depends-on` edges are file overlaps, not logic.** Rows #1, #2 and #6 all write `docs/reference/host-metrics.md`; rows #3 and #6 both write `backend/tests/test_host_readings.py`; rows #6 and #8 both write `backend/idhazh/contracts/knobs/` and `schemas/`. The edges below serialise them so the next dispatch reads the answer rather than re-deriving it.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Does this runner expose a hardware PMU | - | A | DONE | p37r1 | #975 | worker |
| 3 | One status read a tick, not two | - | A | DONE | p37r3 | #974 | worker |
| 7 | One file a panel | - | A | DONE | p37r7 | #977 | worker |
| 8 | The rare-event thresholds become knobs | - | A | DONE | p37r8 | #976 | worker |
| 2 | Settle the peak that falls | 1 | A | DONE | p37r2 | #979 | worker |
| 6 | The bandwidth probe sizes itself against the cache | 1, 3, 8 | A | DONE | p37r6 | #978 | worker |
| 4 | The sampler stops calling theft our work | 2, 3 | B | DONE | p37r4 | - | worker |
| 9 | Panels grouped by the decision they serve | 7 | B | DONE | p37r9 | #981 | worker |
| 5 | `ItemHealthRow` gains three columns and loses one | 4 | C | DONE | p37r5 | #982 | worker |
| 10 | Did another tenant take the processor | 5, 8, 9 | C | PENDING | - | - | - |
| 11 | Is the kernel taking the model's weights back | 5, 8, 9 | C | PENDING | - | - | - |
| 12 | What one article costs the machine | 9 | C | PENDING | - | - | - |
| 13 | Two panels leave the page | 9 | C | PENDING | - | - | - |
| 14 | The memory board drops the disputed mark | 2, 9 | C | PENDING | - | - | - |
| 15 | The shard board gains the clocks nobody reads | 9 | C | PENDING | - | - | - |
| 16 | Machine cards gain uptime, clock speed, cache size and copy speed | 6, 9 | C | DONE | p37r16 | #988 | worker |
| 19 | Which prompts get re-read, and how fast | 9 | C | PENDING | - | - | - |
| 20 | What is holding the runner's memory | 5, 9 | C | PENDING | - | - | - |
| 21 | What the context window actually costs | 9 | C | PENDING | - | - | - |
| 22 | Dotted rules where a setting moved | 9, 21 | C | PENDING | - | - | - |
| 17 | Every published column names its reader | 5, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22 | D | PENDING | - | - | - |
| 18 | Docs, the living-page corrections, and the orphan sweep | all | E | PENDING | - | - | - |

**Rows are listed in dispatch order, not numeric order.** A row number records when it was written; the `Depends-on` column records when it runs.

---

# PART A - The instruments

## Row #1 - Does this runner expose a hardware PMU

- **Scope:** six read-only commands on a workflow that already runs, and one dated line recording what they returned, so the cache-utilization question is closed by a reading instead of by a prior.
- **Files touched:** `.github/workflows/probe.yml`, `docs/reference/host-metrics.md`
- **Acceptance gates:** local - none, this is a workflow change. CI - the probe job completes and its log carries all six readings.
- **Oracle:** the job log names whether `/sys/bus/event_source/devices/cpu/events/` exists and is populated, and `docs/reference/host-metrics.md` carries the runner, the date and the listing. **What it cannot settle:** whether a different runner image or a different Azure fleet would answer differently; the line records which runner it read.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The probe is six file and directory reads and installs nothing | Carmack - it runs under a second on a job that already exists, and the decision rule is reached without a package. An absent or empty `events/` directory closes the question, and only a populated one justifies the cost of a profiling toolchain |
| 2 | The result is written as a dated reading with its runner, not as a rule | Guardrail #10 - a rule carries its reason and a reading lives in the instrument log. The next person asking about cache counters reads a measurement rather than repeating an estimate |
| 3 | `perf_event_paranoid` is recorded but is not the blocker | Carmack - runners carry passwordless sudo, so the sysctl is adjustable. A missing PMU is not |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Assert the PMU is unavailable and skip the probe | It is a strong prior from how the platform is built, not a reading. Guardrail #10 requires the label or the measurement, and the measurement is under a second | Nothing to take - that is the point. The refusal costs the project a permanent unanswered question | Carmack |
| 2 | Install a profiling toolchain and measure cache events directly | Prejudges the answer. The versioned package is frequently missing on this kernel line, so the install is itself a coin flip | An estimated 20 to 40 s of job time on a package that may not resolve, to reach a conclusion the six reads already reach | Carmack |
| 3 | Read cache occupancy through the resource-director interface | It is a host-level tenant-isolation feature and the host keeps it. It also varies by draw - the recorded cache sizes span 32 MiB to 480 MiB - so a working reading would carry a selection bias | A metric that exists on some machines and not others, which cannot be compared across a run | Carmack |

## Row #2 - Settle the peak that falls

- **Scope:** find out why a high-water mark that cannot fall for a live process falls between items in every shard, then correct the column's description to say what it measures.
- **Files touched:** `backend/utilities/` (a new operator script), `backend/idhazh/contracts/item_health.py` (description only), `schemas/item-health-row.schema.json` (generated), `docs/reference/host-metrics.md`
- **Acceptance gates:** local - ruff, mypy, `python -m idhazh.contracts.export` then `git status --porcelain -- schemas/` empty. CI - full suite, drift gate.- **Oracle:** the script names, for one shard, whether the server process identity changed between two items whose recorded peak fell; the corrected description states what the column measures in terms a reader can check against the code. **What it cannot settle:** whether rows already committed are wrong or merely mis-described - if they are wrong, that is ESCALATE 0b2 and a person decides what happens to them.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is an operator surface under `backend/utilities/`, never a pytest assertion | CLAUDE.md section 13 - an assertion a run can turn red belongs to production, not to the suite, and no reviewer can see it coming |
| 2 | The finding is a blocking precondition for Rows #5 and #14 | Fowler and Susan independently - two more memory columns built beside a disputed one inherit its credibility, and a panel cannot honestly draw a mark whose instrument is under investigation |
| 3 | Measured 2026-09-20 over 64 full shards of the committed tree: the recorded peak falls item-to-item in 64 of 64 | Exact counts over committed files, so no spread. Replicated independently by Fowler over a different row selection |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Correct the description to match the behaviour and investigate no further | The behaviour contradicts the mechanism, so a description matching it would be a guess written as a contract | A field description that documents a defect as a feature, which the next reader builds on | Fowler |
| 2 | Delete the column | It is the only recorded process-level peak, and Row #14 needs to know whether it is recoverable before the page gives it up | The one instrument that could have answered the prefill-against-decode memory question, discarded before it was understood | Susan |

## Row #3 - One status read a tick, not two

- **Scope:** the sampler opens the server process status file once a tick and reads both lines from it, the way it already reads five keys from one memory file.
- **Files touched:** `backend/idhazh/telemetry/host.py`, `backend/tests/test_host_readings.py`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/test_host_readings.py -n auto`. CI - full suite.
- **Oracle:** a fixture status file is opened exactly once per tick and both values are recovered from it, asserted by counting opens rather than by reading the values back. **What it cannot settle:** nothing material - the values are unchanged by construction.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Ships before Row #4 rather than inside it | Fowler - a structural change and a behavioural change in one commit is the interleaving CLAUDE.md section 6 asks to avoid, and this one is a pure tidy with no behaviour to review |
| 2 | The saving is not the justification | Carmack measured a tick at an estimated 10 to 50 microseconds a file, so the sampler costs about 0.001 percent of an item. The reason is that two opens for two lines from one file is a defect a reader trips over, not a cost |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it and fold the fix into Row #4 | Row #4 is a behavioural change to a published figure. A reviewer reading it should not also be reading a file-handle refactor | Two kinds of change in one diff, on the commit that corrects the project's most-published number | Fowler |

## Row #4 - The sampler stops calling theft our work

- **Scope:** the sampler counts hypervisor steal separately from our own busy time, and reads the model server's major page faults across the item.
- **Files touched:** `backend/idhazh/telemetry/host.py`, `backend/idhazh/stages/work.py`, `backend/tests/test_host_readings.py`, `backend/tests/test_telemetry.py`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/test_host_readings.py backend/tests/test_telemetry.py -n auto`. CI - full suite.
- **Oracle:** a fixture processor-time pair with a known steal component yields a busy figure that excludes it and a steal figure that equals it, and the two plus idle and iowait sum to the whole interval; a fixture process status with a known major-fault count at open and at close yields exactly their difference. **What it cannot settle:** whether the hypervisor's steal accounting is itself accurate - that is the platform's contract, not ours.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Both readings are counter differences taken at item open and item close, never sampled gauges | Carmack - a counter differenced across the window gives the exact whole-item total regardless of the tick interval, which is why neither reading depends on a knob. Both remain correct with the sampler switched off |
| 2 | Steal costs zero new file reads | Carmack - the two processor-time texts are already read and already differenced. This is arithmetic on data in hand |
| 3 | Major faults are a canary with a named trigger, not a diagnostic for a live problem | Carmack - the busy floor of 96.33 percent across all 1,174 committed rows bounds idle plus iowait at 3.67 percent, and a fault storm would have driven busy far below that. The trigger is the 9B model candidates already in `config/models/`, where weight-page eviction begins and pinning becomes a question |
| 4 | Both land at item grain | Carmack and Fowler agree - a neighbour arrives and leaves inside a job, and a shard is about nine times an item, so a job-grain figure would average the stolen item with the quiet ones. Fowler's grain test is whether the reading can differ between two items of the same job; both can |
| 5 | The fault count is persisted as a count over the window the row already names, never as a rate | Fowler - a rate is a quotient that hides its denominator and cannot disagree with anything. The row already carries the interval, so the reader divides |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Persist raw counter endpoints and let each reader difference them | Every reader would subtract identically, so the subtraction is a fold belonging to the producer, which holds both endpoints already. Two columns for one fact, and the wrong-order bug handed to each consumer | A second copy of one fact, which is a thing that can disagree | Fowler |
| 2 | Persist a per-second rate | The denominator becomes implicit and the figure cannot disagree with anything on its row - the ground that retired `n_decode_calls` in plan 33 | A number that reads as a measurement and functions as decoration | Fowler |
| 3 | Add a swap-activity reading instead of major faults | Weight pages are file-backed, so eviction returns as a major fault and touches no swap counter. The instrument would miss the one failure it was added for | The only visible signal for the failure mode the row exists to catch | Carmack |

## Row #5 - `ItemHealthRow` gains three columns and loses one

- **Scope:** one contract commit adds the steal figure, the major-fault count, a flag recording whether the weights were pinned and the two anonymous-memory readings the fill bar needs; corrects two descriptions; and removes the column that has never held a value.
- **Files touched:** `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/machine_shard.py`, `schemas/item-health-row.schema.json` and `schemas/machine-shard-row.schema.json` (generated), `frontend/src/contracts/` (generated), `backend/idhazh/telemetry/publish/machine.py`, `frontend/scripts/build-canary.mjs`, `backend/tests/contracts/`, `backend/tests/test_item_records.py`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/contracts backend/tests/test_item_records.py -n auto`, `python -m idhazh.contracts.export` then `git status --porcelain -- schemas/` empty. CI - full suite, drift gate, and the `site` and `browser` jobs, which are the only gates that see the canary builder.
- **Oracle:** every committed day file migrates without raising, proved by driving the header migration over the canary day plus a fixture carrying the removed column; a built sampler over a fixture item produces the three new columns with the expected values and produces nulls rather than zeros where no reading was taken. **What it cannot settle:** whether the published machine payload's consumers survive the removed column - that is Row #17's gate and the browser job.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One commit, one changelog entry, one version stamp, oldest real entry pruned | Fowler - the cap is five and it is full. The cap bounds the generated schema that ships to readers, not source tidiness, so a rolling window is what it is for. Row #7 of plan 33 set this precedent with six columns in one entry |
| 2 | The pinning flag ships with the fault count, not after it | Susan - Row #11's panel states that the weights are not pinned. Nothing on the row records whether they are, so the panel's premise rots silently the day somebody sets the flag. The row already carries six comparable server settings |
| 3 | An item with no reading records null, never zero | CLAUDE.md section 1a - a zero steal figure and an unrecorded one are different facts, and only one of them is reassuring |
| 4 | The constant swap-total column stays, and its description gains the clause saying it is constant | Fowler - it survives because the band reads it paired with free swap off one row, and the pairing is the reading. But nothing on the line says it never varies, so a reader will take a distribution over it |
| 5 | The removed column also leaves `MachineShardRow` and the published machine payload in this row's sequence | Fowler - it is folded into the shard row and published as a permanently empty column of a file readers download. Removing it from one place and not the other leaves the published promise intact |
| 6 | The removal is added to the dropped-cell list in the same commit | Fowler - the header migration raises on every committed day without it. That list is the whole migration |
| 7 | Two anonymous-memory readings join, one for the model server and one for our python | Susan, 2026-09-20. They are the cheapest columns in this plan - the same process status file the sampler already parses, one more key each. Anonymous memory is not file-backed, so it cannot double-count with the page cache, which is what makes Row #20's four-segment bar a genuine partition rather than a sum that exceeds the machine |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Separate commits per column | Each spends a changelog entry against a full cap, so three columns would prune three entries and hand-conflict in one block | Two extra prunes and a three-way conflict in one file, for no reviewer benefit | Fowler |
| 2 | Keep the empty column and fix its producer instead | The runner does not expose the interface it reads, recorded absent on 2026-09-09 and still absent. The fix is not available | The operator loses the field's claim - the number the runner kills a job over - but that claim is currently unanswered by an empty column pretending to be an instrument | Fowler |
| 3 | A separate machine-condition ledger at item grain instead of more columns | It would key on the same identity, so it is an extraction with no second identity to extract to. Width is not the test; the key is | A seventh segment ledger, a schema, a generated type, a compaction path, a join on every panel, and a new failure mode where one file is present and the other is not | Fowler |
| 4 | Deleting the end-of-item resident-memory column as unread | It was unread. Susan named two readers for it in the same session - the item-to-item rise, which is the question of whether a larger model fits, and the memory board's second track once the disputed mark leaves | The one series that answers whether memory climbs across a shard | Susan |
| 5 | Deleting the page-cache column as unread | Same - it was promised a reader and did not get one. It is the only cell separating a kernel reclaim from an allocation that grew, which is what makes Row #11's canary legible on the morning it fires | A fault count that says something happened and not why | Susan |

## Row #6 - The bandwidth probe sizes itself against the cache

- **Scope:** the memory-bandwidth probe derives its buffer from the machine's own reported cache size instead of a configured constant, so it cannot silently become a cache reading.
- **Files touched:** `backend/idhazh/telemetry/silicon.py`, `config/idhazh.json`, `backend/idhazh/contracts/knobs/`, `schemas/` (generated), `backend/tests/test_silicon.py`, `docs/reference/host-metrics.md`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/test_silicon.py backend/tests/test_host_readings.py -n auto`, `python -m idhazh.contracts.export` then `git status --porcelain -- schemas/` empty. CI - full suite, drift gate.
- **Oracle:** a fixture machine reporting a cache larger than the configured floor produces a probe buffer at least twice that cache; a fixture reporting a small cache keeps the configured floor. **What it cannot settle:** whether the resulting figure is accurate on silicon nobody has drawn yet.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The configured value becomes a floor, not the answer | Carmack - the recorded buffer is 512 MiB and the largest cache drawn is 480 MiB, a 32 MiB margin defended only by a sentence in a doc telling a human to raise it. Derivation removes the human from the loop |
| 2 | The recorded buffer size stays a column | It is what tells a reader whether a given figure was a memory reading or a cache reading, and after this row it also proves the derivation ran |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Raise the configured constant and keep the doc sentence | It restores the same margin against a fleet that already varies fifteenfold in cache size, so the next larger draw silently reintroduces the defect | A column that lies with nothing flagging it, on a machine nobody has drawn yet | Carmack |

---

# PART B - The console

## Row #7 - One file a panel

- **Scope:** the fifteen panels on the Hardware route move into a file each, with no change to any rendered byte, so the rows that follow fan out instead of queueing.
- **Files touched:** `frontend/src/routes/console/machine/+page.svelte`, a new `frontend/src/lib/console/machine/` directory of panel components, `frontend/tests/`
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list` then the selected checks; the browser smoke per CLAUDE.md section 12. CI - full suite, the `site` and `browser` jobs.
- **Oracle:** the rendered HTML of the route is byte-identical before and after, captured from a build on each side and compared directly. **What it cannot settle:** nothing - byte identity is the whole claim, and anything else is ESCALATE 0b4.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row exists because ten rows name one file | Fowler - plan 33 group I serialised seven rows over this route and priced the extraction in its Row #27 without taking it. Ten rows is where the price is paid |
| 2 | It is a pure move and ships alone | Fowler - a move that also changes something is a rewrite nobody reviewed. Byte identity is the acceptance gate, not a nice-to-have |
| 3 | Panel titles are NOT changed here | Row #9 owns the titles. Moving and retitling in one commit destroys the byte-identity oracle that makes this row safe |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Chain the console rows as plan 33 did | It reproduces in the frontend the exact collision the backend half of plan 33 existed to remove, and there is no merge driver for markup | The console half becomes the critical path a second time, ten links long, each link its own pull request | Fowler |
| 2 | Extract only the panels this plan touches | The route keeps two organising principles at once, and the next plan has to decide which half a new panel joins | A half-migrated directory, which is the shape that never finishes | Fowler |

## Row #8 - The rare-event thresholds become knobs

- **Scope:** four thresholds that decide when a quiet day becomes a loud one are declared in config with schema-validated defaults, before the panels that read them exist.
- **Files touched:** `backend/idhazh/contracts/knobs/console.py`, `backend/idhazh/contracts/appearance_config.py`, `schemas/appearance-config.schema.json` (generated), `config/appearance.json`, `frontend/src/lib/server/config.ts`, `backend/tests/contracts/`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/contracts -n auto`, `python -m idhazh.contracts.export` then `git status --porcelain -- schemas/` empty. CI - full suite, drift gate.
- **Oracle:** changing a threshold in config changes which fixture day is drawn as loud, with no source edit - the substitution test of Guardrail #6. **What it cannot settle:** what the defaults should be; they are argued in decision 2 and a person may move them without a code change, which is the point.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Two thresholds per signal, not one | Susan - quiet decides whether the tile fills, loud decides whether the headline sentence names a worst case. One threshold cannot do both |
| 2 | This is a full contract change, not a line in a config file | Fowler - the appearance contract also holds five changelog entries against a cap of five, so this row pays the same wall Row #5 pays. A worker who edits only the config file ships a key with no schema and fails validation at build time |
| 3 | It ships before the panels that read it | Guardrail #3 - a shape is declared before logic reads it |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Literals in the chart module | Guardrail #6. A threshold that decides whether the operator is alarmed is the definition of a tunable | A source edit and a rebuild every time the fleet's behaviour shifts | Susan |

## Row #9 - Panels grouped by the decision they serve

- **Scope:** every panel on the Hardware route is retitled to the question it answers, given a one-line subtitle saying why that answer changes what the operator does, and moved into one of four groups named for a decision rather than for a time grain.
- **Files touched:** the panel components Row #7 creates, `frontend/src/routes/console/machine/+page.svelte`, `config/appearance.json` (the group names and order), `docs/architecture/publishing/console.md`, `frontend/tests/`
- **Acceptance gates:** local - the shared test selector then the selected checks; the browser smoke per CLAUDE.md section 12. CI - full suite, the `site` and `browser` jobs.
- **Oracle:** every panel resolves to exactly one group and every group carries at least one panel, asserted over the rendered route; no title names a column, a subsystem or a vendor. **What it cannot settle:** whether the four groups are the right four - Susan ruled them and a reader may disagree, which is a design finding rather than a test failure.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four groups are: was it us or the machine; where this run's time went; how much room is left; what the model is spending it on | Susan - the order is triage, locate, project, tune, and each group's answer decides whether the next is worth reading. Today's groups sort by time grain, which is a fact about the instrument and not a question anybody has |
| 2 | Every subtitle's last clause states its own time grain | Susan - group membership today silently carries "this panel follows the span control", and the page spends four paragraphs explaining it. Mixing grains inside a group breaks that carrier, so the grain moves onto the panel. More words per panel, fewer per group, because a reader reads a panel |
| 3 | A title states the question; a subtitle states why the answer changes what you do | Owner, 2026-09-20. The words question and answer are never printed |
| 4 | Titles are written in plain language with no subsystem term, no column name and no vendor name | CLAUDE.md section 0b - a term from a subsystem is not a term for a user, and a third-party product name is not a design vocabulary |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the time-grain groups and retitle only | The grouping is the part that makes an operator scan the whole page to find where their question lives | The triage order, which is the reason the steal and eviction panels sit at the top | Susan |
| 2 | Rebuild the route rather than retitle it | The discipline the page already has - absence drawn as absence, named recording states, the sub-pixel band rule, one colour ramp a page - is the reason a retitle is sufficient | A rewrite of the parts that work, to change the parts that do not | Susan |

## Row #10 - Did another tenant take the processor

- **Scope:** one panel showing the time the host gave to somebody else's machine while ours was working, at day grain and at shard grain, carrying the sentence that the busy figure used to include it.
- **Files touched:** a new panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** a fixture window where one shard lost a known share of its processor draws that shard as loud and prints the share; a fixture window with no steal draws every tile outlined and prints the quiet sentence; a fixture day predating the column draws a blank cell and prints neither. **What it cannot settle:** whether the steal we measure is the whole of what the host took - that is the platform's accounting.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The panel carries a printed correction naming the date before which the busy figure counted theft as ours | Susan - a drawn figure that changed meaning says so on the surface that drew it. Without it every historical run silently reports a clean machine |
| 2 | A run predating the column draws a fourth state saying the reading begins later, never a zero | Susan - a zero steal figure is a claim about the host, and we have none for those runs |
| 3 | Steal also becomes a column on the shard board | Carmack and Susan - it is the standing candidate for the spread between shards of one run, and the rates it would explain already sit there |
| 4 | A second row of tiles, one a shard of the newest run | Susan - a per-day figure hides exactly the within-run spread the panel exists to explain |
| 5 | The row states whether steal is ever non-zero before it draws | ESCALATE 0b3 - a reading that is constant cannot disagree with anything, and one query against one committed day settles it |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A line chart over days | A value axis has to pick a top. Auto-scaled, a trivial day draws identically to a severe one; fixed to the threshold, almost every day is a flat line on the floor and the reader stops looking | A panel that either cries wolf or is ignored, with no third setting | Susan |
| 2 | Fold steal into the existing busy panel as a second series | The busy panel is being corrected by Row #4, so the two would share an axis while one of them changed meaning under the reader | The correction notice, which needs a panel of its own to be read | Susan |

## Row #11 - Is the kernel taking the model's weights back

- **Scope:** one panel showing whether the model's weight pages were reclaimed and read back off disk, with the page-cache reading beside it on the same date axis, and the pinning setting printed from the run's own record.
- **Files touched:** a new panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** a fixture day with a known fault count above the loud threshold fills its tile and prints the count; a fixture day with faults but a steady page-cache reading and one with faults and a falling page cache are distinguishable on the panel; a day predating the column draws a blank cell distinct from a quiet one. **What it cannot settle:** whether a fault was a weight page or another mapping - the count is per process, not per mapping.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The pinning line is read from the run's record, never written as a literal | Susan - a panel that states the weights are not pinned while nothing records whether they are will lie the day somebody sets the flag. Row #5 supplies the column |
| 2 | The page-cache reading is drawn beside the fault count, not instead of it | Susan - a fault count says something happened and not why, and the page cache is the only cell separating a kernel reclaim from an allocation that grew. This is the reader that took that column off probation |
| 3 | Three tile states, three marks: not recorded, recorded and quiet, recorded and fired | Susan - the archive is mostly null for these columns, so an absence that looks like a quiet day is the default failure |
| 4 | Fixed height whether or not anything fired | Susan - the page does not reflow when something goes wrong, so an operator who has learned where the strip sits checks it in one glance |
| 5 | The panel leads with the finding as a sentence and the strip is the evidence | Susan - a panel whose finding is only a shape makes the reader do the reading |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Draw swap activity instead | Weight eviction touches no swap counter, so the panel would draw a quiet strip through the exact failure it exists to catch | The one signal for the failure mode | Carmack |
| 2 | Wait until a fault storm has actually happened | The busy floor says one has not happened yet, and the named trigger is a model change somebody will make without remembering this panel does not exist | The canary arrives after the morning it was for | Carmack |

## Row #12 - What one article costs the machine

- **Scope:** one panel printing processor seconds, added memory and model seconds for a single article, each with its spread, so a change to the prompt, the model or the item count can be priced before it runs.
- **Files touched:** a new panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** each printed figure equals the value recomputed from the fixture's item rows, asserted on a data attribute; a fixture run whose host record names no core count prints a dash for processor seconds rather than assuming a core count. **What it cannot settle:** which half of the model call holds the memory - the panel says so and names the measurement that would settle it.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three figures, each with a spread bar, never three bare numbers | Susan - a single figure from a distribution this wide is a claim the data does not support |
| 2 | The memory figure is the rise between consecutive items of a shard, not a level | Susan - flat means the server is steady and climbing means something grows across the shard, which is the direct input to whether a larger model fits |
| 3 | The panel prints what it cannot answer and names the measurement that would | Susan - the memory half of the question belongs to plan 33 Row #8, and naming the measurement beats faking the answer |
| 4 | Processor seconds print with what a runner-hour actually supplies, next to the number | Guardrail #10 - a count of processor seconds means nothing without its denominator |
| 5 | Where the host record names no core count, the figure prints a dash and says why | Susan - never assume the core count, because the fleet varies |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Derive the per-article cost from the run total divided by the item count | It cannot disagree with the run total, so it is not a check - the ground that retired the derived decode count in plan 33 | A number that reads as a measurement and is arithmetic | Fowler |

## Row #13 - Two panels leave the page

- **Scope:** the panel holding three unrelated figures is deleted and the single-run distribution panel is deleted.
- **Corrected 2026-09-20:** the title said three panels. Decision 4 cancelled the cache fold, so two panels leave and Row #19 rebuilds the cache panel at call grain.
- **Files touched:** the panel components Row #7 creates, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `config/appearance.json`, `frontend/tests/`, `docs/architecture/publishing/console.md`
- **Acceptance gates:** as Row #9, plus the payload shrinks: the prerendered figure count and the per-span array count both fall.
- **Oracle:** the route's payload carries two fewer prerendered figures and the removed per-span arrays are absent, asserted on the built output rather than on the source. **What it cannot settle:** whether an operator was using a deleted panel in a way nobody recorded.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The three-figure panel dies as a junk drawer, and its title named a subsystem | Susan - one of its figures has read the same value on 382 of 383 committed rows, and another becomes false the moment Row #4 separates steal out |
| 2 | Its span band survives, on the steal panel | Susan - that is where the honest version of the busy figure now lives, so the band moves rather than dying |
| 3 | The single-run distribution panel dies because it draws the newest column of the panel below it | Susan - the loading code says so outright. The trend panel gains one printed ratio, which is what the curve was being eyeballed for |
| 4 | The cache panel is NOT folded - that ruling is cancelled | Susan, reversing herself 2026-09-20 on a measurement. The fold target is day grain, and the day figure is the mean of a 53.00 percent reuse on the first call and a 98.73 percent reuse on the second, which describes neither. Folding would have moved the defect rather than fixed it. Row #19 rebuilds the panel at call grain instead |
| 5 | The run's configuration loses its home, and that is named rather than absorbed | Susan - the three-figure panel was the only place a run could be read against its own settings. Row #11's pinning line is the first plank of a replacement, and the gap stands until somebody builds it |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the three-figure panel and retitle it | A container holding three unrelated figures has no question to be titled with | A title that names a subsystem because nothing else fits, which is the defect Row #9 exists to remove | Susan |
| 2 | Keep the distribution panel for its shape | The trend panel's readout already prints all five of its values for the hovered run | Nothing, once the ratio is printed | Susan |

## Row #14 - The memory board drops the disputed mark

- **Scope:** the memory board leads with how close an item took the machine to running out, drops the mark whose instrument Row #2 disputes, and says on the page why it is not drawn.
- **Files touched:** a panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** the printed item minimum equals the minimum over the fixture's item rows, asserted on a data attribute; a fixture day predating the kernel columns draws no mark for those items and prints how many were skipped, rather than drawing a zero. **What it cannot settle:** whether two items' minima fell on the same moment - where they did not, the panel states the sum is an upper bound.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The disputed mark comes off the page and stays in the ledger | Susan - an instrument known to be wrong says so on the surface that would have drawn it, and nothing is deleted while Row #2 is open |
| 2 | The lead becomes the within-item floor of what the kernel had left | Susan - a shard maximum cannot show this, because one item can take the machine to the ceiling while its shard reads as normal |
| 3 | The end-of-item process reading is drawn as a bracket labelled at most, never as a track against the machine's total | Susan, correcting herself 2026-09-20. A process resident-set figure drawn against a total reads as a budget, and that is the exact figure this project retracted on 2026-09-09. Row #20's bar is the board's second half |
| 4 | A day with no kernel columns draws no mark and prints the date the reading begins | Susan - 227 of 13,717 committed rows carry them, so this is the common case rather than the edge case. Never a zero line, never a silent fallback to the disputed mark |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep drawing the disputed mark with a caveat | A caveat under a mark does not stop the mark being read | A figure the page itself says is wrong, drawn anyway | Susan |
| 2 | Wait for Row #2 before touching the board | The board's lead is wrong independently of the dispute - it leads with a shard figure where the question is per item | The one reading that says how close a single article took the machine to its limit | Susan |

## Row #15 - The shard board gains the clocks nobody reads

- **Scope:** the shard board gains the time no named stage claimed, the time an item spent queued, and the time opening the weights, so a slow shard gets an address rather than an adjective.
- **Files touched:** a panel component, `frontend/src/lib/server/payload.ts`, `frontend/src/lib/server/machine-counters.ts`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** the unclaimed-time figure equals the fixture's own column rather than a difference recomputed on the page, and a fixture row carrying a negative value renders it as a disagreement between clocks rather than as zero. **What it cannot settle:** which stage the unclaimed time belongs to - that is what the column exists to flag rather than to answer.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The unclaimed-time column is drawn as it is stored, sign included | Susan - it is signed on purpose, and a negative value means two clocks disagreed. Taking the absolute value discards the finding |
| 2 | It is the highest-value unread column on the row | Susan - its own contract calls it the one column that can catch a regression in a stage nobody named, and nothing on the site reads it |
| 3 | Queue time joins the clock track rather than becoming a figure | Susan - the board already draws a job clock and a model clock and cannot say how much of the gap was queueing, and the two have different fixes |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Recompute the unclaimed time on the page from the stage clocks | It would then agree with them by construction and could never flag the disagreement it exists to flag | The column's entire purpose | Fowler |

## Row #16 - Machine cards gain uptime, clock speed, cache size and copy speed

- **Scope:** each machine card says how long the machine had been up when we got it, what clock it ran at, how much cache it has and how fast it copies memory - and refuses the copy figure where the probe was too small to have measured memory at all.
- **Files touched:** a panel component, `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/charts/machine.ts`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** a fixture host record whose probe buffer is under twice its cache size renders the card's named absent state for copy speed with the sentence saying why, and one with a large enough buffer renders the figure; every other figure renders from the record and a record missing one renders the existing absent state rather than a zero. **What it cannot settle:** why a machine was below its top clock - throttling and sharing look the same from inside a guest.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Uptime earns its place because a freshly booted machine has a cold page cache | Susan - that is Row #11's other candidate cause, and without it the fault strip has one explanation instead of two |
| 2 | The top clock column is empty on all 57 committed host rows, so the card prints the probe clock alone until a producer writes it | Susan, 2026-09-20. The column sits in the header and is never written. A card that divides by an empty column is the empty-column defect a second time, and the first draft of this row would have shipped it |
| 3 | The card's three existing named absent states are kept verbatim | Susan - they already distinguish recording switched off, record lost, and no machine drawn |
| 4 | Cache size and copy speed go on the card; the fleet SPREAD goes on the existing per-machine panel | Susan - a card cannot show a spread, and the spread is the defect. Measured over 57 committed host rows, copy speed spans 21.96 to 48.57 GiB a second and cache size spans 32 MiB to 480 MiB, a 15-fold range across machines we draw at random |
| 5 | Where the probe buffer is under twice the cache, the copy figure is refused and the card says why | Susan, 2026-09-20, **on a corrected premise**. Re-measured by Row #6's worker over 60 committed host rows, not the 57 first written: the buffer was 512 MiB on every row and **7 of them carry a cache too large for it** - 3 at 480 MiB and 4 at 260 MiB - so those seven figures are cache readings wearing a memory reading's name. **They are the seven SLOWEST in the fleet, 21.96 to 26.42 GiB a second against a median of 39.57 - not the fastest, as this row first claimed.** So the undersized buffer is a reason to distrust those seven rather than evidence they were inflated, and the fastest figure in the fleet, 48.57, comes from a 32 MiB machine with a 16-fold buffer and is a clean reading. The refusal still stands; its reason is the opposite of what was written. Row #6 fixes the probe going forward; the card has to tell the truth about rows already committed |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A separate panel for clock speed or for cache size | Two figures about one machine, on a route fourteen rows already serialise over | A card the reader has to hold in their head while looking at a panel | Susan |
| 2 | Draw the four suspect copy figures with a footnote | A footnote under a number does not stop the number being compared, and these four sit at the top of any ranking | The ranking, quietly wrong at its head | Susan |

## Row #19 - Which prompts get re-read, and how fast

- **Scope:** one panel showing the spread of prompt reuse and reading speed across the model requests an item makes, so the requests that re-read their whole prompt are visible however many requests there are.
- **Files touched:** a panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** the panel is built by iterating whatever reuse columns the row carries, and a test proves it by rendering a fixture with a different number of them and asserting the track count follows the fixture rather than a constant; a fixture whose reuse spans nothing to nearly everything renders that spread rather than its mean. **What it cannot settle:** why a given prompt reuses nothing - the panel locates it and the prompt is where the answer is.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The panel is never shaped by the number of calls** | Owner, 2026-09-20 - the standing rule in section 0. The track count is read off the data, so merging two requests into one or splitting into three changes the drawing and breaks nothing |
| 2 | The finding is the SPREAD, not which request owns which end | Susan, amended 2026-09-20 - measured over 1,161 committed item rows, reuse runs from a floor of **0.00 percent** to a ceiling of **98.73**, and the mean of that range describes nothing. A request that re-reads its whole prompt is the defect whatever it was for, and the readout names it from the data |
| 3 | Reading speed is drawn because it is the variable half | Susan - reading speed spans 9.13 to 42.03 tokens a second across the fleet, a 4.3-fold range, while writing speed sits between 2.76 and 7.49 and barely moves. Reading is 60.3 percent of model time at the median, so the variable half is also the expensive half |
| 4 | The distribution is taken at item grain and drawn as spans, never as one mark a request | Susan and Carmack - item grain is the finest the ledger holds, and over a thousand marks in the payload would spend the whole byte saving on a chart nobody can read |
| 5 | This row cancels Row #13's fold | Susan, 2026-09-20 - the fold target is day grain, and a day figure averages a request that reused nothing with one that reused nearly everything |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Four tracks, two per named call, as first drafted | It is the design the standing rule forbids. It reads as two facts about two fixed things, and the number of those things is a config value | A panel that silently becomes wrong the day somebody clears one config marker, with no test and no gate to catch it | Owner, 2026-09-20 |
| 2 | Keep one reuse figure a day | It is the mean of a floor near zero and a ceiling near 99, so it cannot move when either end does | The one asymmetry on this page that names a fixable defect | Susan |
| 3 | One mark a request rather than a span | Over a thousand marks answer no question a span does not, and the payload cost is the whole saving this design claims | A chart that is a texture | Susan |

## Row #20 - What is holding the runner's memory

- **Scope:** one panel showing what consumes the runner's memory, drawn so that the parts a reader may add are a true partition and the parts they may not are visibly overlapping, with the swap actually in use ruled underneath.
- **Files touched:** a panel component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/tests/`, `docs/concepts/console-design.md`, `docs/reference/pipeline-cost.md`
- **Acceptance gates:** as Row #9.
- **Oracle:** the drawn segments sum to the machine total on every fixture row and the test fails if they exceed it; the two brackets render visibly overlapping and carry the at-most label; a fixture row where the residue computes negative renders the disagreement rather than clamping to zero. **What it cannot settle:** which of the two brackets owns a shared page - the panel says so in a sentence rather than guessing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The bar as first asked cannot be drawn, and this is measured rather than feared** | Susan, 2026-09-20. Stacking the model server, our python, the page cache and what is free exceeds the machine total on **227 of 227 committed rows, by up to 1.870 times**. Two independent double-counts cause it: the weights are resident in the server and counted in the page cache at the same time, and what the kernel reports as available is mostly reclaimable page cache. The sampler's own source already carried the warning in a comment and nobody read it before drawing |
| 2 | Today it ships as two segments that genuinely partition the machine, plus two overlapping brackets | Susan - what the kernel says it could still hand out, and what is held. The two process readings sit inside the held segment as brackets labelled at most, drawn overlapping on purpose. **A reader cannot add two brackets that visibly overlap, which is the whole point of the shape**; abutting slices would invite the addition that produced the 1.870 |
| 3 | Two columns turn it into the four-segment bar that was asked for, and Row #5 carries them | Susan - anonymous memory is not file-backed, so it cannot double-count with the page cache. Modelled against the measured weight-file size, the residue is positive on **227 of 227 rows at a minimum of 0.26 and a median of 0.33 GiB** - about the size of a kernel plus a runner agent - so the decomposition closes on every committed row |
| 4 | The swap actually in use is ruled below the bar | Susan - measured on 227 rows it runs a median of zero, a p90 of 48.1 MiB and a worst case of 657.9 MiB, and it is non-zero on **198 of them**. `docs/reference/pipeline-cost.md` records that we had no reading for this and that the marks and the job's survival did not sit together; this is the reading that settles it, so that page is corrected in this row |
| 5 | Where the residue computes negative, draw the disagreement and never clamp to zero | Susan - the same rule Row #15 applies to the unclaimed-time column |
| 6 | The panel states what it cannot separate, on the panel | Susan - the weights are read from a file rather than loaded, so they count inside the server's bracket and inside the page cache at once, and the two brackets cannot be added |
| 7 | It draws the days it has and says so | Susan - the machine-total column carries two committed days, so the panel draws two and prints the date the reading begins. Row #14 decision 4's rule already covers it |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | The four-slice stack as originally asked for | It exceeds the machine on every committed row by up to 87 percent, and the owner's stated use - seeing what grew when a prompt changed - is exactly where a double-count misleads | A confident wrong answer on the question the panel was requested for | Susan |
| 2 | Draw the process readings as abutting slices | Abutting invites addition, and these two may not be added | The 1.870, rebuilt in a prettier shape | Susan |
| 3 | Wait for the two columns and ship nothing today | The swap rule alone closes a question a reference page records as open, and the two-segment partition is true now | A measured finding left undrawn while a better version is built | Susan |

## Row #21 - What the context window actually costs

- **Scope:** the context panel gains what the current setting already spends, so the question stops being only whether the window could grow.
- **Files touched:** a panel component, `frontend/src/lib/server/payload.ts`, `frontend/tests/`
- **Acceptance gates:** as Row #9.
- **Oracle:** the printed unused share equals the value recomputed from the fixture's item rows, and a run mark renders both ends - the high percentile and the largest - rather than one. **What it cannot settle:** whether a smaller window would change summary quality; that is Editor's and Andre's, on a different route.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The panel prints what the window costs and not only whether it could grow | Susan - measured over 1,161 committed item rows against a 65,536-token window, the largest prompt ever sent used **42.5 percent** of it, the 99th percentile used **18.4 percent** and the median used **2.8 percent**. Nothing has ever been cut off: both calls report a natural stop on 1,161 of 1,161 rows |
| 2 | Run marks gain a second end | Susan - one mark cannot show both the typical prompt and the worst one, and the decision to shrink a window turns on the worst |
| 3 | The row states the finding rather than acting on it | The window is a config knob and shrinking it is the owner's call. The panel's job is to make the slack impossible to miss |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the panel as a headroom reading | It answers whether the window could grow, which nobody is asking, and stays silent on the window being 57 times the median prompt | The single largest piece of slack visible anywhere in this plan | Susan |

## Row #22 - Dotted rules where a setting moved

- **Scope:** four time-series panels gain a dotted rule on every date the run record says a setting moved, so a before-and-after is never read across a change nobody saw.
- **Files touched:** a shared rule component, `frontend/src/lib/charts/machine.ts`, `frontend/src/lib/server/payload.ts`, the four panel components, `frontend/tests/`, `docs/concepts/console-design.md`
- **Acceptance gates:** as Row #9.
- **Oracle:** a fixture where five settings move on one date renders exactly one rule whose readout names all five; a fixture date with a rule and no reading renders the rule beside the panel's named absent state; a fixture date with no run record renders no rule at all. **What it cannot settle:** whether a setting moved on a day the record does not cover - which is why decision 5 forbids inferring one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No new column. The record already exists and already reaches the payload** | Susan, 2026-09-20, correcting the brief she was given. The run record carries the prompt digest, the context size, the truncation cap, the sampling settings and the turn markers, and the payload builder already passes them through. Measured: 18 of 118 committed run entries carry them, and the prompt moved **six distinct values in eight days**. This makes the markers the cheapest of the five asks rather than the most expensive |
| 2 | One rule a date, never one a setting | Susan - **2026-09-15 moved five settings at once**, measured. Five hairlines on one date is a smear; one hairline whose readout names all five is a finding |
| 3 | A hairline behind every data mark, in the neutral rule colour, never a semantic one | Susan - these are not facts about the machine, so they never borrow the machine's colour ramp, and a marker is never the topmost thing in a panel |
| 4 | A date with a rule and no reading draws both | Susan - the record starts before the memory columns do, so some dates have a rule and no data. **That is the marker's most useful state**: a setting moved on a day nobody was measuring, which is what an owner needs before trusting any before-and-after |
| 5 | A rule is drawn only where the record says so, and never inferred from a gap | Susan - 100 of 118 run entries carry no record. Drawing nothing-moved for a day we have no record of is the same class of claim as a zero theft figure, refused in Row #10 for the same reason |
| 6 | On the day strips a change is a corner notch, not a rule | Susan - a strip is already one cell a day, and a hairline inside a cell is noise |
| 7 | Four panels carry rules: the tail trend, the context panel, the rebuilt cache panel and the memory bar | Susan - the cards have no time axis and the shard board is one run, so neither can carry one |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A labelled marker on the plot | The readout carries words and the plot carries the line, which is the split the design page already makes for shared columns | A plot with five labels on one date | Susan |
| 2 | One rule per setting that moved | Measured, one date moved five settings, so the panel would draw a smear on exactly the date that most needs reading | The date a reader most needs to see, rendered illegible | Susan |
| 3 | A new column on the item row for the prompt digest | The record already exists at run grain and already reaches the payload | A second copy of a fact, which is a thing that can disagree | Fowler |

---

# PART C - Closure

## Row #17 - Every published column names its reader

- **Scope:** a contract test asserts that every column the pipeline publishes resolves to a named reader, and a companion operator surface reports any column that is empty on every committed row, so a column nobody draws and a column nobody writes both stop shipping.
- **Files touched:** `backend/tests/contracts/`, `backend/idhazh/contracts/item_health.py` and `backend/idhazh/contracts/host_fingerprint.py` (the reader annotations), `backend/utilities/`
- **Acceptance gates:** local - ruff, mypy, `pytest backend/tests/contracts -n auto`. CI - full suite.
- **Oracle:** the test fails when a column is added with no named reader, proved by adding one in the test itself. **What it cannot settle:** whether the named reader actually draws it - that is the browser job's arm, not this one - and whether a column is empty, which a run can change and therefore belongs to the operator surface rather than to the suite.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A fixed-size read over a static list, never a walk of the committed tree | CLAUDE.md section 13 - a test's cost belongs to the code it checks, and a run must not be able to turn it red |
| 2 | The emptiness census is an operator surface under `backend/utilities/`, never a test | CLAUDE.md section 13 - whether a column is empty depends on what runs have written, so an assertion on it goes red because somebody edited the tree |
| 3 | It runs after the console rows, not before | The console rows are what create the readers the test asserts |
| 4 | Scope is every published column, not only the machine ones | Susan, 2026-09-20 - the census found four more empty columns beyond the one Row #5 deletes. `truncation_cap_tokens` and `failed_field` are empty on every committed item row, and `mhz_max` and `vm_zone` are empty on every committed host row. Two of the four are not machine columns, so a machine-only gate would have missed them. **Corrected 2026-09-20** from a first reading that named `prefix_shared_with_previous` as empty and missed `failed_field` and `vm_zone`: it read one day file's header as the column list, and the day files are two widths. `prefix_shared_with_previous` holds values |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A column-count budget on the row | Width is not the test. A row with one key answers one question at any width, and a count would block a column that earns its place while permitting one that does not | A gate that fires on the wrong thing, which teaches people to raise it | Fowler |

## Row #18 - Docs, the living-page corrections, and the orphan sweep

- **Scope:** the living docs record what this plan decided, the phase-split ruling lands on the page that owns the item row rather than in a plan-doc, and every doc, test and surface the deletions orphaned is removed.
- **Files touched:** `docs/reference/host-metrics.md`, `docs/architecture/sources/item-health.md`, `docs/architecture/publishing/console.md`, `docs/concepts/console-design.md`, `docs/architecture/publishing/telemetry-series.md`, any page the sweep finds
- **Acceptance gates:** local - `python backend/utilities/doc_load.py` before and after, and every link resolves. CI - full suite.
- **Oracle:** no page names a deleted column, no page claims the busy figure excludes theft for a period when it did not, no page states a fixed number of model calls or phases, and the doc-load report shows the split test was applied to every page that gained a section. **What it cannot settle:** whether a reader finds the new grouping clearer - that is a design finding.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No plan-doc is edited by this row.** Plan 33 is being distilled and deleted, so a correction written into it would be deleted with it | Guardrail #4 - a plan-doc is a cache and `docs/` is the memory. Git holds every plan that ever existed, and a worker who needs the original reads it there rather than expecting a file |
| 2 | The phase-split ruling lands as a `## Design rationale` entry on the page that owns the item row | Guardrail #4 - a decision is recorded in the living doc it impacts, never as a standalone record. That entry is what stops the brittle design being re-derived once the plan-doc is gone |
| 3 | **That entry states no number.** It says the phase count is set by the model's thinking marker in config and gives the rule for deriving it | Owner, 2026-09-20. Every fixed count written about this pipeline has been wrong - plan 33 said four, this plan's own first draft said six, and the code plus the active config say eight today. A number written down here is a number that rots on a config edit |
| 4 | The rejected unblock is recorded with its price, not merely as a refusal | CLAUDE.md section 0d - a rejection with no price is indistinguishable from a prohibition, and the next reader inherits the prohibition. The price is that task-named timestamp columns hard-code a call shape a config value controls |
| 5 | The probe result is written as a dated reading with its runner | Guardrail #10 - the next person asking about cache counters reads a measurement instead of repeating an estimate |
| 6 | The rare-event strip doctrine is written into the design page once | Guardrail #4 - so no later panel row re-argues why a rare event is a strip rather than a line |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Edit plan 33's escalated row in place | It is being distilled and deleted, so the edit would be reverted by the deletion, and a row that depends on another plan-doc still existing is a row that fails for a reason nobody can see | A conflict against a sibling's distillation, and a correction that vanishes | Fowler |
| 2 | Record this plan's decisions only in this plan | A plan-doc is a cache, not the memory | The decisions vanish when this plan is distilled in turn | Guardrail #4 |
| 3 | State the current phase count in the docs so a reader knows what is true today | It is true today and false after one config edit, with no test and no reviewer able to see the change | A rotting number in a living doc, which is the defect this row exists to remove from two other pages | Owner, 2026-09-20 |
