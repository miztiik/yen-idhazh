"""Which ledgers can the header widener be pointed at, and how does it say no?

`utilities.widen_ledger_header` re-files a CSV day file under the column list its
contract holds now, so an append can land again. Its vocabulary is the prune
verb's CSV word list, and the contract that reads a row comes from
`ledger.keyed_paths`, the ledgers the post-merge settlement covers. Both are
empty now: the judge's fitted line, the last ledger either named, moved to the
ledger door, where a file keeps the shape it was written under and nothing
re-files it. So no ledger is left for the widener to re-file, and the tests
that re-filed fitted-line days left with that ledger's CSV path.

What is left here is how the utility refuses: a word that is not a ledger, and
a ledger the registry names no reader for. Nothing walks the committed ledger
(`CLAUDE.md` section 13).
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest

from idhazh import ledger
from idhazh.telemetry import prune
from utilities import widen_ledger_header


def test_a_store_no_registry_names_a_reader_for_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator who typed a real ledger is holding a real question.

    No ledger in the vocabulary has a reader now, so the case is built: a word
    for the folder the judge's fitted line filled as CSV before it moved to the
    door. Its day files are real, and the registry names no contract that reads
    one of their rows. Saying so beats reporting that nothing happened to a file
    that is plainly there.

    **This target used to be `scores`, and that was a bug.** `scores` was a day
    tree, so the refusal it was asserting stopped being about a ledger with no
    reader the moment the lookup learnt to ask the day trees' own table.
    """
    folder = "content-similarity-judge/fitted-thresholds"
    word = folder.replace("/", "-")
    monkeypatch.setattr(
        widen_ledger_header,
        "LEDGERS",
        MappingProxyType({**widen_ledger_header.LEDGERS, word: folder}),
    )
    day = tmp_path / folder / "2026" / "09" / "18.csv"
    day.parent.mkdir(parents=True)
    day.write_text("version\n", encoding="utf-8", newline="")

    with pytest.raises(ValueError, match="names a reader for"):
        widen_ledger_header.widen(word, names=["2026/09/18.csv"], state_dir=tmp_path)


def test_the_utility_refuses_a_word_that_is_not_a_store(tmp_path: Path) -> None:
    """A path is never a name here, and the refusal names the command that said no."""
    with pytest.raises(ValueError, match="re-files a ledger"):
        widen_ledger_header.widen("scored-pairs", names=["2026/09/18.csv"], state_dir=tmp_path)


def test_the_utility_names_exactly_the_prune_verbs_csv_ledgers() -> None:
    """One vocabulary, two commands: a ledger an operator prunes by day is one this re-files."""
    assert dict(widen_ledger_header.LEDGERS) == dict(prune.TARGETS)


def test_no_ledger_is_left_for_the_widener_to_re_file(tmp_path: Path) -> None:
    """The vocabulary and the readers are both empty, so the fitted line is refused as a word.

    A ledger that returned to CSV would join both lists, and this fails until
    the change that brings it back says what reads its rows.
    """
    assert widen_ledger_header.LEDGERS == {}
    assert ledger.keyed_paths(tmp_path, date=None) == []
    with pytest.raises(ValueError, match="re-files a ledger"):
        widen_ledger_header.widen(
            "content-similarity-judge-fitted-thresholds",
            names=["2026/09/18.csv"],
            state_dir=tmp_path,
        )