"""Does a listing answer only for its folders, weigh each file, and refuse to read an absent one?

A task learns what its folders hold from a `FileListing`, never from the disk.
These tests pin the three promises that makes: a folder the task did not declare
is refused rather than read as empty; a declared folder the commit does not
hold answers empty; and a file the commit holds is never taken for a missing
member - after the checkout is widened for it, it is on disk or the read fails.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

from idhazh.gardener.file_listing import FileListing, FileNotFetchedError, TreeEntry

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


def test_a_listing_read_off_the_disk_names_every_file_with_its_size(tmp_path: Path) -> None:
    listing = FileListing.from_disk(a_checkout(tmp_path), ["state/days", "state/traces/"])

    assert dict(listing.sizes) == {
        "state/days/2026/09/01.csv": 1,
        "state/days/2026/09/02.csv": 2,
        "state/traces/2026/09/01/0001-0.jsonl": 3,
    }
    assert listing.files_under("state/days") == [
        "state/days/2026/09/01.csv",
        "state/days/2026/09/02.csv",
    ]
    assert listing.paths_under(tmp_path / "state" / "traces") == [
        tmp_path / "state/traces/2026/09/01/0001-0.jsonl"
    ]
    assert listing.size_of(tmp_path / "state/days/2026/09/02.csv") == 2
    assert listing.downloaded() is None, "nothing was downloaded to read the disk"


def test_named_paths_ignore_unlisted_neighbours(tmp_path: Path) -> None:
    root = a_checkout(tmp_path)
    named = root / "state/days/2026/09/01.csv"
    listing = FileListing.from_paths(root, [named], folders=["state/days"])
    assert dict(listing.sizes) == {"state/days/2026/09/01.csv": 1}
    assert listing.paths_under(root / "state/days") == [named]
    assert not listing.holds(root / "state/days/2026/09/02.csv")
    with pytest.raises(ValueError, match="outside"):
        FileListing.from_paths(root, [root / "state/other/x.csv"], folders=["state/days"])


def test_a_folder_the_task_did_not_declare_is_refused_and_never_read_as_empty(
    tmp_path: Path,
) -> None:
    listing = FileListing.from_disk(a_checkout(tmp_path), ["state/days", "state/other"])
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
    listing = FileListing.from_disk(a_checkout(tmp_path), ["state/days", "state/not-yet"])

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
        tmp_path, ["state/days"], entries, {"2" * 40: 34}, widen=lambda _: None
    )

    assert dict(listing.sizes) == {"state/days/2026/09/01.csv": 12, "state/days/2026/09/02.csv": 34}
    with pytest.raises(ValueError, match=r"state/days/2026/09/02\.csv has no size"):
        FileListing.from_commit(tmp_path, ["state/days"], entries, {}, widen=lambda _: None)


def test_a_file_entry_brings_only_the_files_beside_it(tmp_path: Path) -> None:
    """What a sparse checkout takes for a name that is a file: its folder's own files."""
    listing = FileListing.from_commit(
        tmp_path,
        ["state/compact/x"],
        [
            TreeEntry(path="state/compact/x/daily/watermark.json", blob="1" * 40, size=5),
            TreeEntry(path="state/compact/x/daily/2026/09/01.parquet", blob="2" * 40, size=7),
            TreeEntry(path="state/compact/x/index/daily.json", blob="3" * 40, size=9),
        ],
        {},
        widen=lambda _: None,
    )

    with pytest.raises(FileNotFetchedError) as refused:
        listing.fetch(beside=["state/compact/x/daily/watermark.json"])

    assert "(1 such files)" in str(refused.value), "a file entry brought a folder beside it"


def test_a_folder_whose_files_are_on_disk_is_not_widened_for(tmp_path: Path) -> None:
    """Only the entries that bring an absent file reach the checkout, in one call."""
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
        widen=asked.append,
    )

    with pytest.raises(FileNotFetchedError):
        listing.fetch(["state/days", "state/lacking"])

    assert asked == [["state/lacking"]]


def test_a_later_task_sees_what_an_earlier_one_deleted_and_wrote(tmp_path: Path) -> None:
    """A deleted file is gone from the listing; a written one is there, weighed on disk."""
    listing = FileListing.from_disk(a_checkout(tmp_path), ["state/days"])
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
