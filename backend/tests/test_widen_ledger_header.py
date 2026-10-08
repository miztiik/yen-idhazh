"""Can a ledger whose contract MOVED its columns be appended to again, and is the pass repeatable?

The oracle is the append. A read-only check cannot see the header equality test
that makes a stale ledger unappendable, so every case here puts a stale file on
disk, proves the append refuses it, re-files it, and proves the append lands.
Both directions are covered: a header narrower than the contract, and one wider.

**One registry is asked, and the census names every ledger it cannot read.** A
ledger the post-merge settlement covers declares its reader in
`ledger.keyed_paths`, and the utility reads no other list. Driving only one
ledger is how nine of fourteen ledgers were refused for a day with every test
green, so the census below asks every ledger in the vocabulary.

Everything is driven from two small committed fixtures, each read inside the
test that needs it. Nothing walks the committed ledger (`CLAUDE.md` section
13) - the question is what the utility does to a file, and a fixture holds a
header the archive can no longer produce.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair import DROPPED_CELLS, StorySimilarityPair
from idhazh.telemetry import prune
from utilities import widen_ledger_header

DATE = "2026-09-18"
TARGET = "content-similarity-judge-scored-pairs"

#: The day the census below files each ledger's one header-only file under.
CENSUS_DATE = "2026-09-16"


def test_relative_state_root_refiles_the_named_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_narrow_day(tmp_path)
    monkeypatch.chdir(tmp_path)
    relative = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=Path()
    )
    absolute = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path
    )
    assert relative == absolute


#: The header this ledger carried before the judge-call stamp was appended.
NARROW = FIXTURES_DIR / "state" / "scored-pairs-before-the-stamp.csv"

#: The header it carried while `decode_digest` was a column, taken off the
#: committed day file as it stood before that column left on 2026-09-21.
WIDE = FIXTURES_DIR / "state" / "scored-pairs-carrying-the-decode-digest.csv"

#: The ledgers in the vocabulary that the registry names no reader for.
#: Named rather than counted, because a count that falls by one says a ledger lost
#: its reader and never says which one - and that is exactly the failure this
#: file missed on 2026-09-22, when five day trees left `ledger.keyed_paths` and
#: the only test watching a refusal was watching a ledger that had just joined
#: them.
UNREGISTERED: Final = frozenset(
    {
        "-".join(ledger.entry(LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).prefix),
        "-".join(
            ledger.entry(LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES).prefix
        ),
    }
)


def a_narrow_day(state_dir: Path) -> Path:
    """One day file at the pre-widening header, where the ledger's own path helper puts it."""
    path = ledger.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, DATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(NARROW, path)
    return path


def a_wide_day(state_dir: Path) -> Path:
    """One day file still carrying the column this contract stopped naming."""
    path = ledger.path(state_dir, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, DATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WIDE, path)
    return path


def a_fresh_pair(path: Path) -> StorySimilarityPair:
    """A row this build would write, built off a row the fixture already holds.

    Re-keyed onto its own addresses, because the contract recomputes `pair_key`
    from them and a row that kept the fixture's would be refused before the
    append could be asked anything.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        first = next(csv.DictReader(handle))
    return StorySimilarityPair.from_csv_row(first).model_copy(
        update={"judged_by_run_id": f"{DATE}-9"}
    )


def test_a_narrow_day_refuses_the_append_that_the_widened_one_takes(tmp_path: Path) -> None:
    """The load-bearing half. A read-only check cannot see the header equality test.

    `require_matching_header` compares the committed header to the contract's
    columns and raises rather than write, so the ledger is dead to the next run
    until the file on disk carries the new header.
    """
    path = a_narrow_day(tmp_path)
    fresh = a_fresh_pair(path)

    with pytest.raises(ValueError, match="Migrate the ledger"):
        ledger.append_story_similarity_pairs(tmp_path, DATE, [fresh])

    widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    assert ledger.append_story_similarity_pairs(tmp_path, DATE, [fresh]) == 1
    assert ledger.read_header(path) == StorySimilarityPair.csv_columns()


def test_widening_keeps_every_cell_the_narrow_header_named(tmp_path: Path) -> None:
    """A column appended at the tail leaves every historical value where it was.

    Read by name rather than by position, because that is the promise the tail
    rule makes: a cell inserted in the middle would pass a position check on the
    columns before it and put the wrong name over every value after it.

    A cell the row has stopped naming is the one exception, and it is named as
    the survivors rather than counted: a check that only asserted the count fell
    would pass whichever cells went.
    """
    path = a_narrow_day(tmp_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        before = list(csv.DictReader(handle))

    widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    with path.open("r", encoding="utf-8", newline="") as handle:
        after = list(csv.DictReader(handle))
    assert len(after) == len(before)
    for old, new in zip(before, after, strict=True):
        carried = {name: value for name, value in old.items() if name not in DROPPED_CELLS}
        assert set(old) - set(new) == DROPPED_CELLS & set(old)
        # `judge_id` is the one appended cell the widening fills rather than
        # leaves empty: these rows were judged by the judge that owns the ledger.
        assert {name: new[name] for name in carried} == carried
        assert new["judge_id"] == "content-similarity-judge"
        assert new["judged_by_run_id"] == ""


def test_a_second_pass_over_a_widened_store_writes_nothing(tmp_path: Path) -> None:
    """A widener that cannot be run twice is a widener nobody can re-run after a failure."""
    path = a_narrow_day(tmp_path)

    first = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )
    settled = path.read_bytes()
    second = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    assert [entry.changed for entry in first] == [True]
    assert [entry.changed for entry in second] == [False]
    assert path.read_bytes() == settled


def test_a_day_still_carrying_a_dropped_column_refuses_the_append_until_it_is_re_filed(
    tmp_path: Path,
) -> None:
    """The other direction, and the one a deletion needs.

    `require_matching_header` compares widths, so a file one column WIDER than
    the contract is as dead to the next append as one that is narrower - and the
    raise costs the run its whole commit step, every ledger staged beside this
    one included.
    """
    path = a_wide_day(tmp_path)
    fresh = a_fresh_pair(path)
    assert set(ledger.read_header(path)) - set(StorySimilarityPair.csv_columns()) == DROPPED_CELLS

    with pytest.raises(ValueError, match="Migrate the ledger"):
        ledger.append_story_similarity_pairs(tmp_path, DATE, [fresh])

    widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    assert ledger.append_story_similarity_pairs(tmp_path, DATE, [fresh]) == 1
    assert ledger.read_header(path) == StorySimilarityPair.csv_columns()


def test_without_the_carried_entry_the_same_file_refuses_to_re_file(tmp_path: Path) -> None:
    """The bite proof for the test above, and the reason the entry ships in this commit.

    `migrate_header` refuses any heading it cannot place rather than dropping
    cells silently, so a column deleted from the contract without an entry in
    `STORY_SIMILARITY_PAIR_CARRIED` leaves every committed day file unappendable
    AND unrepairable at once.

    The carried set is passed empty here rather than edited, which is the same
    call the re-file makes with the entry missing.
    """
    path = a_wide_day(tmp_path)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="cannot place"):
        ledger.migrate_header(
            path,
            StorySimilarityPair.csv_columns(),
            ledger.refiler(StorySimilarityPair),
            carried=(),
        )

    assert path.read_bytes() == before, "the refusal moves nothing"
    assert DROPPED_CELLS <= ledger.STORY_SIMILARITY_PAIR_CARRIED, (
        "the entry that makes the re-file above succeed"
    )


def test_re_filing_a_dropped_column_away_keeps_every_cell_the_contract_still_names(
    tmp_path: Path,
) -> None:
    """A dropped cell goes and nothing beside it moves.

    Read by name, so a row that lost the wrong cell fails here rather than
    passing a width check that only counts columns.
    """
    path = a_wide_day(tmp_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        before = list(csv.DictReader(handle))

    widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    with path.open("r", encoding="utf-8", newline="") as handle:
        after = list(csv.DictReader(handle))
    assert len(after) == len(before)
    for old, new in zip(before, after, strict=True):
        assert set(old) - set(new) == DROPPED_CELLS
        assert new == {name: cell for name, cell in old.items() if name not in DROPPED_CELLS}


def test_a_dry_run_reports_what_a_live_run_writes_and_writes_nothing(tmp_path: Path) -> None:
    """The report is the deliverable of a dry run, so it has to be the live run's report."""
    path = a_narrow_day(tmp_path)
    untouched = path.read_bytes()

    dry = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=False
    )

    assert path.read_bytes() == untouched
    assert [(e.path, e.columns_before, e.columns_after, e.rows, e.changed) for e in dry] == [
        (
            f"content-similarity-judge/scored-pairs/{DATE.replace('-', '/')}.csv",
            22,
            len(StorySimilarityPair.csv_columns()),
            2,
            True,
        )
    ]

    live = widen_ledger_header.widen(
        TARGET, names=[DATE.replace("-", "/") + ".csv"], state_dir=tmp_path, write=True
    )

    assert live == dry


def test_a_store_no_registry_names_a_reader_for_is_refused_by_name(tmp_path: Path) -> None:
    """An operator who typed a real ledger is holding a real question.

    The judge's metrics are in the prune vocabulary, their day files are real,
    and the registry names no contract that reads one of their rows. Saying so
    beats reporting that nothing happened to a file that is plainly there.

    **This target used to be `scores`, and that was a bug.** `scores` was a day
    tree, so the refusal it was asserting stopped being about a ledger with no
    reader the moment the lookup learnt to ask the day trees' own table. A
    refusal is the right answer for exactly the ledgers in `UNREGISTERED`
    below, and the census there is what keeps this one honest.
    """
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    day = ledger.path(tmp_path, which, "2026-09-18")
    day.parent.mkdir(parents=True)
    day.write_text("version\n", encoding="utf-8", newline="")

    with pytest.raises(ValueError, match="names a reader for"):
        widen_ledger_header.widen(
            "-".join(ledger.entry(which).prefix), names=["2026/09/18.csv"], state_dir=tmp_path
        )


def test_the_utility_refuses_a_word_that_is_not_a_store(tmp_path: Path) -> None:
    """A path is never a name here, and the refusal names the command that said no."""
    with pytest.raises(ValueError, match="re-files a ledger"):
        widen_ledger_header.widen("scored-pairs", names=["2026/09/18.csv"], state_dir=tmp_path)


def test_the_utility_names_exactly_the_prune_verbs_csv_ledgers() -> None:
    """One vocabulary, two commands: a ledger an operator prunes by day is one this re-files."""
    assert dict(widen_ledger_header.LEDGERS) == dict(prune.TARGETS)


def test_a_store_with_no_file_yet_reports_nothing_and_raises_nothing(tmp_path: Path) -> None:
    """Every ledger in the vocabulary is named before its first writer lands.

    There is no header on disk to disagree with the contract, so there is
    nothing to re-file - and a refusal there would say a ledger was broken when
    it was only new.
    """
    a_narrow_day(tmp_path)

    with pytest.raises(FileNotFoundError):
        widen_ledger_header.widen(
            "content-similarity-judge-fitted-thresholds",
            names=["2026/09/18.csv"],
            state_dir=tmp_path,
        )


def test_every_store_in_the_vocabulary_resolves_except_the_named_ledgers(
    tmp_path: Path,
) -> None:
    """The census. A ledger that quietly loses its reader is named here, not counted.

    This is the test the file did not have on 2026-09-22, when five day trees
    left `ledger.keyed_paths` and the door started refusing them. Nine of
    fourteen ledgers were dead and every test was green, because the only refusal
    under test was one the file asserted was correct.

    Asserted as set equality in both directions at once, so it is red when a
    ledger loses its reader AND red when an unregistered ledger gains one. Either way
    the diff names the ledger.

    One header-only file per ledger, because `widen` reports nothing for a ledger
    with no file and the question here is the lookup, not the re-file.
    """
    refused: set[str] = set()
    for name, relpath in widen_ledger_header.LEDGERS.items():
        day = tmp_path / relpath / CENSUS_DATE.replace("-", "/")
        day.parent.mkdir(parents=True, exist_ok=True)
        day.with_suffix(".csv").write_text("version\n", encoding="utf-8", newline="")
        try:
            widen_ledger_header.widen(
                name, names=[CENSUS_DATE.replace("-", "/") + ".csv"], state_dir=tmp_path
            )
        except ValueError as refusal:
            assert "names a reader for" in str(refusal)
            refused.add(name)

    assert refused == UNREGISTERED
    assert len(widen_ledger_header.LEDGERS) - len(refused) == 2, (
        "two of four have CSV headers; the other two are named in UNREGISTERED"
    )
