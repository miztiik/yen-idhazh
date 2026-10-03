# Test Selection

**Last Updated**: 2026-09-29

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

**The panel pictures and gates are bought by a wider set than the console.** The
`panels` group - a picture of every console panel at three widths in both themes,
and the sufficiency gates a selector can decide - is two spec files, so a pull
request buys it whenever it buys the console and also for anything every panel is
drawn from: the panel frame and readout strip, the chart modules, the stylesheets
and tokens, `config/appearance.json`, and the pictures' own specs, fixture and
helpers. Those are the edits that move every picture at once, and a reviewer
approving one needs the pictures on the pull request, not after the merge. The
cost is the group's own run time on those pull requests, recorded in
[../how-to/run-the-gates.md](../how-to/run-the-gates.md).

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

## Rejected alternatives

| Rejected | Why |
| --- | --- |
| A nightly job for the deferred console specs | A second copy of the browser job is a second thing to keep correct, and a `main` push carrying code already runs every group. |
| The panel pictures following the console's own answer | One answer fewer to keep in step, but a token, chart, readout or appearance edit - the kind that moves every panel picture at once - would be pictured only on the merge push, after a reviewer had approved it without seeing it (Susan, 2026-09-28). |
| A guard listing the paths a test may not read | Written and deleted the same day; the reasoning is in [../concepts/growing-reads.md](../concepts/growing-reads.md). Guardrail #12 is stated as a property instead and review is the control. What that costs: nothing fails automatically, so a growing step can merge if nobody asks. |
| Treating the shared gate lock as a result cache | It only caps how many callers run at once across worktrees and knows nothing about what ran. Two workers can still do identical work. |
| Trusting a cached green step without its executed-test count | Collected output is not executed-test evidence, and a run that collected nothing has the same shape as a suite that passed. |
| Deleting backend tests to make CI faster | It buys close to zero wall clock, and it pays for that with coverage of the half that is cheap to check. |
| Splitting tests by directory instead of by dependency | The union of groups can be complete while the mapping from a changed file to those groups is still wrong, and only the second one decides what runs. |

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the commands, the groups, and what each CI answer decides.
- [../../CLAUDE.md](../../CLAUDE.md) - section 13 on the four test tiers and what a test may read, and Guardrail #12.
- [../concepts/growing-reads.md](../concepts/growing-reads.md) - the deleted guard, and why the rule is a property rather than a list.
- [benchmarks/what-the-suite-costs.md](benchmarks/what-the-suite-costs.md) - where the suite spends its time.
- [benchmarks/what-the-suite-paid-to-re-read-the-archive.md](benchmarks/what-the-suite-paid-to-re-read-the-archive.md) - what the growing reads cost, and what removing them returned.
- [agent-notes.md](agent-notes.md) - the traps that make a test command lie about its result.
