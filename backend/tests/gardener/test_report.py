"""Does a task end on the right word, say what happens next, and never say a dry run deleted anything?

`classify` reads a pass for the one word a person acts on: a fault first, then
work only reported, then the ceiling, then work done, then the pass's own idle
word. A dry run deletes nothing, so no sentence it gets may say a member is
gone, and the switch it names has to exist: the gardener takes no
`--no-dry-run`, and a task runs live when its own declaration says
`dry_run: false`. A pass a fault stopped is told its fault's own sentence.

`finished` is the event the runner logs for a task: the pass's own fields, its
fold, and the exception that stopped it named by type and place, never by text.

Every pass here is a real `Pass`, built whole the way a task hands one to the
runner. The report reads nothing else, so nothing else is built.
"""

from __future__ import annotations

import dataclasses

import pytest

from idhazh.contracts.collection_prune import Recovery, StopReason
from idhazh.contracts.gardener_events import TaskOutcome
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.gardener import report
from idhazh.gardener.closed_day_fold import Folded
from idhazh.gardener.one_at_a_time import Pass, Window

pytestmark = pytest.mark.contract

#: Three run ids, oldest first, in the order a pass takes them.
TAKEN = ("18000000001", "18000000002", "18000000003")
#: The run a pass stopped at, or failed at.
NEXT = "18000000004"
#: The setting that makes a task live, in the file that holds it.
SETTING = "dry_run: false in config/gardener/<task>.json"

#: The fault each stop that has one carries, unless a case names another.
NATURAL_FAULT = {
    StopReason.FAILED: GardenerFault.RAISED,
    StopReason.DEFERRED: GardenerFault.API_UNAVAILABLE,
}


def a_pass(
    *,
    dry_run: bool,
    stopped_because: StopReason,
    resume_from: str | None = None,
    taken: tuple[str, ...] = TAKEN,
    recovered: tuple[Recovery, ...] = (),
) -> Pass:
    """A pass over workflow runs that took `taken` and stopped where it says.

    The counts agree with each other the way `one_at_a_time.take` keeps them: a
    member the pass stopped at was selected and not taken. A stop for a fault
    carries the fault that stop is made of.
    """
    return Pass(
        collection="workflow-runs",
        since=None,
        until="2026-07-06",
        ceiling=len(taken) if stopped_because is StopReason.CEILING else None,
        dry_run=dry_run,
        seen=10,
        selected=len(taken) + (resume_from is not None),
        taken=taken,
        written=(),
        bytes_freed=0,
        stopped_because=stopped_because,
        resume_from=resume_from,
        fault=NATURAL_FAULT.get(stopped_because),
        recovered=recovered,
    )


#: A pass that found nothing to do, before it says which idle word it is.
NOTHING = dataclasses.replace(
    a_pass(dry_run=False, stopped_because=StopReason.EXHAUSTED, taken=()), selected=0
)


@pytest.mark.parametrize(
    ("outcome", "folded", "word"),
    [
        pytest.param(
            a_pass(dry_run=True, stopped_because=StopReason.FAILED, resume_from=NEXT),
            None,
            TaskOutcome.FAILED,
            id="a-defect-first-even-on-a-dry-run",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.DEFERRED, resume_from=NEXT),
            None,
            TaskOutcome.DEFERRED,
            id="an-outage",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.EXHAUSTED),
            Folded(dry_run=False, fault=GardenerFault.API_UNAVAILABLE),
            TaskOutcome.DEFERRED,
            id="a-fold-an-outage-stopped",
        ),
        pytest.param(
            a_pass(dry_run=True, stopped_because=StopReason.CEILING, resume_from=NEXT),
            None,
            TaskOutcome.DRY_RUN,
            id="work-only-reported-before-the-ceiling",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, selected=6),
            None,
            TaskOutcome.DRY_RUN,
            id="a-live-compaction-whose-only-work-is-the-window-s-reported-drops",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.CEILING, resume_from=NEXT),
            None,
            TaskOutcome.CEILING,
            id="work-done-and-more-left",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.EXHAUSTED),
            None,
            TaskOutcome.DONE,
            id="work-done-and-nothing-left",
        ),
        pytest.param(
            dataclasses.replace(
                a_pass(
                    dry_run=False,
                    stopped_because=StopReason.EXHAUSTED,
                    taken=(),
                    recovered=(Recovery(note=RecoveryNote.NOT_DELETABLE, subject=TAKEN[0]),),
                ),
                selected=1,
            ),
            None,
            TaskOutcome.DONE,
            id="github-refused-every-member",
        ),
        pytest.param(
            NOTHING,
            Folded(dry_run=False),
            TaskOutcome.NOT_DUE,
            id="nothing-reached-its-line",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, idle_outcome=TaskOutcome.EMPTY),
            None,
            TaskOutcome.EMPTY,
            id="the-ledger-holds-nothing",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, idle_outcome=TaskOutcome.OUTSIDE_RANGE),
            None,
            TaskOutcome.OUTSIDE_RANGE,
            id="nothing-inside-the-range",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, appended=("state/raw/visual-prunes/x.parquet",)),
            None,
            TaskOutcome.NOT_DUE,
            id="a-report-filed-every-pass-is-not-work",
        ),
    ],
)
def test_a_task_ends_on_the_first_word_that_holds(
    outcome: Pass, folded: Folded | None, word: TaskOutcome
) -> None:
    assert report.classify(outcome, folded) is word


def test_what_a_dry_run_is_told_next_names_the_setting_and_never_says_anything_is_gone() -> None:
    said = report.next_step(TaskOutcome.DRY_RUN, None)

    assert SETTING in said, "a dry run did not name the setting that makes it live"
    assert "--no-dry-run" not in said, "a dry run named a flag the gardener does not take"
    assert "nothing was changed" in said


def test_no_sentence_a_task_can_be_told_says_a_member_is_gone() -> None:
    """A sentence is fixed for its word, so it says the same on a dry run and a live one."""
    sentences = [*report.NEXT.values(), *report.WHY.values(), *report.NOTED.values()]

    assert not [sentence for sentence in sentences if "gone" in sentence]


@pytest.mark.parametrize("fault", list(GardenerFault))
def test_a_task_a_fault_stopped_is_told_its_fault_s_own_sentence(fault: GardenerFault) -> None:
    word = TaskOutcome.FAILED if fault is GardenerFault.RAISED else TaskOutcome.DEFERRED

    assert report.next_step(word, fault) == report.WHY[fault]


def test_every_word_a_record_or_a_line_can_hold_has_a_sentence_a_person_reads() -> None:
    """A word with no sentence would print a blank where the reason belongs."""
    assert set(report.WHY) == set(GardenerFault)
    assert set(report.NOTED) == set(RecoveryNote)
    assert set(report.NEXT) == set(TaskOutcome)


def test_a_finished_task_says_what_its_pass_did_and_names_its_error_by_type_alone() -> None:
    """THE ORACLE for the event: the pass's fields, the fold beside them, and no exception text."""
    window = a_pass(dry_run=False, stopped_because=StopReason.FAILED, resume_from=NEXT)
    with pytest.raises(ValueError) as refused:
        Window(since="Breaking: click https://example.invalid/now")
    folded = Folded(dry_run=True)

    finished = report.finished(
        window,
        task="workflow-runs",
        duration_ms=12,
        folded=folded,
        settled=(),
        failure=refused.value,
    )

    assert finished.outcome is TaskOutcome.FAILED
    assert (finished.taken, finished.resume_from, finished.fault) == (
        list(TAKEN),
        NEXT,
        GardenerFault.RAISED,
    )
    assert finished.next == report.WHY[GardenerFault.RAISED]
    assert finished.error == "ValueError"
    assert finished.where is not None
    assert finished.where.startswith("idhazh.gardener.one_at_a_time:")
    assert "example.invalid" not in finished.model_dump_json()
    assert finished.fold is not None and finished.fold.dry_run
    assert finished.periods is None


@pytest.mark.parametrize(
    ("folded", "ended"),
    [
        pytest.param(None, (StopReason.EXHAUSTED, None), id="no-fold"),
        pytest.param(Folded(dry_run=False), (StopReason.EXHAUSTED, None), id="a-fold-that-finished"),
        pytest.param(
            Folded(dry_run=False, fault=GardenerFault.RAISED),
            (StopReason.FAILED, GardenerFault.RAISED),
            id="a-fold-a-defect-stopped",
        ),
        pytest.param(
            Folded(dry_run=False, fault=GardenerFault.API_UNAVAILABLE),
            (StopReason.DEFERRED, GardenerFault.API_UNAVAILABLE),
            id="a-fold-an-outage-stopped",
        ),
    ],
)
def test_a_task_ends_as_its_fold_ends_when_the_fold_stopped(
    folded: Folded | None, ended: tuple[StopReason, GardenerFault | None]
) -> None:
    """The window finished, so the task's row says what the fold met, defect or outage."""
    window = a_pass(dry_run=False, stopped_because=StopReason.EXHAUSTED)

    assert report.ended(window, folded) == ended
