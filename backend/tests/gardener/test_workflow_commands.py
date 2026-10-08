"""Which workflow commands does GitHub read beside each gardener event, and does each stay on its line?

GitHub reads a command from any line of a step's output that starts with `::`.
A command is text by definition - GitHub reads the text - so these tests read
the lines `workflow_commands.around` hands the event log, never an event's
payload.
"""

from __future__ import annotations

from typing import Any, Final

import pytest

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.gardener_events import (
    RawFileSkipped,
    ShardPublished,
    ShardStop,
    TaskFinished,
    TaskOutcome,
    TaskPlanned,
)
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import report
from idhazh.gardener.outcome import EXIT_OK, EXIT_PUSH_REFUSED, MEANS
from idhazh.gardener.workflow_commands import around, escaped_data, escaped_property

RUN_ID: Final = "2026-10-08-18012345678"
RECORD: Final = "state/raw/gardener/2026/10/08/0b6f8a52-4f0e-4c55-9a7a-3d1b2c9e7f10.parquet"


def a_failure(**changed: Any) -> TaskFinished:
    """A task a code defect stopped while it worked on one day."""
    said: dict[str, Any] = {
        "task": "defect",
        "outcome": TaskOutcome.FAILED,
        "dry_run": False,
        "seen": 0,
        "selected": 0,
        "taken": [],
        "written": [],
        "bytes_freed": 0,
        "stopped_because": StopReason.FAILED,
        "resume_from": "2026-09-20",
        "fault": GardenerFault.RAISED,
        "error": "KeyError",
        "where": "idhazh.gardener.runner:302",
        "recovered": [],
        "next": report.WHY[GardenerFault.RAISED],
        "duration_ms": 4,
    }
    return TaskFinished.model_validate({**said, **changed})


def a_shard(landing: ShardLanding, **changed: Any) -> ShardPublished:
    """A shard of one task whose commit came to rest on main as `landing` on its last try."""
    said: dict[str, Any] = {
        "shard": 0,
        "run_id": RUN_ID,
        "attempt": 1,
        "tasks": ["old-days"],
        "failed_tasks": [],
        "landing": landing,
        "push_try": 6,
        "push_tries": 6,
        "record": RECORD,
        "max_downloaded_mb": 128,
        "exit_code": EXIT_OK,
        "means": MEANS[EXIT_OK],
    }
    return ShardPublished.model_validate({**said, **changed})


def test_a_task_s_lines_fold_into_one_group_named_for_the_task_and_its_kind() -> None:
    planned = TaskPlanned(
        task="compact-gardener",
        kind=TaskKind.COMPACTION,
        shard=0,
        run_id=RUN_ID,
        attempt=1,
        today="2026-10-08",
        operator_range=None,
        declared={},
        absent=[],
    )
    done = a_failure(
        outcome=TaskOutcome.DONE,
        stopped_because=StopReason.EXHAUSTED,
        resume_from=None,
        fault=None,
        error=None,
        where=None,
        next=report.NEXT[TaskOutcome.DONE],
    )

    assert around(planned) == (("::group::compact-gardener (compaction)",), ())
    assert around(done) == ((), ("::endgroup::",))


def test_a_failed_task_adds_one_error_after_its_group_naming_its_fault_and_its_place() -> None:
    """After the group, so it shows while the group is folded; the event's own `next` ends it."""
    assert around(a_failure()) == (
        (),
        (
            "::endgroup::",
            "::error title=defect::raised while it worked on 2026-09-20 (KeyError at "
            "idhazh.gardener.runner:302): a code defect stopped it, and the log names the error",
        ),
    )
    _, (_, bare) = around(a_failure(resume_from=None, where=None))
    assert bare == (
        "::error title=defect::raised (KeyError): a code defect stopped it, and the log names "
        "the error"
    )
    _, (_, unnamed) = around(a_failure(fault=None, error=None, where=None))
    assert unnamed.startswith("::error title=defect::failed while it worked on 2026-09-20: ")


def test_an_error_line_escapes_percent_cr_and_lf_so_nothing_in_it_starts_a_command() -> None:
    """THE ORACLE for the error line: what follows a break would be a command of its own."""
    injected = a_failure(next="100% done\r\n::warning::not ours")

    _, (_, line) = around(injected)

    assert "\r" not in line and "\n" not in line
    assert line.endswith(": 100%25 done%0D%0A::warning::not ours")
    assert escaped_data("a:b,c%\r\n") == "a:b,c%25%0D%0A"
    assert escaped_property("a:b,c%\r\n") == "a%3Ab%2Cc%25%0D%0A"


def test_a_shard_main_moved_past_warns_and_a_shard_that_landed_or_was_refused_does_not() -> None:
    """Only `stale` and `lost` warn: a refused push is red, and the summary says why."""
    stale = a_shard(ShardLanding.STALE, push_try=1, stale_paths=["state/a", "state/b"])
    alone = a_shard(ShardLanding.STALE, push_try=1, stale_paths=["state/a"])

    assert around(stale) == (
        (),
        (
            "::warning title=shard 0::stale - main changed state/a and 1 more after the commit "
            "this shard ran on, so nothing landed. The next wake does the work again",
        ),
    )
    assert around(alone)[1][0].startswith("::warning title=shard 0::stale - main changed state/a ")
    assert around(a_shard(ShardLanding.LOST)) == (
        (),
        (
            "::warning title=shard 0::lost - all 6 tries failed, and main changed during the "
            "last one, so other writers were landing first. Nothing landed; the next wake does "
            "the work again",
        ),
    )
    assert around(a_shard(ShardLanding.LANDED, push_try=1)) == ((), ())
    refused = a_shard(
        ShardLanding.REFUSED, exit_code=EXIT_PUSH_REFUSED, means=MEANS[EXIT_PUSH_REFUSED]
    )
    assert around(refused) == ((), ())


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(RawFileSkipped(path="state/raw/x/notes.txt"), id="a-compaction-event"),
        pytest.param(
            a_failure(
                outcome=TaskOutcome.DEFERRED,
                stopped_because=StopReason.DEFERRED,
                fault=GardenerFault.API_UNAVAILABLE,
                next=report.WHY[GardenerFault.API_UNAVAILABLE],
            ),
            id="a-deferred-task-closes-its-group-and-adds-nothing",
        ),
        pytest.param(
            ShardPublished(
                shard=0,
                run_id=RUN_ID,
                attempt=1,
                tasks=["old-days"],
                failed_tasks=[],
                stopped_because=ShardStop.CHECK_REFUSED,
                push_tries=6,
                max_downloaded_mb=128,
                exit_code=2,
                means=MEANS[2],
            ),
            id="a-shard-a-check-refused",
        ),
    ],
)
def test_no_other_event_adds_a_command_beyond_closing_its_group(event: Any) -> None:
    before, after = around(event)

    assert before == ()
    assert all(line == "::endgroup::" for line in after)
