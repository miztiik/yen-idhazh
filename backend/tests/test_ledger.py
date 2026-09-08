"""Append-only state ledger protections."""

from __future__ import annotations

import csv
import io
import tracemalloc
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh import cli, ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.evals import writer
from idhazh.evals.writer import OBSERVATION_KEY
from utilities import migrate_score_ledger as migrate
from utilities import split_published_ledger as split_ledger
from utilities.migrate_feed_health import NARROW_COLUMNS, WIDENED_AT, widen
from utilities.migrate_published_ledger import narrow
from utilities.reconcile_prefill import TOLERANCE, pool_counters, pool_ledger, reconcile

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FIXTURES = FIXTURES_DIR / "state"
DATE = "2026-08-23"
RUN_ID = "2026-08-23-1"
STAMP = "2026-08-23T06:00:00Z"
URL = "https://example.org/items/one"
URL_KEY = derive_url_key(URL)
#: The one committed run both instruments measured. Its four `runtime-log-*`
#: artifacts were pulled before they expired and its item-health rows are in the
#: committed month shard, so the reconciliation runs on real data with no
#: network and no mocks (Rule #7).
RECONCILED_DATE = "2026-08-26"
RECONCILED_RUN = "2026-08-26-5"


def seen_row() -> SeenRow:
    return SeenRow(
        version=SeenRow.schema_version(),
        url_key=URL_KEY,
        first_seen_at=STAMP,
        first_seen_run=RUN_ID,
    )


def published_row(*, url_key: str = URL_KEY, on: str = DATE) -> PublishedRow:
    return PublishedRow(
        version=PublishedRow.schema_version(),
        url_key=url_key,
        published_on=on,
        item_id="ai-01",
    )


def health_row() -> FeedHealthRow:
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=RUN_ID,
        date=DATE,
        feed_id="example-feed",
        checked_at=STAMP,
        outcome=FetchOutcome.OK,
        status=200,
        items=1,
        detail=None,
    )


def stale_header(path: Path, columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns[:-1])
        writer.writerow(["stale"] * (len(columns) - 1))


def test_seen_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.seen_path(state, DATE), SeenRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_seen(state, DATE, [seen_row()])


def test_published_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.published_path(state, DATE), PublishedRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_published(state, DATE, [published_row()])


def test_feed_health_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.health_path(state, DATE), FeedHealthRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_health(state, DATE, [health_row()])


def test_load_published_answers_the_same_from_either_header(tmp_path: Path) -> None:
    """The reader maps cells by name, so a column nothing reads could leave without it.

    Both fixtures hold the same eleven rows copied out of `state/published.csv`
    before it was narrowed; the second has no `canonical_url`. The header check
    guards the writer only - `require_matching_header` is called from `_append`
    and from nothing on the read path - and that is what made narrowing the row
    one commit rather than an expand-migrate-contract sequence (CLAUDE.md
    section 11). It still runs because a fork or a stale branch can hold a wide
    ledger, and this says what happens when one does.
    """
    wide, narrow_state = tmp_path / "wide", tmp_path / "narrow"
    for state, fixture in ((wide, "published-v1.csv"), (narrow_state, "published-v2.csv")):
        state.mkdir()
        _flat_file(state).write_bytes((STATE_FIXTURES / fixture).read_bytes())

    wide_header = ledger.read_header(_flat_file(wide))
    narrow_header = ledger.read_header(_flat_file(narrow_state))
    assert set(wide_header) - set(narrow_header) == {"canonical_url"}
    assert {"url_key", "published_on"} <= set(narrow_header)

    published = ledger.load_published(wide)
    assert len(published) == 11, (
        "an empty or trimmed ledger would pass the comparison while proving nothing"
    )
    assert published == ledger.load_published(narrow_state)


def test_the_state_ledgers_append_blind_and_the_reads_absorb_a_repeat(tmp_path: Path) -> None:
    """`ledger._append` writes every row it is handed. Its callers own the repeats.

    Pinned because the promise in `ledger._append` names those callers, and a
    dedupe quietly added here would make that docstring wrong while every test
    still passed. The eval ledger is the other half of the contrast: it refuses
    an observation it already holds, because a row there is a measurement rather
    than a fact about a run.
    """
    state = tmp_path / "state"
    assert ledger.append_published(state, DATE, [published_row()]) == 1
    assert ledger.append_published(state, DATE, [published_row()]) == 1

    with ledger.published_path(state, DATE).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2, "the append path does not deduplicate"
    assert ledger.load_published(state) == {URL_KEY: DATE}, "the read keeps the earliest date"


def _published_fixture(state: Path, *, rows: int, keys: int) -> dict[str, str]:
    """`rows` records over `keys` distinct addresses. Returns what the read owes."""
    state.mkdir(parents=True, exist_ok=True)
    expected: dict[str, str] = {}
    with _flat_file(state).open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=PublishedRow.csv_columns(), lineterminator="\n")
        out.writeheader()
        for number in range(rows):
            key = derive_url_key(f"https://example.org/items/{number % keys}")
            on = f"2026-{8 + number % 4:02d}-0{1 + number % 9}"
            out.writerow(
                {
                    "version": PublishedRow.schema_version(),
                    "url_key": key,
                    "published_on": on,
                    "item_id": f"ai-{number:06d}",
                }
            )
            if key not in expected or on < expected[key]:
                expected[key] = on
    return expected


def _peak_of_load_published(state: Path) -> tuple[dict[str, str], int]:
    tracemalloc.start()
    try:
        published = ledger.load_published(state)
        return published, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_load_published_costs_the_answer_and_not_the_file(tmp_path: Path) -> None:
    """The one unwindowed read over the one ledger with no time bound streams.

    `state/published.csv` is the only ledger here whose read carries no window,
    so it was the only one whose peak was the whole file. Measured 2026-09-07 on
    an Intel Core i7-1265U over the committed 7,243 rows, the materialising read
    peaked at 500.9 B a row against a stored row of 106.9 B - 3.63 MB then, and
    265 MB at the third year of the measured 483 rows a day.

    A threshold in bytes a row would pass for the wrong reason, because what a
    reduction legitimately keeps is its mapping. So the property is asserted
    directly: hold the answer still, double the file, and the peak must not
    follow. Both populations are built and fixed, so this costs the same on the
    day the archive holds ten times either (Rule #12, section 13).
    """
    keys = 20_000
    small = tmp_path / "small"
    large = tmp_path / "large"
    expected_small = _published_fixture(small, rows=keys * 2, keys=keys)
    expected_large = _published_fixture(large, rows=keys * 4, keys=keys)

    published_small, peak_small = _peak_of_load_published(small)
    published_large, peak_large = _peak_of_load_published(large)

    assert published_small == expected_small, "the reduction must keep the earliest date"
    assert published_large == expected_large
    assert len(published_large) == keys, "the fixture has to hold repeats or it proves nothing"
    assert peak_large < peak_small * 1.1, (
        f"twice the rows over the same addresses moved peak from {peak_small} B to "
        f"{peak_large} B, so the read is still holding the file rather than the answer"
    )


def _address(number: int) -> str:
    return derive_url_key(f"https://example.org/items/{number}")


def _day_file(state: Path, date: str) -> Path:
    """`state/published/YYYY/MM/DD.csv`, spelled out rather than asked for.

    The ledger's own path helper would make this a restatement of the code it
    checks, and both the reader and the writer are checked against it now. The
    layout is the thing under test, so the test writes it.
    """
    return state / "published" / date[:4] / date[5:7] / f"{date[8:10]}.csv"


def _flat_file(state: Path) -> Path:
    """`state/published.csv`, spelled out for the reason `_day_file` gives.

    Read and never written. It has no path helper left to ask, because the
    shape a caller names is the day tree.
    """
    return state / "published.csv"


def _tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, POSIX path to bytes. Bounded by what a test wrote."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _published_file(path: Path, dates: dict[str, str]) -> None:
    """One published-shaped file at `path`, holding `url_key -> published_on`.

    Rows go through the contract, so a fixture cannot drift from what a run
    would really append. Every fixture here is built and fixed, so these checks
    cost the same on the day the archive holds ten times the rows (Rule #12).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=PublishedRow.csv_columns(), lineterminator="\n")
        out.writeheader()
        for number, (url_key, on) in enumerate(sorted(dates.items())):
            row = PublishedRow(
                version=PublishedRow.schema_version(),
                url_key=url_key,
                published_on=on,
                item_id=f"ai-{number:010d}",
            )
            out.writerow(row.model_dump(mode="json"))


def test_load_published_reads_no_history_from_a_fresh_clone(tmp_path: Path) -> None:
    """A missing flat file and a missing day tree both mean nothing has published yet.

    Neither is an error. A clone with no history is the state every fresh
    checkout is in, and an empty mapping is what "nothing has run" looks like.
    """
    assert ledger.load_published(tmp_path / "state") == {}


def test_load_published_reads_the_flat_file_the_day_tree_and_their_union(
    tmp_path: Path,
) -> None:
    """Both shapes answer, and holding both answers with the union of the two.

    `state/published.csv` is moving to `state/published/YYYY/MM/DD.csv`. The
    reader learns both shapes before anything writes the new one, so a split
    that half-finishes, or a flat file a union merge brings back after it was
    removed, still returns every address rather than silently dropping the
    shape nobody is reading.
    """
    flat_only = tmp_path / "flat-only"
    _published_file(_flat_file(flat_only), {_address(1): "2026-08-20"})
    assert ledger.load_published(flat_only) == {_address(1): "2026-08-20"}

    days_only = tmp_path / "days-only"
    _published_file(_day_file(days_only, "2026-08-21"), {_address(2): "2026-08-21"})
    _published_file(_day_file(days_only, "2026-08-22"), {_address(3): "2026-08-22"})
    _published_file(_day_file(days_only, "2026-09-03"), {_address(4): "2026-09-03"})
    assert ledger.load_published(days_only) == {
        _address(2): "2026-08-21",
        _address(3): "2026-08-22",
        _address(4): "2026-09-03",
    }, "two days of one month and a day of the next"

    both = tmp_path / "both"
    _published_file(_flat_file(both), {_address(1): "2026-08-20"})
    _published_file(_day_file(both, "2026-08-21"), {_address(2): "2026-08-21"})
    _published_file(_day_file(both, "2026-09-03"), {_address(4): "2026-09-03"})
    assert ledger.load_published(both) == {
        _address(1): "2026-08-20",
        _address(2): "2026-08-21",
        _address(4): "2026-09-03",
    }, "the union, so neither shape can hide an address from the guard"


@pytest.mark.parametrize("earlier_in_the_day_tree", [False, True])
def test_load_published_keeps_the_earliest_date_whichever_shape_holds_it(
    tmp_path: Path, earlier_in_the_day_tree: bool
) -> None:
    """One address in both shapes on two dates. The answer cannot follow read order.

    Asserted both ways round because a reader that simply overwrote would pass
    one arm and fail the other, and which arm it passed would depend on which
    shape it happened to open first.
    """
    state = tmp_path / "state"
    key = _address(1)
    early, late = "2026-08-21", "2026-09-03"
    flat_on, day_on = (late, early) if earlier_in_the_day_tree else (early, late)

    _published_file(_flat_file(state), {key: flat_on})
    _published_file(_day_file(state, day_on), {key: day_on})

    assert ledger.load_published(state) == {key: early}


@pytest.mark.parametrize(
    ("relative", "what"),
    [
        ("2026/08/notes.csv", "a day stem that is not two digits"),
        ("2026/8/21.csv", "a month that is not two digits"),
        ("archive/08/21.csv", "a year that is not four digits"),
        ("README.csv", "a file where a year directory belongs"),
    ],
)
def test_load_published_refuses_a_file_it_cannot_place_in_the_day_tree(
    tmp_path: Path, relative: str, what: str
) -> None:
    """A file the reader cannot place is a fault, and it is never skipped.

    A glob would answer "what matched" and say nothing about what did not, so a
    stray file would sit in a state directory unread and unmentioned - which is
    how a reader starts missing rows without anyone noticing. Every arm here
    holds a real published row, so the refusal is about the name and not about
    the contents.
    """
    state = tmp_path / "state"
    _published_file(state / "published" / relative, {_address(1): "2026-08-21"})

    with pytest.raises(ValueError, match="is not a YYYY/MM/DD published day"):
        ledger.load_published(state)


def test_append_published_writes_the_day_its_rows_name_and_no_other_file(
    tmp_path: Path,
) -> None:
    """The Oracle: one run writes one file, and it is that run's own day.

    The whole state directory is compared rather than the day file alone. An
    append that also touched the flat file, or that opened a neighbouring day
    to check something, would pass an assertion about the day file and fail
    here - and touching a day nobody is publishing is what a partitioned writer
    must never do (`docs/concepts/month-partitions.md`).

    The relpath is asserted against the file that was really written rather
    than against a second spelling of the layout, so a log line cannot drift
    from the file it names.
    """
    state = tmp_path / "state"
    date = "2026-09-07"

    landed = ledger.append_published(state, date, [published_row(on=date)])

    assert landed == 1
    assert list(_tree(state)) == ["published/2026/09/07.csv"]
    assert not _flat_file(state).exists(), "the flat file is read and never written"
    assert ledger.published_relpath(date) == "state/published/2026/09/07.csv"
    assert ledger.published_path(state, date) == _day_file(state, date)


def test_a_run_in_a_later_month_leaves_the_earlier_one_byte_identical(
    tmp_path: Path,
) -> None:
    """A closed day is not rewritten, and the bytes say so rather than a count.

    This is the freeze rule read from the writer's side: the run's own date
    picks the file, so every other day is out of reach. Compared byte for byte
    because a row appended to yesterday would leave the file count unchanged.
    """
    state = tmp_path / "state"
    ledger.append_published(state, "2026-09-30", [published_row(on="2026-09-30")])
    september = _tree(state)
    assert september, "nothing was written, so the comparison below would prove nothing"

    ledger.append_published(
        state, "2026-10-01", [published_row(url_key=_address(2), on="2026-10-01")]
    )

    october = _tree(state)
    assert set(october) - set(september) == {"published/2026/10/01.csv"}
    assert {name: october[name] for name in september} == september


def test_what_the_writer_files_by_day_answers_beside_the_flat_file(tmp_path: Path) -> None:
    """The reader's union still holds once the writer produces the new shape.

    The move only works while both halves agree, so the two are checked
    together here rather than each against a fixture of the other's output: a
    row this writer really appended, and a flat file the split has not taken
    yet, and both addresses back from one read.
    """
    state = tmp_path / "state"
    _published_file(_flat_file(state), {_address(1): "2026-08-20"})

    ledger.append_published(
        state, "2026-09-07", [published_row(url_key=_address(2), on="2026-09-07")]
    )

    assert ledger.load_published(state) == {
        _address(1): "2026-08-20",
        _address(2): "2026-09-07",
    }


def _flat_ledger(path: Path, rows: list[tuple[str, str]]) -> list[str]:
    """One flat `state/published.csv` holding `rows` as (address, published_on).

    Returns the data lines it wrote, in file order, so a test can assert the
    split carried them across rather than re-serialising them. Rows go through
    the contract, so a fixture cannot drift from what a run would append; the
    order and the repeats are the test's, because both are what the split has
    to preserve.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=PublishedRow.csv_columns(), lineterminator="\n")
        out.writeheader()
        for number, (url_key, on) in enumerate(rows):
            out.writerow(
                PublishedRow(
                    version=PublishedRow.schema_version(),
                    url_key=url_key,
                    published_on=on,
                    item_id=f"ai-{number:010d}",
                ).model_dump(mode="json")
            )
    return path.read_text(encoding="utf-8", newline="").split("\n")[1:-1]


def test_the_split_files_every_row_under_the_day_its_own_date_names(tmp_path: Path) -> None:
    """The Oracle: `load_published` answers the same before and after, from day files.

    Four rows over three days and two months, one address published twice, so
    the arms that matter are all here: a day file holds exactly its own rows,
    two months are two directories, and the earliest date still wins for an
    address the flat file held twice.

    The day file is compared byte for byte rather than row by row. Rows are
    copied, never rewritten - so a split that re-serialised them through the
    contract would pass a cell comparison and fail here, which is what stops a
    `version` cell being restamped with today's.
    """
    state = tmp_path / "state"
    written = _flat_ledger(
        _flat_file(state),
        [
            (_address(1), "2026-08-31"),
            (_address(2), "2026-09-01"),
            (_address(3), "2026-08-31"),
            (_address(1), "2026-09-02"),
        ],
    )
    before = ledger.load_published(state)
    assert before == {
        _address(1): "2026-08-31",
        _address(2): "2026-09-01",
        _address(3): "2026-08-31",
    }, "the flat file has to hold a repeat or the earliest-wins arm proves nothing"

    report = split_ledger.run(state)

    assert (report.rows_in, report.rows_out, report.days) == (4, 4, 3)
    assert report.digest == split_ledger.digest(before)
    assert not _flat_file(state).exists(), "the flat file is retired, not left beside the tree"
    assert sorted(_tree(state)) == [
        "published/2026/08/31.csv",
        "published/2026/09/01.csv",
        "published/2026/09/02.csv",
    ]
    header = ",".join(PublishedRow.csv_columns())
    assert _day_file(state, "2026-08-31").read_text(encoding="utf-8", newline="") == (
        f"{header}\n{written[0]}\n{written[2]}\n"
    ), "the two rows that name this day, verbatim and in the order the flat file held them"
    assert ledger.load_published(state) == before


@pytest.mark.parametrize("bad", ["2026-08", "20260831"])
def test_the_split_refuses_a_row_it_cannot_place_and_leaves_the_flat_file(
    tmp_path: Path, bad: str
) -> None:
    """A row that lands nowhere stops the whole split, and nothing is written.

    A published address the split dropped is an address `rank.plan_vertical`
    would plan again, so the answer to a row nobody can place is the reader's
    answer to a file nobody can place: refuse the read rather than skip it.

    Two shapes, because they fail in different places. `2026-08` names a month,
    and the date parser refuses it. `20260831` is a real ISO date the parser
    accepts, and it is the dangerous one: `published_path` cuts a date by
    position, so it would file the row at `state/published/2026/83/.csv` and
    `load_published` would never find it again.

    The bad row is written past the contract on purpose. `PublishedRow` refuses
    it, so the only way this ledger holds one is a hand edit or a mangled merge
    - which is exactly when the flat file has to survive.
    """
    state = tmp_path / "state"
    flat = _flat_file(state)
    _flat_ledger(flat, [(_address(1), "2026-08-31")])
    text = flat.read_text(encoding="utf-8", newline="")
    good = text.split("\n")[1]
    with flat.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"{text}{good.replace('2026-08-31', bad)}\n")
    was = flat.read_bytes()

    with pytest.raises(ValueError, match="names no day file"):
        split_ledger.run(state)

    assert flat.read_bytes() == was, "the flat file is the only copy until the split finishes"
    assert not (state / "published").exists(), "no day file is written when a row cannot be placed"


def test_the_split_retires_a_flat_file_that_holds_nothing(tmp_path: Path) -> None:
    """A header and no rows is a finished cutover, so the file goes and nothing is made.

    A fresh clone that has never published has no flat file at all. This is the
    other end of the same state - the file a run created and never filled - and
    leaving it behind would keep `load_published` opening a file with nothing in
    it for ever.
    """
    state = tmp_path / "state"
    _flat_ledger(_flat_file(state), [])

    report = split_ledger.run(state)

    assert (report.rows_in, report.rows_out, report.days) == (0, 0, 0)
    assert not _flat_file(state).exists()
    assert _tree(state) == {}, "an empty ledger names no day, so no day file is created"
    assert ledger.load_published(state) == {}


def test_the_split_keeps_what_a_day_file_already_holds(tmp_path: Path) -> None:
    """A run that already filed today's rows is not overwritten by the split.

    The writer moved to the day layout before this ran, so a day can hold rows
    in both shapes at once - an early run in the flat file, a later one in the
    day file. Overwriting would lose the later run, which is the one failure
    this cutover is not allowed to have.
    """
    state = tmp_path / "state"
    date = "2026-09-07"
    ledger.append_published(state, date, [published_row(url_key=_address(9), on=date)])
    already = _day_file(state, date).read_text(encoding="utf-8", newline="")
    _flat_ledger(_flat_file(state), [(_address(1), date)])
    before = ledger.load_published(state)
    assert set(before) == {_address(1), _address(9)}, "one address in each shape"

    report = split_ledger.run(state)

    assert report.rows_in == 1
    assert _day_file(state, date).read_text(encoding="utf-8", newline="").startswith(already)
    assert ledger.load_published(state) == before


def carried_row(
    number: int,
    *,
    source_id: str,
    outcome: ItemOutcome = ItemOutcome.OK,
    date: str = DATE,
) -> ItemHealthRow:
    """One item-health row for a distinct address, so a count has something to count."""
    url = f"https://{source_id}.example.org/items/{number}"
    code = None if outcome is ItemOutcome.OK else FailureCode.PAYWALLED
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=date,
        run_id=f"{date}-1",
        item_id=f"ai-{number:010d}",
        url_key=derive_url_key(url),
        canonical_url=url,
        vertical="ai",
        source_id=source_id,
        stage=ItemStage.PUBLISH if outcome is ItemOutcome.OK else ItemStage.EXTRACT,
        outcome=outcome,
        code=code,
    )


def test_the_day_count_is_what_each_feed_put_in_front_of_a_reader(tmp_path: Path) -> None:
    """A slot a feed spent and lost is not a slot it filled.

    The ceiling this feeds is about how much of the day a reader sees from one
    publication. A paywall costs the run a slot, but it puts nothing on the
    page, so charging the feed for it would quarantine a source for a door
    somebody else locked.
    """
    state = tmp_path / "state"
    ledger.append_item_health(
        state,
        DATE,
        [
            carried_row(1, source_id="wire"),
            carried_row(2, source_id="wire"),
            carried_row(3, source_id="wire", outcome=ItemOutcome.FAILED),
            carried_row(4, source_id="lab"),
        ],
    )

    assert ledger.load_source_counts(state, DATE) == {"wire": 2, "lab": 1}


def test_one_story_recorded_twice_is_counted_once(tmp_path: Path) -> None:
    """Both jobs write this ledger and a replay of the day writes it again.

    `state/item-health/` is appended by the work shards and by assemble, and
    the committed file has held repeated keys before now. Counting rows would
    charge a feed twice for one story and cut its share of the day in half for
    no reason a reader could see.
    """
    state = tmp_path / "state"
    ledger.append_item_health(state, DATE, [carried_row(1, source_id="wire")])
    twice = carried_row(1, source_id="wire")
    ledger.append_item_health(state, DATE, [twice.model_copy(update={"run_id": f"{DATE}-2"})])

    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_yesterdays_share_is_not_todays(tmp_path: Path) -> None:
    """The window is the day. A feed that filled yesterday starts today empty."""
    state = tmp_path / "state"
    yesterday = "2026-08-22"
    ledger.append_item_health(state, yesterday, [carried_row(1, source_id="wire", date=yesterday)])
    ledger.append_item_health(state, DATE, [carried_row(2, source_id="wire")])

    assert ledger.load_source_counts(state, yesterday) == {"wire": 1}
    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_a_day_nothing_was_recorded_for_counts_nothing(tmp_path: Path) -> None:
    """A fresh clone has no history, and no history is an empty count."""
    assert ledger.load_source_counts(tmp_path / "state", DATE) == {}


def test_the_item_health_read_stops_at_the_window(tmp_path: Path) -> None:
    """A shard older than the window is never opened (Rule #12).

    This is the ledger a run appends to five times a day, so a reader that
    globbed the directory would cost more every run for an answer about the last
    few weeks - and the extra rows are thrown away by the caller's own date
    filter anyway. Without this test a bounded read and an unbounded one are
    indistinguishable until the archive is large enough to hurt.

    The old row is one a census would notice if it arrived, so this fails loudly
    rather than by a count nobody reads.
    """
    state = tmp_path / "state"
    old = "2026-05-14"
    ledger.append_item_health(state, old, [carried_row(1, source_id="ancient", date=old)])
    ledger.append_item_health(state, DATE, [carried_row(2, source_id="recent")])

    inside = ledger.load_item_health(state, today=DATE, within_days=30)
    assert {row.source_id for row in inside} == {"recent"}

    wide = ledger.load_item_health(state, today=DATE, within_days=120)
    assert {row.source_id for row in wide} == {"ancient", "recent"}


def test_narrowing_the_published_ledger_keeps_every_pair_the_skip_read_uses() -> None:
    """The Oracle for dropping `canonical_url`: same rows, same pairs, same order.

    `load_published` opens `url_key` and `published_on` and nothing else, so a
    rewrite that preserves those two cells cannot make a published address
    plannable again. The fixture is eleven real rows out of the ledger that was
    migrated.
    """
    with (STATE_FIXTURES / "published-v1.csv").open(encoding="utf-8", newline="") as handle:
        wide = handle.read()

    report = narrow(wide)

    assert report.rows_in == 11
    assert report.rows_out == report.rows_in, "a row was lost or invented"
    assert report.bytes_out < report.bytes_in
    read = csv.DictReader(report.text.splitlines())
    assert tuple(read.fieldnames or ()) == PublishedRow.csv_columns()
    before = [(row["url_key"], row["published_on"]) for row in csv.DictReader(wide.splitlines())]
    assert [(row["url_key"], row["published_on"]) for row in read] == before


def test_narrowing_an_already_narrow_published_ledger_is_refused() -> None:
    """Running it twice must not be a way to lose a file it no longer understands."""
    with (STATE_FIXTURES / "published-v2.csv").open(encoding="utf-8", newline="") as handle:
        already = handle.read()

    with pytest.raises(ValueError, match="nothing to migrate"):
        narrow(already)


def _scores(**cells: str) -> str:
    """One committed-shaped eval ledger, with only the cells a test cares about set."""
    columns = EvalRow.csv_columns()
    base = dict.fromkeys(columns, "0")
    base.update(
        {
            "version": "2026-08-23",
            "date": "2026-08-23",
            "run_id": "2026-08-23-1",
            "item_id": "energy-01",
            "url_key": "a" * 64,
            "source_url": "https://newsroom.example-grid.com/a",
            "title": "A title",
            "vertical": "energy",
            "model_id": "qwen3-8b-q4-k-m",
            "band": "high",
            "scorer_version": "hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
            "scored_at": "2026-08-23T06:18:02Z",
            "truncation_flagged": "False",
            "hedge_dropped": "False",
            "extraction_suspect": "False",
            "determinism_violation": "False",
        }
    )
    base.update(cells)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerow(base)
    return out.getvalue()


def test_an_untruncated_row_recovers_the_article_length_it_already_recorded() -> None:
    """The whole article IS the text the model saw, so the count is not a guess.

    `truncate_to_tokens` returns the body unchanged below the cap, and
    `Article.word_count` counts that same string, so the recovered value is
    exactly what today's writer would put there.
    """
    report = migrate.honest(_scores(source_word_count="1201", source_seen_word_count="1210"))
    row = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_recovered == 1
    assert report.rows_emptied == 0
    assert row["source_word_count"] == "1210", "the seen count was the honest one all along"


def test_a_truncated_row_says_it_does_not_know_rather_than_saying_zero() -> None:
    """Extract discarded the pre-cap body, so the length exists nowhere."""
    report = migrate.honest(
        _scores(source_word_count="1921", source_seen_word_count=str(migrate.SEEN_WORD_CAP))
    )
    row = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_emptied == 1
    assert row["source_word_count"] == ""
    assert row["source_seen_word_count"] == str(migrate.SEEN_WORD_CAP)


def test_the_score_migration_moves_no_cell_it_does_not_own() -> None:
    """The Oracle: every other column comes out byte-identical, row for row."""
    before = _scores(source_word_count="900", source_seen_word_count="905", hhem="0.91")
    report = migrate.honest(before)

    was = next(csv.DictReader(before.splitlines()))
    now = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_in == 1
    assert {name: value for name, value in now.items() if name != "source_word_count"} == {
        name: value for name, value in was.items() if name != "source_word_count"
    }


def test_a_row_the_fixed_pipeline_wrote_is_left_alone() -> None:
    """Selection is by the row's own stamp, so a later run's real count survives."""
    with pytest.raises(ValueError, match="already the whole article"):
        migrate.honest(
            _scores(
                version=migrate.FIXED_FROM,
                source_word_count="5240",
                source_seen_word_count="4310",
            )
        )


def narrowed(text: str) -> str:
    """The wide shard as it stood before 2026-09-02, built from the committed bytes.

    The pre-migration file itself is gone from the working tree, so the fixture
    for it is derived rather than pasted: drop the five appended columns off the
    committed shard and the result is the header every scheduled run appended to
    until this change landed.
    """
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=NARROW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    with io.StringIO(text, newline="") as handle:
        for row in csv.DictReader(handle):
            writer.writerow({name: row[name] for name in NARROW_COLUMNS})
    return out.getvalue()


def migrated_prefix(text: str) -> str:
    """The committed bytes for exactly the rows this migration produced.

    The stamp is the marker `migrate_feed_health.py` deliberately preserved, and
    rows are appended in run order, so the pre-widening rows are the head of the
    file and this is a byte-exact slice rather than a re-serialisation. That is
    what keeps the comparison below a claim about the committed bytes.
    """
    lines = text.splitlines(keepends=True)
    kept = lines[:1]
    for line in lines[1:]:
        if line.split(",", 1)[0] >= WIDENED_AT:
            break
        kept.append(line)
    return "".join(kept)


def test_the_committed_feed_health_shards_have_the_shape_the_contract_writes() -> None:
    """The read-side migration for the widened row is the files themselves.

    `require_matching_header` stops the append when the two disagree, so a
    contract widened without the shards being rewritten would take down the next
    scheduled run at its first stage (CLAUDE.md section 11). Every row is also
    read back, because a header that matches over cells that do not parse is a
    ledger nothing can use.

    Only a row stamped below `WIDENED_AT` is held to five empty cells. The
    changelog entry that appended them made every one nullable, so a row written
    since may fill them or leave them; asserting every row was empty only held
    until the next scheduled run, and that is exactly how long it held.
    """
    known = {entry.version for entry in FeedHealthRow.__changelog__}
    shards = sorted((REPO_ROOT / "state" / ledger.HEALTH_DIRNAME).glob("*.csv"))
    assert shards, "no committed feed-health shard - the read is broken"

    read = 0
    for path in shards:
        assert ledger.read_header(path) == FeedHealthRow.csv_columns(), path.name
        assert b"\r\n" not in path.read_bytes(), f"{path.name} carries CRLF"
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                parsed = FeedHealthRow.from_csv_row(row)
                assert parsed.version in known, f"{path.name} carries {parsed.version}"
                if parsed.version < WIDENED_AT:
                    assert parsed.endpoint_key is None, "a migrated row claims an identity"
                    assert parsed.robots_outcome is None, "a migrated row checked permission"
                    assert parsed.target_attempted is None, "absent is not False"
                read += 1
    assert read > 0


def test_the_widening_restores_the_committed_bytes_and_the_guard_forces_it(
    tmp_path: Path,
) -> None:
    """The Oracle, both halves, over real shards rather than hand-written ones.

    The narrow file is the committed pre-widening rows with their five appended
    columns taken off again, so it is the exact shape every run wrote until
    2026-09-02. Appending to it is refused, which is what put the migration in
    the same commit as the contract; and running the migration over it
    reproduces the committed bytes, which is what proves those bytes are the
    migration's output and not a hand edit.

    Only the pre-widening rows can carry that proof, because a row written since
    fills cells this migration writes empty. They are a fixed set that never
    grows, so when retention finally takes the last one the claim becomes
    unprovable and irrelevant together, and this skips rather than reporting a
    defect that is not there.
    """
    shards = sorted((REPO_ROOT / "state" / ledger.HEALTH_DIRNAME).glob("*.csv"))
    proved = 0
    for path in shards:
        migrated = migrated_prefix(path.read_text(encoding="utf-8"))
        if migrated.count("\n") < 2:
            continue
        stale = ledger.health_path(tmp_path / str(proved), DATE)
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text(narrowed(migrated), encoding="utf-8", newline="\n")

        with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
            ledger.append_health(tmp_path / str(proved), DATE, [health_row()])

        assert widen(stale.read_text(encoding="utf-8")).text == migrated, path.name
        proved += 1

    if not proved:
        pytest.skip("no committed row predates the widening, so there is nothing to prove")


def test_widening_an_already_wide_feed_health_shard_is_refused() -> None:
    """Re-running the migration on a migrated shard must not rewrite it a second time.

    That is what makes it the tool for the merge conflict this change is
    guaranteed to hit: take the upstream file whole and run this over it. A
    utility that widened a wide file would add five more empty columns.
    """
    committed = sorted((REPO_ROOT / "state" / ledger.HEALTH_DIRNAME).glob("*.csv"))[-1]

    with pytest.raises(ValueError, match="already the wide shape"):
        widen(committed.read_text(encoding="utf-8"))


def test_the_retirement_ledger_exists_in_a_fresh_checkout() -> None:
    """`git add` on a path that is not there aborts the whole commit step.

    The plan job stages its ledgers in one `git add "$@"` under
    `set -euo pipefail`, so a retirement file that only appears on the first run
    that retires something would cost that job the sight and health ledgers
    staged beside it. The header ships with the contract instead, exactly as
    `state/runtime-counters.csv` does.
    """
    path = ledger.feed_retirements_path(REPO_ROOT / "state")

    assert path.exists(), "the retirement ledger must exist before the first retirement"
    assert ledger.read_header(path) == FeedRetirementRow.csv_columns()
    assert ledger.feed_retirements_relpath() == "state/feed-retirements.csv"


def test_the_cleanup_ledger_exists_in_a_fresh_checkout() -> None:
    """The same rule, for the ledger the cleanup gained on 2026-09-06.

    The step that writes it is committed by a call that stages `state` whole, so
    a file appearing only on the first run that cleans something would be staged
    fine - and would still be missing on every run before it, which is the run
    somebody reads to find out that nothing has ever been cleaned. The header
    ships with the contract instead.
    """
    path = ledger.visual_prunes_path(REPO_ROOT / "state")

    assert path.exists(), "the cleanup ledger must exist before the first cleanup"
    assert ledger.read_header(path) == VisualPruneRow.csv_columns()
    assert ledger.visual_prunes_relpath() == "state/visual-prunes.csv"


def test_committed_state_csv_rows_match_their_headers() -> None:
    mismatches: list[str] = []
    for path in sorted((REPO_ROOT / "state").rglob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.reader(handle) if row]
        if not rows:
            continue
        header_width = len(rows[0])
        relpath = path.relative_to(REPO_ROOT).as_posix()
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != header_width:
                mismatches.append(
                    f"{relpath}:{line_number} has {len(row)} cells; header has {header_width}"
                )

    assert mismatches == []


# --- The pass that runs after the merge ------------------------------------


def test_no_committed_ledger_repeats_a_key_it_says_makes_a_row_unique() -> None:
    """The guard. Every reader of these files sums a run and would be wrong here.

    Measured on this checkout 2026-08-31 before the repair: `2026-08-29-3` held
    six counter rows for four shards and 44 repeated `(date, run_id, item_id)`
    item-health keys, because two workflow runs computed that id and neither
    could see what the other had pushed. Summing that run's reading clock over
    the rows gave 19,305.8 seconds against 11,810.3 - 63 percent high.

    Feed-health joined the set on 2026-09-02 and arrived dirtiest of the four:
    6,577 rows over 6,022 distinct `(run_id, feed_id)` keys, so 555 rows were a
    second account of an event already on record, and 37 of those keys held rows
    that disagreed about what the feed did.
    """
    repeated: list[str] = []
    state = REPO_ROOT / "state"
    targets = [
        *ledger.keyed_paths(state),
        *((shard, OBSERVATION_KEY) for shard in writer.ledger_shards(state)),
    ]
    for path, key in targets:
        for found, count in sorted(ledger.repeated_keys(path, key).items()):
            relpath = path.relative_to(REPO_ROOT).as_posix()
            repeated.append(f"{relpath}: {'/'.join(found)} has {count} rows, keyed by {key}")

    assert repeated == []


def test_a_repeated_row_is_dropped_and_every_other_byte_is_left_alone(tmp_path: Path) -> None:
    """First row wins, and a kept row is the line that was read.

    The rule is the one every appending caller already states: a re-run's items
    are skipped, so the ledgers keep describing the attempt that got there first.
    Rewriting rather than re-serializing is what makes a clean file a no-op -
    a pass that re-quoted a cell would show up as a diff on every run.
    """
    path = tmp_path / "runtime-counters.csv"
    header = ",".join(RuntimeCountersRow.csv_columns())
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=100)]) == 1
    assert ledger.append_runtime_counters(tmp_path, [counters_row(1, prompt_tokens_total=200)]) == 1
    clean = path.read_text(encoding="utf-8")
    assert clean.startswith(header)

    # What the union merge leaves behind: the same key twice, different cells.
    second_scrape = clean.splitlines()[1].replace(",100,", ",999,")
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(f"{second_scrape}\n")
    assert ledger.repeated_keys(path, ledger.RUNTIME_COUNTERS_KEY)

    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 1
    assert path.read_text(encoding="utf-8") == clean
    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 0
    assert path.read_text(encoding="utf-8") == clean


def test_the_pass_leaves_a_ledger_it_cannot_key_alone(tmp_path: Path) -> None:
    """A shard written before the key existed is not a shard to start deleting from.

    Refusing would cost a run the whole commit step it was called from, over a
    file nothing is appending to any more.
    """
    path = tmp_path / "runtime-counters.csv"
    path.write_text("date,shard\n2026-08-29,0\n2026-08-29,0\n", encoding="utf-8", newline="")
    before = path.read_bytes()

    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 0
    assert path.read_bytes() == before
    assert ledger.drop_repeated_rows(tmp_path / "absent.csv", ledger.RUNTIME_COUNTERS_KEY) == 0


def test_the_keyed_set_names_every_ledger_that_declares_one(tmp_path: Path) -> None:
    """`state/seen/` is absent on purpose, not by omission.

    It declares no key at all: a second sight is folded by `load_seen` keeping
    the earliest, so a repeat costs bytes and never moves an age. Everything
    else here says what makes two of its rows one record, and everything that
    says so is settled.
    """
    ledger.append_seen(tmp_path, DATE, [seen_row()])
    ledger.append_health(tmp_path, DATE, [health_row()])
    ledger.append_runtime_counters(tmp_path, [counters_row(0)])
    item_health = ledger.item_health_path(tmp_path, DATE)
    item_health.parent.mkdir(parents=True, exist_ok=True)
    item_health.write_text(",".join(ItemHealthRow.csv_columns()) + "\n", encoding="utf-8")

    keyed = [
        (path.relative_to(tmp_path).as_posix(), key) for path, key in ledger.keyed_paths(tmp_path)
    ]

    assert keyed == [
        ("runtime-counters.csv", ledger.RUNTIME_COUNTERS_KEY),
        ("feed-retirements.csv", ledger.FEED_RETIREMENT_KEY),
        ("visual-prunes.csv", ledger.VISUAL_PRUNE_KEY),
        (f"feed-health/{DATE[:7]}.csv", ledger.FEED_HEALTH_KEY),
        (f"item-health/{DATE[:7]}.csv", ledger.ITEM_HEALTH_KEY),
    ]


# --- One feed, one run, one result ------------------------------------------


def account(outcome: FetchOutcome, *, items: int = 0, at: str = "06:00:00") -> FeedHealthRow:
    """One attempt's account of one run's read of one feed. Always the same key."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=RUN_ID,
        date=DATE,
        feed_id="example-feed",
        checked_at=f"{DATE}T{at}Z",
        outcome=outcome,
        status=200,
        items=items,
    )


def health_rows(state: Path) -> list[FeedHealthRow]:
    return ledger.load_health(state, today=DATE, within_days=1)


def test_a_second_attempt_at_one_run_leaves_one_row_per_feed(tmp_path: Path) -> None:
    """The write-side half. A run is one read of one feed, however often it is run.

    A second attempt at one execution appends against the file it checked out,
    which is frozen at the commit the run was triggered at - so the filter that
    would have caught this cannot see the first attempt's row until the merge.
    Settling straight after the append is what stops the shard the same job
    pushes from already holding both.
    """
    assert ledger.append_health(tmp_path, DATE, [account(FetchOutcome.TRANSIENT)]) == 1
    retry = [account(FetchOutcome.TRANSIENT, at="07:00:00")]
    assert ledger.append_health(tmp_path, DATE, retry) == 0

    rows = health_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].checked_at == f"{DATE}T07:00:00Z"
    assert ledger.repeated_keys(ledger.health_path(tmp_path, DATE), ledger.FEED_HEALTH_KEY) == {}


def test_the_attempt_that_carried_articles_wins_however_late_it_ran(tmp_path: Path) -> None:
    """A retry that got nothing describes the retry, not the feed.

    This is the one ledger here that cannot settle by arrival order. Keeping the
    first row would leave a failure on record for a run that recovered; keeping
    the last would throw the recovery away when the retry came back empty.
    """
    ledger.append_health(tmp_path, DATE, [account(FetchOutcome.TRANSIENT, at="06:00:00")])
    ledger.append_health(tmp_path, DATE, [account(FetchOutcome.OK, items=9, at="07:00:00")])
    assert [(row.outcome, row.items) for row in health_rows(tmp_path)] == [(FetchOutcome.OK, 9)]

    later = tmp_path / "later"
    ledger.append_health(later, DATE, [account(FetchOutcome.OK, items=9, at="06:00:00")])
    ledger.append_health(later, DATE, [account(FetchOutcome.OK, items=0, at="07:00:00")])
    assert [(row.outcome, row.items) for row in health_rows(later)] == [(FetchOutcome.OK, 9)]


def test_the_settlement_reads_the_union_a_merge_leaves_behind(tmp_path: Path) -> None:
    """The post-merge half, on the shape `merge=union` really produces.

    `state/**/*.csv` never conflicts - it concatenates - so a settled shard comes
    back repeated with no marker to notice. The pass has to be unconditional,
    and it has to pick the same winner it picked before the merge.
    """
    path = ledger.health_path(tmp_path, DATE)
    ledger.append_health(tmp_path, DATE, [account(FetchOutcome.TRANSIENT, at="06:00:00")])
    theirs = account(FetchOutcome.OK, items=4, at="07:00:00").csv_row()
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(",".join(theirs[name] for name in FeedHealthRow.csv_columns()) + "\n")
    assert len(ledger.repeated_keys(path, ledger.FEED_HEALTH_KEY)) == 1

    assert ledger.drop_repeated_rows(path, ledger.FEED_HEALTH_KEY) == 1
    assert [(row.outcome, row.items) for row in health_rows(tmp_path)] == [(FetchOutcome.OK, 4)]
    assert ledger.drop_repeated_rows(path, ledger.FEED_HEALTH_KEY) == 0


def test_the_whole_state_tree_settles_in_one_call(tmp_path: Path) -> None:
    """What the commit step calls between the rebase and the push.

    It returns zero whatever it finds, because a repeat it drops is a repair
    rather than a finding: a non-zero exit inside `commit-and-push.sh` runs under
    `set -euo pipefail` and would abort the commit, costing the run every ledger
    row staged beside the one it just fixed.
    """
    state = tmp_path / "state"
    ledger.append_runtime_counters(state, [counters_row(0, prompt_tokens_total=100)])
    counters = ledger.runtime_counters_path(state)
    with counters.open("a", encoding="utf-8", newline="") as handle:
        handle.write(counters.read_text(encoding="utf-8").splitlines()[1] + "\n")

    assert cli.stage_dedupe_ledgers(state_dir=state) == 0
    assert ledger.repeated_keys(counters, ledger.RUNTIME_COUNTERS_KEY) == {}
    assert len(ledger.load_runtime_counters(state, run_id=RUN_ID)) == 1


# --- The server's own counters, and what they are for ----------------------


def counters_row(shard: int, **counters: object) -> RuntimeCountersRow:
    return RuntimeCountersRow.model_validate(
        {
            "date": DATE,
            "run_id": RUN_ID,
            "shard": shard,
            "shards": 4,
            "scraped_at": STAMP,
            **counters,
        }
    )


def test_every_ledger_a_work_shard_stages_exists_in_a_fresh_checkout() -> None:
    """`git add` on a path that is not there aborts the whole commit step.

    The script runs under `set -euo pipefail` and stages all three of the work
    job's ledgers in one call, so a `state/runtime-counters.csv` that only
    appears once the counters stage has succeeded would let a broken scrape cost
    the shard its item-health rows as well - the exact loss the commit step was
    added to prevent. The header ships with the contract instead.
    """
    path = ledger.runtime_counters_path(REPO_ROOT / "state")

    assert path.exists(), "the ledger a work shard stages must exist before the first run"
    assert ledger.read_header(path) == RuntimeCountersRow.csv_columns()


def test_a_re_run_shard_cannot_be_counted_twice(tmp_path: Path) -> None:
    """The cells are cumulative totals, so a second row is not a second fact.

    A re-run of a failed job starts a fresh server and scrapes it again. Nothing
    pools two rows for one shard correctly - the tokens would simply be added to
    themselves - and `merge=union` keeps both lines rather than collapsing them,
    so the filter has to run before the write.
    """
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=100)]) == 1
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=999)]) == 0
    assert ledger.append_runtime_counters(tmp_path, [counters_row(1, prompt_tokens_total=200)]) == 1

    landed = ledger.load_runtime_counters(tmp_path, run_id=RUN_ID)
    assert [row.shard for row in landed] == [0, 1]
    assert [row.prompt_tokens_total for row in landed] == [100, 200]


def test_a_shard_whose_server_was_gone_still_counts_as_a_shard(tmp_path: Path) -> None:
    """Pooling a run has to see the shard that contributed nothing.

    Three shards' tokens quoted as a four-shard run is a number nobody can read.
    An empty scrape writes nulls, not zeroes, so the row says "this shard ran and
    the server did not answer" rather than "this shard read no tokens".
    """
    ledger.append_runtime_counters(
        tmp_path, [counters_row(0, prompt_tokens_total=100, prompt_seconds_total=10.0)]
    )
    ledger.append_runtime_counters(tmp_path, [counters_row(1)])

    pooled = pool_counters(ledger.load_runtime_counters(tmp_path, run_id=RUN_ID))

    assert pooled.parts == 2, "a silent shard is still a shard"
    assert pooled.tokens == 100
    assert pooled.rate == 10.0


def _counters_fixture(path: Path, *, runs: int, shards: int) -> list[RuntimeCountersRow]:
    """One row per shard for `runs` runs. Returns what run `RUN_ID` owes, in shard order.

    Only the run id changes from run to run, so both arms of the peak check hold
    the same answer and the file is the only thing that differs. The shard rows
    are built through the contract once and rewritten under each run id, so a
    fixture line is the shape a real work job appends.
    """
    wanted = [
        RuntimeCountersRow.model_validate(
            {
                "date": DATE,
                "run_id": RUN_ID,
                "shard": shard,
                "shards": shards,
                "scraped_at": STAMP,
                "prompt_tokens_total": 100_000 + shard,
                "prompt_seconds_total": 10.5 + shard,
                "cpu_model": "Intel(R) Core(TM) i7-1265U",
            }
        )
        for shard in range(shards)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(
            handle, fieldnames=RuntimeCountersRow.csv_columns(), lineterminator="\n"
        )
        out.writeheader()
        for number in range(runs):
            run_id = RUN_ID if number == 0 else f"{DATE}-{number + 100}"
            for row in wanted:
                out.writerow({**row.csv_row(), "run_id": run_id})
    return wanted


def _peak_of_load_runtime_counters(state: Path) -> tuple[list[RuntimeCountersRow], int]:
    tracemalloc.start()
    try:
        counted = ledger.load_runtime_counters(state, run_id=RUN_ID)
        return counted, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_loading_one_runs_counters_costs_the_run_and_not_the_file(tmp_path: Path) -> None:
    """The read already asks about one run, so it must cost one run.

    `state/runtime-counters.csv` is never windowed and never partitioned - one
    lifetime file that gains 20 rows on a full day. The question put to it is
    always about a single run, and a run id already names its date, so the
    answer is a handful of shard rows however long the file gets. Materialising
    every row to find eight of them made the cost the file's instead.

    Measured 2026-09-08 on an Intel Core i7-1265U, Windows 11, over 2,400 and
    4,800 lines carrying the same eight shard rows. Before, three runs each:
    2,197,419 B of peak against 4,237,123 B - the file doubled and the cost went
    with it, 1.93x. After: 193,513 B against 193,481 B, a ratio of 1.000. So the
    4,800-line arm peaks 21.9 times lower and stops moving when the file grows.
    Spread over the three runs was 32 B or less on every arm. On the committed
    ledger as it stands - 209 rows, 35,950 B - the newest run's read went from
    429,441 B to 173,831 B, 2.47 times lower.

    A threshold in bytes a row would pass for the wrong reason, because what the
    read legitimately keeps is the run's own rows. So the property is asserted
    directly: hold the answer still, double the file, and the peak must not
    follow. Both populations are built and fixed, so this costs the same on the
    day the committed ledger holds ten times either (Rule #12, section 13).
    """
    shards = 8
    small = tmp_path / "small"
    large = tmp_path / "large"
    owed_small = _counters_fixture(ledger.runtime_counters_path(small), runs=300, shards=shards)
    owed_large = _counters_fixture(ledger.runtime_counters_path(large), runs=600, shards=shards)

    assert owed_small == owed_large, "both arms must owe one answer or this proves nothing"
    assert len(owed_large) == shards, "the answer is a run's shards, and one row would prove less"

    counted_small, peak_small = _peak_of_load_runtime_counters(small)
    counted_large, peak_large = _peak_of_load_runtime_counters(large)

    assert counted_small == owed_small, "the rows one run owes must not move"
    assert counted_large == owed_large
    assert peak_large < peak_small * 1.1, (
        f"twice the runs over the same {shards} shard rows moved peak from {peak_small} B "
        f"to {peak_large} B, so the read is still holding the file rather than the run"
    )


def test_the_ledgers_prefill_rate_agrees_with_the_servers_own_counters() -> None:
    """The Oracle for row 9, on one real committed run.

    `docs/architecture/summarize/throughput.md` and the console both publish a
    read rate derived from the item-health ledger, which sums a field copied out
    of one model reply per item. The server counted the same work for itself.
    Until the counters were committed the two could not be held against each
    other at all, which is what Rule #10 forbids.

    The tolerance was written down before either side was read. The four
    `.prom` bodies are real captures from run `2026-08-26-5`'s `runtime-log-*`
    artifacts; the ledger side is the committed `state/item-health/2026-08.csv`.
    """
    rows = [
        RuntimeCountersRow.from_metrics_text(
            path.read_text(encoding="utf-8"),
            date=RECONCILED_DATE,
            run_id=RECONCILED_RUN,
            shard=int(path.stem[-1]),
            shards=4,
            scraped_at="2026-08-26T21:32:30Z",
        )
        for path in sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))
    ]
    assert len(rows) == 4, "all four shards, or the run figure is not the run"

    server = pool_counters(rows)
    committed = pool_ledger(
        ledger.item_health_path(REPO_ROOT / "state", RECONCILED_DATE), run_id=RECONCILED_RUN
    )
    assert committed.parts > 100, (
        "the committed ledger no longer holds this run's rows - the oracle has no input"
    )

    gap = abs(committed.rate - server.rate) / server.rate
    assert gap <= TOLERANCE, (
        f"ledger {committed.rate:.4f} tok/s against server {server.rate:.4f} tok/s "
        f"is {gap * 100:.2f} percent apart, outside the {TOLERANCE * 100:.0f} percent bound"
    )


def test_a_run_with_no_committed_snapshot_says_so_rather_than_reporting_zero() -> None:
    """An audit that finds nothing must not read as an audit that found agreement."""
    result = reconcile(REPO_ROOT / "state", run_id="1970-01-01-1")

    assert result.server.parts == 0
    assert "nothing to check against" in result.verdict
