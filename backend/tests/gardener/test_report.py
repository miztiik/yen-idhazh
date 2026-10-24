"""Does a task end on the right word and give a person accurate next-step copy?

`classify` reads a pass for the one word a person acts on: a fault first, then
work only reported, then the ceiling, then work done, then the pass's own idle
word. A dry run changes nothing; its report names the setting that makes the
task live, and a pass a fault stopped is told its fault's own sentence.

`finished` is the event the runner logs for a task: the pass's own fields and
the exception that stopped it, named by type and place, never by text.

Every pass here is a real `Pass`, built whole the way a task hands one to the
runner. The report reads nothing else, so nothing else is built.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from idhazh.contracts.collection_prune import Recovery, StopReason, stop_for
from idhazh.contracts.gardener_events import TaskOutcome
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.gardener import report
from idhazh.gardener.one_at_a_time import Pass, Window

pytestmark = pytest.mark.contract

#: Three run ids, oldest first, in the order a pass takes them.
TAKEN = ("18000000001", "18000000002", "18000000003")
#: The run a pass stopped at, or failed at.
NEXT = "18000000004"
#: The setting that makes a task live, in the file that holds it.
SETTING = "dry_run: false in config/gardener/<task>.json"

# These explicit forms are screened in the fixed copy below. This is not a
# general natural-language classifier.
_EXPLICIT_REMOVAL_FORM = re.compile(
    r"\b(?:"
    r"(?:member|file|day|period)s?\s+(?:is|are|was|were|has been|have been)\s+"
    r"(?:gone|deleted|removed)"
    r"|(?:gone|deleted|removed)\s+(?:\d+\s+)?(?:member|file|day|period)s?"
    r")\b",
    re.IGNORECASE,
)

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
    ("outcome", "word"),
    [
        pytest.param(
            a_pass(dry_run=True, stopped_because=StopReason.FAILED, resume_from=NEXT),
            TaskOutcome.FAILED,
            id="a-defect-first-even-on-a-dry-run",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.DEFERRED, resume_from=NEXT),
            TaskOutcome.DEFERRED,
            id="an-outage",
        ),
        pytest.param(
            a_pass(dry_run=True, stopped_because=StopReason.CEILING, resume_from=NEXT),
            TaskOutcome.DRY_RUN,
            id="work-only-reported-before-the-ceiling",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, selected=6),
            TaskOutcome.DRY_RUN,
            id="a-live-compaction-whose-only-work-is-the-window-s-reported-drops",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.CEILING, resume_from=NEXT),
            TaskOutcome.CEILING,
            id="work-done-and-more-left",
        ),
        pytest.param(
            a_pass(dry_run=False, stopped_because=StopReason.EXHAUSTED),
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
            TaskOutcome.DONE,
            id="github-refused-every-member",
        ),
        pytest.param(
            NOTHING,
            TaskOutcome.NOT_DUE,
            id="nothing-reached-its-line",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, idle_outcome=TaskOutcome.EMPTY),
            TaskOutcome.EMPTY,
            id="the-ledger-holds-nothing",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, idle_outcome=TaskOutcome.OUTSIDE_RANGE),
            TaskOutcome.OUTSIDE_RANGE,
            id="nothing-inside-the-range",
        ),
        pytest.param(
            dataclasses.replace(NOTHING, appended=("state/raw/visual-prunes/x.parquet",)),
            TaskOutcome.NOT_DUE,
            id="a-report-filed-every-pass-is-not-work",
        ),
    ],
)
def test_a_task_ends_on_the_first_word_that_holds(outcome: Pass, word: TaskOutcome) -> None:
    assert report.classify(outcome) is word


def test_a_dry_run_report_names_the_setting_and_says_nothing_changed() -> None:
    window = dataclasses.replace(
        a_pass(dry_run=True, stopped_because=StopReason.EXHAUSTED, taken=()),
        selected=1,
    )
    finished = report.finished(window, task="workflow-runs", duration_ms=0, failure=None)
    said = finished.next

    assert finished.outcome is TaskOutcome.DRY_RUN

    assert SETTING in said, "a dry run did not name the setting that makes it live"
    assert "--no-dry-run" not in said, "a dry run named a flag the gardener does not take"
    assert "nothing was changed" in said
    assert not _EXPLICIT_REMOVAL_FORM.search(said)


@pytest.mark.parametrize(
    "phrase",
    ["a member has been removed", "Removed 3 members", "files are gone"],
)
def test_explicit_removal_forms_are_recognized(phrase: str) -> None:
    assert _EXPLICIT_REMOVAL_FORM.search(phrase)


def test_fixed_guidance_avoids_explicit_completed_removal_forms() -> None:
    """Screen these direct forms in fixed copy, not general English meaning."""
    guidance = [*report.NEXT.values(), *report.WHY.values()]
    recovery_notes = list(report.NOTED.values())

    assert not [sentence for sentence in guidance if _EXPLICIT_REMOVAL_FORM.search(sentence)]
    assert not [
        sentence for sentence in recovery_notes if _EXPLICIT_REMOVAL_FORM.search(sentence)
    ]


@pytest.mark.parametrize("fault", list(GardenerFault))
def test_a_task_a_fault_stopped_is_told_its_fault_s_own_sentence(fault: GardenerFault) -> None:
    word = (
        TaskOutcome.FAILED
        if stop_for(fault) is StopReason.FAILED
        else TaskOutcome.DEFERRED
    )
    window = dataclasses.replace(
        a_pass(dry_run=False, stopped_because=stop_for(fault), resume_from=NEXT),
        fault=fault,
    )
    finished = report.finished(window, task="workflow-runs", duration_ms=0, failure=None)

    assert finished.outcome is word
    assert finished.next == report.WHY[fault]


def test_every_word_a_record_or_a_line_can_hold_has_a_sentence_a_person_reads() -> None:
    """A word with no sentence would print a blank where the reason belongs."""
    assert set(report.WHY) == set(GardenerFault)
    assert set(report.NOTED) == set(RecoveryNote)
    assert set(report.NEXT) == set(TaskOutcome)
    assert all(isinstance(sentence, str) and sentence.strip() for sentence in report.WHY.values())
    assert all(
        isinstance(sentence, str) and sentence.strip() for sentence in report.NOTED.values()
    )
    assert all(isinstance(sentence, str) and sentence.strip() for sentence in report.NEXT.values())


def test_a_finished_task_says_what_its_pass_did_and_names_its_error_by_type_alone() -> None:
    """THE ORACLE for the event: the pass's fields, and no exception text."""
    window = a_pass(dry_run=False, stopped_because=StopReason.FAILED, resume_from=NEXT)
    with pytest.raises(ValueError) as refused:
        Window(since="Breaking: click https://example.invalid/now")

    finished = report.finished(
        window,
        task="workflow-runs",
        duration_ms=12,
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
    assert finished.periods is None
