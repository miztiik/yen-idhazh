"""Does the report of a pass tell a dry run from a live one?

A dry run deletes nothing, so no line it prints may say a member is gone, and
the switch it names has to exist. The gardener takes no `--no-dry-run`: a task
runs live when its own declaration says `dry_run: false`, so that is the
setting a dry run names. A live pass that failed part way still says the
members above are gone, because they are.

Every pass here is a real `Pass`, built whole the way a task hands one to the
runner. The report reads nothing else, so nothing else is built.
"""

from __future__ import annotations

import pytest

from idhazh.contracts.collection_prune import StopReason
from idhazh.gardener import report
from idhazh.gardener.one_at_a_time import Pass

pytestmark = pytest.mark.contract

#: Three run ids, oldest first, in the order a pass takes them.
TAKEN = ("18000000001", "18000000002", "18000000003")
#: The run a pass stopped at, or failed at.
NEXT = "18000000004"
#: The setting that makes a task live, in the file that holds it.
SETTING = "dry_run: false in config/gardener/<task>.json"

#: Every way a pass that took members can end, with the member it names for
#: the next pass.
STOPS = (
    pytest.param(StopReason.CEILING, NEXT, id="ceiling"),
    pytest.param(StopReason.EXHAUSTED, None, id="exhausted"),
    pytest.param(StopReason.FAILED, None, id="failed-before-naming-a-member"),
    pytest.param(StopReason.FAILED, NEXT, id="failed-at-a-member"),
)


def a_pass(
    *,
    dry_run: bool,
    stopped_because: StopReason,
    resume_from: str | None,
    taken: tuple[str, ...] = TAKEN,
    handled_through: str | None = None,
) -> Pass:
    """A pass over workflow runs that took `taken` and stopped where it says.

    The counts agree with each other the way `one_at_a_time.take` keeps them: a
    member the pass stopped at was selected and not taken, and only a pass that
    hit its ceiling has one. `handled_through` is set on a pass that walked from
    a mark.
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
        handled_through=handled_through,
    )


@pytest.mark.parametrize(("stopped_because", "resume_from"), STOPS)
def test_a_dry_run_that_took_members_says_nothing_was_deleted(
    stopped_because: StopReason, resume_from: str | None
) -> None:
    """Its last line says nothing was deleted and names the setting that makes it live.

    However the pass stopped, no line says a member is gone, and no line names
    a flag the gardener does not take.
    """
    said = report.lines(
        a_pass(dry_run=True, stopped_because=stopped_because, resume_from=resume_from)
    )

    printed = "\n".join(said)
    assert "gone" not in printed, "a dry run said a member it kept is gone"
    assert "--no-dry-run" not in printed, "a dry run named a flag the gardener does not take"
    assert "nothing was deleted" in said[-1]
    assert "a live run would delete the members above" in said[-1]
    assert SETTING in said[-1], "a dry run did not name the setting that makes it live"


def test_a_dry_run_that_failed_before_taking_a_member_says_nothing_is_gone() -> None:
    """A failed dry run says nothing is gone, and has no list to make live."""
    said = report.lines(
        a_pass(dry_run=True, stopped_because=StopReason.FAILED, resume_from=None, taken=())
    )

    assert "gone" not in "\n".join(said), "a dry run said a member is gone"
    assert not any(SETTING in line for line in said), "a dry run that took nothing named it"


def test_a_dry_walk_past_its_ceiling_says_where_a_live_pass_would_stop_and_what_it_counted() -> None:
    """It finished the day without naming the rest, so the next dry run starts after that day.

    Telling a person to run it again would send them to a pass that starts on
    the next day and never names the members this one counted.
    """
    said = report.lines(
        a_pass(
            dry_run=True,
            stopped_because=StopReason.CEILING,
            resume_from=NEXT,
            handled_through="2026-07-06",
        )
    )

    assert (
        f"  the ceiling of 3 would stop a live pass at {NEXT}; the rest of that day was "
        "counted, not listed, and the next pass starts after 2026-07-06"
    ) in said
    assert not any("run it again" in line for line in said)
    assert "nothing was deleted" in said[-1]


def test_a_live_walk_its_ceiling_stopped_says_it_stopped_there() -> None:
    """A live pass deletes as it goes, so the next one meets the member it stopped at."""
    said = report.lines(
        a_pass(
            dry_run=False,
            stopped_because=StopReason.CEILING,
            resume_from=NEXT,
            handled_through="2026-07-05",
        )
    )

    assert said[-1] == f"  the ceiling of 3 stopped this pass at {NEXT} - there is more, so run it again"


@pytest.mark.parametrize(
    ("resume_from", "then"),
    [
        pytest.param(
            None,
            "the next pass starts again from the oldest member the window holds",
            id="failed-before-naming-a-member",
        ),
        pytest.param(NEXT, "the next pass retries that one", id="failed-at-a-member"),
    ],
)
def test_a_live_pass_that_failed_part_way_still_says_the_members_are_gone(
    resume_from: str | None, then: str
) -> None:
    """The members above it were deleted, so the line says so, and where the next pass starts."""
    said = report.lines(
        a_pass(dry_run=False, stopped_because=StopReason.FAILED, resume_from=resume_from)
    )

    assert said[-1].endswith(f"the members above are gone, and {then}")
    assert not any("nothing was deleted" in line for line in said)
    assert not any(SETTING in line for line in said), "a live pass named the dry-run setting"
