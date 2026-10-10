# Known defects

**Last Updated**: 2026-10-10

**Thirty-nine defects are open.** Five of them need evidence or a ruling before any code
is worth writing; the rest are known fixes
with named blast radiuses.
Defect 2 needed three repairs before a person could label anything, and all three
shipped. The owner settled the counting rule on 2026-08-27, which took the
draw from 32 of 60 to 60 of 60. What is left is **60 human labels** and eight
more run-days at one scorer, and neither is code. Defect 18 is the opposite
shape: the code now works and the measurement it produces still cannot fire, so
what it needs is a ruling on which instrument to keep. Defects 23 and 24 were
filed on 2026-09-21 by the plan that rebuilt the Hardware route; each is a known
fix with a named blast radius rather than an open question. Defect 36 was filed on
2026-09-27 by the row that closed defect 33: the band above every console route
reads the same machine ledger raw, and calls every run written in two halves
unreadable. Defect 37 came from the same row's browser check: in the dark theme
two of the chart colours look the same, and that row put them side by side.
Defects 38 to 47 were filed on 2026-09-28 from what plan 51's rows found outside
their own files. 38 and 39 closed on 2026-09-30, when plan 51's row 8 made a
machine's colour its speed and the counters reader kept each shard's
fingerprint; each of the other eight names the change or the plan row that
fixes it. Defect 48 was filed the same day, while plan 51's row 5 merged: GitHub stamps
its squash merges in local time, and one account setting is the first thing to
try. Defects 49 to 52 were filed on 2026-09-30, when plan 50 closed, from what
its workers found outside their own rows. Defect 50 was already fixed that day;
defect 51 needed evidence, because one abort is not enough to find its cause,
until a second abort reproduced it on 2026-10-08. Defects 53 and 54 were filed
on 2026-09-30 as well, from two findings plan
50's rows wrote down and never filed, and 54 has a date: the first squash that
rewrites history is due on 2026-10-29. Defect 55 was filed on 2026-10-04 from
Fowler's review of plan 60: a page names a test that two pull requests deleted.
Defects 56 to 58 were filed the same day: three tests that each failed once in
the checks of plan 60's row 7 and passed when run again. The runs' own records
settle 56, and show that 57 was a page that stopped drawing, not a slow runner;
57 needed evidence too, because one stall is not enough to find its cause,
until a second stall came in main's own checks on 2026-10-08. Defect 59 was
filed on 2026-10-05 by plan 60's row 10: reading named
days of a ledger that the ledger door files lists every raw day folder the ledger
holds. Defect 60 was filed on 2026-10-07 by plan 62's row L10: on open, the data
explorer fetches each chosen ledger's three indexes twice. Defects 61 and 62
were filed the same day from plan 62's rows L7 and L20: three backend command
lines stamp log records in local time, and in a worktree with no `.venv` the
test launcher hands its inner run a Python it then refuses. Defect 63 was
filed the same day by plan 62's text update after row L7: the plan status
utility's docstring shows a usage that does not work and a no-install claim
that is not true. Defects 64 and 65 were filed the same day by the plan text
update after plan 60's row 21: the canary's telemetry step refuses a
repository path spelled with a short name, which plan 62's row L25 met, and a
retention task run over a person's range that finds nothing ends `not-due`,
which plan 60's row 21 found. Defect 66 was filed on 2026-10-08 by a plan text
update (#1437): the plan status utility splits a quoted row title wherever
"and" appears in it. Defect 67 was filed the same day from the checks of plan
62's row L37 (#1431): a browser test that failed once and passed when run
again. It is the third that needs evidence, because one failure is not enough
to find its cause. Defect 68 was filed the same day from plan 62's row L40
(#1448): the merge line's hold has no floor on its pair count. Whether one
pair may hold a run is Andre's to rule, so it is the fourth that needs
evidence or a ruling. Defect 60 closed the same day: #1435 made the data
explorer read each index once before a run.
**This file cannot
be deleted by writing more of it.**

Defects 15, 16 and 17 closed on 2026-08-27. Defects 19 and 20 were filed later,
on 2026-09-12, by two rows that found them and declined to widen into them. Both
closed on 2026-09-13. Defect 20 got its ruling and the ruling moved the fix: the
fingerprint was right and the producer was wrong. Defect 21 came from plan 24,
which ruled it a row on 2026-09-12 and never cut one; it closed on 2026-09-13.
Defect 22 was reported from the published days on 2026-09-14 and closed the same
day; like defect 20, the symptom pointed at a number and the fault was upstream
of it.

Closed rows are removed after checking their current production code, regression
tests and canonical docs. Git history holds their execution record; the living
docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Guardrail #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - queue repaired, counting rule settled; 0 of 60 labels; 2 of 10 run-days** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 3 | CLOSED 2026-08-27 (PR #180) |
| 16 | The truncation-gap detector has never been fed, and the run pays twice for the answer | 5 | CLOSED 2026-08-27 |
| 17 | Two different word counters share one string and read as truncation | 5 | CLOSED 2026-08-27 |
| 18 | The truncation flag still cannot fire, now for a different reason | 5 | **OPEN - not measurable without the scorer weights** |
| 19 | A summarize call that failed on its reply reports no cost at all | 2 | CLOSED 2026-09-13 (PR #657) |
| 20 | The `publishing` group dirties a file the build fingerprint hashes, so it can never certify its own build | 2 | CLOSED 2026-09-13 (PR #660) |
| 21 | A test walked every published telemetry shard, and it was the only thing reading them back | 2 | CLOSED 2026-09-13 |
| 22 | The same story publishes several times in one day, and each copy says only one source carried it | 3 | CLOSED 2026-09-14 |
| 23 | The canary day records no settings, so nothing renders the rules that say a setting moved | 2 | **OPEN - the pure module is tested; the page is not** |
| 24 | `failed_field` costs a cell on every row and answers nobody | 5 | **OPEN - draw it or migrate it out** |
| 25 | `host_model` is a column nothing fills, and two rulings disagree about whether it should | 5 | CLOSED 2026-10-04 - the council record rationale ([llm-council.md](../docs/architecture/publishing/llm-council.md#the-venue-files-the-row-not-the-tenant)) keeps machine details out of each row |
| 26 | The settlement-key check reads one constant twice, so it cannot see a key lose a cell | 2 | **OPEN - every keyed ledger is exposed** |
| 27 | The decode stamp excludes the grammar but not the schema | 3 | **OPEN - changing it moves every summariser digest** |
| 28 | The one-at-a-time guard tells the operator the wrong verb | 1 | **OPEN - about four lines across three call sites** |
| 29 | A shard is called a `unit` in the council's workflow and its tests | 1 | **OPEN - one borrowed word replaced by another** |
| 30 | A third spelling of the vector norm lives in the canary builder | 1 | **OPEN - the one it duplicates is now public** |
| 31 | The council's selection artifact is named for one date and carries several | 1 | **OPEN - cosmetic today, wrong the day somebody reads the name** |
| 32 | The console reads the score ledger raw, so the newest day counts twice | 2 | CLOSED 2026-09-23 |
| 33 | The console reads the machine ledger raw, so every job counts twice and one copy has no machine | 3 | CLOSED 2026-09-27 |
| 34 | `donut_thickness_px` is a knob nothing reads | 1 | CLOSED 2026-09-27 |
| 35 | The chart loading flag flips at import, so the waiting sentence goes while the box is still empty | 2 | CLOSED 2026-09-27 |
| 36 | The band above every console route calls every run written in two halves unreadable | 2 | **OPEN - merge or settle is the one ruling it needs** |
| 37 | Two colours of the dark chart ramp look the same, so two machines read as one | 2 | **OPEN - one colour to pick, then every pair measured again** |
| 38 | The machine colours go to the first machines by an arbitrary key, not to the most-placed ones | 2 | CLOSED 2026-09-30 |
| 39 | The run-counter records name no machine, so the Hardware route counts 10 machines where there are 8 | 3 | CLOSED 2026-09-30 |
| 40 | The canary never writes a job in two halves, so no built page tests the merge | 2 | **OPEN - the canary builder writes one job in two halves** |
| 41 | Span sentences print "in these 1 days" at the one-day window | 1 | **OPEN - one rule for a count and its noun** |
| 42 | The processor-share tiles print "under 1%" past their own bottom edge | 1 | **OPEN - one panel's tiles** |
| 43 | A section that follows the days control changes height and moves the page under the reader | 2 | **OPEN - one layout rule, not a fix per panel** |
| 44 | One hatch means two things on the console: no reading, and time counted twice | 2 | **OPEN - the no-reading half is done; a plan 52 row takes the run timeline's** |
| 45 | A change to `Panel.svelte` does not buy the console tests on a pull request | 2 | **OPEN - one pattern in the selector and a truth-table case** |
| 46 | `DateSeries` cannot draw the settings-change rule that gate 6 asks of every trend | 2 | **OPEN - plan 52's row 26, before a date series is judged** |
| 47 | The Pipelines route draws no panel ids, so the pictures and gates reach 15 panels, not 26 | 2 | **OPEN - a plan 52 route row gives each section an id** |
| 48 | GitHub stamps its squash merges in local time, `+02:00`, not UTC | 1 | **OPEN - one account setting to try, then one merge to read** |
| 49 | The local test selector sends a backend test helper to every frontend group | 2 | **OPEN - two patterns in the selector and their truth-table cases** |
| 50 | A publisher link on the home page named a story the page did not draw, so a news run's site build failed | 2 | CLOSED 2026-09-30 (PR #1168) |
| 51 | The canary builder's score-key step aborted once at exit, after printing its whole answer | 2 | **OPEN - reproduced twice; a row to fix it is now due** |
| 52 | Reading one month of a packed ledger downloads every month file of its year | 3 | **OPEN - costs nothing until a compaction runs live** |
| 53 | The `traces` upkeep task cannot date eight old trace files, so it never deletes them | 2 | **OPEN - matters from the day the task deletes live** |
| 54 | The first squash that rewrites history may not fit in its 30-minute job | 2 | **OPEN - due 2026-10-29: raise the limit, or time one replay first** |
| 55 | The query-door page names a deleted test, so nothing may hold the rule it states | 2 | **OPEN - find the test that holds the rule, or restore one over named config** |
| 56 | A byte-range test counts a correct 304 as a failure | 1 | FIXED 2026-10-06 (PR #1354) |
| 57 | A day page stopped drawing during a browser test, and the test waited three minutes for it | 2 | **OPEN - two stalls seen in CI; a row to fix it is now due** |
| 58 | A ledger test expects an order for two runs written in the same millisecond | 1 | CLOSED 2026-10-09 (plan 60 row 44) |
| 59 | Reading named days of a door ledger lists every raw day folder the ledger holds | 2 | **OPEN - one function; costs little until a ledger packed report-only grows** |
| 60 | On open, the data explorer fetches each chosen ledger's three indexes twice | 1 | CLOSED 2026-10-08 (PR #1435) |
| 61 | Three backend command lines stamp log records in local time | 1 | FIXED 2026-10-10 (plan 60 row 46) |
| 62 | In a worktree with no `.venv`, the test launcher hands its inner run a Python it then refuses | 1 | **OPEN - hand the inner run a full path; until then, set `IDHAZH_PYTHON`** |
| 63 | The plan status utility does not do what its docstring says | 1 | **OPEN - fix the docstring's example and its no-install claim, or make both true** |
| 64 | The canary's telemetry step refuses a repository path spelled with a short name | 1 | **OPEN - resolve the path before `relative_to`; until then, name the copy by the long form of `TEMP`** |
| 65 | A retention task run over a person's range that finds nothing ends not-due | 1 | CLOSED 2026-10-10 (PR #1524) |
| 66 | The plan status utility splits a quoted row title wherever "and" appears in it | 1 | **OPEN - stop splitting a Depends-on cell inside a quoted title** |
| 67 | A browser test of a summary with a paragraph break failed once, and passed when run again | 2 | **OPEN - one failure seen; make it come back before changing code** |
| 68 | The merge line's hold has no floor on its pair count, so one pair can hold a run | 2 | **OPEN - reasoned, not measured; whether one pair may hold a run is Andre's to rule** |
| 69 | A re-run of a day that predates fragments may record a line it did not use | 5 | **OPEN - reasoned, not measured; measure the preserved day and its run record before any contract decision** |
| 70 | The raw-listing test does not check the value included in the built site | 2 | **OPEN - check the real build on generated data against written-out days** |

## 70 - The raw-listing test does not check the value included in the built site (OPEN)

**The test's title promises a build check, but its assertions read only staged
files.** In `frontend/tests/published-ledgers.spec.ts`, the test
`raw-day listings are complete, bounded and become the baked listed-through value`
calls `rawListedThrough(STATIC)` and compares it with days found by reading the
staged listings again. It does not read `__RAW_LISTED_THROUGH__` from the built
page. The production binding in `frontend/vite.config.ts` instead calls
`rawListedThrough()` with no argument.

**The production path is fixed; the integration check is still missing.**
PR #1427 made the default path relative to the script and added generated-tree
tests of that default. Those tests do not prove that the build passes the
result to the page. A future edit that supplies another folder or an empty
object in `vite.config.ts` can leave the published-listing test green while
the page reads no raw day. This is a test gap, not evidence of a current
incorrect build. Confirmed by reading the named test, script and build binding;
no application test was rerun for this documentation change.

**The receiving work is one bounded integration check.** Build a generated
state root with two selected ledgers and two named raw days per ledger. Assert
written-out newest days from the value the real build supplies to the browser,
not from another listing read. Include a raw-day query with written-out rows.
Keep the existing default-path unit cases. No test reads the committed archive
or reaches the network.

**Acceptance:** the generated case passes with the production binding and
fails when that binding supplies `{}` or the wrong staged folder. It must
exercise the actual built page, including its raw-day selection. Do not merely
rename the existing test or compare two readers of the same files.

This receives the unfinished test finding from PR #1427, reported in plan 62
row L46 and deferred by its Table B, B7. The finding is preserved here before
that completed plan is deleted; it is not claimed fixed.

## 69 - A re-run of a day that predates fragments may record a line it did not use (OPEN)

**`stage_assemble` keeps the published day unchanged when its previous
`digest.json` predates run fragments, but still writes the selected floor to
the new `run.json`.** The branch is in
`backend/idhazh/stages/assemble.py`: it assigns `day = previous_day` and skips
`assemble_day`, then builds the new manifest with
`same_story_floor_applied=same_story.floor_min`. The field description in
`backend/idhazh/contracts/run_manifest.py` says it is the line the run grouped
the day at. Reasoned from the code, not measured. No such day is the newest
published day.

**The smallest measurement is one generated two-run case.** First build a day
with a known `same_story_floor_applied` value and its matching digest. Then
make the next run take the `predates_fragments` branch with the adaptive switch
enabled and a different selected line. Compare the digest before and after,
then compare the new run record's `same_story_floor_applied` with the value
that built the preserved digest. This establishes whether the new persisted
record names a line the day did not use.

**The possible consequence is persisted meaning, not a missing field.** If the
measurement confirms the mismatch, the existing `RunRecord` value would say
that a preserved day was grouped at a floor it never used. Any correction to
that persisted meaning must stop at Table C, C1 for contract review; this entry
does not choose a fix, change backend code or change a shape.

Found in plan 62's row L52 follow-up 4, while recording #1469's findings, and
filed on 2026-10-09.

## 68 - The merge line's hold has no floor on its pair count, so one pair can hold a run (OPEN)

**A day on which the judge read one pair, and its two readings disagreed, can
hold the merge line where it was.** `set_merge_line.py`
(`backend/idhazh/stages/set_merge_line.py`) works out the day's two rates over
however many pairs it read: "disagreed" over the pairs read twice, and "could
not tell" over the pairs whose two readings agreed. It hands both to `gates` in
`backend/idhazh/similarity/fit.py`, which holds the run, as `JUDGE_UNSTABLE` or
`JUDGE_UNCERTAIN`, when a rate passes its mark, `disagreement_max` or
`unclear_max`. No floor counts the pairs behind the rate. The console prints no
share for fewer than `console.min_attempts_for_rate` pairs
(`config/appearance.json`), so the run can hold the line on a share the console
calls too few to report. Reasoned from the code, not measured: once the record
is large enough to pass the gate on its size, which `gates` checks first, one
disagreeing pair on a day is enough.

**The console now shows such a day as held, with its counts.** Since #1448
(plan 62's row L40), the Judgement page's agreement chart draws no dot for a
rate under that floor, and its strip prints the day's counts, while the merge
line above it marks the day held.

**Doing nothing costs a line that stays where it was on a day whose evidence
is one pair, once the merge switch is on.** While
`assemble.same_story.adaptive_dedup_threshold.enabled` in `config/idhazh.json`
is `false`, every build groups at the committed floor, whatever the fit holds.

**The next move is a ruling, not code: whether one pair should hold a run is a
question for whoever owns the merge line's fit, Andre's area (CLAUDE.md section
14).** If Andre rules a floor, the fix is in `gates` or in what
`set_merge_line.py` hands it, with a test on pairs the test builds. Level 2 -
the rule that holds the line, which the fitted rows record and the Judgement
page draws.

Found by plan 62's row L40 (#1448), its third follow-up, and filed on
2026-10-08.

## 67 - A browser test of a summary with a paragraph break failed once, and passed when run again (OPEN)

**One browser test found no story drawn as two paragraphs, once.** "A summary
with a paragraph break is drawn as two paragraphs"
(`frontend/tests/item-card.spec.ts`, line 318), in the `reader` project,
failed in CI run 37779056528, attempt 1, at 12:49 UTC on 2026-10-08, in the
checks of #1431 (browser job 113317369182). The page drew stories, so the
check at line 334 passed, but none of them drew more than one paragraph, so
the check at line 336, "the canary story with a break drew one paragraph",
found none where the canary gives exactly one. A re-run of the job, attempt 2
(job 113323035071), passed. #1431 changed the cost of one article on Hardware
(`frontend/src/lib/console/machine/article-cost.ts`), two console specs, one
docs page and plan 62. It did not touch that spec, or
`frontend/src/lib/components/DigestItem.svelte`, which draws each paragraph of
a summary.

**Doing nothing costs a red browser job each time it comes back, and a
re-run.** How often that is, nobody knows: it has been seen once. The run's
trace is in its `playwright-traces` artifact, which expires on 2026-10-15.

**The next move is a worker's: make the failure come back where it can be
watched.** Run this one test in the `reader` project a few hundred times with
Playwright's `--repeat-each` on a canary build, and read the trace of a run
that fails: it shows whether the story with a break had not been drawn yet,
or was drawn as one paragraph. The spec's `open` waits for the page to load
and for its theme, not for every story, so check the first case first. A
raised timeout or a retry would hide the cause, not explain it (CLAUDE.md
Guardrail #5). Level 2 - the fix may be in `DigestItem.svelte`, which every
reader sees, rather than in the test.

Found in the checks of plan 62's row L37 (#1431), and filed on 2026-10-08.

## 66 - The plan status utility splits a quoted row title wherever "and" appears in it (OPEN)

**A Depends-on cell that quotes another row's title loses a piece of that
title to the parser, whenever the title itself contains the word "and".**
`backend/utilities/plan_status.py`, line 343, reads a Depends-on cell with
`for piece in re.split(r",|;| and ", text):`, which splits on the literal
substring " and " anywhere in the cell, including inside a quoted title. Plan
62's row L48 depends on plan 55's row "The reader chooses the chart and the
columns it draws"; the parser splits that title at its own " and ", so it
looks for a row named `plan 55's row "The reader chooses the chart` and a row
named `the columns it draws" (holds ...)`, finds neither, and reports two
false `dependency-not-found` findings for L48 (seen on a direct run against
`origin/main`, and carried by #1432).

**The next move is a worker's: stop splitting inside a quoted title**, such as
by matching a quoted span first and splitting only the text outside it, or by
reading the Depends-on cell's row references with a dedicated small parser
instead of a blanket `re.split`. Level 1 - one regular expression in one
function; a wrong version shows as a spurious finding against a row whose
dependency is in fact present, which a reader can confirm from the cell
itself.

Found on 2026-10-08, confirmed on `origin/main` by a direct run of
`plan_status.py --plan` against plan 62.

## 65 - A retention task run over a person's range that finds nothing ends not-due (CLOSED 2026-10-10, PR #1524)

**A retention task that a person runs with `--from` and `--to`, and that finds
nothing, used to end `not-due` instead of `outside-range`.** `TaskContext` now
keeps `operator_range`, which holds only the range a person named, separate
from `period_range`, the effective range the task reads. The shared retention
helper ends an empty named pass as `outside-range` and an empty scheduled pass
as `not-due`. Compaction reads `operator_range`, and `task-planned` reports it
only when a person supplied one. Plan 60 row 45 fixes the defect.

**Doing nothing costs a person who named a range the wrong advice about it.**
`task-finished` says "nothing has reached its line yet", the sentence for a
scheduled wake. The one that helps is the sentence for `outside-range`:
"nothing that may be taken is inside the range named; widen it, or run the
task without one". The code now selects the existing sentence that matches the
run.

**Resolved:** the task context keeps a person's range apart from the effective
read window, and the shared retention helper chooses the matching idle outcome.
The persisted words and report text did not change.

Found by plan 60's row 21 (#1387), and filed on 2026-10-07.

## 64 - The canary's telemetry step refuses a repository path spelled with a short name (OPEN)

**Where `TEMP` is a short 8.3 name, with a `~1` in it, a canary build in a copy
under it stops in its telemetry step with `ValueError: ... is not in the
subpath of ...`.** `main()` in
`backend/idhazh/telemetry/publish/public_telemetry.py` prints each shard it
writes as `path.relative_to(config.REPO_ROOT)` (lines 237 and 248).
`config.REPO_ROOT` is resolved (`backend/idhazh/config.py` line 61), so it
spells the long name. The shard's path comes from `--public`, which
`frontend/scripts/build-canary.mjs` passes as it spelled the copy's path, and
`main()` does not resolve it, so the two spellings of one folder do not
compare. Plan 62's row L25 met it on 2026-10-07 (Windows, Python 3.14.2).

**Doing nothing costs a canary build in any copy named by a short `TEMP`,
after the build's earlier steps have run.**
[run-the-gates.md](../docs/how-to/run-the-gates.md#run-a-new-test-against-the-base-commit)
now names the base-commit copy by the long form of `TEMP` (row L25, #1384),
which steers around it; a copy named any other way still stops.

**The next move is a worker's: resolve the path before `relative_to`, in both
places `main()` prints one.** Level 1 - two lines of one command's output; a
wrong version stops the first canary build that meets a short name.

Found by plan 62's row L25 (#1384), and filed on 2026-10-07.

## 63 - The plan status utility does not do what its docstring says (OPEN)

**`backend/utilities/plan_status.py`'s docstring does not match the command it
describes.** Its own usage line reads `python backend/utilities/plan_status.py
--plan 23    # one plan`, but `--plan` is `action="append", required=True,
help="Named plan path. Repeatable."`: it takes a path, such as
`TODO/20261004-60-gardener-recovers-on-its-own-plan.md`, not a bare plan
number, so the docstring's own example fails before it reads a line. The same
docstring says the utility "imports nothing from idhazh and reads no
configuration, so it runs from a fresh clone with any supported Python and no
install," but `read_plans()` does `from utilities.named_inputs import
named_files`, an import that only resolves once the project is installed; run
that same example with a Python that has not installed the project, and the
command stops with `ModuleNotFoundError: No module named 'utilities'`. Plan
62's text update confirmed both after row L7, on 2026-10-07.

**Doing nothing costs a worker who copies the docstring's own example into a
terminal: the bare number is refused, and on a fresh clone with no install the
same line fails at its first import, though the docstring promises neither
failure.**

**The next move is a worker's: correct the docstring's example to a real plan
path, and either make the no-install claim true by moving the import inside
the project, or drop the claim and say what install the command needs.**
Level 1 - a docstring and, if the owner keeps the no-install claim, one
import; a wrong version is obvious on the next run.

Found by plan 62's text update after row L7, and filed on 2026-10-07.

## 62 - In a worktree with no `.venv`, the test launcher hands its inner run a Python it then refuses (OPEN)

**In a worktree with no `.venv`, `npm run test:changed` stops with "The
selected Python executable does not exist." whenever it selects a test
group.** `pythonPath` in `frontend/scripts/run-checks.ts` finds no `.venv` and
falls back to the bare name `python`, or `python3` off Windows (line 182). The
launcher starts its test lock with that name, which the system finds on the
`PATH`, and hands the same name to the run inside the lock as `IDHAZH_PYTHON`
(line 220). That run calls `pythonPath` again, which requires `IDHAZH_PYTHON`
to name a file that exists (lines 174 to 176), and a bare name does not. So the
fallback can never work. Plan 62's row L20 met it on 2026-10-07.

**Doing nothing costs a stopped check in every worktree without a `.venv`, and
the time to find out why.** The workaround is to set `IDHAZH_PYTHON` to the
full path of a Python, or to set up `.venv` first, as
[run-the-gates.md](../docs/how-to/run-the-gates.md#set-up-the-backend-environment)
says. [gates-and-builds.md](../docs/reference/agent-notes/gates-and-builds.md)
carries the symptom and the workaround where an agent looks for them.

**The next move is a worker's: hand the inner run a full path.** One way is for
the fallback to ask that Python for its own path, `sys.executable`, before it
hands the path on. Level 1 - one function of the test launcher, and a wrong
version stops the first check that uses it.

Found by plan 62's row L20 (#1371), and filed on 2026-10-07.

## 61 - Three backend command lines stamp log records in local time (OPEN)

**Three backend command lines stamp each log record with the machine's local
time, not UTC** (CLAUDE.md section 2). `backend/idhazh/cli.py` line 541,
`backend/idhazh/gardener/cli.py` line 87 and `backend/idhazh/telemetry/cli.py`
line 135 set the format `%(asctime)s %(levelname)s %(name)s %(message)s` and
keep the clock `logging` uses by default, which is local time. The stamp names
no zone, so nothing on the line says which clock it read. Plan 62's row L7 saw
it on 2026-10-07: `site-weight` printed 11:46 when it was 09:46 UTC.

**The three do not share one logging setup.** Each command line calls
`logging.basicConfig` on its own (lines 539, 85 and 133), with the same three
arguments.

**Doing nothing puts every log time off by its machine's distance from UTC:
two hours on the machine where row L7 saw it.** A GitHub runner's local time is
UTC, so a workflow's log is right, and the fault shows only on a machine set to
another zone, such as a developer's.

**The gardener's part is fixed by plan 60's row "Every gardener log line is one
JSON event".** `idhazh gardener` and `backend/utilities/gardener_publish.py`
install one handler through `settings_or_none`, and each line it writes carries
`at`, the record's own instant in UTC as ISO-8601 with `Z`.
`backend/tests/gardener/test_event_log.py` pins it under a zone that is not UTC,
in the test process and in a fresh one. The other two command lines,
`backend/idhazh/cli.py` and `backend/idhazh/telemetry/cli.py`, still stamp
local time and need a fix of their own: the records they log carry a UTC time
and say so, with a test that reads one. Level 1 - the time printed on each log
line, and a wrong version shows on the first line.

Found by plan 62's row L7 (#1370), and filed on 2026-10-07.

## 60 - On open, the data explorer fetches each chosen ledger's three indexes twice (CLOSED 2026-10-08)

**When the data explorer opens, it fetches each chosen ledger's three indexes
twice.** Plan 62's row L10 saw it on 2026-10-07, on the live site and on a
local build, both before and after its own change (#1360). An index is fetched
with `cache: 'no-store'` (`frontend/src/lib/data/fetched-bytes.ts`), so the
second read is a request of its own, not a copy the browser kept. The likely
cause, an estimate from reading the page and not measured, is two callers that
each read the indexes: `updateCostAndColumns` in
`frontend/src/routes/console/data-explorer/+page.svelte` asks for the window's
cost (`askCost`), then for each ledger's columns, through `askColumns` since
#1360 and through a `DESCRIBE` sent to `ask` before it.

**Doing nothing costs three extra small requests for each chosen ledger, every
time the page opens.** What the page shows is not wrong.

**Closed on 2026-10-08 by #1435**, plan 55's row "The page reads each index once
before a run, and the ledger list raises no accessibility warning". The cause
was not the two callers guessed above: the page keeper
(`frontend/src/lib/data/page-keeper.ts`) keeps each index's read, so
`askCost` and `askColumns` share one. Opened from a link or a kept run, the
page started a cost pass for the restored selection, and `refreshRegistry()`
then called `startAfresh()`, which dropped every index the page had read, so
the next pass read them all again. On `origin/main` at 62da7be9a,
`refreshRegistry` drops the page's reads only when the reader presses Refresh,
and the test "opened from a link, the page reads each index and listing once
before a run" in `frontend/tests/console-data-explorer.spec.ts` checks, on a
ledger it builds, that no `.json` file under `state/` is read twice before Run.
Level 1.

Found by plan 62's row L10 (#1360), and filed on 2026-10-07.

## 59 - Reading named days of a door ledger lists every raw day folder the ledger holds (OPEN)

**`ledger.load_days` lists every raw day folder its ledger holds, then keeps the
days it was handed.** It finds raw files with `raw_files.list_raw_files` and its
`days` argument. That walks every `<YYYY>/<MM>/<DD>` folder under
`state/raw/<ledger>/` (`_day_folders` in `backend/idhazh/ledger/raw_files.py`)
and skips the days nobody asked for. It opens only the files of the days it was
handed, so what grows is the walk: one folder name for every raw day on disk.
[`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) says the
read is the raw files of the named days alone, and Guardrail #12 forbids a walk
over a committed tree that grows.

**It costs little today, and it grows where a ledger is not packed live.** A
ledger packed live keeps only its newest days raw, so the walk is a day or two.
A ledger packed report-only keeps every raw day: `state/raw/gardener/` held 6
day folders on 2026-10-05, from 2026-09-30, and gains one a day until plan 60's
row 23 packs it live. A gardener shard's checkout holds only the folders it
fetched, so on a runner the walk sees those alone; a full checkout, such as a
developer's, holds them all.

**The fix is one function.** When `days` is named, `list_raw_files` builds each
named day's folder from `paths.raw_root` and reads those alone. With `days=None`
it keeps the walk, which `raw_days` and the whole-ledger reads need, and only
those then warn about a folder that is not a day. Level 2 - the rows each caller
gets do not change, and the callers include the reads that keep a story from
being published twice, so each is checked by name.

Found on 2026-10-05 by plan 60's row 10 (#1307), whose `workflow-runs` task reads
seven named days of the gardener's own record at every wake.

Since #1335 a ledger's raw root can also hold a `set-aside/` folder, and the
reads that walk a whole raw root - `ledger.raw_days`, `list_raw_files` and
`named_trees.raw_days` - log it as a stray folder (plan 60's row 18 report).
The fix above stops that warning in a read of named days, and a walk it keeps
still logs it.

## 58 - A ledger test expects an order for two runs written in the same millisecond (CLOSED 2026-10-09)

**The test now checks replacement and preservation without ordering the runs.**
`backend/tests/test_ledger.py::test_a_second_attempt_replaces_its_first_and_another_run_is_kept`
pins the writer clock to 2026-09-07 00:00:00.000 UTC. In a copy of main at
`86fca9a542ca0456fec3eb2b1009574cda10ea7d`, the old positional assertion
fails: run 2 comes before run 1 because their file hashes break the
same-millisecond tie. The cause is confirmed, not estimated.

**Who reads it:** the backend contract suite reads the two visual-prune runs
this test writes. No production caller reads `load_visual_prunes`; its
oldest-day-first, one-row-per-run contract is unchanged.

**What settles it:** exactly two returned rows and the literal mapping
`{"2026-09-07-1": 200, "2026-09-07-2": 300}` prove that run 1 keeps
attempt 2's value and run 2 keeps its original value. The row count exposes
duplicates; the mapping exposes missing runs and stale attempts. The test
does not sort loaded rows or claim an order between independent runs.
Plan 60 row 44 closes this Level 1 test defect.

## 57 - A day page stopped drawing during a browser test, and the test waited three minutes for it (OPEN)

**One browser test waited out its whole 180-second limit for a page that had
stopped drawing.** "Every drawn string resolves to a size on a 390 px screen"
(`frontend/tests/item-visual.spec.ts`, line 547) timed out in CI run
37220465924, attempt 1, at 17:32 UTC on 2026-10-04. It stopped inside
`revealDayDrawings` (`frontend/tests/support/day-drawings.ts`), which scrolls
the day one screen at a time and waits for two animation frames after each
step. The test's trace shows the scroll start at 17:29:26.790 UTC, the page's
last drawn frame at 17:29:26.937 and its last request at 17:29:26.948. Nothing
was drawn or asked for in the three minutes after. The next run, on the next
commit, passed the test, and on the last green run of that pull request it
took 1.6 seconds.

**The runner was not slow, though row 7's report read it that way.** The 374
other tests that the red run and the last green run share took 335 seconds in
all on the red run and 361 on the green one: 7 percent less time, not more. A
page script that never finished and a browser that stopped drawing look the
same in this trace, so it cannot say which one happened.

**A second stall came in main's own checks.** "THE ORACLE: every fact is
reachable without a mouse > the platform reads the figure by the sentence, not
by its marks" (`frontend/tests/item-visual.spec.ts`, line 471), another test of
the same spec, failed in CI run 37796300534, the checks main ran on f668b3e62
(#1439), in its browser job (job 113376700083) at 15:02 UTC on 2026-10-08.
`page.evaluate` waited out the test's 180-second limit at line 123, where
`drawnDay` calls `revealDayDrawings`: the step the first stall stopped in. The
next commit on main that CI ran on, 60f33fa4b (#1440, run 37799982887), passed
it. #1439 changed the Judgement route, the module it reads its line from, that
module's test, the test group list, one docs page and plan 62, and not that
spec or its helper. The two stalls meet the bar this entry set: a second stall
in CI opens a row.

**Doing nothing costs a red browser job each time it comes back, three runner
minutes and a re-run.** How often that is, nobody knows: it has been seen
twice in CI, on 2026-10-04 and on 2026-10-08.

**The next move is a worker's: make the stall come back where it can be
watched.** Run this one test a few hundred times with Playwright's
`--repeat-each`. At 1.6 seconds a run, 400 runs take about 11 minutes, an
estimate. A stall caught that way shows whether a page script or the browser
stopped. If none comes back, a second stall in CI opens a row, as defect 51
does. The first run's trace is kept in its `playwright-traces` artifact until
2026-10-11, and the second run's artifact expires on 2026-10-15. A raised
timeout or a retry would hide the stall, not explain it (CLAUDE.md
Guardrail #5). Level 2 - the fix is in the day page or in a helper that three
specs share.

Found by plan 60's row 7 (#1286), whose checks went red three times with three
different tests, and filed on 2026-10-04. Seen again on 2026-10-08 in main's
checks of #1439.

## 56 - A byte-range test counts a correct 304 as a failure (FIXED 2026-10-06)

**A browser test of reading a year file by byte range keeps failing on a 304
that its own setup makes correct.** "A year file whose ETag changed after the
browser kept part of it is still read by byte range"
(`frontend/tests/ledger-ranges.spec.ts`, line 310 today and 271 on the commit
that failed first) failed first in CI run 37218615995, attempt 1, at about
17:00 UTC on 2026-10-04, and a re-run of the job passed. The test lets the
browser keep an answer for 1 second, reads the year file, gives the file a new
ETag (its `redeploy` step), waits 2 seconds, reads the file again from a new
page, and expects the test's host to answer every GET with a 206.

**The host's own request log settles the cause.** The run's
`playwright-traces` artifact keeps it, as `ledger-ranges/requests.json`, until
2026-10-11. The second read asked for byte 0 and got a 206, then for the end
of the file. Then, before fetching the middle, the browser checked the copy of
byte 0 it held from that same read: the request names the file's new ETag in
`If-None-Match`, which asks whether a held copy is still current. The browser
asks that only when its copy is older than the 1 second the test allows, so
the read took longer than that, and the host answered 304, which is right. The
read's answer still matched the disk, which the test checks first.

**It failed twice more the same way, and the second time in main's own
checks.** CI run 37382246965, the checks of #1326, failed it on attempt 1 (job
id 112007006566) at about 22:28 UTC on 2026-10-05, and a re-run of the job
passed. CI run 37427112258, the checks main ran when #1328 merged, failed it
in the browser job (job id 112149278674) at about 07:05 UTC on 2026-10-06, and
that run stays red. The failed assertion prints the request it counted. In
both runs that request is a GET for byte 0 of
`compact/host-fingerprint/yearly/2026/2026.parquet`, answered 304 with no
body. Its `If-None-Match` names the ETag the host was serving:
`"6ac43266-4fe1"` in run 37382246965 and `"6ac4ab97-4fe1"` in run
37427112258. Its address carries a `read` mark that no other read uses
(`read=37617a44d53a84f5` and `read=f9688832d6ad26de`), so the copy the browser
checked came from that same read. That is the request the host's log showed
the first time, so the cause is the same.

**Doing nothing costs a red browser job whenever that read takes more than a
second, and a re-run.** It has cost that three times in three days, and once
it was the one failure that turned main's own checks red. The site is not
wrong: Pages lets the browser keep an answer for 600 seconds, and 304 is the
right answer to a browser checking its copy.

**Fixed on 2026-10-06 by #1354.** The test sets the host back to Pages' 600
seconds after its 2-second wait and before the second read starts, so only what
the first read kept is stale and every GET of the second read is a 206. Level 1 -
one test.

Found by plan 60's row 7 (#1286), whose checks went red three times with three
different tests, and filed on 2026-10-04. The two later failures were added on
2026-10-06.

## 55 - The query-door page names a deleted test, so nothing may hold the rule it states (OPEN)

**The page that says how the query door answers a panel names a test that is
gone.**
[how-the-query-door-answers-a-panel.md](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)
says that `backend/tests/contracts/test_published_ledgers_cover_the_panels.py`
holds the two sides together: every ledger a panel names in a `slice()` or
`ledgerReach()` call is in `ledger.published` in `config/idhazh.json`. #1228
deleted that file on 2026-10-03, when the contract tests stopped reading trees
that grow with the repository; it took out the scan of the frontend source and
its parser. Its description names
`test_every_ledger_the_door_can_be_asked_for_is_published` as the check that
stays, but #1201 had deleted that check three hours before. Neither test is on
`main`, and no test there names `cover_the_panels` or calls `ledgerReach(`.

**Doing nothing costs a broken panel that no check catches.** A panel that asks
the door for a ledger the site does not hold gets a 404 on that ledger's index,
and that 404 is the only sign that the ledger was left out. The tests that read
`ledger.published` today, such as `backend/tests/contracts/test_page_ceilings.py`
and `frontend/tests/published-ledgers.spec.ts`, check other things: each
published ledger's page-weight key, and what the build copies.

**The next move is a worker's.** Find which test, if any, holds the rule now.
If one does, the page names it instead, Level 0. If none does, restore a
bounded test that reads only named config and never scans the frontend tree,
Level 2.

On 2026-10-08 the page stopped naming the deleted test, and says instead that
no test checks the rule. A search of `backend/tests/contracts/` on `origin/main`
at 702b00be7 found none that does. The rule holds today: the one panel that
asks the door, `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, asks
it for `host-fingerprint`, which is published. The bounded test is still the
next move.

Found by Fowler's review of plan 60 on 2026-10-04 (item 17), and filed the same
day.

## 54 - The first squash that rewrites history may not fit in its 30-minute job (OPEN)

**The first corpus squash that collapses commits is due at the upkeep wake of
2026-10-29, and at the only measured rate one replay needs about twice the
job's limit.** `corpus/corpus.meta.json` records the last run on 2026-09-29, and
`config/gardener/corpus-squash.json` sets `every_days` to 30 and `window` to 60
days. The `history` job of `.github/workflows/idhazh-gardener.yml` has
`timeout-minutes: 30`. That squash collapses every commit authored at or before
00:00 UTC on 2026-08-30 into one new root and replays every commit after it,
less the merge commits, which a rebase drops. Counted on `main` on 2026-09-30, it
would collapse 437 commits and replay 2,465. The seven days 2026-09-23 to
2026-09-29 added 489 commits, about 70 a day, so the replay reaches about 4,400
commits by 2026-10-29 - an estimate. One replay of 1,001 commits took 824 s on
the Windows development machine, about 0.82 s a commit, and nobody has timed one
on `ubuntu-latest`. At that rate 4,400 commits take about 61 minutes, and the
job's 30 minutes hold about 2,190, fewer than the 2,465 already there. The 4,800 on
[the gardener's config page](../docs/concepts/config/idhazh-gardener.md#the-history-declaration-corpus-squash),
from September's average of about 80 commits a day, gives about 66 minutes.

**Doing nothing costs a squash that fails every day and bounds nothing.** A job
stopped at its limit has pushed nothing and recorded no run, so `main` is safe.
But the squash is then due again at the next day's wake, is stopped again, and
goes on that way every day, 30 runner minutes each time. The history it exists
to bound keeps growing meanwhile: the workflow's own header puts the article
text alone at about 154 MB a year.

**The home is the `history` job's `timeout-minutes`, and a person picks the
move.** One move is to raise it. GitHub stops any job at 6 hours, which leaves
room for all three of the squash's `push_attempts`, each a whole replay, at the
Windows rate. What that costs is the quiet time the force push is placed in:
`backend/tests/workflows/test_triggers.py` checks that the push, at the latest
start it allows plus the three jobs' limits, lands before 07:23 UTC, the
earliest a digest run was seen to start. With 30 minutes it lands by 07:09, so a
limit of 44 minutes or more also needs a new wake time or a new rule, or that
test goes red. The other move is to time one replay on `ubuntu-latest` first and
set the limit from that number. The squash program's dry run stops before the
replay, so this needs a run that replays and does not push, before 2026-10-29.
Level 2 - that test and the comment above the workflow's cron line hold the 30.

Found by plan 50's row 13 (#1167), whose worker timed the replay, and filed on
2026-09-30, when plan 50 closed.

## 53 - The `traces` upkeep task cannot date eight old trace files, so it never deletes them (OPEN)

**Eight trace files sit where the task that deletes old traces cannot date
them, so it will never delete them.** They are
`state/traces/2026/09/22-<run>-<shard>.jsonl`, 687,103 bytes in all, in the flat
shape traces had before #1067 moved 104 flat traces into day folders at 05:22
UTC on 2026-09-23. Two runs of 2026-09-22 wrote these eight, in eight work
commits from 20:37 UTC that day to 00:28 UTC the next; the traces of that day's
three earlier runs moved, and these did not. The `traces` task,
`backend/idhazh/gardener/tasks/traces.py`, dates each file with `trace_date` in
`backend/idhazh/telemetry/traces.py`. That function reads the day from the
folders and returns None for any path that is not year, month, day and file
below `state/traces/`. These eight are year, month and file, so the task passes
over them: at its wake on 2026-09-30 it selected the 124 files in the day
folders from 2026-09-15 to 2026-09-23, and none of these eight, though their
names say 2026-09-22.

**The other fault plan 50's row 10 found is still true, and the code is not
its cause.** Day folders still sit past the window. The task keeps a trace while
it is less than 7 days old (`window` in `config/gardener/traces.json`, which
replaced `observability.trace_window_days`), so on 2026-09-30 the nine day
folders from 2026-09-15 to 2026-09-23 are past it: 124 files, 10,488,025 bytes.
The 52 files and 4,386,597 bytes that the row counted past it, 2026-09-15 to
2026-09-18, are among them. The task selects them and deletes none because it
runs report-only (`dry_run: true`), as a new upkeep task does until a person
reads its records and turns it live
([`docs/concepts/config/idhazh-gardener.md`](../docs/concepts/config/idhazh-gardener.md)).
That switch clears them, and no function changes.

**The home is `trace_date`, or the eight files' paths.** Either that function
learns the flat shape, `<YYYY>/<MM>/<DD>-<rest>.jsonl`, or the eight files move
into `state/traces/2026/09/22/`, where it already dates them. That move is the
`traces` shape of `backend/utilities/migrate_to_day_shards.py`: it turns the day
prefix into a folder and reads the tree back through `trace_date`. Nobody has
run it on these eight, and none of their names is already in that folder. The
move costs one commit of eight renames and no code; a second shape in
`trace_date` is a rule kept alive for eight files. Until the task deletes live
these eight cost nothing the other old traces do not; from that day they stay
for good. Level 2 - `trace_date` decides what the `traces` task deletes, and
`backend/tests/test_telemetry.py` holds the paths it refuses.

Found on 2026-09-26 by plan 50's row 10, while it was held, and filed on
2026-09-30, when plan 50 closed.

## 52 - Reading one month of a packed ledger downloads every month file of its year (OPEN)

**A gardener task that reads one month file downloads every month file of that
year.** A month file is `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet`, so it
sits in its year's folder beside up to eleven others. Since #1173 an upkeep shard
downloads only what its tasks read, and it widens its checkout by whole folders,
so a step that opens one month file fetches the whole year folder: up to twelve
files where it needed one. The extra counts against the shard's 128 MB
`max_downloaded_mb` alarm. A month of the scores ledger was about 3.5 MB in
September 2026, so a full year folder of it is about 40 MB, an estimate. It costs
nothing today: every compaction is report-only, and on 2026-09-30 `main` held 146
day files and no month file. It starts when a compaction runs live and a task
reads a month it packed, such as the census summary, `telemetry-aggregate`, whose
first month falls due about late 2027 (an estimate).

**The home is the month file's path.** The gardener page already names the fix:
give each month file a folder of its own, once the readings show the cost
([`docs/architecture/publishing/idhazh-gardener.md`](../docs/architecture/publishing/idhazh-gardener.md#what-a-shard-downloads)).
Plan 56's row 2 would pack a finished year's month files into one year file,
`state/compact/<ledger>/yearly/<YYYY>.parquet`, so the new path is chosen with that
layout in view. Level 3 - the compaction writes the path and the browser's ledger
reader reads it.

Found on 2026-09-30 by plan 50's row 14 (#1173), while its checkout was designed.

## 51 - The canary builder's score-key step aborted once at exit, after printing its whole answer (OPEN)

**Once, a program that had finished its work aborted on its way out, and the
site build that called it failed.** In `main`'s CI run 36655319104, attempt 1, the
browser job's step "Build the site from the canaries" ran
`python backend/utilities/build_canary_day.py --scored-keys` at 01:30:51 UTC on
2026-09-30. It printed its whole answer, the eight canary keys as JSON, then died
with "terminate called without an active exception" (SIGABRT), so
`frontend/scripts/build-canary.mjs` failed the build. The same tree had passed on
its pull request (#1166), and a re-run of the failed job passed at 06:40 UTC. The
site's next publication waited about five hours for that re-run.

**The home is the program that aborted, not its caller.** The likely cause is a
native thread still running when Python exits, now that this program opens
parquet files - an estimate, not reproduced. One abort is not enough to find it,
so a second one opens a row to reproduce and fix it. A retry in
`build-canary.mjs` would hide the same fault from every other program that opens
parquet, so it is not the fix (CLAUDE.md Guardrail #5). Level 2 - the canary
build, and every browser group behind it, read this program's answer.

**A second abort reproduced it.** In PR #1428's first browser job (CI run
37773872779, attempt 1, job 113299900513), the same step printed its whole
answer and then aborted the same way, on 2026-10-08; attempt 2 passed. The two
occurrences now meet the bar this entry set: a second abort opens a row to
reproduce and fix it.

Found on 2026-09-30 by plan 50's row 9, on the merge of #1166. Reproduced on
2026-10-08 in PR #1428's first browser job.

## 50 - A publisher link on the home page named a story the page did not draw, so a news run's site build failed (CLOSED 2026-09-30)

**A news run's site build failed on one link.** Content refresh run 36639197643
failed at 01:11 UTC on 2026-09-30, in its assemble job's "Build the site" step:
SvelteKit's prerender found that `/` linked to `/#world-32bhzh97bx1nk7s5` and that
no element on `/` had that id. The link was a publisher name on a grouped story,
an "Also covered by" pill in `frontend/src/lib/components/ItemMeta.svelte`,
written as a bare `#<item id>`. The home page does not draw a folded or paged
card in its first HTML, so the fragment named nothing. None of that run's 49 new
stories reached a reader until the fix below, because the later runs published
their own day and not that one.

**Filed and closed the same day.** #1168, merged at 12:20 UTC on 2026-09-30,
writes each publisher link as the dated address `<base>/<YYYY-MM-DD>/#<item id>`,
which loads the day and shows the story. `frontend/tests/reading-page.spec.ts`
asserts that address, and
[`docs/architecture/publishing/autotune-content-similarity.md`](../docs/architecture/publishing/autotune-content-similarity.md)
records the rule. The same change recovered the run's saved results and published
its 49 stories. **Do not re-run that run's failed jobs** while GitHub still allows
it, until about 2026-10-29: a re-run uses the code of the run's own commit, which
files the item-health, scores and host-fingerprint rows as CSV again. If one was
re-run, run `backend/utilities/migrate_to_parquet.py --run-id 2026-09-29-1`, then
its `--check`, and commit what it moved.

## 49 - The local test selector sends a backend test helper to every frontend group (OPEN)

**An edit to a backend test helper selects every group the local selector
knows**, where the backend test modules that import it would do.
`npm --prefix frontend run test:changed` takes its choice from `selectPaths` in
`frontend/scripts/test-scope.ts`, which knows a backend test module only as
`test_*.py` at most one folder below `backend/tests/`. A helper such as
`backend/tests/workflows/_harness.py` or
`backend/tests/workflows/_ledger_derivation.py` matches no rule, so it falls to
the last one, "shared or unknown input; full coverage": the whole backend suite,
all eight frontend groups, and so a canary site build. Counted on `main` on
2026-09-30, the same rule catches all 14 helpers under `backend/tests/` and the 14
test modules two folders down, in `backend/tests/gardener/tasks/`. A row that
edits one helper is asked to run the whole local suite for it.

Plan 60's row 35 met it on 2026-10-08: `frontend/scripts/test-scope.ts` takes a
backend test module as one only at most one folder under `backend/tests/`, so a
change to `backend/tests/gardener/tasks/test_yearly_expiry.py` alone falls to
"shared or unknown input; full coverage", which selects every frontend group and
turns on CI's browser job (`ciAnswer` does so for any group but `backend` and
`logic`).

**The home is `test-scope.ts`**: send a file under `backend/tests/` that is not a
test module to the backend group alone, since no frontend test or script reads
one; let the test-module rule match at any depth; and add both cases to the truth
table in `frontend/scripts/tests/test-scope.test.mjs`. Defect 45 changes the same
file. Level 2 - the truth table is the dependant to check.

Found on 2026-09-29 by the worker of plan 50's row 12, whose change edited one of
them.

## 48 - GitHub stamps its squash merges in local time, `+02:00`, not UTC (OPEN)

**Every squash merge GitHub writes on `main` carries a `+02:00` offset**, for its
author and its committer time alike. All 39 of GitHub's commits among `main`'s
last 200 read that way on 2026-09-28, while every commit the pipeline's runner
writes ends in `Z`. The instant is right and only its offset is wrong, but
CLAUDE.md section 2 says a commit time is UTC, and two such times compared as text
rather than as instants sort a merge and a pipeline commit in the wrong order.
The one program here that reads commit dates, `backend/utilities/corpus_history.py`,
decides by `%at`, which carries no offset, so no decision reads it today; its
dry-run line prints the boundary's author time with whatever offset that commit
carries.

**The home is outside the repository, and it is not yet known where.** A commit
made on this machine takes `TZ=UTC` for the commit
([`docs/reference/agent-notes/git-and-github.md`](../docs/reference/agent-notes/git-and-github.md)),
and a merge GitHub writes takes no such switch. The likeliest source is the
time-zone setting of the account that merges - an estimate, not measured. One
merge settles it: set that zone to UTC, merge one pull request, and read
`git log -1 --format=%cI` on the merge. If the offset stays, the remaining choice
is between living with it and merging on this machine under `TZ=UTC`, which
changes how every row merges. Level 1 - a wrong offset is visible on the commit
that carries it, and nothing depends on it.

Execution owner: the repository owner for row 48; check both `%aI` and `%cI` on the next normal squash merge, and require UTC offsets or an explicit UTC-policy decision before closing the row.

Found on 2026-09-28 by plan 51's owner, while merging that plan's row 5.

## 47 - The Pipelines route draws no panel ids, so the pictures and gates reach 15 panels, not 26 (OPEN)

**The panel pictures and the sufficiency gates reach only a panel that carries
an id, and the Pipelines route (`/console/`) gives none.** Of its eleven sections
one draws three panels, four draw no panel frame, and none carries a
`data-console-panel-id`, so `frontend/tests/panel-captures.spec.ts` pictures the
Hardware route's 15 panels and nothing else. Plan 51 counted 26 panels on two
routes; the row that built the pictures corrected it to 15 on one route on
2026-09-28. Its capture spec names the Pipelines route and fails the day that
route starts drawing ids, so the count cannot go stale without a red.

**The home is a plan 52 route row that gives each Pipelines section a panel
id.** Plan 52 already plans the same for the three routes that draw no id
(`/console/model/`, `/console/voices/`, `/console/judgement/`), and it still says
the gates reach 26 panels on two routes; that row, or one beside it, takes the
Pipelines route too. Level 2 - each section's id, its `console.panel_groups`
entry and its pictures move together.

Found on 2026-09-28 by plan 51's row 6, which built the pictures.

## 46 - `DateSeries` cannot draw the settings-change rule that gate 6 asks of every trend (OPEN)

**Gate 6 asks every trend over days to carry its confounders**: the trend
declares `data-model-rule`, and `yes` either draws the settings-change rule or
says in visible words that no setting changed inside the span
([`docs/concepts/design-system.md`](../docs/concepts/design-system.md#sufficiency-is-a-gate-not-a-taste)).
`DateSeries`, the d3 trend in `frontend/src/lib/charts/d3/`, draws no rule and
takes no settings - neither `DateSeries.svelte` nor `dateSeries.ts` carries
one. The witness panel the gates are proven against passes gate 6 only by
printing the no-change sentence beside the chart. So a real date series can pass
gate 6 only on that sentence, and it cannot pass at all over a span in which a
setting did change.

**The home is plan 52's row 2, the settings-change rule on every
`dateSeries`**, and it has to land before plan 52's first date-series panel
joins `console.judged_panel_ids`. Level 2 - one component, and every panel that
draws it.

Filed on 2026-09-28 from plan 51's rows.

## 45 - A change to `Panel.svelte` does not buy the console tests on a pull request (OPEN)

**On a pull request, CI runs the console's own specs only when the change is
the console's own**, and `CONSOLE_OWNED` in `frontend/scripts/test-scope.ts`
counts a shared component as the console's only when its name starts with
`Console`. `frontend/src/lib/components/Panel.svelte` is every console panel's
frame - the 22 files that import it are all under a console path, counted
2026-09-28 - so a change to it defers the console specs to the merge push, and a
break is found on `main` rather than on the pull request that caused it. The
local selector is not affected: it reads the file as a shared frontend input and
selects every frontend group. Since #1144 a change to it does buy the panel
pictures and the sufficiency gates, through `PANELS_DRAWN`; it still does not
buy the console specs.

**The home is `test-scope.ts`**: name `Panel.svelte` in `CONSOLE_OWNED`, and add
the case to the truth table in `frontend/scripts/tests/test-scope.test.mjs`.
Level 2 - the truth table is the dependant to check.

Execution owner: [plan 52](20260926-52-fifty-panels-move-and-six-projections-go-plan.md) row 1; its selector truth-table case is the acceptance check for defect 45.

Filed on 2026-09-28 from plan 51's rows.

## 44 - One hatch means two things on the console: no reading, and time counted twice (OPEN)

**A hatch means "no reading" on one console panel and "time counted twice" on
another.** `MemoryBoard.svelte` hatches the bar of an item that carries no kernel
reading. `RunTimelinePanel.svelte` hatches the notch where a job's steps add up
to more than its own clock, keyed "overclaimed - two steps counted over it". A
reader who learns the texture on one panel reads the other wrong. The chart
vocabulary page
([`the-mark-shapes-a-panel-may-reach-for.md`](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md))
names the clash, and plan 51's row 4 made the absent hatch one builder,
`absentHatch` in `frontend/src/lib/charts/d3/ordered-colour.ts`, for a known
thing with no reading.

**The remaining execution owner is plan 52 row 6**, which redraws
`RunTimelinePanel.svelte` and resolves what its overrun is drawn with. The
memory-board half is complete (#1171). Level 2 - two panels, each checked by name
in both themes.

**The first half is done**, 2026-09-30: the memory board draws an item with no
reading in the reserved grey's stripes from `absentHatch`, at
`console.absent_hatch_degrees`, the same hatch the machine-kinds panel draws a
machine with no speed reading in. What is left is the run timeline's overrun.

Plan 51 row 8's final real and canary captures verify the no-reading texture in
both themes. PR #1171 closes that half; the timeline half remains with its
existing plan 52 row and is not part of the row 8 completion.

Found on 2026-09-27 by plan 51's row 4, which built the hatch builder.

## 43 - A section that follows the days control changes height and moves the page under the reader (OPEN)

**When the reader changes the span, a section that follows it can redraw at a
new height, and everything below it moves.** A reader looking at a panel further
down loses their place, for a reason they did not cause and cannot see. Jony
raised it in review of plan 51's rows. The console already holds this rule for
one surface: `frontend/src/lib/console/strip.ts` keeps the page still when the
tab strip sticks and gets shorter.

**The home is the console layout**, as one rule for every section that follows
the window, not a fix inside each panel. Level 2 - every windowed section on the
five routes, each checked by name.

Execution owner: this plan's row 43 worker; changing every preset at the documented widths in both themes must leave the windowed sections' settled positions unchanged.

Filed on 2026-09-28 from Jony's review.

## 42 - The processor-share tiles print "under 1%" past their own bottom edge (OPEN)

**On the Hardware route, the "By day" tiles of the processor-share panel - "How
much of the processor went to somebody else" - print their "under 1%" label past
the tile's bottom edge**, so the words sit outside the box they describe. Seen at
1440 px in the light theme by plan 51's row 2, whose files do not draw it. The
label is `under ${marked}%` from `processor-lost.ts`, drawn by
`ProcessorLostPanel.svelte`, both in `frontend/src/lib/console/machine/`.

**The home is that panel.** Level 1 - one panel's tiles, checked at every width
in both themes.

## 41 - Span sentences print "in these 1 days" at the one-day window (OPEN)

**At the one-day preset, a panel's sentence reads "in these 1 days".** The
sentences put the window's number straight in front of a literal `days`. A text
search on 2026-09-28 finds 102 lines in 25 files under `frontend/src` that
splice a day count in front of `days`, so each is a candidate. Seen on the
console by plan 51's row 2, which changes no panel.

**The home is the console sentence helpers**: one rule for a count and its
noun, used by every sentence that names the span. Level 1 - wording, and a wrong
version is obvious on the page.

Execution owner: this plan's row 41 worker; browser checks of one-day and multi-day windows must show the correct singular and plural wording on every console route.

## 40 - The canary never writes a job in two halves, so no built page tests the merge (OPEN)

**Every job now writes its machine record in two halves** - the first names the
machine, the second what the job cost - and both build-time readers of
`state/host-fingerprint/` merge the two by the settlement key. The canary day's
machine rows, written by `frontend/scripts/build-canary.mjs`, never hold a job in
two halves, so no built page and no browser spec ever reads one. Only the
readers' fixture tests prove the merge, and a page that stopped merging would
pass every browser spec.

**The home is the canary builder**: write at least one job as its two halves.
Level 2 - every browser spec shares the canary, so the specs that count machine
rows are checked by name.

Execution owner: [plan 52](20260926-52-fifty-panels-move-and-six-projections-go-plan.md) row 4; its built-page check of one merged canary job is the acceptance check for defect 40.

Found on 2026-09-27 by plan 51's row 1, which built the merge.

## 37 - Two colours of the dark chart ramp look the same, so two machines read as one (OPEN)

**The chart ramp is meant to tell eight series apart, and in the dark theme it
tells six.** Its third and sixth colours - stops 3 and 6 in
`frontend/src/styles/tokens.css`, `#4fc7dd` and `#3fc3e0` - are 2.3 apart on the
CIEDE2000 scale. That scale measures how different two colours look: about 2 is
the smallest difference most people can see with the colours touching, and about
10 reads as clearly different. Every other pair of the first seven dark stops is
9.3 or more apart, and the same pair in the light theme is 9.2 apart. Measured
2026-09-27.

**A reader meets it first on the Hardware route's machine-kinds chart.** The
colour ramp hands out its stops by sorting on each machine's key, which is
arbitrary on purpose, and AMD EPYC 7763 and AMD EPYC 9V74 landed on stops 3
and 6. Plan 51's row 1 moved the ramp's own `Other machines` group from second
place to last, and that put those two bars next to each other: over the 30-day
window both draw in 8 of the 11 day groups, and at a glance the second reads as
part of the first. The readout under the plot names every bar and the order is the same
on every day, so a reader who looks can tell them apart. A reader who glances
cannot, so the panel fails the two-second check on the dark theme, which is the
default. Any chart that draws both stops has the same fault, wherever they land.
Since 2026-09-30 the machine panels colour a machine by its speed, one hue in
steps, so they no longer draw these two stops; the fault stays with every other
chart that does.

**The fix is one colour, then every pair measured again.** Pick a new dark
`--chart-6` that is at least 10 from every other stop and from `--chart-change`,
is not green, amber or red, and reaches at least 3:1 on `--color-surface`
(`#141922`). Then measure every pair in both themes again: dark stops 1 and 5
(9.3) and light stops 3 and 6 (9.2) are also under 10. Level 2 - every chart that
draws stop 6 changes colour, so each one is checked by name, in both themes.
Susan rules the colour.

Found on 2026-09-27 by plan 51's row 1, in its browser check. Susan ruled it out
of that row: the fault is in the colours the whole site shares, so it takes its
own change and its own browser check, and it is the next thing to fix on that
chart.

## 36 - The band above every console route calls every run written in two halves unreadable (OPEN)

**This is defect 33's backend twin.** `console_band._machine_rows` in
`backend/idhazh/telemetry/publish/console_band.py` reads `state/host-fingerprint/`
raw, on purpose: refusing a run is the band's point, and `_one_run` refuses a run
when two rows for one shard differ in any cell but the key and `version`, because
that is two hosts answering for one shard. The rule is older than the two halves.
A job's probe half and its clock half fill different cells, so the band reads them
as two hosts.

Measured 2026-09-27 over the 90 days the band reads: **24 of 47 runs are refused,
and they are exactly the runs written in two halves** - every run filed from
2026-09-23 on, when each job's halves began landing in one file. None of the 23 it
keeps has a clock-only half. The committed `frontend/public/console/band.json`,
written at 21:31 UTC that day, names the Hardware route's worst line as
`24 runs cannot be read`, and its sentence says no figure on that route counts
them. That is not true: the route merges the halves and counts every one. The
band's newest-run figures come from the newest run it did not refuse, which is a
run from 2026-09-22.

**The fix is the frontend's rule, on this side.** Merge a shard's rows by
`ledger.HOST_FINGERPRINT_KEY` before `_one_run` compares them, and go on refusing a
key whose rows fill one cell two different ways. `day_shards.settled_day` unions
the halves already, but it settles a contested cell by attempt order rather than
refusing it, so it is not a drop-in: whether the band refuses a retried shard or
reads its newest attempt is the one ruling this needs. Level 2 - one reader and the
band's own tests.

Found on 2026-09-27 by plan 51's row 1, which closed defect 33 and was scoped to no
backend change.

## 32 - The console reads the score ledger raw, so the newest day counts twice (CLOSED 2026-09-23)

`evalRows` in `frontend/src/lib/server/payload.ts` opened `state/scores/`
through `readDayShards` and handed the rows straight to the panels. That ledger
declares a settlement - `ledger.OBSERVATION_KEY` is `(url_key, output_digest,
scorer_version)` - and every backend reader applied it. This one did not.

Two jobs write a score row for one observation, so the day a run is publishing
held both. Measured 2026-09-23 over the committed ledger: the day being
published held **441 rows over 237 distinct keys**, and every one of the
thirty-two days before it held 0 repeats. An older day has been folded into one
settled file, which is why no fixture built from folded days could reach this.

Filed and closed the same day. The fix is the one `itemHealthRows` took beside
it: settle at the shared read door. Both now go through `settledDayShards`,
which settles **within each recorded day** rather than over the cover - the part
that needed measuring, because `OBSERVATION_KEY` carries no date and exactly one
key of 12,463 legitimately spans two days. Collapsing the cover would have
deleted it.

The rule is written up in `docs/architecture/publishing/console-payloads.md`: a
reader function that opens a `state/` ledger settles it, settles it once, and
settles it per day.

## 31 - The council's selection artifact is named for one date and carries several (OPEN)

`.github/workflows/llm-council.yml:243` names the upload
`council-selection-${{ steps.decide.outputs.date }}`, and the collecting job
downloads it on `council-selection-*`. Since the night plan landed, that one
artifact carries **every** date the night covers, as directory levels inside it.

Nothing collides, because a run makes exactly one of them. So this costs nothing
until somebody reads the artifact list to find out what a night did, and the
name tells them one date when the contents hold three.

Found 2026-09-21 by the row that built the night plan, which left it rather than
churn a test it did not otherwise touch.

## 30 - A third spelling of the vector norm lives in the canary builder (OPEN)

`backend/utilities/build_canary_day.py:1104` declares its own `_vector_norm`.
`idhazh.assemble` has carried the same rule all along and its helper became
public on 2026-09-21, so the duplicate now has a callable original sitting next
to it.

It is an operator tool rather than a pipeline stage, which is why it was left.
The cost is the ordinary cost of two spellings of one rule: the autotune page
already records one occasion where a second word reduction drifted from the
first and moved a measured line.

## 29 - A shard is called a `unit` in the council's workflow and its tests (OPEN)

The scrub that deleted `leg` on 2026-09-21 replaced it with `unit` across
`backend/tests/workflows/test_llm_council_workflow.py` and
`.github/workflows/llm-council.yml` - six test names and about forty comments,
`test_one_server_per_unit`, `Run this unit of the tenant's work`.

**`unit` is a second name for `shard`, which is already the column, the knob and
the count.** `CLAUDE.md` section 0b says a borrowed second name is deleted
rather than replaced, so the scrub swapped one for another and is not done. The
guard test was renamed at the time; nothing else was.

A rename of test names and comments, no behaviour. What makes it worth writing
down is that this is the **fifth** borrowed word this repository has had to
remove, and the first one removed by substituting a sixth.

## 28 - The one-at-a-time guard tells the operator the wrong verb (OPEN)

`backend/idhazh/gardener/one_at_a_time.refuse_by_name` spells the word "prune" into
the message it refuses with. The helper is general - it is what stops any verb
running over two members at once - so the first other verb to reuse it refuses
an operator in the name of a verb they did not run.

About four lines across three call sites, plus the assertions that read the
wording. Level 1: a wrong word in an operator message, with nothing depending on
it today because nothing else uses the helper yet.

## 27 - The decode stamp excludes the grammar but not the schema (OPEN)

`UNSTAMPED_REQUEST_KEYS` at `backend/idhazh/llm/server.py:127` leaves `grammar`
out of the decode digest and leaves `json_schema` in. A caller on the grammar
route therefore stamps a digest with no grammar in it, and a caller on the
schema route stamps its whole schema with no column beside it saying so.

**The schema route is the summariser's**, so correcting the exclusions changes
every summariser digest on every row written after the change - which is the
reason it was left rather than fixed in passing. It is a persisted-contract
change with a reset behind it, the same shape as the one the judge's record
took on 2026-09-21 and recorded in
`docs/reference/benchmarks/what-the-margin-rule-changes.md`.

## 26 - The settlement-key check reads one constant twice, so it cannot see a key lose a cell (OPEN)

`backend/tests/workflows/test_ledger_staging.py` checks that a ledger's writer
and the settlement registry agree on the key a row is settled by. Both sides
read the **same constant**, so the check compares a value with itself and passes
whatever that value is.

What it cannot catch is the failure it exists for: a key that loses a cell. Drop
a column from the key and both sides drop it together, the check stays green,
and two rows that differ only in the dropped cell start settling as one.

**Every keyed ledger is exposed to this**, not just the one it was found on. The
fix is for one side to be derived from something other than the constant - the
committed header, or the contract's own field list.

Execution owner: this plan's row 26 worker; for each key cell, a bounded fixture pair differing only in that cell must stay separate, and dropping the cell must fail without deriving the expected answer from the key constant.

## 25 - `host_model` is a column nothing fills, and two rulings disagree (CLOSED 2026-10-04)

`backend/idhazh/contracts/council_shard_outcome.py` declares `host_model`. No
writer fills it.

It is open rather than obvious because **two rulings point opposite ways and
both are written down**. The contract's own argument is that a venue recording
what a unit cost should say what ran it. The council row that files the outcome
rejected recording the machine per shard, on the grounds that the digest
pipeline already characterises the same runner pool and the probe wants 1.9 GiB
on a job whose two processes already hold up to 9.02 GiB in 16 GB.

The council record rationale
([llm-council.md](../docs/architecture/publishing/llm-council.md#the-venue-files-the-row-not-the-tenant))
keeps machine details out of each row. The replacement contract refuses a
filled legacy cell during migration.

Found 2026-09-21, while the council's own record was being built.

## 24 - `failed_field` costs a cell on every row and answers nobody (OPEN)

`backend/utilities/empty_column_census.py` exits non-zero naming one column.
`failed_field` on the item row is empty on all **14,026 committed rows**,
measured 2026-09-21, and nothing under `frontend/src` draws it - so it has
neither a reader nor a writer that has ever written. `two_calls.py` can fill it,
with the field a refused reply failed on, and no refused reply has yet named one.

**It is not deleted yet because removing a published column is a migration, not
an edit.** The shape is the one that removed `cgroup_peak_bytes`: add the name to
`DROPPED_CELLS` in `backend/idhazh/contracts/item_health.py`, stamp the schema
`version` and append its changelog entry, write the read-side migration in the
same commit so a row an earlier run wrote still loads, and update the canary
builder. The contract refuses a silent removal, which is what makes this four
edits rather than one, and it is Level 5 because it changes a persisted contract.

**The other half of the census's verdict is to draw it**, and that needs a panel
somebody wants. `failed_rule` sits beside it under the same heading and does
carry values, so a reader for the pair is not obviously worthless - which is the
choice this defect is open on.

Found on 2026-09-21 by the census that shipped with the reader annotations, which
declined to widen into it.

## 23 - The canary day records no settings, so nothing renders the rules (OPEN)

Four Hardware panels draw a dotted rule on every date a run recorded a changed
setting, with a readout naming what moved. No test renders one. The canary day
carries **22 run entries and not one has an `inputs` block**, so every panel that
reads the record draws its named absent state instead, and a browser check
asserting a rule would assert nothing.

What is covered is the pure module: `frontend/tests/settings-moved.spec.ts`
drives `frontend/src/lib/console/settings-moved.ts` from a six-day fixture that
carries states the committed archive has never produced. That holds the
arithmetic and the words. It cannot hold the page - whether the rule draws
behind the data marks rather than over them, whether the readout reaches the
reader, or whether a date with a rule and no reading draws both, which is the
state the panel exists for.

**The fix is a canary change, and the blast radius is why this is filed rather
than done.** `backend/utilities/build_canary_day.py` writes those run records and
four other panels' specs read the tree it builds, so a widened record is a change
every browser spec on that route runs against. The smallest version gives one
canary date an `inputs` block and leaves the rest without one, because that
mixture is the state the committed archive is actually in.

Found on 2026-09-21 by the row that shipped the rules, which declined to widen
into it.

## 22 - The same story publishes several times in one day (CLOSED 2026-09-14)

On 2026-08-25 Dolly Parton's death ran five times from five feeds. On 2026-09-03
one acquisition ran five times under two spellings of its price. Across the 25
committed days, 42 groups of items from **different** sources published under one
headline and the pass grouped 15 of them.

**The threshold was not the fault.** `collapse_same_story` scores vectors built
by `embed.text_for` over `f"{title}. {summary}"`, and the summary is our own
model's prose about one article - a median 16 tokens of headline in a median
121, so 87 percent of what the encoder reads, measured 2026-09-14 with the
committed tokenizer over 75 items of the 2026-09-13 day. Two outlets writing the
same story give our summariser two different articles, so the comparison is
dominated by the one part guaranteed to differ. The 53 cross-source pairs whose
headlines match score a median of
**0.9177** against a floor of **0.94**, and the pair a person has already marked
as two stories sits at **0.9317** - above that median. No floor separates the two
populations, so lowering one would have traded this defect for a worse one.

**What shipped is a second joiner, not a new number.** Two items are also the
same story when their reduced headlines say the same thing - threshold-free,
still vector-gated, still across sources, still all-pairs.
`assemble.duplicate_similarity_min` is untouched at 0.94. The words must match
exactly; the numbers only have to agree to the coarser of the two precisions
they were written with, so `$12.9 billion`, `$12.93 billion` and `$13 billion`
are one acquisition while `25 percent` and `50 percent` are two figures. That
tolerance admits twelve cross-source pairs the exact-digit rule refused and
every one is the same acquisition - no false merge. Owner ruling 2026-09-14,
over Andre's narrower stop-at-punctuation. Replayed through the shipped pass
over every committed day: **27 of the 42 were apart before, 1 after**. The
reasoning, the flowchart of the whole rule, the two headline classes that would
break it, and the guard measurements that say neither fires today are in
[../docs/architecture/publishing/layout.md](../docs/architecture/publishing/layout.md).

**What is still unmeasured is recall** - every number above starts from pairs
found *by* matching headlines, so none of them says anything about same-story
pairs whose headlines differ. Andre named the measurement that would settle it
and it is not code: a blind hand-label of same-day cross-source pairs drawn
without consulting titles.

## 21 - A test walked every published telemetry shard (CLOSED 2026-09-13)

`backend/tests/test_publish_telemetry.py` copied **every** file under
`frontend/public/telemetry/` and ran the migration over all of them, on every
run. Two files and 1,516,467 bytes on 2026-09-13, gaining one file a month.
`CLAUDE.md` section 13 refuses a test that walks a collection the pipeline
appends to.

**It could not simply be bounded, which is why it survived two plans.** The loop
was the only thing in the build that opened every published telemetry file and
checked it still loaded through its contract: `cli._console_payload_faults`
named six producers and `publish_telemetry` was not one of them. Deleting the
loop would have traded a broken rule for a coverage hole.

So the check moved to the producer's own gate, which is where section 13 says
data hygiene belongs, and the test was rebuilt on a projection it writes itself -
carrying an empty month and a one-row month, neither of which the committed
archive has ever produced. The gate's own docstring now names the one directory
whose `keep_months` is declared and not enforced, because a sentence that said
all seven were bounded would have been wrong.

Found by plan 24 row #4 on 2026-09-12 and ruled a row rather than a gap by
Fowler the same day. No row was cut, and
[`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md)
closed with it outstanding.

## 18 - The truncation flag still cannot fire, now for a different reason (OPEN)

Row 16 fed the scorer the real pre-cap body, so `hhem_full` now reads a
different text from `hhem`. The flag built on the gap between them still cannot
fire, and the reason is the aggregation rather than the input.

`score_over_chunks` takes the **maximum** over 900-word windows at a step of
750. The seen text is a prefix of the full text, so the full pass sees the same
first windows, one of them lengthened, plus every window after the cut. A
maximum over a superset cannot be smaller than a maximum over the subset. So
`hhem_full >= hhem` in almost every case, `hhem_delta = hhem - hhem_full` is
zero or negative, and `truncation_flagged = delta > evaluation.truncation_gap_max`
never clears a positive threshold.

Two consequences follow, and only the first is certain:

- The run pays a second cross-encoder pass on every truncated item for a number
  that is negative by construction. At the measured 6.1 percent truncation rate
  that is small, and it is not the argument for changing anything.
- The console's "Article read only in part" counter reads `truncation_flagged`.
  It said **1** when the committed ledger held **157** rows sitting on the cap.
  `Article.truncated` is already persisted and answers that question exactly.

**Why this is not closed by measurement.** No test may fetch the HHEM weights
(Guardrail #7), so the monotonicity claim above is an argument about the aggregation
rather than an observation of the scorer. Confirming it needs a run with the
weights present, and the honest first step is to look at `hhem_delta` on the
rows written since row 16 shipped rather than to reason further.

**The decision, when the evidence exists.** Either the second pass earns its
place under a different comparison, or `truncation_flagged` reads
`Article.truncated`, `evaluation.truncation_gap_max` is deleted as a knob
nothing reads, and the console counter is pointed at the flag that moved. The
second changes what a committed column means and what an operator page reports,
so it is Level 5 and needs an owner ruling before any of it is written.

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

No current threshold has a measured human error rate. Re-cutting the bands is a
Level-5 reader-facing decision, so no threshold moves until the evidence exists
(Guardrail #10).

### The three queue repairs shipped on 2026-08-27

A person could not use the queue. All three gaps are now closed.

- **The labeller was never shown the article.** `state/scores.csv` carries no
  summary text and no source text, so the CLI printed a fallback string on every
  row. The run now writes the exact premise the scorer read, plus the summary,
  to `backend/var/evidence/<date>/`, and the work job uploads it. The CLI shows
  both, and refuses any row whose text does not match its recorded digest. A row
  scored before that column existed is marked not labellable rather than guessed
  at. PR #178 added the `source_digest` column; PR #182 added the package.
- **The draw leaked the score stratum through its order.** `draw()` returned
  rows decile block by decile block, so a labeller working down the queue was
  handed the confidence gradient in order. It now returns one global `label_id`
  sort. Measured over the 38 rows at `draw_id=d1`: 9 runs of equal decile
  before, 28 after. PR #179.
- **A draw could silently mix pipelines.** `eligible()` filtered on
  `scorer_version` only, and warned about mixed fingerprints instead of refusing
  them. Both halves are now required. An empty pool exits non-zero and prints
  every `(scorer_version, pipeline_fingerprint)` pair in the ledger with its row
  count and date range. PR #179.

Measurement corrected one design note. A global hash shuffle removes the
ordering leak but **does not balance a prefix**. Over the same 38 rows the first
ten deciles run 9, 9, 8, 9, 9, 9, 5, 8, 9, 7. Balance holds in expectation, not
per draw, so stopping early gives a roughly balanced sample rather than a
guaranteed one.

### What is left is not engineering

**0 of 60 labels.** No `state/labels.csv` is committed.

**2 of 10 run-days.** The owner settled the counting rule on 2026-08-27: count
run-days at one `scorer_version`, and carry `pipeline_fingerprint` as a reported
stratum rather than a disqualification. The pair rule it replaced was
unreachable - the stamp digests seventeen inputs, so a reworded prompt or a
sanitizer fix reset the count, and no pair ever held for more than three
consecutive run-days. Measured effect on the same ledger: the drawable sample
went from 32 of 60 with seven deciles short to **60 of 60**, over 450 eligible
rows at `hhem-2.1-open@8e4a2e6e`. What it gives up is stated wherever a result
prints: a rate over a pooled draw is a prior with wide bounds, and a stratum
under `evaluation.label_min_stratum_rows` may not move a threshold. The rule,
the rejected freeze and the measured reset rate are stated once, in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).

**The evidence packages are not on this machine.** `label_queue.py` reports
`labellable 0 of 60`: 34 rows have no package here, and 26 predate the
`source_digest` column and can never be proved against their article. The run
writes packages to `backend/var/evidence/<date>/` and the `work` job uploads
them, so a labeller downloads that artifact before starting. Nothing is broken;
the evidence simply lives where the run put it.

Remaining steps, in order:

1. Download the evidence artifact for the run-days in the draw.
2. Draw and label 60 rows, six per HHEM decile. Keep the score, band,
   counterweights, model identity, fingerprint and running tally hidden.
3. Collect the remaining run-days at `hhem-2.1-open@8e4a2e6e`.
4. Re-test the cuts by stratum. Move a threshold only when the labels support
   the new cut, and never on a stratum under the floor.

The canonical measurement contract lives in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 15 | `median()` returned `0` for an empty sample, so all four stage timings lost the difference between "not measured" and "measured as zero" before the chart saw them. `StageTimings.svelte` reconstructed absence from the value, which is a repair on top of a lost fact. | 2026-08-27, PR #180. `median()` returns `null`, `StageTimingDay` carries `number | null`, and the console reads the null directly. Both a missing timing and a real zero are pinned in `frontend/tests/console.spec.ts`. Recorded in [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md). |
| 16 | `dual_score` exists to tell "the model invented something" from "the model faithfully summarized the half we gave it", and its only production caller handed it `article.text` twice. Measured over the whole committed ledger: `hhem_delta` exactly 0.0 on **2,232 of 2,232 rows**. The run also paid for the duplicate pass - about 2 s an item, 21 to 24 minutes of runner wall-clock a day. | 2026-08-27. `extract.to_article_with_source` returns the payload beside the untruncated body; the body stays in the process that extracted it and is never persisted or republished (Guardrail #1). The work stage scores against it, and `dual_score` scores identical texts once. About 97 percent of items are never cut, so most now pay one pass instead of two. Stamped `2026-08-27T20:30` with the read-side rule: a row older than that stamp recorded two scores of one text, so its zero means "never measured". Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 17 | `source_word_count` came from `metrics.word_count(full_text)` and `source_seen_word_count` from `article.word_count` - the **same post-cap string** through two different counters. Read as a truncation signal the pair said 87 percent of items were truncated; the real rate is 6.3 percent. The proof is the impossible direction: `source_seen_word_count` was larger on **590 of 2,232 rows**, which cannot happen when one string is a cut of the other. | 2026-08-27. The column is `Article.source_word_count`, the pre-cap count the payload already carried, so one counter produces both numbers and the difference between them is the cut. An article written before that field existed reports its post-cap count rather than inventing a source length. Stamped `2026-08-27T20:00`. Proved by a test that builds its article through the real extractor, so the pair is a genuine cut. Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 19 | `summarize._failed` never received the `Completion`, so a reply the stage refused wrote a `Summary` whose five cost cells were the model's defaults of zero - and `telemetry`'s failed-summarize branch then passed the three stage timings and none of the five model cells, so the census row carried blanks. `reconcile_prefill.pool_ledger` skips a blank rather than pooling it, so the model server counted those requests and the ledger counted none of them. Measured on the committed ledger 2026-09-13: **93 of 93 failed summarize rows carried no cost at all**, and on run `2026-09-12-34717684802` one refused reply is the whole of that run's disagreement with the server - 72,739 tokens over 3,918.41 s against 73,616 over 3,936.07 s, **0.746 percent apart, one article consuming 15 percent of the 5 percent tolerance.** The two neighbouring runs carry no refused reply and match the server to the token, at 0.051 and 0.070 percent. | 2026-09-13. `_failed` takes the `Completion` and records a `CallCost` from it at all six sites in `to_summary` that hold one; the two that do not - the article never extracted, the model never answered - leave the slot empty, because that null is the real zero and is what a pooled read skips rather than averages in. The census row carries the same five cells and call slots a passing row does. No lenient path: the sum rule on `Summary` and on `ItemHealthRow` binds a failed row exactly as it binds an ok one. Both contracts stamped `2026-09-13T14:20` with the read-side rule - on a failed payload written earlier, a zero or an empty cost cell means never recorded, not free. Recorded in [`docs/architecture/summarize/throughput.md`](../docs/architecture/summarize/throughput.md) and [`docs/architecture/sources/item-health.md`](../docs/architecture/sources/item-health.md). The same sweep found the symptom on the flagged two-call path, in a different function; Fowler refused the widening and it is plan 11 row #3h. |
| 20 | Filed as a fingerprint problem: `npm run test:changed -- --group publishing` passed 72 of 72 tests and exited 1 with `The canary build has stale inputs`, because `frontend/tests/malformed-day.spec.ts` ran `idhazh validate-days` with `--digest-root` at a scratch tree and no `--state-root`, so receipts about those scratch trees landed in the tracked `state/day-validations.csv` that `inputFingerprint` hashes. **Both candidate fixes in the original filing were built on a wrong premise.** The message comes from `assertBuild`, which hashes the **build** fingerprint, so excluding `state/` from the **checks** fingerprint would not have changed the failure at all; and `validate-days` already had the flag the second one proposed to add. The exclusion list has no stated rule but is not arbitrary - read against the code it holds exactly two kinds, a tree the tooling itself writes and prose no program reads, and a ledger the console prerenders from is neither. **The real defect was a correctness one and the dirty file was its shadow.** A receipt records a payload's LENGTH and a day is settled on that length, never on a re-read, so the committed receipts settle a same-length day in any other tree without opening it: measured 2026-09-13, a copy of the newest committed day with `"items"` overwritten by `"itemz"`, one byte for one byte, passed against the committed ledger reporting `0 of them opened`, and was refused against an empty one. The spec's `unbroken` check - which exists because a guard that only ever refuses proves nothing - had stopped proving anything. | 2026-09-13. Neither candidate: the fingerprint was telling the truth and the producer was fixed (Fowler). `validate-days` refuses a `--digest-root` that is not the committed tree unless `--state-root` is named too, so the pairing is enforced rather than remembered, and the spec names a scratch ledger beside each scratch tree. `inputFingerprint`'s list is unchanged and now carries the rule it was always following, in writing, including why a `state/` ledger stays in. Caught next time by an argument-level test in `backend/tests/contracts/` - one fabricated day under `tmp_path`, no archive walk, nothing to age out - and by `changedInputNote`, which makes both stale-input failures name the paths that moved instead of saying only that something did. Recorded in [`CLAUDE.md`](../CLAUDE.md) and [`docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md). Base-tree re-measurement, 2026-09-13: the reported symptom no longer reproduces - 72 of 72 pass and the launcher exits **0** in 269.3 s - because every committed day now has a current receipt, which makes the dirty file latent and the silent skip live. |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the label and calibration contract.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console timing surface defect 15 repaired.
- [`CLAUDE.md`](../CLAUDE.md) - the validation receipt defect 20 pinned to the tree it is about.
- [`docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md) - what a stale-input failure says now that defect 20 is closed.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - how closed rows leave this file.
