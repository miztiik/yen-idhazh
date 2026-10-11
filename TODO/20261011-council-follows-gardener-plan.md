# LLM council follows the gardener

**Last Updated**: 2026-10-11
**Level**: 5 (CLAUDE.md section 6). Row #8 changes a persisted shape and pauses for the owner; every other row states its own level.
**Status**: drafted 2026-10-11 at the owner's request that the LLM council follow the gardener's pattern, and reviewed by Fowler, who applied the runtime persona's rule for the one runtime question. The summary-fidelity-judge plan registers its judge paused and model-free in the entry shape row #1 defines, so that plan's row #3 waits for row #1 of this plan. No row started. Table P awaits the owner.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The council starts a model server on every cell, runs every registered judge every night, gives every job a write token, checks out the whole tree in every job, logs prose that can carry an exception's text, and writes nothing on its job page. The gardener already solved each of these, and the owner asked the council to follow it (2026-10-11). |
| A2 | Hard scope - in | - Each judge carries a lifecycle status and a model need, and only active judges run (row #1)<br>- Each council job holds only the permissions its steps use (row #2)<br>- One-line JSON events, no exception text, the crash printer, and one exit-code vocabulary (row #3)<br>- Refusals of a bad judge set before any unit runs (row #4)<br>- A job-page summary of the night (row #5)<br>- A collecting job that checks out code and config and fetches only named inputs (row #6)<br>- Each judge runs over its own outstanding dates (row #7)<br>- A unit that raises files a failed council record (row #8)<br>- The council's record published for the console (row #9) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Adopt the gardener's declared units, statuses, refusals, events, summary, least-privilege permissions and named inputs; keep the council's model server, clocks, matrix width, nights_outstanding, collecting job and recovery policy, which the gardener has no equivalent for. Fowler (architecture review, 2026-10-11, gap table in Table S) |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows #3, #6 and #7 all edit backend/utilities/council_publish.py, so the dispatcher serialises them through their Files touched lists. |

### Hard scope - out

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | A rehearsal (dry-run) status for judges | A new judge's first live night commits rows before a person reads them | An owner ruling, priced as a fourth status every council step must handle |
| B2 | A standard-library planning job that runs before the package is installed | The planning job keeps its install, about a minute (estimate) | Moving nights_outstanding and prepare out of the planning job, because both need installed judge code |
| B3 | Binding a judge's module by its slug, as the gardener binds a task by name and kind | Judges are still found by a sorted search over the council's subpackages | Renaming backend/idhazh/similarity and every import of it |
| B4 | Sparse checkout and a download budget (cone_bytes, downloaded_bytes) for judging cells | Full checkouts in judging cells; their time cost is not measured | A run log showing the checkout takes more than about a third of a no-model cell's minutes (estimate); then a per-judge input declaration and the byte columns (Level 5) |

### ESCALATE triggers

Table C - when to stop and ask

| # | Name | Trigger | What happens |
| --- | --- | --- | --- |
| C1 | Stored shape | A row changes a persisted shape (council-run-records or a judge's ledger) | Stop. The owner rules on the shape (CLAUDE.md section 0). Row #8's shape is P5 |
| C2 | Judge import | A judge module or contract would enter the council's own import closure | Stop. backend/tests/council/test_council_runs_without_a_judge.py holds the seam, and the list of judge contracts that cross it may not grow (llm-council.md) |
| C3 | Untrusted text | Text from a judge, an article or an exception would reach an event, the job summary, a commit message or a file path | Stop (Guardrail #11) |
| C4 | Write token | A judging cell would hold a write token | Stop |
| C5 | Model change | A row changes a model, the weights cache or the model-server action, or adds a dependency | Stop. Name its cost and who it serves (Guardrail #8); consult the runtime persona |
| C6 | Unearned publish | A row would publish output no unit completed, or re-run a judge to recover a failed push | Stop (docs/architecture/publishing/committing.md) |
| C7 | Exact repeat | A row would expect a judge's re-run to repeat a recorded output | Stop. Determinism is not an expectation (owner, 2026-10-11; docs/architecture/contracts/determinism.md) |

## 1. Status Reckoner

Table D - rows

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Judges carry a status and a model need | - | A | PENDING | - | - | - |
| 2 | Each council job holds only the permissions its steps use | - | A | PENDING | - | - | - |
| 3 | Council programs log one JSON event a line and exit with one vocabulary | 1 | B | PENDING | - | - | - |
| 4 | The council refuses a bad judge set before any unit runs | 1, 3 | C | PENDING | - | - | - |
| 5 | The collecting job writes the night's summary on its job page | 3 | C | PENDING | - | - | - |
| 6 | The collecting job checks out code and config and fetches only named inputs | 1 | B | PENDING | - | - | - |
| 7 | Each judge runs over its own outstanding dates | 1 | B | PENDING | - | - | - |
| 8 | A unit that raises files a failed council record | 3 | C | PENDING | - | - | - |
| 9 | The council's record is published for the console | 8 | D | PENDING | - | - | - |

## 2. Rows

### Row #1 - Judges carry a status and a model need

- **Scope:** each council.tenants entry becomes a judge's slug, its lifecycle_status (Table E3) and runs_model, none defaulted; every council step resolves, asks and runs only active judges; the planning step refuses by name an active judge whose ledger sits in a paused or retired family; the judging job starts the model server only on a cell whose judge runs a model; the content-similarity judge's entry is active and runs a model, so its nights do not change.
- **Level:** 3 (changes the council's config shape, the judges every council step reaches, and its workflow).
- **Files touched:**
  - backend/idhazh/contracts/knobs/council.py (JudgeLifecycleStatus; TenantEntry: slug, lifecycle_status and runs_model, none defaulted, unknown keys refused; tenants becomes an ordered tuple of entries, each slug once; running() names the active slugs in order)
  - config/idhazh.json (council.tenants: [{"slug": "content-similarity-judge", "lifecycle_status": "active", "runs_model": true}])
  - backend/utilities/council_matrix.py (cells and committed paths from running(); runs_model on each cell; an active judge whose committed ledger sits in a paused or retired family is refused, naming the judge, the ledger and the family; each registered judge and its status logged, never printed to the step output)
  - backend/idhazh/council/night_plan.py, backend/idhazh/council/session.py and backend/utilities/council_publish.py (resolve running(), never every entry)
  - backend/idhazh/council/registry.py and backend/idhazh/council/tenancy.py (docstrings: a hosted judge is an active one; a judge that runs no model declares runs_model false and pays no weights restore)
  - .github/workflows/llm-council.yml (the model-server step gains `if: matrix.runs_model`; the fan-out comment names five values on a cell)
  - backend/tests/council/test_council_matrix.py (one judge of each status: only the active one gets cells and staged paths, and each cell carries its runs_model; the family refusal; the empty room)
  - backend/tests/council/test_session.py, backend/tests/council/test_night_plan.py, backend/tests/council/test_council_runs_without_a_judge.py, backend/tests/council/_config.py and backend/tests/council/_tenants.py (prepare, settle, publication paths and nights_outstanding reach only active judges; a night whose only judge is paused runs every step and judges nothing; re-derive at dispatch)
  - backend/tests/workflows/test_llm_council_workflow.py (five values on a cell; the model-server step's condition)
  - backend/tests/contracts/test_app_config.py (an entry with a missing field, an unknown status or a repeated slug is refused by name; re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md (registration and status, Table E3, five values on a cell, the earlier deadline of a cell with no model server)
  - docs/architecture/contracts/ledger-registry.md (pausing a judge's family needs that judge paused first)
  - Every other reader of council.tenants or of a cell, from git grep -n -e "council.tenants" -e "tenants(" -e "matrix.shards" -e "model-server" -- .github backend config docs frontend at dispatch
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/, backend/tests/contracts/test_app_config.py and backend/tests/workflows/test_llm_council_workflow.py per docs/how-to/run-the-gates.md; CI - full suite. Observation, not a gate: the first scheduled night after merge, whose content-similarity cells still start the model server and file their rows.
- **Oracle:** over a written config registering one judge of each status, every council step - plan, fan-out, prepare, settle and publish - reaches exactly the active judge, and each of its cells carries its runs_model. Cannot settle: the registry's search still imports every judge package that sorts before the slug it resolves, so a paused judge must keep importing cleanly (E2.8).

Table E1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| E1.1 | Each council.tenants entry carries its judge's lifecycle_status and runs_model, with no default, so registration and status are one line and cannot disagree | Owner ruling pending (P1); ledger-registry.md (a family carries its status on its entry) |
| E1.2 | An entry stays for every status: a judge stops by its status, never by losing its entry, and a retired entry keeps its slug from reuse, so judge_id keeps one meaning in council-run-records | knobs_gardener.py (a retired declaration stays as the record) |
| E1.3 | Every council step resolves running() only; retyping tenants makes mypy name any step that still passes every entry | Fowler (architecture review, 2026-10-11) |
| E1.4 | A judge's status says whether the council runs it, and its family's status says whether rows are written; the planning step refuses by name an active judge whose committed ledger sits in a paused or retired family, and allows every other pairing | ledger-registry.md |
| E1.5 | A judge is registered paused in the change that lands its tenant module, and a named decision makes it active | ledger-registry.md (a switch ships safe until a named decision) |
| E1.6 | runs_model travels on the cell beside the judge's width; every cell keeps the council's one bound, preamble and reserve; the planning job still prints llama_cpp_build every night | llm-council.md |

Table E2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E2.1 | A council block in each judge's own file under config/judges/, as the gardener keeps one declaration file a task | Every council step would read a judge's file from disk before resolving it, the file would have two owners, and the judge plan's P6 would change; two fields fit on the list entry, as config/ledgers.json holds a family's status | A reader in every step, a new file for the content-similarity judge and a field in each judge's settings model | Owner ruling pending (P1) |
| E2.2 | Derive a judge's status from its ledger family's status | Two questions with two subjects: the content-similarity family also takes holdout-pairs marks a person writes, which must not stop when the judge pauses | No status field | ledger-registry.md |
| E2.3 | Require the two statuses to be equal | Refuses legal pairings, such as a paused judge whose family keeps its readers and other writers | One equality check | Fowler |
| E2.4 | An eighth Tenant protocol member | The status is needed before the council imports a judge; a protocol member is read after | One property per judge | backend/idhazh/council/registry.py |
| E2.5 | A default status or model need | A value nobody chose | One field fewer per entry | CLAUDE.md Guardrail #3 |
| E2.6 | Stop a judge by deleting its entry | Frees the slug, so a later judge could file under the same judge_id | None | E1.2 |
| E2.7 | One lifecycle enum shared by ledgers, gardener tasks and judges | The same three words mean written, run by the gardener and run by the council | One enum and three imports | ledger-registry.md |
| E2.8 | Make the registry's search import only active judges | Each entry would have to name its package: a config value choosing code to run | One field per entry | idhazh-gardener.md |
| E2.9 | A condition naming the judge in llm-council.yml | The workflow names no tenant | One line | llm-council.yml |
| E2.10 | A shorter preamble or bound for a cell with no model server | A second clock for a unit that runs for minutes; the earlier deadline is the safe direction | One cell value and one knob | llm-council.md |

Table E3 - judge lifecycle statuses (JudgeLifecycleStatus; declared once here)

| # | Value | What the council does | What keeps running |
| --- | --- | --- | --- |
| E3.1 | active | Resolves the judge, asks nights_outstanding, builds its cells, runs prepare, run_shard and settle, starts the model server where runs_model is true, and stages its committed paths | Its ledgers take rows while their family is active; the gardener packs and ages them; the console reads them |
| E3.2 | paused | Nothing: no resolve, no nights_outstanding, no cell, prepare, settle, model server, staged path or council record; nothing is deleted. Back at active, it is asked only about nights inside the repair window, so nights paused longer stay unjudged | Packing, ageing and console reads of its ledgers, other writers into its family, and the family's own status |
| E3.3 | retired | As paused, for good; its entry stays, and its tenant package may be deleted | As paused; its row contracts stay while its family keeps rows, because packing and reading need them |

### Row #2 - Each council job holds only the permissions its steps use

- **Scope:** the workflow-level permissions block moves to the jobs: the planning job reads contents, the judging cells read contents and actions, and only the collecting job writes contents, held by a workflow test.
- **Level:** 2.
- **Files touched:**
  - .github/workflows/llm-council.yml
  - backend/tests/workflows/test_llm_council_workflow.py
  - docs/architecture/publishing/llm-council.md
  - docs/reference/github-actions.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/workflows/test_llm_council_workflow.py; CI - full suite. Observation, not a gate: the next scheduled night commits as before.
- **Oracle:** the workflow test reads llm-council.yml and finds contents write on the collecting job and on no other job. Cannot settle: a step a future change adds that needs a scope its job lacks; it fails loudly on its first run.

Table F1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| F1.1 | Judge code that runs beside fetched article text holds no write token | Guardrail #11; idhazh-gardener.md (each job holds only the permissions its steps use) |

Table F2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F2.1 | Keep the workflow-level contents write | Every judging cell holds a token it never uses | None | Fowler |

### Row #3 - Council programs log one JSON event a line and exit with one vocabulary

- **Scope:** every council program logs one JSON event a line through a shared event writer, names an exception by its type and place and never by its text, installs the crash printer, and exits with one vocabulary of codes 0 to 3 where the worst code across judges and dates wins.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/event_lines.py (new; moved from backend/idhazh/gardener/event_log.py and backend/idhazh/gardener/workflow_commands.py in a separate structural commit first)
  - backend/idhazh/gardener/event_log.py and backend/idhazh/gardener/workflow_commands.py (import the moved code)
  - backend/idhazh/contracts/council_events.py (new: night planned, unit finished, night published)
  - backend/idhazh/council/event_log.py (new)
  - backend/idhazh/council/outcome.py (new: codes 0 to 3, one fixed sentence each, the worst-code rule)
  - backend/idhazh/council/session.py, backend/idhazh/council/night_plan.py and backend/idhazh/council/run_identity.py
  - backend/utilities/council_matrix.py and backend/utilities/council_publish.py (no exception text printed; the crash printer installed)
  - backend/tests/council/_imports.py
  - backend/tests/council/test_events.py (new)
  - The gardener's event tests (re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and the gardener's event tests; CI - full suite.
- **Oracle:** a test drives a night in which one judge raises: the log holds one JSON event a line, the raised exception appears by type and place and its text appears nowhere, and the night exits with the worst code its judges earned. Cannot settle: events a future verb forgets to emit; the summary in row #5 prints only what the events say.

Table G1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| G1.1 | The event writer moves to a shared module in its own structural commit, so the gardener and the council write one line format | Fowler; CLAUDE.md section 1a |
| G1.2 | Stale or lost publication stays red, exit 1: no council step redoes every judge's work to recover a push | Owner ruling pending (P7); docs/architecture/publishing/committing.md |

Table G2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G2.1 | A second event writer for the council | Two line formats a reader must parse | A copy of the gardener's module | Fowler |

### Row #4 - The council refuses a bad judge set before any unit runs

- **Scope:** the planning step imports every tenant module once and refuses with exit 2, by name, an entry no module declares, a module with no entry, a module whose entry is retired but still imported for work, two modules that declare one slug, and a module that raises on import.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/council/registry.py
  - backend/utilities/council_matrix.py
  - backend/tests/council/test_registry.py (re-derive at dispatch)
  - backend/tests/council/_tenants.py
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/; CI - full suite.
- **Oracle:** a written package set with each defect fails the planning step with exit 2 and names the slug or module; a clean set plans as before. Cannot settle: a judge whose import is slow but clean.

Table H1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| H1.1 | A tenant module imports heavy libraries (scipy, a model client) inside its functions, so the planning job never installs every judge's extras | Owner ruling pending (P8) |

Table H2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H2.1 | The planning job installs every judge's extras | A judge's dependency would slow and can break every night's plan | One install line and its minutes | Fowler |

### Row #5 - The collecting job writes the night's summary on its job page

- **Scope:** the collecting job appends one Markdown summary to its job page, built from the night's events alone, with one log group per judge and an error annotation for a failed unit.
- **Level:** 2.
- **Files touched:**
  - backend/idhazh/council/run_summary.py (new)
  - backend/utilities/council_publish.py
  - backend/tests/council/_imports.py
  - backend/tests/council/test_run_summary.py (new)
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/; CI - full suite.
- **Oracle:** a summary rendered from a fixture of events states, for each judge and date, how it ended, and holds only closed words, counts, dates and fixed sentences. Cannot settle: whether a person reads it.

Table I1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| I1.1 | The summary says nothing the events do not, so it cannot contradict the log | idhazh-gardener.md ("What a person reads on the job page") |

Table I2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I2.1 | A summary written by every judging cell | Up to twenty pages to open for one night | One summary step per cell | Fowler |

### Row #6 - The collecting job checks out code and config and fetches only named inputs

- **Scope:** the collecting job checks out code and config with a sparse, blob-less checkout and lazy fetching off, and fetches each active judge's publication_inputs by name.
- **Level:** 3.
- **Files touched:**
  - .github/workflows/llm-council.yml
  - backend/utilities/council_publish.py
  - backend/tests/workflows/test_llm_council_workflow.py
  - backend/tests/council/test_publication.py (re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and the workflow tests; CI - full suite. Observation, not a gate: the next scheduled night's collecting job, read for its checkout time and a committed result unchanged.
- **Oracle:** a test drives the collecting step over a sparse checkout and finds every judge's declared input fetched by name and nothing else read. Cannot settle: a judge that reads an undeclared input; council_publish.py already refuses one by name.

Table J1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| J1.1 | Judging cells stay full checkouts until a run log shows the checkout's cost (B4) | Owner ruling pending (P4) |

Table J2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J2.1 | Sparse judging cells now | Each judge would first need an input declaration, and the time saved is not measured | A per-judge input declaration and the byte columns (Level 5) | Fowler, applying the runtime persona's rule: measure only when the answer changes a decision |

### Row #7 - Each judge runs over its own outstanding dates

- **Scope:** the night plan names tonight plus each judge's own outstanding dates, cells, prepare and settle follow each judge's own list, and a dispatched date may name one judge.
- **Level:** 3 (changes which dates the live content-similarity judge runs).
- **Files touched:**
  - backend/idhazh/council/night_plan.py
  - backend/utilities/council_matrix.py
  - backend/idhazh/council/session.py
  - backend/utilities/council_publish.py
  - The council-prepare verb (re-derive at dispatch)
  - backend/idhazh/council/tenancy.py
  - .github/workflows/llm-council.yml (a dispatch input naming one judge)
  - The night plan, matrix, session and workflow tests (re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and the workflow tests; CI - full suite.
- **Oracle:** with two active judges where only one names an older date, that date fans out cells for that judge alone, and tonight fans out for both. Cannot settle: a judge whose own window misses a night the repair cap drops.

Table K1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| K1.1 | Each judge's own window decides what it takes, as each gardener task's does; a date one judge names no longer runs every judge at model cost | Owner ruling pending (P2); idhazh-gardener.md |

Table K2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K2.1 | Keep the union of every judge's dates | A date only one judge names makes every other judge re-judge it at model cost | None | Fowler |

### Row #8 - A unit that raises files a failed council record

- **Scope:** the council files outcome failed with fault raised in its finally when a unit raises, extending the council's record without breaking rows already written.
- **Level:** 5 (a persisted contract changes). ESCALATE C1 fires: the owner rules on P5 before work starts.
- **Files touched:**
  - backend/idhazh/contracts/council_run_record.py (ShardOutcome gains failed, a fault field; version and changelog entry)
  - backend/idhazh/council/session.py
  - The contract fixture and backend/tests/contracts/_fixtures.py
  - backend/tests/council/test_session.py
  - docs/architecture/contracts/state-ledgers.md
  - docs/architecture/publishing/llm-council.md
  - Every reader of ShardOutcome (re-derive at dispatch)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/contracts/ and backend/tests/council/; CI - full suite.
- **Oracle:** a unit that raises files one row with outcome failed and fault raised, and a row written before the change still reads. Cannot settle: a unit the platform kills, which files nothing, as today.

Table L1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| L1.1 | A code defect and a platform kill need different fixes, so the record tells them apart | Owner ruling pending (P5) |

Table L2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L2.1 | Keep a raising unit silent in the record | A defect reads like a kill | None | Fowler |

### Row #9 - The council's record is published for the console

- **Scope:** council-run-records joins ledger.published, so the console's Data explorer can query its compact files.
- **Level:** 3.
- **Files touched:**
  - config/idhazh.json (ledger.published gains council-run-records)
  - The frontend vocabulary and field-set tests (re-derive at dispatch)
  - docs/concepts/growing-reads.md
  - docs/architecture/publishing/llm-council.md
- **Acceptance gates:** local - the contract tests through the shared selector; CI - full suite.
- **Oracle:** the site build copies the record's indexes and compact files, and the Data explorer lists the ledger. Cannot settle: whether a person reads it.

Table M1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| M1.1 | Every cell of the record is a closed word, a count or an instant, so publishing it shows no fetched text | Owner ruling pending (P6) |

Table M2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M2.1 | Keep the record off the site | The console cannot show how a judging night went | None | Fowler |

## 3. Owner rulings

Table P - rulings pending before the rows that cite them run

| # | Question | Proposed answer | Evidence | Rows held |
| --- | --- | --- | --- | --- |
| P1 | Where a judge's status and model need live: on its council.tenants entry, or in a council block of its own file under config/judges/ (the gardener's one file a task) | On the entry | Two fields fit on the list entry, as config/ledgers.json holds a family's status; every council step already holds the council's config, so it needs no extra disk read; a judge's own file stays read only by the judge (judge plan P6) | 1 |
| P2 | Each judge runs over its own outstanding dates now, folding in the judge plan's deferred P10 | Approve | Today a date one judge names runs every judge at model cost; the gardener lets each task's own window decide; the row stays off the judge's switch path | 7 |
| P3 | No rehearsal (dry-run) status for judges (B1) | Approve | A council night deletes nothing, and a new judge lands paused (E1.5), which is the gardener's safe default in the council's terms | - |
| P4 | Sparse judging cells and a download budget wait for a run log (B4) | Approve | Each judge first needs an input declaration; the time saved is not measured | 6 |
| P5 | A unit that raises files a failed council record (a persisted shape) | Approve | A code defect and a platform kill need different fixes, and the record cannot tell them apart today | 8 |
| P6 | Publish council-run-records for the console | Approve | The gardener's own record is published; every cell is a closed word, a count or an instant | 9 |
| P7 | Stale or lost publication stays red, exit 1 | Approve | No council step redoes every judge's work to recover a push (committing.md) | 3 |
| P8 | Tenant modules import heavy libraries inside their functions | Approve | The planning job then never installs every judge's extras | 4 |

Table S - the gap review this plan rests on (Fowler, 2026-10-11)

| # | Gardener property | Council today | This plan |
| --- | --- | --- | --- |
| S1 | One declaration per unit, closed words, a named list | council.tenants holds slugs only | Adapted: status and model need on each entry (row #1) |
| S2 | lifecycle_status | None: a registered judge always runs | Adopted (row #1) |
| S3 | dry_run; every default reports and deletes nothing | tenants defaults to empty | Adapted: a new judge lands paused (E1.5); no rehearsal status (B1) |
| S4 | A standard-library plan job before install | The planning job needs installed judge code | Skipped (B2) |
| S5 | Binding by name and kind; refusals before work | A sorted search; an unknown slug refused | Adapted: refusals kept, binding by search kept (row #4, B3) |
| S6 | Sparse checkout and a download budget | Full checkouts; council_publish.py already fetches declared inputs when sparse | Adapted: the collecting job now (row #6), judging cells later (B4) |
| S7 | Ownership: owns, appends_to | Already matches: committed_paths, venue ledgers declared, broad state roots refused | Kept |
| S8 | Exit codes and the worst-code rule | Ad hoc codes | Adopted (row #3) |
| S9 | One record per shard | One row per unit in a finally; a raising unit files nothing | Adapted (row #8) |
| S10 | One-line JSON events; no exception text; the crash printer | Plain lines; council_publish.py prints an exception's text | Adopted (row #3) |
| S11 | Job-page summary | None | Adopted (row #5) |
| S12 | Landing through the shared publisher | Already matches | Kept |
| S13 | Least-privilege permissions | contents write on every job | Adopted (row #2) |
| S14 | Each unit's own window | A date any judge names runs every judge | Adopted (row #7) |
| S15 | The record is published | Not published | Adopted (row #9) |
| S16 | (council only) the model server, the 6 h job, matrix width, nights_outstanding, the judge seam | - | Kept as the council's own |
