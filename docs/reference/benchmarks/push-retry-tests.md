# What the push retry tests cost

**Last Updated**: 2026-10-04

What changing the retry wait settings removes from the real-Git tests, and
what one local duration run can establish.

## Method and conditions

The baseline is the user's supplied `pytest --durations` reading from a shared
development box. Its interpreter, hardware and concurrent load were not
recorded. It was not repeated.

The after reading is one serial run on Windows 11, Python 3.14.2, an Intel
Core i7-1265U with 10 cores and 12 logical processors, and 31.8 GiB RAM.
The invocation required the shared gate lock; it did not isolate the machine
from other work. All 82 tests passed in
478.09 seconds. The full application suite was not run locally.

```powershell
$env:GIT_CONFIG_COUNT = '0'
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
python backend/utilities/gate_lock.py --require-lock --retry-every 0.25 --timeout 7200 -- python -m pytest -n 0 backend/tests/workflows/test_commit_script.py backend/tests/workflows/test_daily_commit_steps.py --durations=25
```

Use an environment with the project's development dependencies installed.
The harness reads the committed retry config, writes a private copy with a
3 ms base step and a 24 ms ceiling, and passes it through `PUSH_RETRY_CONFIG`.
The seeded test origin commits the same copy as `config/push-retry.json`, so a
caller that resolves the checkout's own file, such as `publish_inputs`, waits
the same milliseconds. Git commands, producers and sleeps are real. The deadline-exhaustion case uses
50 ms in `deadline_seconds.default`; successful retry cases retain the
production deadline. Deadlines are selected by workflow job id from the
`deadline_seconds` map, with its `default` entry used for other jobs.

## Current readings

Table A reports pytest's call phase, in seconds. Rows A1-A6 are in
`backend/tests/workflows/test_commit_script.py`; A7 is in
`backend/tests/workflows/test_daily_commit_steps.py`.

| Id | Test | User-supplied baseline (s) | After (s) |
| --- | --- | ---: | ---: |
| A1 | `test_the_day_publishes_when_origin_moved_under_it` | 80.29 | 47.12 |
| A2 | `test_two_runs_that_rendered_one_item_still_publish_the_day` | 73.19 | 43.00 |
| A3 | `test_a_rebuild_that_fails_spends_the_attempts_and_says_which` | 59.73 | 27.13 |
| A4 | `test_a_push_rejected_more_times_than_the_old_loop_allowed_still_lands` | 36.67 | 9.96 |
| A5 | `test_a_new_file_in_a_drained_directory_still_rebases` | 18.43 | 16.25 |
| A6 | `test_the_commit_step_pushes_what_it_staged[assemble]` | 14.15 | 7.43 |
| A7 | `test_two_runs_that_conflict_each_keep_the_file_they_wrote` | 19.60 | 35.72 |

These are not paired measurements under the same load. Six rows took less time
and one took more, so this reading cannot attribute an overall speed change
to the retry settings.

What the change does prove is narrower: four rejected pushes now request
22.5-67.5 ms of sleep, rather than 7.5-22.5 seconds, with the same jitter
distribution. The remaining Git and producer work is unchanged. The failed
rebuild already stopped after one rejected push; the test now asserts that
count. The harness already shares seed origins, so its clone strategy was not
changed without evidence that another change would help.

## See also

- [../../architecture/publishing/committing.md](../../architecture/publishing/committing.md) - production retry settings and failure behavior.
- [../agent-notes.md](../agent-notes.md#git-fixtures-and-child-producers) - the two environment settings needed by the fixture command.
