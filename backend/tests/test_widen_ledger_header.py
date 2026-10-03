"""Can a ledger whose contract MOVED its columns be appended to again, and is the pass repeatable?

The oracle is the append. A read-only check cannot see the header equality test
that makes a stale ledger unappendable, so every case here puts a stale file on
disk, proves the append refuses it, re-files it, and proves the append lands.
Both directions are covered: a header narrower than the contract, and one wider.

**Two kinds of ledger, because the utility has two registries to ask.** A ledger
the post-merge settlement covers declares its reader in `ledger.keyed_paths`; a
day tree declares it in `ledger.keys._TREE_SHAPES`. Driving only the first is how
nine of fourteen ledgers were refused for a day with every test green.

Everything is driven from two small committed fixtures and one day file a test
builds, each read or built inside the test that needs it. Nothing walks the
committed ledger (`CLAUDE.md` section 13) - the question is what the utility
does to a file, and a fixture holds a header the archive can no longer produce.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair import DROPPED_CELLS, StorySimilarityPair
from idhazh.telemetry import prune
from utilities import widen_ledger_header

DATE = "2026-09-18"
TARGET = "content-similarity-judge-scored-pairs"

#: The day tree this drives end to end. Feed health is a day tree the widener
#: names, and five of its columns are optional ones an older generation lacked,
#: so a day file under the narrower header re-files and every row still reads.
TREE_TARGET = LedgerName.FEED_HEALTH
TREE_DATE = "2026-09-16"

#: The header this ledger carried before the judge-call stamp was appended.
NARROW = FIXTURES_DIR / "state" / "scored-pairs-before-the-stamp.csv"

#: The header it carried while `decode_digest` was a column, taken off the
#: committed day file as it stood before that column left on 2026-09-21.
WIDE = FIXTURES_DIR / "state" / "scored-pairs-carrying-the-decode-digest.csv"

#: A feed-health header narrower than the one this checkout writes: the row's
#: first nine columns, without the five that name the address asked and what its
#: robots file said. Built rather than read off the archive, so the case is on
#: disk whatever day the archive happens to end at.
NARROWER_TREE_HEADER: Final = (
    "version",
    "run_id",
    "date",
    "feed_id",
    "checked_at",
    "outcome",
    "status",
    "items",
    "detail",
)

#: The ledgers in the vocabulary that neither registry names a reader for.
#: Named rather than counted, because a count that falls by one says a ledger lost
#: its reader and never says which one - and that is exactly the failure this
#: file missed on 2026-09-22, when five day trees left `ledger.keyed_paths` and
#: the only test watching a refusal was watching a ledger that had just joined
#: them.
UNREGISTERED: Final = frozenset(
    {
        "-".join(ledger.entry(LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).prefix),
        "-".join(ledger.entry(LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES).prefix),
        "-".join(ledger.entry(LedgerName.SUMMARY_QUALITY_EVALS_INDEX).prefix),
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


def a_feed_verdict(feed_id: str) -> FeedHealthRow:
    """One feed's verdict for `TREE_DATE`, with none of the five later columns filled."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=f"{TREE_DATE}-1",
        date=TREE_DATE,
        feed_id=feed_id,
        checked_at=f"{TREE_DATE}T06:00:00Z",
        outcome=FetchOutcome.OK,
        status=200,
        items=4,
    )


def a_stale_tree_day(state_dir: Path) -> Path:
    """One day file of a DAY TREE, under a header narrower than the one it writes now.

    Put where the tree's own path helper puts it: a day directory rather than a
    dated file, which is the move that took the day trees out of
    `ledger.keyed_paths` in the first place. Named for the bytes a committed head
    already held, which is the file a narrower generation survives in. Every cell
    comes from the row's own `csv_row`, so only the column list is older.
    """
    path = ledger.path(state_dir, TREE_TARGET, TREE_DATE) / ledger.BEFORE_PARTITION_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.writer(handle, lineterminator="\n")
        out.writerow(NARROWER_TREE_HEADER)
        for row in (a_feed_verdict("wire"), a_feed_verdict("lab")):
            cells = row.csv_row()
            out.writerow([cells[name] for name in NARROWER_TREE_HEADER])
    return path


def rows_of(path: Path) -> list[dict[str, str]]:
    """Every data row of one day file, read by name."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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

    widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

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

    widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

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

    first = widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)
    settled = path.read_bytes()
    second = widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

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

    widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

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

    widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

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

    dry = widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=False)

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

    live = widen_ledger_header.widen(TARGET, state_dir=tmp_path, write=True)

    assert live == dry


def test_a_store_no_registry_names_a_reader_for_is_refused_by_name(tmp_path: Path) -> None:
    """An operator who typed a real ledger is holding a real question.

    The judge's metrics are in the prune vocabulary, their day files are real,
    and neither registry names the contract that reads one of their rows. Saying
    so beats reporting that nothing happened to a file that is plainly there.

    **This target used to be `scores`, and that was the bug this commit fixes.**
    `scores` is a day tree, so the refusal it was asserting stopped being about a
    ledger with no reader the moment the lookup learnt to ask
    `DAY_TREES`. A refusal is the right answer for exactly the ledgers
    in `UNREGISTERED` below, and the census there is what keeps this one honest.
    """
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    day = ledger.path(tmp_path, which, "2026-09-18")
    day.parent.mkdir(parents=True)
    day.write_text("version\n", encoding="utf-8", newline="")

    with pytest.raises(ValueError, match="names a reader for"):
        widen_ledger_header.widen("-".join(ledger.entry(which).prefix), state_dir=tmp_path)


def test_the_utility_refuses_a_word_that_is_not_a_store(tmp_path: Path) -> None:
    """A path is never a name here, and the refusal names the command that said no."""
    with pytest.raises(ValueError, match="re-files a ledger"):
        widen_ledger_header.widen("scored-pairs", state_dir=tmp_path)


def test_the_store_a_prune_refuses_by_name_is_still_re_filable() -> None:
    """It is refused a DELETION, and re-filing a header deletes nothing.

    `summary-quality-evals-index` is what the eval writer reads to refuse a
    measurement it already holds, so no day of it may be taken out. That reason
    is not about a column list, and a widener that inherited it would refuse a
    legitimate migration with a sentence about deletion.
    """
    assert set(widen_ledger_header.LEDGERS) >= set(prune.REFUSED)
    assert set(widen_ledger_header.LEDGERS) >= set(prune.TARGETS)


def test_a_store_with_no_file_yet_reports_nothing_and_raises_nothing(tmp_path: Path) -> None:
    """Every ledger in the vocabulary is named before its first writer lands.

    There is no header on disk to disagree with the contract, so there is
    nothing to re-file - and a refusal there would say a ledger was broken when
    it was only new.
    """
    a_narrow_day(tmp_path)

    assert (
        widen_ledger_header.widen(
            "content-similarity-judge-fitted-thresholds", state_dir=tmp_path
        )
        == []
    )


def test_a_day_tree_re_files_onto_the_column_list_its_contract_holds_now(
    tmp_path: Path,
) -> None:
    """The whole class of ledger this door was refusing, driven end to end.

    A day tree is where a writer holds its own file, so there is no append to
    refuse the stale header the way `require_matching_header` refuses one on a
    shared file - the fold is what rewrites it, and the fold has no ledger
    argument. That is precisely why an operator needs this door.

    Read by name on both sides, so a row that lost the wrong cell fails here
    rather than passing a width check that only counts columns. Then read again
    through the contract, because a header a reader cannot parse is a widening
    that moved cells into the wrong columns.
    """
    path = a_stale_tree_day(tmp_path)
    before = rows_of(path)
    added = set(FeedHealthRow.csv_columns()) - set(ledger.read_header(path))
    assert added, "the fixture has to predate a column the contract names now"

    report = widen_ledger_header.widen(TREE_TARGET, state_dir=tmp_path, write=True)

    assert [entry.changed for entry in report] == [True]
    assert [entry.rows for entry in report] == [len(before)]
    assert ledger.read_header(path) == FeedHealthRow.csv_columns()

    after = rows_of(path)
    for old, new in zip(before, after, strict=True):
        assert {name: new[name] for name in old} == old
        assert all(new[name] == "" for name in added), "a column the day never had is empty"
        assert FeedHealthRow.from_csv_row(new).feed_id == old["feed_id"]


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
        day = tmp_path / relpath / TREE_DATE.replace("-", "/")
        day.parent.mkdir(parents=True, exist_ok=True)
        day.with_suffix(".csv").write_text("version\n", encoding="utf-8", newline="")
        try:
            widen_ledger_header.widen(name, state_dir=tmp_path)
        except ValueError as refusal:
            assert "names a reader for" in str(refusal)
            refused.add(name)

    assert refused == UNREGISTERED
    assert len(widen_ledger_header.LEDGERS) - len(refused) == 4, (
        "four of seven have CSV headers; the other three are named in UNREGISTERED"
    )
