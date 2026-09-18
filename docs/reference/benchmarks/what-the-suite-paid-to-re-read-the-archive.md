# What the suite paid to re-read the archive

**Last Updated**: 2026-09-18
What the test suite spent walking the committed archive, and which job is the
critical path once that walk is gone. The record behind Guardrail #12.

Toolchain: Python 3.14.2, node 24.12.0. Runner
figures are `ubuntu-latest`, 4 vCPU (Guardrail #2), and say so. The archive at the
time: **16 committed days and 6,539 stories**, growing by about 400 stories a
day.

This is the record behind Guardrail #12 and behind the three paragraphs
[../../CLAUDE.md](../../CLAUDE.md) section 13 gained on 2026-09-06. The rule is
about cost, not correctness: every check here passed on every run.

### The critical path was one job, and the archive was not most of it

CI medians over six runs on `main`, 2026-09-05:

| Job | Median |
| --- | ---: |
| `browser` | **462 s** |
| `whole-day` | 150 s |
| `gates` (the entire backend suite is 63 s of it) | 106 s |
| `site` | 83 s |
| `robots` | 38 s |
| `scope` | 10 s |

`browser` is the critical path and the backend is not, which is why **deleting
backend tests buys about zero wall clock** and was not done for speed. After the
work, on `0ea12c6`: browser 267 s, whole-day 158 s, gates 97 s, site 81 s,
robots 36 s, scope 17 s. **Browser went 462 s to 267 s - 42 percent faster** -
and that run still ran the console specs, because the pull request touched the
harness that chooses. An ordinary reader-side change skips them.

### Reading the tree is cheap; asserting once per story is not

Measured 2026-09-05 over the 16 days and 6,539 stories:

| Work | Seconds |
| --- | ---: |
| Read and parse the whole committed tree | **0.15** |
| Call the function under test on every story | 0.02 |
| The two specs that assert once per story | **270** and **93** |

Almost none of it is the archive. It is the assertion machinery, run tens of
thousands of times to re-establish a handful of cases. **It also does not
saturate**: those 6,539 stories carry six distinct combinations of `time_source`
and printed form, so story 6,539 exercises what story 12 did. The cost compounds
and the coverage does not.

### What the migration removed

A tracking list, `ARCHIVE_READERS`, counted the tests that still walked the
committed tree. **It went from 22 entries to 12** over this work. The guard that
held it, `backend/tests/test_archive_readers.py`, was deleted on 2026-09-06 -
it enumerated two collections out of nineteen, and its own upkeep grew with the
rest - so 12 is the last count anything took, not a live figure.

| Change | Before | After |
| --- | --- | --- |
| `backend/tests/workflows/` | 121 tests, 146.0 s | 99 tests, 106.5 s |
| `test_labels.py`, the determinism test | 1.81 s | **0.04 s** |
| `test_labels.py`, the pooled-draw tool test | 0.64 s | 0.03 s |
| The eval ledger those tests read | 6,966 rows over 15 days | 80 built rows |
| The same-story oracle day | 1,041.9 KB, deleted by retention | **280.6 KB, frozen** |

The eval ledger grew by about **465 rows a day**, and eighteen call sites in one
file re-read and re-drew over all of it. The built world is 80 rows for ever and
carries two states the archive cannot be relied on to hold: a decile with fewer
rows than the draw asks for, and a second pipeline at the live scorer.

The frozen oracle keeps only the four fields the grouping reads - `item_id`,
`source_id`, `rank_score`, `introduced_by_run` - and every vector: 431 stories
over 64 sources. No title and no summary, so no article text enters the
repository for a page that will never render it (section 0a).

### Eight walks carried a fuse, and the fuse had a date on it

Eight of the migrated tests counted how many committed entries still **lack** a
migrated field and asserted the count was not zero. Each one goes red on the day
the last unmigrated payload ages out of retention - a date on the calendar
rather than a change anybody made, and it takes every open pull request with it.
Three of the eight were also exact duplicates of the test directly above them.

### The runner and the laptop disagree about parallelism, and the laptop lies

Four Playwright workers, measured 2026-09-05 on runs `33989034726` and
`33991122503`:

| Machine | One worker | Four workers | Change |
| --- | ---: | ---: | --- |
| Runner, 4 vCPU, nothing else on it | 344 s | 207 s | **40 percent faster** |
| a shared developer box, six other checkouts building | 135.5 s | 233.7 s | **72 percent slower** |

Both cases passed all 268 tests, so the local result reads as a clean measurement
of a regression that is not there. Two performance cores shared with six sibling
agents have no spare capacity to hand a second worker. The knob is
`PLAYWRIGHT_WORKERS` and the figure that decides it is the runner's.

Enabling it first needed two races fixed, both invisible at one worker:
`service-worker.spec.ts` rewrote a kill switch while `reading-page.spec.ts`
installed the worker that obeys it, and two console specs shared one scratch
file path.

### Checking the days a change can break

`idhazh validate-days` costs **0.27 s per published day**, so the 16 committed
days are 6.6 to 7.1 s and a year of them would be about 100 s on every run. The
`scope` step decides: a push to `main` and any change to the contracts, the
tooling or a committed payload opens every day; every other pull request opens
none.

### What this did not do

The backend suite is 63 s of a 106 s job and was never the critical path, so
none of this was done to make it faster. It was done because the cost grows with
the corpus and the coverage does not. The whole backend suite still runs on
every change.

## See also

- [../measurements.md](../measurements.md) - the figure this record puts in force, beside every other producer figure.
- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries, and why a re-run replaces it.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, which is why every number here carries its conditions.
