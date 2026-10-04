"""Does year packing keep every row, pack each finished year once, and leave other ledgers alone?

These run the shipped `compact-visual-prunes` task, found the way the runner
finds it, live over trees built under `tmp_path` through the ledger door: the
twelve month files of 2026, the January of 2027 that lets 2026 be packed, and
the indexes and watermarks a compaction leaves beside them. The declaration
ships `dry_run: true` and packs no year, and each test turns on what it needs
for itself only. Each oracle is named where it is checked: every row the month
files held reads back from the year file, one row group a month; a second pass
changes nothing; a pass that stopped part way is finished by the next with no
row lost or read twice; and a ledger that does not pack years keeps its month
files byte for byte.

Nothing here reads the committed `state/` or a clock the test did not set
(CLAUDE.md sections 2 and 13).
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Final

import pyarrow.parquet
import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener import schedule
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.tasks import _yearly_period
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.ledger import StoredRow

from ._task import context_for, run_task

pytestmark = pytest.mark.contract

VISUALS: Final = LedgerName.VISUAL_PRUNES
TASK: Final = "compact-visual-prunes"
MONTHS_OF_2026: Final = [f"2026-{number:02d}" for number in range(1, 13)]

#: The first wake that packs 2026 at the smallest wait the declaration allows:
#: 77 days is `daily_keep_days` 45 plus 32, and 2027-03-20 is 78 days after 2026 ended.
TODAY: Final = date(2027, 3, 20)
PACKS: Final[dict[str, Any]] = {"monthly_window": {"unit": "forever"}, "monthly_keep_days": 77}

#: The compaction's own identity, which every compact file's envelope names.
COMPACTION: Final = WriterIdentity(
    run_id="2027-02-15-1",
    attempt=1,
    job=ServerJob.RUN_TASKS,
    shard=0,
    producer="gardener.tasks.compaction",
    git_sha="c" * 40,
)


def a_pass(on: str) -> VisualPruneRow:
    """One reporting cleanup pass on one day, told from every other day's by what it weighed."""
    weighed = int(on.replace("-", ""))
    return VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=on,
        run_id=f"{on}-1",
        policy_months=-1,
        max_deletes_per_run=200,
        dry_run=True,
        candidates_found=0,
        deleted=0,
        skipped_by_fuse=0,
        fuse_tripped=False,
        bytes_reclaimed=0,
        oldest_kept=None,
        payload_bytes_before=weighed,
        payload_bytes_after=weighed,
    )


def state(root: Path) -> Path:
    return root / ledger.STATE_DIRNAME


def a_month_file(root: Path, scratch: Path, month: str) -> None:
    """One month already absorbed: two passes, filed raw on its 5th and its 20th, in one file."""
    raws = [
        ledger.persist(
            scratch,
            [a_pass(f"{month}-{day}")],
            ledger=VISUALS,
            covers=f"{month}-{day}",
            identity=WriterIdentity(
                run_id=f"{month}-{day}-1",
                attempt=1,
                job=ServerJob.RUN_TASKS,
                shard=0,
                producer="gardener.tasks.visual_prune",
                git_sha="a" * 40,
            ),
        )[0]
        for day in ("05", "20")
    ]
    ledger.persist_period(
        state(root),
        ledger.load_stored(raws, model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.MONTHLY,
        covers=month,
        identity=COMPACTION,
        built_from=len(raws),
    )


def index_entries(root: Path, period: Period, entries: list[CompactEntry]) -> None:
    """One period's index, as a compaction writes it."""
    path = ledger.compact_index_path(state(root), VISUALS, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    index = CompactIndex(
        version=CompactIndex.schema_version(), ledger=VISUALS, period=period, entries=entries
    )
    path.write_bytes(index.to_json().encode("ascii"))


def a_mark(root: Path, period: Period, through: str) -> None:
    """One period's watermark, as a compaction writes it."""
    path = ledger.watermark_path(state(root), VISUALS, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    mark = Watermark(
        version=Watermark.schema_version(),
        ledger=VISUALS,
        period=period,
        through=through,
        advanced_at="2027-02-15T00:41:00Z",
        run_id=COMPACTION.run_id,
    )
    path.write_bytes(mark.to_json().encode("ascii"))


def a_finished_year(tmp_path: Path, *, today: date = TODAY, january: bool = True) -> Path:
    """A checkout whose ledger holds 2026 as twelve month files, and 2027's January if asked.

    The daily watermark stands on the newest day a pass on `today` would take,
    beside a daily index that names no day, so the only work a pass finds is the
    year's and the months'. A pass refuses a watermark whose index is not there.
    """
    root, scratch = tmp_path / "checkout", tmp_path / "scratch"
    months = MONTHS_OF_2026 + (["2027-01"] if january else [])
    for month in months:
        a_month_file(root, scratch, month)
    index_entries(
        root,
        Period.MONTHLY,
        [
            CompactEntry(covers=month, rows=2, bytes=month_file(root, month).stat().st_size)
            for month in months
        ],
    )
    a_mark(root, Period.MONTHLY, months[-1])
    wake = datetime.combine(today, time.min, tzinfo=UTC)
    index_entries(root, Period.DAILY, [])
    a_mark(root, Period.DAILY, schedule.newest_eligible(now=wake, after_days=1).isoformat())
    return root


def month_file(root: Path, month: str) -> Path:
    found = ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month)
    assert found is not None, f"no month file holds {month}"
    return found


def compact(root: Path, today: date, **knobs: Any) -> Pass:
    """One live pass of the shipped compaction over this checkout, with these knobs changed."""
    return run_task(TASK, root, today=today, dry_run=False, **knobs)


def covers(root: Path, period: Period) -> list[str]:
    path = ledger.compact_index_path(state(root), VISUALS, period)
    return [entry.covers for entry in CompactIndex.read(path).entries] if path.is_file() else []


def watermark(root: Path, period: Period) -> str | None:
    path = ledger.watermark_path(state(root), VISUALS, period)
    return Watermark.read(path).through if path.is_file() else None


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def served(root: Path) -> list[StoredRow[VisualPruneRow]]:
    """Every row the ledger's reader serves, each source read once and nothing settled.

    Settling would fold a row read twice into one, so this counts what the
    sources hold as they are: a row two sources both served shows up twice.
    """
    found = ledger.list_ledger_files(state(root), VISUALS)
    return [
        row
        for source in found.sources
        for row in ledger.load_stored(list(source.paths), model=VisualPruneRow)
    ]


def disjoint(outcome: Pass) -> bool:
    """What the shard that lands a pass requires: no path both written and deleted."""
    return set(outcome.written).isdisjoint(outcome.taken)


def days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


# --- one pass packs the year ------------------------------------------------------


def test_one_pass_packs_a_finished_year_and_every_row_its_months_held_reads_back_from_it(
    tmp_path: Path,
) -> None:
    """THE ORACLE: the year file holds each month's rows in order, one row group a month."""
    root = a_finished_year(tmp_path)
    held = {
        month: ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
        for month in MONTHS_OF_2026
    }
    everything = served(root)

    outcome = compact(root, TODAY, **PACKS)

    year = ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026")
    assert year is not None
    assert ledger.load_stored([year], model=VisualPruneRow) == [
        row for month in MONTHS_OF_2026 for row in held[month]
    ]
    footer = pyarrow.parquet.read_metadata(year)
    groups = [footer.row_group(at).num_rows for at in range(footer.num_row_groups)]
    assert groups == [len(held[month]) for month in MONTHS_OF_2026]
    (entry,) = CompactIndex.read(
        ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    ).entries
    assert (entry.covers, entry.rows, entry.bytes) == ("2026", 24, year.stat().st_size)
    assert covers(root, Period.MONTHLY) == ["2027-01"]
    assert all(
        ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month) is None
        for month in MONTHS_OF_2026
    )
    assert (watermark(root, Period.YEARLY), watermark(root, Period.MONTHLY)) == ("2026", "2027-01")
    assert served(root) == everything
    found = ledger.list_ledger_files(state(root), VISUALS)
    assert found.holes == ()
    for day in days("2026-01-01", "2027-01-31"):
        assert len([source for source in found.sources if source.holds(day)]) == 1, day
    assert ledger.load_days(state(root), VISUALS, ["2026-06-20"], model=VisualPruneRow) == [
        a_pass("2026-06-20")
    ]
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


def test_a_second_pass_changes_nothing(tmp_path: Path) -> None:
    root = a_finished_year(tmp_path)
    compact(root, TODAY, **PACKS)
    before = files_under(root)

    again = compact(root, TODAY, **PACKS)

    assert files_under(root) == before
    assert (again.written, again.taken) == ((), ())
    assert again.stopped_because is StopReason.EXHAUSTED


def test_a_dry_run_names_every_path_the_live_pass_changes_and_changes_nothing(
    tmp_path: Path,
) -> None:
    root = a_finished_year(tmp_path)
    before = files_under(root)

    dry = run_task(TASK, root, today=TODAY, **PACKS)

    assert dry.dry_run and files_under(root) == before
    live = compact(root, TODAY, **PACKS)
    assert (dry.written, dry.taken) == (live.written, live.taken)
    assert dry.bytes_freed == live.bytes_freed == sum(len(before[path]) for path in live.taken)


def test_a_window_that_only_reports_packs_a_year_as_a_live_one_does(tmp_path: Path) -> None:
    """A window kept for ever drops nothing, so its switch changes nothing a pass packs."""
    trees = [a_finished_year(tmp_path / "live"), a_finished_year(tmp_path / "reports")]

    live = compact(trees[0], TODAY, **PACKS, month_deletes_dry_run=False)
    reports = compact(trees[1], TODAY, **PACKS, month_deletes_dry_run=True)

    assert (reports.taken, reports.written) == (live.taken, live.written)
    assert reports.selected == live.selected == len(live.taken)
    assert [watermark(root, Period.YEARLY) for root in trees] == ["2026", "2026"]


# --- a pass that stopped part way ------------------------------------------------


@pytest.mark.parametrize(
    "landed",
    [1, 2, 3, 6, 15],
    ids=["data", "year-index", "both-indexes", "three-months-deleted", "all-months-deleted"],
)
def test_a_pass_that_stopped_part_way_is_finished_by_the_next_with_no_row_lost_or_read_twice(
    tmp_path: Path, landed: int
) -> None:
    """Packing decides five kinds of change in order, and any first part of them may land alone."""
    root = a_finished_year(tmp_path)
    everything = served(root)
    context = context_for(TASK, root, today=TODAY, dry_run=False, **PACKS)
    policy = context.policy
    assert isinstance(policy, CompactionPolicy)
    tree = CompactTree.read(context.state_dir, VISUALS, context.listing)
    now = datetime.combine(TODAY, time.min, tzinfo=UTC)

    stops = _yearly_period.absorb(
        tree, policy, now=now, stamp="2027-03-20T00:41:00Z", identity=COMPACTION
    )

    assert stops == ()
    tree.finish()
    compact_root = f"{ledger.STATE_DIRNAME}/compact/{VISUALS.value}"
    decided = [change.path.relative_to(root).as_posix() for change in tree.changes]
    assert decided == [
        f"{compact_root}/yearly/2026/2026.parquet",
        f"{compact_root}/index/yearly.json",
        f"{compact_root}/index/monthly.json",
        *[f"{compact_root}/monthly/{month.replace('-', '/')}.parquet" for month in MONTHS_OF_2026],
        f"{compact_root}/yearly/watermark.json",
    ]
    dataclasses.replace(tree, changes=tree.changes[:landed]).apply()
    assert served(root) == everything, "a reader between the two passes lost or doubled a row"

    outcome = compact(root, TODAY, **PACKS)

    assert served(root) == everything
    assert (covers(root, Period.YEARLY), covers(root, Period.MONTHLY)) == (["2026"], ["2027-01"])
    assert watermark(root, Period.YEARLY) == "2026"
    gone = [ledger.compact_file(state(root), VISUALS, Period.MONTHLY, m) for m in MONTHS_OF_2026]
    assert gone == [None] * len(MONTHS_OF_2026)
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


# --- what waits, what is refused, and who is left alone -----------------------------


@pytest.mark.parametrize(
    "window",
    [{"unit": "forever"}, None],
    ids=["kept-forever", "the-shipped-window"],
)
def test_a_ledger_that_does_not_pack_years_keeps_its_month_files_exactly_as_before(
    tmp_path: Path, window: dict[str, Any] | None
) -> None:
    root = a_finished_year(tmp_path)
    before = files_under(root)

    outcome = compact(root, TODAY, **({} if window is None else {"monthly_window": window}))

    assert files_under(root) == before
    assert (outcome.written, outcome.taken) == ((), ())
    assert not (state(root) / "compact" / VISUALS.value / Period.YEARLY.value).exists()


@pytest.mark.parametrize(
    ("today", "january", "packed"),
    [
        (date(2027, 4, 10), True, False),
        (date(2027, 4, 11), True, True),
        (date(2027, 6, 1), False, False),
    ],
    ids=["a-day-before-its-wait", "the-day-its-wait-ends", "its-next-january-not-absorbed"],
)
def test_a_year_waits_for_its_wait_and_for_its_next_january(
    tmp_path: Path, today: date, january: bool, packed: bool
) -> None:
    """100 days after 2026 ended is 2027-04-11; and a year goes only once January is absorbed."""
    root = a_finished_year(tmp_path, today=today, january=january)

    compact(root, today, monthly_window={"unit": "forever"}, monthly_keep_days=100)

    assert (watermark(root, Period.YEARLY) == "2026") is packed
    assert (ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-06") is None) is packed


def test_a_year_missing_a_month_is_refused_by_name_and_nothing_moves(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = a_finished_year(tmp_path)
    kept = [month for month in [*MONTHS_OF_2026, "2027-01"] if month != "2026-06"]
    month_file(root, "2026-06").unlink()
    index_entries(
        root,
        Period.MONTHLY,
        [
            CompactEntry(covers=month, rows=2, bytes=month_file(root, month).stat().st_size)
            for month in kept
        ],
    )
    before = files_under(root)

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, TODAY, **PACKS)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026")
    assert "monthly.json does not name 2026-06" in caplog.text
    assert f"fault={ledger.LedgerFault.DAY_MISSING}" in caplog.text
    assert files_under(root) == before


def test_a_year_file_over_github_s_large_file_line_is_refused_and_its_months_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The line is GitHub's; it is lowered here so a small year crosses it, and nothing else moves."""
    root = a_finished_year(tmp_path)
    before = files_under(root)
    monkeypatch.setattr(_yearly_period, "GITHUB_LARGE_FILE_BYTES", 1000)

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, TODAY, **PACKS)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026")
    assert "over GitHub's large-file line of 1000" in caplog.text
    assert files_under(root) == before
