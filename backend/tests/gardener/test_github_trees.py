"""Does a shard size a file it never downloaded from GitHub's named blob endpoint?

The fixture records names and blob ids for a small test tree. The fake API
returns only the size of the requested blob, with no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from utilities import gardener_publish

from ._garden import GARDENER_FIXTURES, a_partial_clone, an_origin, quiet_git

#: The folder GitHub was asked about, and what it said.
LISTED: Final = GARDENER_FIXTURES / "trees-api" / "listed"
REPLY: Final = GARDENER_FIXTURES / "trees-api" / "reply.json"

#: Where the origin holds the same bytes.
FOLDER: Final = "state/listed"


class RecordedBlobs:
    """GitHub's blob API as it answers for the named files in the fixture."""

    def __init__(self) -> None:
        self.reply: dict[str, Any] = json.loads(REPLY.read_text(encoding="utf-8"))
        self.sizes = {
            item["sha"]: {"size": item["size"]}
            for item in self.reply["tree"]
            if item.get("type") == "blob"
        }
        self.asked: list[str] = []

    def read(self, path: str) -> dict[str, Any]:
        self.asked.append(path)
        return self.sizes[path.rsplit("/", 1)[-1]]


def test_a_file_the_shard_never_downloaded_is_sized_from_githubs_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    files = {
        f"{FOLDER}/{name}": LISTED.joinpath(*name.split("/")).read_text(encoding="ascii")
        for name in ("2026-09-01.txt", "nested/2026-09-02.txt")
    }
    origin, _ = an_origin(tmp_path, files)
    shard = a_partial_clone(tmp_path, origin, "config")
    checkout = gardener_publish.Checkout(shard)
    blobs = RecordedBlobs()

    listing = gardener_publish.read_the_listing(
        checkout, shard, [FOLDER], [FOLDER], blobs
    )

    assert blobs.asked == [f"git/blobs/{blob}" for blob in sorted(blobs.sizes)]
    assert dict(listing.sizes) == {name: len(text.encode("ascii")) for name, text in files.items()}
    assert not (shard / "state").exists(), "a file was downloaded to be sized"


def test_a_full_clone_is_sized_by_git_and_never_asks_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every file is in the clone, so git prints every size and nothing is asked."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {f"{FOLDER}/a.txt": "abc\n"})
    blobs = RecordedBlobs()

    listing = gardener_publish.read_the_listing(
        gardener_publish.Checkout(checkout), checkout, [FOLDER], [FOLDER], blobs
    )

    assert dict(listing.sizes) == {f"{FOLDER}/a.txt": 4}
    assert blobs.asked == []


def test_many_named_period_paths_are_split_before_git_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {})

    listed = gardener_publish.Checkout(checkout).list_files(
        [
            f"state/old-days/2026/09/01/run-{item:08d}-recorded-period-file.csv"
            for item in range(1200)
        ]
    )

    assert listed == []
