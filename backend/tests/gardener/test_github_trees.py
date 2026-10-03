"""Does a shard size a file it never downloaded from GitHub's own answer, matched by blob id?

The reply beside the folder `tests/fixtures/gardener/trees-api/listed/` was
recorded once from GitHub's trees API, after that folder was pushed. A partial
clone of an origin holding the same bytes holds the same tree, because a tree id
is a hash of the names and blobs inside it, so the recorded reply answers for it
exactly as GitHub would, with no network.
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


class RecordedTrees:
    """GitHub's trees API as it answered once, for the one tree it was asked about."""

    def __init__(self) -> None:
        self.reply: dict[str, Any] = json.loads(REPLY.read_text(encoding="utf-8"))
        self.asked: list[str] = []

    def read(self, path: str) -> dict[str, Any]:
        self.asked.append(path)
        return self.reply


def test_a_file_the_shard_never_downloaded_is_sized_from_githubs_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    files = {
        f"{FOLDER}/{path.relative_to(LISTED).as_posix()}": path.read_text(encoding="ascii")
        for path in sorted(LISTED.rglob("*"))
        if path.is_file()
    }
    origin, _ = an_origin(tmp_path, files)
    shard = a_partial_clone(tmp_path, origin, "config")
    checkout = gardener_publish.Checkout(shard)
    trees = RecordedTrees()
    assert checkout.folder_trees([FOLDER]) == {FOLDER: trees.reply["sha"]}, (
        "the fixture folder changed since GitHub's reply was recorded: push it and record "
        "the reply again"
    )

    listing = gardener_publish.read_the_listing(checkout, shard, [FOLDER], trees)

    assert trees.asked == [f"git/trees/{trees.reply['sha']}?recursive=1"]
    assert dict(listing.sizes) == {name: len(text.encode("ascii")) for name, text in files.items()}
    assert not (shard / "state").exists(), "a file was downloaded to be sized"


def test_a_full_clone_is_sized_by_git_and_never_asks_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every file is in the clone, so git prints every size and nothing is asked."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {f"{FOLDER}/a.txt": "abc\n"})
    trees = RecordedTrees()

    listing = gardener_publish.read_the_listing(
        gardener_publish.Checkout(checkout), checkout, [FOLDER], trees
    )

    assert dict(listing.sizes) == {f"{FOLDER}/a.txt": 4}
    assert trees.asked == []
