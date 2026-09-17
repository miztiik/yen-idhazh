"""Does one pass delete only what the window holds, stop at its ceiling, and survive being cut short?

Four properties, and the third is the one the design exists for.

The window decides which members qualify. The ceiling decides how many of them
one pass takes. The refusal list decides which collections may be pointed at.
And an interruption leaves members 1 to N deleted, N+1 onward untouched, and a
record naming where the next pass starts - no rollback, nothing half-done.

Every collection here is BUILT out of real files in `tmp_path` (CLAUDE.md
section 13). The core's whole contract is three callables, so a test that
supplied anything less than real ones would be testing a description of the
core rather than the core. The one failure that has to be forced is a delete
that cannot work, and it is forced by handing `unlink` a directory - a real
refusal from the real file system, not an exception somebody wrote.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from idhazh.contracts.collection_prune import StopReason
from idhazh.prune import one_at_a_time
from idhazh.prune.one_at_a_time import Collection, Member, PruneInterruptedError, Window

pytestmark = pytest.mark.contract

#: Seven days, spanning a month end so a boundary off by one lands on a real
#: neighbour rather than on nothing.
DAYS = (
    "2026-07-29",
    "2026-07-30",
    "2026-07-31",
    "2026-08-01",
    "2026-08-02",
    "2026-08-03",
    "2026-08-04",
)


def a_collection(root: Path, days: tuple[str, ...] = DAYS) -> Collection[Path]:
    """One real file per day, and the three callables that list, read and delete them."""
    root.mkdir(parents=True, exist_ok=True)
    for index, day in enumerate(days):
        (root / f"{day}.txt").write_text("x" * (index + 1), encoding="utf-8", newline="\n")
    return collection_over(root)


def collection_over(root: Path) -> Collection[Path]:
    """The three callables alone, over whatever the directory holds now.

    Separate from `a_collection` because a test that runs several passes has to
    re-read the directory without re-creating the files an earlier pass deleted.

    The listing is a generator, so the pass walks it and never holds it - which
    is the property that lets the same core page an API of 3,551 members.
    """

    def listing() -> Iterator[Path]:
        yield from sorted(root.glob("*.txt"))

    return Collection(
        name="files",
        listing=listing,
        describe=lambda path: Member(
            id=path.stem, day=path.stem, size_bytes=path.stat().st_size, label=path.name
        ),
        delete=lambda path: path.unlink(),
    )


def on_disk(root: Path) -> list[str]:
    """Which days the collection still holds, counting files and not directories.

    The interruption test turns one member into a directory so that `unlink`
    fails for real, and a directory that survives a failed delete is not a
    member that survived it.
    """
    return sorted(path.stem for path in root.glob("*.txt") if path.is_file())


# --- The window ----------------------------------------------------------------


def test_both_ends_of_a_window_are_inclusive() -> None:
    """`since X until Y` holds X, Y and everything between, and nothing either side."""
    window = Window(since=DAYS[2], until=DAYS[4])

    assert [day for day in DAYS if window.holds(day)] == [DAYS[2], DAYS[3], DAYS[4]]


def test_an_age_window_has_no_lower_end() -> None:
    """`older_than` draws one line and holds everything before it, however old.

    A lower end would quietly strand whatever fell under it, which is the one
    thing an age policy must not do.
    """
    window = Window.older_than(today="2026-09-17", days=30)

    assert window.since is None
    assert window.until == "2026-08-18", "thirty days before the 17th is the 18th"
    assert window.holds("2026-08-18") and window.holds("1999-01-01")
    assert not window.holds("2026-08-19")


@pytest.mark.parametrize("value", ["2026-8-4", "20260804", "yesterday", "2026-13-01"])
def test_a_day_that_is_not_a_day_is_refused(value: str) -> None:
    """The width is checked as well as the parse.

    `date.fromisoformat` takes `20260804`, and a window compared as text - which
    is how every date comparison in this tree works - would then put that day
    outside every window it belongs in.
    """
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        Window(until=value)


def test_a_window_with_neither_end_is_refused() -> None:
    """A window that holds everything is a prune of the collection, not a window."""
    with pytest.raises(ValueError, match="neither end"):
        Window()


def test_a_backwards_window_names_no_day() -> None:
    """An operator who swapped the two ends is told, rather than deleting nothing."""
    with pytest.raises(ValueError, match="is after until"):
        Window(since=DAYS[4], until=DAYS[1])


def test_an_age_window_never_includes_today() -> None:
    """Zero days would delete the artifact the running job just uploaded."""
    with pytest.raises(ValueError, match="at least one whole day"):
        Window.older_than(today="2026-09-17", days=0)


# --- The ceiling and the resume point ------------------------------------------


def test_a_pass_stops_at_its_ceiling_and_names_the_next_member(tmp_path: Path) -> None:
    """Two of five go, and the record says which member the next pass starts at."""
    root = tmp_path / "files"
    collection = a_collection(root)

    taken = one_at_a_time.take(
        collection, window=Window(since=DAYS[0], until=DAYS[4]), ceiling=2, dry_run=False
    )

    assert taken.taken == (DAYS[0], DAYS[1])
    assert taken.stopped_because is StopReason.CEILING
    assert taken.resume_from == DAYS[2], "the resume point is the first member not taken"
    assert taken.more_to_do
    assert on_disk(root) == [DAYS[2], DAYS[3], DAYS[4], DAYS[5], DAYS[6]]


def test_running_again_from_the_resume_point_finishes_the_job(tmp_path: Path) -> None:
    """Three bounded passes clear what one unbounded pass would have taken.

    This is the whole argument for a ceiling: the work is the same, it arrives
    in bites nobody has to size, and each bite is the same shape.

    Bounded at four passes rather than looped until it stops, so a core that
    stopped making progress fails this test instead of hanging it.
    """
    root = tmp_path / "files"
    a_collection(root)
    window = Window(since=DAYS[0], until=DAYS[4])
    passes = []

    for _ in range(4):
        taken = one_at_a_time.take(
            collection_over(root), window=window, ceiling=2, dry_run=False
        )
        passes.append(taken)
        if not taken.more_to_do:
            break

    assert [p.taken for p in passes] == [
        (DAYS[0], DAYS[1]),
        (DAYS[2], DAYS[3]),
        (DAYS[4],),
    ], "three passes of two did not clear a window of five"
    assert passes[-1].stopped_because is StopReason.EXHAUSTED
    assert passes[-1].resume_from is None, "an exhausted pass has nothing to resume from"
    assert on_disk(root) == [DAYS[5], DAYS[6]], "a member outside the window went"


def test_a_ceiling_of_zero_surveys_and_deletes_nothing(tmp_path: Path) -> None:
    """The way to see what a window selects without committing to a number."""
    root = tmp_path / "files"

    taken = one_at_a_time.take(
        a_collection(root), window=Window(since=DAYS[1], until=DAYS[3]), ceiling=0, dry_run=False
    )

    assert taken.taken == ()
    assert taken.resume_from == DAYS[1]
    assert on_disk(root) == list(DAYS)


def test_the_window_is_tested_before_the_ceiling(tmp_path: Path) -> None:
    """A filled ceiling must not name a member the window never held.

    Tested the other way round, a pass that had taken its two would stop at the
    next member it saw - and here that member is outside the window, so the next
    pass would start from something it has no business deleting.
    """
    root = tmp_path / "files"

    taken = one_at_a_time.take(
        a_collection(root), window=Window(since=DAYS[0], until=DAYS[1]), ceiling=2, dry_run=False
    )

    assert taken.stopped_because is StopReason.EXHAUSTED
    assert taken.resume_from is None
    assert taken.seen == len(DAYS), "the walk stopped early on a window that held no more"


def test_a_negative_ceiling_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "files"

    with pytest.raises(ValueError, match="count of members"):
        one_at_a_time.take(a_collection(root), window=Window(until=DAYS[3]), ceiling=-1)


# --- The interruption, which is what atomic means here -------------------------


def test_an_interrupted_pass_keeps_what_it_already_deleted(tmp_path: Path) -> None:
    """Members 1 and 2 are gone, 3 onward are untouched, and the record says where it stopped.

    The third member is a directory, so `unlink` raises for real rather than
    because a test asked it to. That is the whole claim behind the word atomic:
    one delete is the unit, it either happened or it did not, and an
    interruption needs no rollback because nothing was ever half-done.

    It is also what this replaced. Until 2026-09-17 the day-file prune moved a
    whole range into a scratch directory and put every file back if one move
    failed. That bought "the tree is exactly as you found it" and cost a second
    write path that could fail while undoing.
    """
    root = tmp_path / "files"
    collection = a_collection(root)
    (root / f"{DAYS[2]}.txt").unlink()
    (root / f"{DAYS[2]}.txt").mkdir()

    with pytest.raises(PruneInterruptedError) as stop:
        one_at_a_time.take(
            collection, window=Window(since=DAYS[0], until=DAYS[4]), ceiling=5, dry_run=False
        )

    so_far = stop.value.so_far
    assert so_far.taken == (DAYS[0], DAYS[1]), "the pass did not keep what it had deleted"
    assert so_far.stopped_because is StopReason.FAILED
    assert so_far.resume_from == DAYS[2], "the next pass has to retry the one that failed"
    assert (root / f"{DAYS[2]}.txt").is_dir(), "the delete that failed removed something"
    assert on_disk(root) == [DAYS[3], DAYS[4], DAYS[5], DAYS[6]], (
        "a member after the failure was deleted, so the pass did not stop"
    )
    assert isinstance(stop.value.__cause__, OSError), "the file system's own refusal was lost"


def test_a_dry_run_names_every_member_and_deletes_none(tmp_path: Path) -> None:
    """The default, and the list a person reads before passing `--no-dry-run`.

    The same list on both sides: what a dry run prints has to be what a live
    pass removes, member for member, or reading it settles nothing.
    """
    root = tmp_path / "files"
    window = Window(since=DAYS[1], until=DAYS[3])

    reported = one_at_a_time.take(a_collection(root), window=window, ceiling=5)

    assert reported.dry_run is True
    assert on_disk(root) == list(DAYS), "a dry run deleted a member"

    removed = one_at_a_time.take(collection_over(root), window=window, ceiling=5, dry_run=False)
    assert removed.taken == reported.taken
    assert removed.bytes_freed == reported.bytes_freed


# --- The refusal list ----------------------------------------------------------


def test_a_refused_name_is_answered_with_its_reason() -> None:
    """Somebody who typed a refused word is holding a real question."""
    with pytest.raises(ValueError) as refusal:
        one_at_a_time.refuse_by_name(
            "published", allowed=("item-health",), refused={"published": "it cannot forget"}
        )

    assert "published is refused" in str(refusal.value)
    assert "it cannot forget" in str(refusal.value), "the refusal did not say why"


@pytest.mark.parametrize(
    "name", ["state/item-health", "../item-health", "/etc/passwd", "traces", ""]
)
def test_a_name_outside_the_vocabulary_is_refused(name: str) -> None:
    """A path is never a name, which is what stops this being a deletion primitive."""
    with pytest.raises(ValueError, match="the name of a collection"):
        one_at_a_time.refuse_by_name(name, allowed=("item-health",), refused={})


def test_the_noun_in_a_refusal_is_the_caller_s_own_word() -> None:
    """A store and a GitHub collection are the same shape and not the same word."""
    with pytest.raises(ValueError, match="the name of a store"):
        one_at_a_time.refuse_by_name("nope", allowed=("item-health",), refused={}, noun="store")
