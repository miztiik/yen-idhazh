"""Does a listing answer only for what it was given, weigh each file, and refuse to read an absent one?

A task learns what its folders hold from a `FileListing`, never from the disk.
These tests pin the promises that makes: a folder the task did not declare is
refused rather than read as empty; a path under a declared folder that no step
named is refused rather than answered "not held"; `files_under` answers for all
of a folder a step named or refuses, never for the named part of a folder read
as the whole; a step that names a period as it runs is answered for it, and
never handed back a file an earlier task deleted; a declared folder the commit
does not hold answers empty; a file the commit holds is never taken for a
missing member - after the checkout is widened for it, it is on disk or the
read fails; and what a fetch would download is read off the listing's own
sizes, and a fetch past what is left of the shard's budget is refused before
the checkout widens.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

import pytest

from idhazh.gardener.file_listing import (
    FileListing,
    FileNotFetchedError,
    OverBudgetError,
    PathNotNamedError,
    TreeEntry,
)

pytestmark = pytest.mark.contract

FILES: Final = {
    "state/days/2026/09/01.csv": "a",
    "state/days/2026/09/02.csv": "bb",
    "state/traces/2026/09/01/0001-0.jsonl": "ccc",
    "state/other/x.csv": "dddd",
}


def a_checkout(root: Path) -> Path:
    for relative, text in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="ascii", newline="\n")
    return root


def disk_listing(root: Path, folders: Sequence[str]) -> FileListing:
    """Read named fixture folders built by this test."""
    return FileListing.from_disk(
        root, folders, paths=(root / folder for folder in folders)
    )


def test_a_listing_read_off_the_disk_names_every_file_with_its_size(tmp_path: Path) -> None:
    root = a_checkout(tmp_path)
    listing = disk_listing(root, ["state/days", "state/traces/"])

    assert dict(listing.sizes) == {
        "state/days/2026/09/01.csv": 1,
        "state/days/2026/09/02.csv": 2,
        "state/traces/2026/09/01/0001-0.jsonl": 3,
    }
    assert listing.files_under("state/days") == [
        "state/days/2026/09/01.csv",
        "state/days/2026/09/02.csv",
    ]
    assert listing.files_under(tmp_path / "state" / "traces") == [
        "state/traces/2026/09/01/0001-0.jsonl"
    ]
    assert listing.size_of(tmp_path / "state/days/2026/09/02.csv") == 2
    assert listing.downloaded() is None, "nothing was downloaded to read the disk"


def test_named_paths_ignore_unlisted_neighbours(tmp_path: Path) -> None:
    root = a_checkout(tmp_path)
    named = root / "state/days/2026/09/01.csv"
    listing = FileListing.from_paths(root, [named], folders=["state/days"])
    assert dict(listing.sizes) == {"state/days/2026/09/01.csv": 1}
    assert listing.named_files(root / "state/days") == ["state/days/2026/09/01.csv"]
    with pytest.raises(ValueError, match="outside"):
        FileListing.from_paths(root, [root / "state/other/x.csv"], folders=["state/days"])


def test_a_sibling_nobody_named_is_refused_by_name_and_never_answered_not_held(
    tmp_path: Path,
) -> None:
    """The commit holds the sibling, so "not held" would be a wrong answer a step acts on."""
    root = a_checkout(tmp_path)
    listing = FileListing.from_paths(
        root, [root / "state/days/2026/09/01.csv"], folders=["state/days"]
    ).within(["state/days"])

    for ask in (
        lambda: listing.holds(root / "state/days/2026/09/02.csv"),
        lambda: listing.size_of("state/days/2026/09/02.csv"),
        lambda: listing.fetch(beside=["state/days/2026/09/02.csv"]),
    ):
        with pytest.raises(PathNotNamedError) as refused:
            ask()
        said = str(refused.value)
        assert said.startswith("state/days/2026/09/02.csv is under state/days"), said
        assert "The nearest path a step named is state/days/2026/09/01.csv" in said, said
        assert not isinstance(refused.value, ValueError), "a handler of bad data would skip it"


def test_a_named_period_answers_for_every_file_in_it_and_a_period_beside_it_is_refused(
    tmp_path: Path,
) -> None:
    root = a_checkout(tmp_path)
    listing = FileListing.from_disk(
        root, ["state/traces"], paths=[root / "state/traces/2026/09/01"]
    )

    assert listing.holds("state/traces/2026/09/01/0001-0.jsonl")
    assert not listing.holds("state/traces/2026/09/01/0002-0.jsonl"), (
        "a file the named day lacks is not held: a step looked there"
    )
    listing.fetch(["state/traces/2026/09"])
    with pytest.raises(
        PathNotNamedError,
        match=r"^state/traces/2026/09/02 is under state/traces, .* "
        r"The nearest path a step named is state/traces/2026/09/01\. ",
    ):
        listing.fetch(["state/traces/2026/09/02"])


def test_files_under_a_folder_no_step_named_is_refused_by_name_as_holds_is(
    tmp_path: Path,
) -> None:
    """The listing saw one named file of the folder, so every file under it would be a guess."""
    root = a_checkout(tmp_path)
    listing = FileListing.from_paths(
        root, [root / "state/days/2026/09/01.csv"], folders=["state/days"]
    )

    for folder in ("state/days", "state/days/2026/10"):
        with pytest.raises(PathNotNamedError) as refused:
            listing.files_under(folder)
        said = str(refused.value)
        assert said.startswith(f"{folder} is not a path a step named, nor inside one"), said
        assert "The nearest path a step named is state/days/2026/09/01.csv" in said, said
        assert not isinstance(refused.value, ValueError), "a handler of bad data would skip it"
    with pytest.raises(PathNotNamedError):
        listing.holds("state/days/2026/09/02.csv")


def test_a_named_folder_answers_whole_and_named_files_walks_only_the_named_periods(
    tmp_path: Path,
) -> None:
    root = a_checkout(tmp_path)
    (root / "state/traces/2026/09/02").mkdir(parents=True)
    (root / "state/traces/2026/09/02/0002-0.jsonl").write_text("e", encoding="ascii")
    listing = FileListing.from_disk(
        root, ["state/traces"], paths=[root / "state/traces/2026/09/01"]
    )

    assert listing.files_under("state/traces/2026/09/01") == [
        "state/traces/2026/09/01/0001-0.jsonl"
    ]
    assert listing.named_files("state/traces") == ["state/traces/2026/09/01/0001-0.jsonl"], (
        "the walk covers the named day and says nothing of the day beside it"
    )
    with pytest.raises(PathNotNamedError):
        listing.files_under("state/traces")


def test_a_listing_says_whether_it_saw_any_of_a_path_where_a_walk_would_be_refused(
    tmp_path: Path,
) -> None:
    """A caller that may find nothing named under a folder asks, rather than catching the refusal."""
    root = a_checkout(tmp_path)
    listing = FileListing.from_disk(
        root, ["state/days", "state/traces"], paths=[root / "state/traces/2026/09/01"]
    )

    assert listing.saw_any_of("state/traces"), "a period inside it was named"
    assert listing.saw_any_of("state/traces/2026/09/01/0001-0.jsonl"), "a folder above it was"
    assert not listing.saw_any_of("state/traces/2026/09/02")
    assert not listing.saw_any_of(root / "state" / "days")
    with pytest.raises(PathNotNamedError):
        listing.named_files("state/days")
    with pytest.raises(ValueError, match="is not under a folder this task owns or reads"):
        listing.saw_any_of("state/other")


def test_a_step_names_a_period_as_it_runs_and_is_answered_for_it(tmp_path: Path) -> None:
    """The listing a task was handed did not name October; the task names it, and only then reads it."""
    root = a_checkout(tmp_path)
    (root / "state/days/2026/10").mkdir(parents=True)
    (root / "state/days/2026/10/01.csv").write_text("eeeee", encoding="ascii")
    listing = FileListing.from_disk(root, ["state/days"], paths=[root / "state/days/2026/09"])

    named = listing.name(["state/days/2026/10", root / "state/days/2026/09/01.csv"])

    assert named.files_under("state/days/2026/10") == ["state/days/2026/10/01.csv"]
    assert named.size_of("state/days/2026/10/01.csv") == 5
    assert named.name(["state/days/2026/10/01.csv"]) is named, "a named path is not listed again"
    with pytest.raises(PathNotNamedError):
        listing.holds("state/days/2026/10/01.csv")
    assert listing.listed() == named.listed() == {
        "state/days/2026/09/01.csv",
        "state/days/2026/09/02.csv",
        "state/days/2026/10/01.csv",
    }
    with pytest.raises(ValueError, match="owns or reads"):
        named.name(["state/other"])


def test_a_later_naming_never_hands_back_a_file_an_earlier_task_deleted(tmp_path: Path) -> None:
    """The file is still on disk, so a second walk of October would list it again."""
    root = a_checkout(tmp_path)
    (root / "state/days/2026/10").mkdir(parents=True)
    (root / "state/days/2026/10/01.csv").write_text("eeeee", encoding="ascii")
    shard = FileListing.from_disk(root, ["state/days"], paths=[root / "state/days/2026/09"])
    shard.within(["state/days"]).name(["state/days/2026/10"])

    later = shard.settled(written=[], deleted=["state/days/2026/10/01.csv"])

    assert later.answers_for("state/days/2026/10"), "the earlier task's naming was taken in"
    assert later.name(["state/days/2026/10"]) is later
    assert not later.holds("state/days/2026/10/01.csv")
    assert "state/days/2026/10/01.csv" in shard.listed(), "the shard still listed it, once"


def test_a_listing_built_from_named_files_alone_cannot_name_more(tmp_path: Path) -> None:
    root = a_checkout(tmp_path)
    listing = FileListing.from_paths(
        root, [root / "state/days/2026/09/01.csv"], folders=["state/days"]
    )

    with pytest.raises(ValueError, match=r"^state/days/2026/10 cannot be named now"):
        listing.name(["state/days/2026/10"])


def test_a_commit_listing_answers_for_the_paths_git_was_asked_about(tmp_path: Path) -> None:
    listing = FileListing.from_commit(
        tmp_path,
        ["state/days"],
        [TreeEntry(path="state/days/2026/09/01.csv", blob="1" * 40, size=12)],
        {},
        paths=["state/days/2026/09/01.csv", "state/days/2026/09/02.csv"],
        widen=lambda _: None,
    )

    assert listing.holds("state/days/2026/09/01.csv")
    assert not listing.holds("state/days/2026/09/02.csv"), "a named file the commit lacks"
    with pytest.raises(PathNotNamedError) as refused:
        listing.size_of("state/days/2026/10/01.csv")
    assert (
        "The nearest paths a step named run from state/days/2026/09/01.csv to "
        "state/days/2026/09/02.csv (2 paths)"
    ) in str(refused.value)


def test_a_file_an_earlier_task_wrote_counts_as_named(tmp_path: Path) -> None:
    """A later task may weigh what an earlier one wrote, and still not what nobody named."""
    root = a_checkout(tmp_path)
    listing = FileListing.from_paths(
        root, [root / "state/days/2026/09/01.csv"], folders=["state/days"]
    )
    (root / "state/days/2026/09/03.csv").write_text("eeeee", encoding="ascii", newline="\n")

    later = listing.settled(written=["state/days/2026/09/03.csv"], deleted=[])

    assert later.size_of("state/days/2026/09/03.csv") == 5
    with pytest.raises(PathNotNamedError, match=r"^state/days/2026/09/02\.csv "):
        later.holds("state/days/2026/09/02.csv")


def test_a_folder_the_task_did_not_declare_is_refused_and_never_read_as_empty(
    tmp_path: Path,
) -> None:
    listing = disk_listing(a_checkout(tmp_path), ["state/days", "state/other"])
    task = listing.within(["state/days"])

    for ask in (
        lambda: task.files_under("state/other"),
        lambda: task.holds("state/other/x.csv"),
        lambda: task.size_of("state/other/x.csv"),
        lambda: task.fetch(["state/other"]),
    ):
        with pytest.raises(ValueError, match="owns or reads"):
            ask()
    with pytest.raises(ValueError, match="owns or reads"):
        listing.within(["state/traces"])


def test_a_declared_folder_the_commit_does_not_hold_answers_empty(tmp_path: Path) -> None:
    listing = disk_listing(a_checkout(tmp_path), ["state/days", "state/not-yet"])

    assert listing.files_under("state/not-yet") == []
    assert not listing.holds("state/not-yet/2026-09.csv")
    listing.fetch(["state/not-yet"])


def test_a_file_the_commit_holds_and_the_checkout_lacks_is_never_read_as_absent(
    tmp_path: Path,
) -> None:
    """A widening that brings nothing leaves the file absent, and the read fails by name."""
    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        ["state/days"],
        [TreeEntry(path="state/days/2026/09/01.csv", blob="1" * 40, size=12)],
        {},
        paths=["state/days/2026/09"],
        widen=asked.append,
    )

    with pytest.raises(FileNotFetchedError, match=r"state/days/2026/09/01\.csv"):
        listing.fetch(["state/days/2026/09"])
    assert asked == [["state/days/2026/09"]], "the checkout was not widened, once, for the folder"
    assert listing.downloaded() == {"state/days": 0}


def test_a_file_git_never_sized_takes_the_size_github_gave_its_blob_or_is_refused(
    tmp_path: Path,
) -> None:
    entries = [
        TreeEntry(path="state/days/2026/09/01.csv", blob="1" * 40, size=12),
        TreeEntry(path="state/days/2026/09/02.csv", blob="2" * 40, size=None),
        TreeEntry(path="state/elsewhere/x.csv", blob="3" * 40, size=None),
    ]

    listing = FileListing.from_commit(
        tmp_path,
        ["state/days"],
        entries,
        {"2" * 40: 34},
        paths=["state/days/2026/09"],
        widen=lambda _: None,
    )

    assert dict(listing.sizes) == {"state/days/2026/09/01.csv": 12, "state/days/2026/09/02.csv": 34}
    with pytest.raises(ValueError, match=r"state/days/2026/09/02\.csv has no size"):
        FileListing.from_commit(
            tmp_path,
            ["state/days"],
            entries,
            {},
            paths=["state/days/2026/09"],
            widen=lambda _: None,
        )


def test_a_file_entry_brings_only_the_files_beside_it(tmp_path: Path) -> None:
    """What a sparse checkout takes for a name that is a file: its folder's own files."""
    listing = FileListing.from_commit(
        tmp_path,
        ["state/compact/x"],
        [
            TreeEntry(path="state/compact/x/daily/2026/09/01.parquet", blob="1" * 40, size=5),
            TreeEntry(path="state/compact/x/daily/2026/09/old/01.parquet", blob="2" * 40, size=7),
            TreeEntry(path="state/compact/x/index/daily.json", blob="3" * 40, size=9),
        ],
        {},
        paths=[
            "state/compact/x/daily/2026/09/01.parquet",
            "state/compact/x/daily/2026/09/old",
            "state/compact/x/index/daily.json",
        ],
        widen=lambda _: None,
    )

    with pytest.raises(FileNotFetchedError) as refused:
        listing.fetch(beside=["state/compact/x/daily/2026/09/01.parquet"])

    assert "(1 such files)" in str(refused.value), "a file entry brought a folder beside it"


def test_a_folder_whose_files_are_on_disk_is_not_widened_for(tmp_path: Path) -> None:
    """Only the entries that bring an absent file reach the checkout, in one call.

    Each folder fetched holds a named path rather than being one, as a ledger's
    index folder holds the index files a task names.
    """
    a_checkout(tmp_path)
    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        ["state/days", "state/lacking"],
        [
            TreeEntry(path="state/days/2026/09/01.csv", blob="1" * 40, size=1),
            TreeEntry(path="state/lacking/2026-09.csv", blob="2" * 40, size=5),
        ],
        {},
        paths=["state/days/2026/09", "state/lacking/2026-09.csv"],
        widen=asked.append,
    )

    with pytest.raises(FileNotFetchedError):
        listing.fetch(["state/days", "state/lacking"])

    assert asked == [["state/lacking"]]


def test_a_later_task_sees_what_an_earlier_one_deleted_and_wrote(tmp_path: Path) -> None:
    """A deleted file is gone from the listing; a written one is there, weighed on disk."""
    listing = disk_listing(a_checkout(tmp_path), ["state/days"])
    written = tmp_path / "state/days/2026/09/03.csv"
    written.write_text("eeeee", encoding="ascii")
    elsewhere = tmp_path / "state/other/y.csv"
    elsewhere.write_text("f", encoding="ascii")

    later = listing.settled(
        written=["state/days/2026/09/03.csv", "state/other/y.csv"],
        deleted=["state/days/2026/09/01.csv"],
    )

    assert later.files_under("state/days") == [
        "state/days/2026/09/02.csv",
        "state/days/2026/09/03.csv",
    ]
    assert later.size_of("state/days/2026/09/03.csv") == 5
    assert listing.holds("state/days/2026/09/01.csv"), "the earlier listing changed"


# --- what a fetch would download, held to the shard's budget -----------------------

#: Two days the commit holds and the checkout lacks, 12 and 30 bytes.
BUDGETED: Final = [
    TreeEntry(path="state/days/2026/09/01.csv", blob="1" * 40, size=12),
    TreeEntry(path="state/days/2026/09/02.csv", blob="2" * 40, size=30),
]


def a_budgeted_listing(
    root: Path, widen: Callable[[Sequence[str]], None], *, budget: int
) -> FileListing:
    """A shard's listing of September's two days, with the most bytes the shard may download."""
    return FileListing.from_commit(
        root,
        ["state/days"],
        BUDGETED,
        {},
        paths=["state/days/2026/09"],
        widen=widen,
        budget=budget,
    )


def test_a_fetch_costs_each_listed_file_it_brings_once_and_nothing_already_on_disk(
    tmp_path: Path,
) -> None:
    listing = a_budgeted_listing(tmp_path, lambda _: None, budget=100)

    assert listing.cost(["state/days/2026/09"], beside=["state/days/2026/09/01.csv"]) == 42
    on_disk = tmp_path / "state/days/2026/09/02.csv"
    on_disk.parent.mkdir(parents=True)
    on_disk.write_text("x" * 30, encoding="ascii")
    assert listing.cost(["state/days/2026/09"]) == 12
    assert listing.room() == 100


def test_a_fetch_past_what_is_left_of_the_budget_is_refused_before_the_checkout_widens(
    tmp_path: Path,
) -> None:
    """Refused by a type of its own: a step that refuses a file it cannot read must not catch it."""
    asked: list[Sequence[str]] = []
    listing = a_budgeted_listing(tmp_path, asked.append, budget=41)

    with pytest.raises(OverBudgetError) as refused:
        listing.fetch_within_budget(["state/days/2026/09"])

    assert (refused.value.needed, refused.value.room, refused.value.budget) == (42, 41, 41)
    assert not isinstance(refused.value, ValueError)
    assert asked == []
    assert listing.downloaded() == {"state/days": 0}


def test_a_fetch_of_exactly_what_is_left_goes_ahead(tmp_path: Path) -> None:
    """The widening is asked for; it brings nothing here, so the read then fails by name."""
    asked: list[Sequence[str]] = []
    listing = a_budgeted_listing(tmp_path, asked.append, budget=42)

    with pytest.raises(FileNotFetchedError):
        listing.fetch_within_budget(["state/days/2026/09"])

    assert asked == [["state/days/2026/09"]]


def test_a_listing_read_off_the_disk_answers_to_no_budget(tmp_path: Path) -> None:
    listing = disk_listing(a_checkout(tmp_path), ["state/days"])

    assert (listing.budget, listing.room()) == (None, None)
    listing.fetch_within_budget(["state/days/2026/09"])
