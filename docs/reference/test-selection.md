# Test Selection

**Last Updated**: 2026-10-03

Why a pull request runs only some of the tests, what that choice gives up, and
what was rejected on the way to it. The commands, the groups and the current
truth table are in [../how-to/run-the-gates.md](../how-to/run-the-gates.md);
this page is the argument behind them.

## A suite gets expensive in two ways, and only one of them is selection

**Running tests a change cannot break.** One function answers this - `ciAnswer`
in `frontend/scripts/test-scope.ts` - rather than a rule repeated in each
workflow, because a second place to decide is a second place to be wrong.

**A test whose cost rises because a run appended data.** This is the one that
compounds. The test re-reads a collection that grows every four hours while its
coverage stays the same, so nobody watches the bill arrive and no diff shows it
growing. It became [CLAUDE.md](../../CLAUDE.md) Guardrail #12 and section 13,
and it is why a per-item rule is driven from a fixture rather than from a loop
over whatever the archive happens to hold.

Gardener integration fixtures copy the declarations named in
`backend/tests/gardener/_garden.py`, and import its named task modules.
Adding an unrelated declaration or source module does not expand those inputs.
Full shard and fold-landing fixtures copy those named real task sources into a
temporary package, so discovery reads only the package the test built.
The producer's preflight still checks its live registry. Council command-line
fixtures copy the five config inputs and the active model file, not `config/`.
Their static import check reads the named inputs in `council/_imports.py` and
refuses an unlisted dependency before opening it.
Visual-retention fixtures use sparse boundary days and a two-file deletion cap,
so month and year skipping and an unfinished deletion run need no large archive.

**A fixed fixture can still do needless work.** Per-item pipeline record and
run-metadata tests limit the recorded plan to one item. Continuing after a
failure, ordering and sibling totals need two. The
timeout test keeps a real socket timeout of 60 ms; the stopwatch test keeps a
real server wait of 50 ms. Both exercise the production path without changing
production timeouts. Longer waits and unrelated items add cost, not coverage.

**The second one was the larger cost, and selection would not have touched it.**
The browser job is the critical path and the backend suite is small beside it
([benchmarks/what-the-suite-paid-to-re-read-the-archive.md](benchmarks/what-the-suite-paid-to-re-read-the-archive.md)),
so deleting backend tests buys close to zero wall clock. Selection was worth
doing for the browser suite and for nothing else.

## What the selection gives up

**A pull request defers the operator console's specs** unless the change is the
console's own, or the harness that chooses. They are most of the browser suite,
and the console is a page one operator opens rather than anything a reader is
served. The cost, stated rather than implied: a shared component or a token edit
that breaks the console is found on the merge push to `main`, not on the pull
request that caused it.

**Panel sufficiency checks use a wider selection than the console.** They run
for panel frames, readout strips, chart modules, styles, appearance config and
their own fixtures and helpers. Bulk review pictures are explicit instead:
dispatch CI with `panel_captures=true` on the branch being reviewed.
Routine runs no longer supply those pictures automatically. Browser assertions
and sufficiency checks still run when selected.

**A path filter is not a dependency map.** Shared styles, layouts and frontend
dependencies reach the console without naming it, and the boundary is crossed in
the other direction too - a browser spec that shells out to a Python command is
checking both halves. A directory split cannot decide which tests a change
needs, so a new dependency between areas owes a selector regression test rather
than only a new group label.

**Ledger-query helpers have a local mapping.** Changes under
`frontend/src/lib/data/` select `logic`, `console`, `panels` and `publishing`.
This keeps the ledger query checks and console consumers, without selecting
the reader, offline, archive and model-search groups for a data-only change.
A new consumer outside those groups needs a mapping update and a regression
test. Mixed edits still select the union of their groups. The pull-request
deferral above and full coverage on a code push to `main` do not change.

**An unclassified path falls to full coverage on purpose.** A selector that
guesses narrow on a path nobody listed fails silently, and it fails in the
direction that loses coverage.

**A backend module with no mapped tests buys the whole backend suite and no
browser** on a pull request. This covers every `backend/idhazh/` Python file
outside `contracts/`. The browser reaches backend code only through the canary
build, and buying the build and every group for each backend edit made most
backend pull requests wait on the browser job. The cost: a backend change that
breaks a published page is found on the merge push to `main`, which still runs
every group. A contract keeps full coverage, because it is the shape both halves
read.

## Design rationale

The owner approved removing routine bulk panel captures on 2026-10-03.
Pictures are review material, not pixel-comparison checks. Keeping their explicit
review path retains that material without charging every routine run for it.
The second model-absent build remains on code pushes to `main` and on pull
requests that can change asset loading. Skipping unrelated PR inputs defers no
model-asset check that those inputs can change. Unknown inputs still buy it.
Individual browser durations are retained in the `browser-results` artifact so
the next reduction can use measured costs rather than test counts.
Build-independent machine arithmetic and token checks are assigned to `logic`
by the named inventory, not by a `console-` filename prefix. This retains every
assertion while removing browser preparation from edits confined to those specs.
Tests that inspect built documents or packed canary ledgers still need their build.
Machine-ledger tests compare a populated fixture root with an empty root, then
read the populated root again. This checks that a reader neither falls back to
the archive nor reuses another root's rows. They do not require a function call
to have one spelling. Day-split tests compare the seed and remainder directly
with the original stories; no unused reconstruction helper is kept for tests.

## Rejected alternatives

| Rejected | Why |
| --- | --- |
| A nightly job for the deferred console specs | A second copy of the browser job is a second thing to keep correct, and a `main` push carrying code already runs every group. |
| A guard listing the paths a test may not read | Written and deleted the same day; the rule is now stated directly in [../../CLAUDE.md](../../CLAUDE.md) Guardrail #12 and section 13. What that costs: a regression can still merge if no check catches it. |
| Treating the shared gate lock as a result cache | It only caps how many callers run at once across worktrees and knows nothing about what ran. Two workers can still do identical work. |
| Trusting a cached green step without its executed-test count | Collected output is not executed-test evidence, and a run that collected nothing has the same shape as a suite that passed. |
| Deleting backend tests to make CI faster | It buys close to zero wall clock, and it pays for that with coverage of the half that is cheap to check. |
| Splitting tests by directory instead of by dependency | The union of groups can be complete while the mapping from a changed file to those groups is still wrong, and only the second one decides what runs. |

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the commands, the groups, and what each CI answer decides.
- [../../CLAUDE.md](../../CLAUDE.md) - section 13 on the four test tiers and what a test may read, and Guardrail #12.
- [../../CLAUDE.md](../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [benchmarks/what-the-suite-costs.md](benchmarks/what-the-suite-costs.md) - where the suite spends its time.
- [benchmarks/what-the-suite-paid-to-re-read-the-archive.md](benchmarks/what-the-suite-paid-to-re-read-the-archive.md) - what the growing reads cost, and what removing them returned.
- [agent-notes.md](agent-notes.md) - the traps that make a test command lie about its result.
