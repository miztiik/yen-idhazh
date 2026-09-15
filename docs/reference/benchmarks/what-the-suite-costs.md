# What the test suite spends its time on, 2026-09-14

**Last Updated**: 2026-09-14

Living, one question one answer. The reading below was taken on one day and the
date is in the title; a re-run REPLACES this page and moves **Last Updated**, and
git history holds what it said.

Nothing recorded what the suite costs, so nothing pointed at the tests worth
fixing. `backend/tests/test_marks.py` had grown to 95.6 s without anybody
noticing, and the `slow` marker is declared as a measured property that nobody
measured. This is the standing reading.

## Conditions

| | |
| --- | --- |
| Instrument | `pytest backend/tests -q -n auto --durations=0`, which is what `addopts` now prints a prefix of |
| Runtime | CPython 3.14.2, pytest 9.1.1, pytest-xdist 3.8.0, Windows 11 |
| Box | A developer machine, 12 logical processors. **Seven sibling agent processes were running** |
| Run | One run. 3,407 tests reported a duration, 740 s wall, 5,312 s summed across workers |

**The box was busy, so read the shares rather than the seconds.** Every number
here comes from one run, so a comparison between two rows of it cancels the box.
An absolute second does not, and is high. How high: the same suite on the same
box later the same evening, with the siblings gone and `test_marks` fixed, took
**159.3 s** against this run's 740 s. That is the contention, not the code, and
it is exactly why no threshold belongs anywhere near these numbers.

`--durations` is free. `_pytest.runner.CallInfo.from_call` starts a timer for
every phase of every test whether or not the option is set, and
`pytest_terminal_summary` returns early when it is `None`. Switching it on adds
printed lines and nothing else.

## The cost is far more concentrated than four-fifths from a fifth

| Share of the time | Comes from | Which is |
| ---: | ---: | --- |
| 50% | 46 tests | 1.4% of them |
| 80% | 185 tests | **5.4%** of them |
| 90% | 358 tests | 10.5% |
| 95% | 681 tests | 20.0% |

Four-fifths of the cost sits in one test in nineteen. A fifth of the tests carry
95%. So a pass over the top 200 is the whole of the available win, and a pass
over the other 3,200 is not worth starting.

Of the phases, 4,805 s is `call`, 498 s is `setup` and 9 s is `teardown`. The
4,169 tests under 5 ms are not listed by pytest and sum to at most 21 s, which is
0.4% and changes no row above.

## The ten dearest tests

| Seconds | Share | Test |
| ---: | ---: | --- |
| 160.4 | 3.0% | `test_visual_planner.py::TestTheReachabilityGate::test_the_gate_admits_nothing_the_validator_would_have_passed` |
| 158.0 | 3.0% | `test_retrieval_eval.py::test_the_ranking_clears_its_bar` |
| 137.3 | 2.6% | `test_extract.py::test_the_labelled_short_source_oracle_matches_disposition_and_reason` |
| 130.1 | 2.4% | `workflows/test_worker_ledgers.py::test_every_shard_of_a_full_fan_out_lands_its_rows` |
| 120.5 | 2.3% | `test_summarize.py::test_exactly_one_function_spells_a_llama_server_flag` |
| 115.6 | 2.2% | `retention/test_score_ledger.py::test_a_score_month_past_the_window_is_summarised_and_then_deleted` |
| 108.2 | 2.0% | `test_entity_gap.py::test_two_runs_over_one_tree_print_the_same_bytes` |
| 95.6 | 1.8% | `test_marks.py` - **fixed on this date, see below** |
| 90.4 | 1.7% | `workflows/test_commit_script.py::test_the_day_publishes_when_origin_moved_under_it` |
| 86.2 | 1.6% | `test_ledger.py::test_load_published_costs_the_answer_and_not_the_file` |

## The ten dearest modules

| Seconds | Share | Module |
| ---: | ---: | --- |
| 509.0 | 9.6% | `workflows/test_commit_script.py` |
| 464.4 | 8.7% | `retention/test_score_ledger.py` |
| 372.4 | 7.0% | `test_plan.py` |
| 302.1 | 5.7% | `test_console_payloads_producer.py` |
| 301.1 | 5.7% | `test_retrieval_eval.py` |
| 267.8 | 5.0% | `test_ledger.py` |
| 218.3 | 4.1% | `pipeline/test_publish_window.py` |
| 178.1 | 3.4% | `workflows/test_worker_ledgers.py` |
| 174.6 | 3.3% | `retention/test_visual_pruning.py` |
| 166.0 | 3.1% | `test_visual_planner.py` |

## The `slow` mark disagrees with the suite half the time

`pyproject.toml` declares `slow` as "a module whose average test takes over a
second". That is a measurable property, and it was never measured.

| State | Modules |
| --- | ---: |
| Over 1 s a test and **not** marked `slow` | 17 |
| Marked `slow` and **under** 1 s a test | 19 |
| Marked `slow` and over 1 s a test | 19 |

**Thirty-six of the seventy-four classified modules are wrong.**
`test_console_payloads_producer.py` runs at 8.63 s a test with no mark at all.
`pipeline/test_banding.py` runs at 0.08 s a test and carries `slow`.

Half of the second row is self-inflicted. Before
[#720](https://github.com/miztiik/yen-idhazh/pull/720) split it,
`test_workflows.py` carried `[workflow, slow]` as one module. The split gave all
13 workflow modules that same `pytestmark`, and only 3 of them earn `slow`. A
module-level mark travels with the module, which is the property that makes the
mark cheap - and it is also what let one correct mark become 13, of which 10 are
wrong. Correcting them is not in this reading.

## What this reading already changed

`test_marks.py` bought its answer with a subprocess that collected the whole
suite - 29.2 s for the answer, 95.6 s of reported test time, to defend a
developer shortcut that never gates a merge. It now reads the module-level
`pytestmark` off 131 files with `ast`, which is **1.89 s**, and it is held to the
same answer: the same 53 unmarked modules and the same 33/38/7/14 modules a mark.

## Non-goals of this reading

- **No threshold, and no gate.** CI's own suite duration on 2026-09-14 spread
  62.9 s to 85.4 s over seven runs. An effect under a second cannot be judged
  against a 22 s spread, so a rule that fails a build on a duration would fail on
  the runner rather than on the code.
- **Nothing about the frontend suites.** Playwright is measured by its own
  reporter and is not in this run.
- **No claim that a dear test is a bad test.** Several of the dearest are the
  oracles that hold a whole subsystem. This says where the time is, not where the
  waste is.

## See also

- [`../measurements.md`](../measurements.md) - the instrument log, which carries the figure now in force and links here.
- [`../test-execution-audit.md`](../test-execution-audit.md) - which tests were run unnecessarily, a different question from what they cost.
- [`../../how-to/run-the-gates.md`](../../how-to/run-the-gates.md) - the commands, and which arm is authoritative.
