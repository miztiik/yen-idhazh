# Test Selection

**Last Updated**: 2026-10-11

Why a pull request runs only some of the tests, what that choice gives up, and
what was rejected on the way to it. The commands, the groups and the current
truth table are in [../how-to/run-the-gates.md](../how-to/run-the-gates.md);
this page is the argument behind them.

## A suite gets expensive in two ways, and only one of them is selection

**Running tests a change cannot break.** `ciAnswer` in
`frontend/scripts/test-scope.ts` selects the extra native, frontend logic and
tooling checks. The local selector names the affected browser groups.

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
Ledger import-order tests start a fresh interpreter for each order; they do not
parse every package module to infer whether imports work. Budget-test config
copies include only the model file selected by `idhazh.json`, not every model
config stored beside it.
Published-ledger tests check the answer and the named months requested by the
real reader. They do not gate a merge on Python allocation peaks: two unchanged
CI runs exceeded the old 10 percent margin without proving retained history.
The repeated-address case uses two addresses across two months, not a memory
benchmark with repeated reads.

**A fixed fixture can still do needless work.** Per-item pipeline record and
run-metadata tests limit the recorded plan to one item. Continuing after a
failure, ordering and sibling totals need two. The
timeout test keeps a real socket timeout of 60 ms; the stopwatch test keeps a
real server wait of 50 ms. Both exercise the production path without changing
production timeouts. Longer waits and unrelated items add cost, not coverage.
Browser coverage follows [CLAUDE.md section 13](../../CLAUDE.md#13-test-coverage-policy):
a very narrow representative set of real journeys and independent runtime
boundaries. A shared component does not gain coverage by being checked at every
caller. Do not multiply cases by width, theme, chart or state, or move incidental
geometry and wording assertions wholesale into lower-tier tests.

## What local selection covers

**Panel rules run below the browser.** The panel browser group and bulk
capture generator are deleted, not parked behind a dispatch flag. Shared layout
and live chart interaction are covered once by representative journeys.

**Route-owned config selects the console, not every group.** Each named file
under `config/console/` selects `logic`, `console` and `publishing`.
Mixed edits keep the union of their groups, and unknown paths still select
full frontend coverage locally. Both slash conventions produce the same answer.

The extracted `tests/support/console-expect/` files are also console-owned
inputs. Editing route-owned expectations alone selects local console checks,
just as editing the original spec does. There is no per-panel driver registry
to maintain.

The bounded `tests/support/console-window/` helpers are also console-owned.
Both Windows and normalized paths select logic, console and publishing
checks, so changing only a fixture or compiler helper cannot leave its
consumers untested. Focused window specs are named in `test-groups.ts`; the
console-name fallback does not register a spec. Each new spec has an explicit
registration test. Config and fixture inputs load inside tests or their helpers,
not when a module is imported.

Judgement evidence semantics are integration checks over real packed readers
and rendered Svelte components. They do not receive special private site builds
or browser width/theme/state sweeps. The ordinary site build proves packaging;
the on-demand console journey proves shared layout and interaction.

**The explicit inventory registers every retained spec.** There is no test
requiring each route to acquire a separate browser driver or expectation folder.
A new browser case must protect a distinct failure mechanism before it joins
`frontend/scripts/test-groups.ts`. The one Voices journey checks that changing
the window keeps native panel readings and feed-evidence counts available;
the feed, source and retirement rules remain deterministic logic tests.

**A path filter is not a dependency map.** Shared styles, layouts and frontend
dependencies reach the console without naming it, and the boundary is crossed in
the other direction too - a browser spec that shells out to a Python command is
checking both halves. A directory split cannot decide which tests a change
needs, so a new dependency between areas owes a selector regression test rather
than only a new group label.

**Ledger-query helpers have a local mapping.** Changes under
`frontend/src/lib/data/` select `logic`, `console` and `publishing`.
This keeps the ledger query checks and console consumers, without selecting
the reader, offline, archive and model-search groups for a data-only change.
A new consumer outside those groups needs a mapping update and a regression
test. Mixed edits still select the union of their groups.

**An unclassified path falls to broad local coverage on purpose.** A selector that
guesses narrow on a path nobody listed fails silently, and it fails in the
direction that loses coverage.

**A backend module with no mapped tests selects the whole backend suite
locally.** Contracts select both backend and frontend groups since both
read those shapes.

**A utility that nothing else runs selects only its own test module.** No
stage, build or workflow imports or runs `backend/utilities/doc_load.py`, so a
change to it selects `backend/tests/test_doc_load.py` and no browser. The list
is closed and lives in `UTILITY_TESTS` in `frontend/scripts/test-scope.ts`. A
utility that something else reaches, such as the canary day's builder, stays
off it and falls to full coverage.

## Design rationale

The suite proves representative behaviour and distinct runtime
boundaries, not every presentation combination. Exhaustive cosmetic and
interaction-permutation coverage is deliberately removed. Running the same
matrix in parallel, below the browser or nightly would retain the waste.

Pictures are design-review material, not pixel-comparison checks. The later
representative-coverage decision also removed the bulk capture generator:
keeping the presentation matrix opt-in would retain its maintenance cost.
Routine CI runs one real build and reader smoke, not the canary build or
browser suites. The trade-off is no automatic browser verdict for console,
offline, model-search, or hostile-input rendering. See
[run the gates](../how-to/run-the-gates.md#one-real-site-build) for the current
boundary and on-demand checks.
Build-independent machine arithmetic and token checks are assigned to `logic`
by the named inventory, not by a `console-` filename prefix. This retains useful
rules while removing browser preparation from edits confined to those specs.
Logic tests generate their own temporary inputs; build-output gates remain
after the build. They never borrow artifacts from a previous local run.
Date-axis spacing, compression-row placement, model-day counts and readout-data
checks have focused logic specs with their original assertions. They share the
existing telemetry-row fixture builder and a consecutive-UTC-days helper with
the browser checks. A change confined to one of these specs needs no build or
browser. Changes to their chart and server modules still select logic and
browser consumers through the shared-frontend mapping.
Machine-ledger tests compare a populated fixture root with an empty root, then
read the populated root again. This checks that a reader neither falls back to
the archive nor reuses another root's rows. They do not require a function call
to have one spelling. Day-split tests compare the seed and remainder directly
with the original stories; no unused reconstruction helper is kept for tests.
The console spec's empty `package.json` `dependencies` assertion did not measure
browser code. The existing bundle gate still checks first-load encoders and the
configured gzip limits for routes and fetched payloads; no test requires
`dependencies` to be empty.

## Rejected alternatives

| Rejected | Why |
| --- | --- |
| Moving the full browser suite to a nightly job | It still needs a second build, all fixture preparation, and a separate runner. Run the relevant cases on demand. |
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
