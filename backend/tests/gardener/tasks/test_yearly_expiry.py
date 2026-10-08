"""Does finite yearly retention delete only due indexed years, keep restart progress, and say so?"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import config, ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.gardener_events import (
    CompactionStep,
    ExpiredYearsChosen,
    PeriodRefused,
    ShardPublished,
    TaskFinished,
    TaskOutcome,
)
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    ForeverWindow,
    MonthsWindow,
)
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import event_log, run_summary, runner
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.outcome import MEANS, Outcome
from idhazh.gardener.tasks import compaction
from idhazh.gardener.tasks._yearly_expiry import expires_at
from idhazh.telemetry.door_prune import take_days

from .._events import events, the_event
from .._garden import a_config
from ._marks import marks_on_disk
from ._task import context_for
from .test_compaction_years import (
    COMPACTION,
    TASK,
    VISUALS,
    a_finished_year,
    compact,
    index_entries,
    state,
)

pytestmark = pytest.mark.contract

#: The run a pass through the runner names, on the first UTC day a year expires.
RUN_ID: Final = "2030-01-01-18012345678"

#: The first wake at which a year expires: 2026, kept 36 calendar months after its UTC end.
EXPIRY_WAKE: Final = datetime(2030, 1, 1, 0, 40, tzinfo=UTC)


def indexed_years(root: Path, years: tuple[str, ...]) -> dict[str, Path]:
    """A bounded tree with three indexes and unreadable files expiry must not download."""
    paths = {}
    for year in years:
        path = ledger.compact_path(state(root), VISUALS, Period.YEARLY, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"expiry deletes by path, never by parsing rows")
        paths[year] = path
    index_entries(
        root,
        Period.YEARLY,
        [CompactEntry(covers=year, rows=1, bytes=paths[year].stat().st_size) for year in years],
    )
    index_entries(root, Period.MONTHLY, [])
    index_entries(root, Period.DAILY, [])
    return paths


def run(
    root: Path,
    today: date = date(2030, 1, 1),
    *,
    period_range: tuple[str, str] | None = None,
    **changed: object,
) -> Pass:
    """One pass at a scheduled wake on `today`, or over the range a person names."""
    context = context_for(
        TASK, root, today=today, period_range=period_range, wake=period_range is None
    )
    policy = CompactionPolicy.model_validate(
        {
            **context.policy.model_dump(mode="json"),
            "dry_run": False,
            "monthly_window": {"unit": "forever"},
            "monthly_keep_days": 93,
            "yearly_keep_months": 36,
            "yearly_prune_enable": True,
            **changed,
        }
    )
    return compaction.run(replace(context, policy=policy))


def said_as_text(records: Iterable[logging.LogRecord]) -> list[str]:
    """What the expiry logged with no event on it, each a line the handler wraps as text."""
    return [
        record.getMessage()
        for record in records
        if record.name == expires_at.__module__ and event_log.payload(record) is None
    ]


def empty(covers: str) -> CompactEntry:
    """The entry of a period a pass looked at and found no row in, so it has no file."""
    return CompactEntry(covers=covers, rows=0, bytes=0, state=EntryState.EMPTY)


def caught_up(root: Path) -> Path:
    """2026 packed and indexed, and every later period looked at by the 2030-01-01 UTC wake.

    2027 and 2028 are packed years, the months of 2029 to October are closed,
    and the days from 2029-11-01 to 2029-12-30 are packed, each an `empty`
    entry. So the expiry is the only step with a period to take: 2029-12-30 is
    the newest day one whole day past its end, 2029-10 the newest month 45 days
    past its end, and 2029 is not yet 93 days past its own. Hands back 2026's file.
    """
    year_file = indexed_years(root, ("2026",))["2026"]
    index_entries(
        root,
        Period.YEARLY,
        [
            CompactEntry(covers="2026", rows=1, bytes=year_file.stat().st_size),
            empty("2027"),
            empty("2028"),
        ],
    )
    index_entries(root, Period.MONTHLY, [empty(f"2029-{month:02d}") for month in range(1, 11)])
    first = date(2029, 11, 1)
    index_entries(
        root,
        Period.DAILY,
        [empty((first + timedelta(days=offset)).isoformat()) for offset in range(60)],
    )
    return year_file


def run_by_the_runner(root: Path, *, dry_run: bool) -> Outcome:
    """The compaction as the runner runs it at a wake on 2030-01-01 UTC, which logs its events.

    The declaration is the committed one with every knob the caught-up tree
    depends on named, so a deployment choice cannot move what a test expects.
    """
    declared = root / "declared" / f"{TASK}.json"
    declared.parent.mkdir(parents=True)
    committed = json.loads(read_text(CONFIG_DIR / "gardener" / f"{TASK}.json"))
    knobs = {
        "dry_run": dry_run,
        "compact_after_days": 1,
        "daily_keep_days": 45,
        "monthly_keep_days": 93,
        "monthly_window": {"unit": "forever"},
        "yearly_keep_months": 36,
        "yearly_prune_enable": True,
    }
    declared.write_text(json.dumps(committed | knobs), encoding="ascii")
    return runner.run(
        (TASK,),
        settings=config.load_gardener(a_config(root, declared)),
        repo_root=root,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha="a" * 40,
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        clock=lambda: EXPIRY_WAKE,
    )


def summary_of(root: Path, outcome: Outcome, finished: TaskFinished) -> str:
    """The job summary of a shard that ran this one task and landed on its first try."""
    assert outcome.record is not None
    published = ShardPublished(
        shard=0,
        run_id=RUN_ID,
        attempt=1,
        tasks=[finished.task],
        failed_tasks=[],
        landing=ShardLanding.LANDED,
        push_try=1,
        push_tries=6,
        record=outcome.record.relative_to(root).as_posix(),
        downloaded_bytes=outcome.downloaded_bytes,
        max_downloaded_mb=128,
        exit_code=outcome.exit_code,
        means=MEANS[outcome.exit_code],
    )
    return run_summary.markdown(published, [finished])


def test_exact_calendar_expiry_uses_year_end_and_utc() -> None:
    due = expires_at("2026", 36)
    assert due == datetime(2030, 1, 1, tzinfo=UTC)
    assert expires_at("2026", 37) == datetime(2030, 2, 1, tzinfo=UTC)
    assert due - timedelta(microseconds=1) < due
    assert datetime(2030, 1, 1, 2, tzinfo=timezone(timedelta(hours=2))) == due


def test_the_years_a_pass_takes_are_one_event_and_never_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """2026 expires at 00:00 UTC on 2030-01-01, and the pass says so as `expired-years-chosen`."""
    indexed_years(tmp_path, ("2026",))

    with caplog.at_level(logging.INFO):
        run(tmp_path)

    assert said_as_text(caplog.records) == []
    chosen = the_event(caplog.records, ExpiredYearsChosen)
    assert (chosen.ledger, chosen.years) == (VISUALS, ["2026"])


@pytest.mark.parametrize(
    ("dry_run", "word", "row"),
    [
        pytest.param(
            False,
            TaskOutcome.DONE,
            "| `compact-visual-prunes` | done | deleted 1 expired year |",
            id="live",
        ),
        pytest.param(
            True,
            TaskOutcome.DRY_RUN,
            "| `compact-visual-prunes` | dry-run | would delete 1 expired year |",
            id="dry-run",
        ),
    ],
)
def test_a_pass_whose_only_work_is_an_expired_year_says_so_on_its_event_and_its_summary(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    dry_run: bool,
    word: TaskOutcome,
    row: str,
) -> None:
    """THE ORACLE: the year a pass took is on its `task-finished` event, and its row says so.

    A live pass deletes 2026, and its row says it did; a dry run deletes nothing,
    lists the same year, and its row says only that it would. Neither row says
    "nothing", which is what each said while the event listed no expired year.
    """
    year_file = caught_up(tmp_path)

    with caplog.at_level(logging.INFO):
        outcome = run_by_the_runner(tmp_path, dry_run=dry_run)

    finished = the_event(caplog.records, TaskFinished)
    assert (finished.task, finished.outcome, finished.dry_run) == (
        "compact-visual-prunes",
        word,
        dry_run,
    )
    assert finished.periods is not None
    rows = [
        line
        for line in summary_of(tmp_path, outcome, finished).splitlines()
        if line.startswith("| `compact-visual-prunes` |")
    ]
    assert (finished.periods.model_dump(mode="json"), rows) == (
        {
            "days_packed": [],
            "days_retaken": [],
            "months_closed": [],
            "years_packed": [],
            "years_expired": ["2026"],
            "months_dropped": [],
            "raw_days_dropped": [],
            "empty_periods": [],
            "lost_days": [],
            "set_aside_paths": [],
            "daily_mark": "2029-12-30",
            "monthly_mark": "2029-10",
            "yearly_mark": "2028",
        },
        [row],
    )
    assert year_file.exists() is dry_run, "a live pass deletes the year, and a dry run keeps it"


@pytest.mark.parametrize(
    ("today", "changed", "deleted", "chosen"),
    [
        (date(2029, 12, 31), {}, False, []),
        (date(2030, 1, 1), {}, True, ["2026"]),
        (date(2030, 1, 1), {"yearly_prune_enable": False}, False, None),
        (date(2030, 1, 1), {"dry_run": True}, False, ["2026"]),
        (date(2030, 1, 1), {"yearly_keep_months": 37}, False, []),
    ],
)
def test_boundary_toggle_and_dry_run(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    today: date,
    changed: dict[str, Any],
    deleted: bool,
    chosen: list[str] | None,
) -> None:
    """With the expiry on, a pass says which years it takes, none included; with it off, nothing."""
    paths = indexed_years(tmp_path, ("2026", "2027"))
    with caplog.at_level(logging.INFO):
        result = run(tmp_path, today, **changed)
    assert paths["2026"].exists() is not deleted
    assert paths["2027"].exists()
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY))
    assert held.expired_through == ("2026" if deleted else None)
    if changed.get("dry_run"):
        assert paths["2026"].relative_to(tmp_path).as_posix() in result.taken
    assert not set(result.taken) & set(result.written)
    said = [event.years for event in events(caplog.records, ExpiredYearsChosen)]
    assert said == ([] if chosen is None else [chosen])


def test_a_range_that_skips_an_older_indexed_year_is_refused_there_and_deletes_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Expiry is a prefix, so a range that holds 2027 and not 2026 waits at 2026 for a wider one.

    A person's range is not a code defect, so the pass is deferred and the job stays green.
    """
    paths = indexed_years(tmp_path, ("2026", "2027"))

    with caplog.at_level(logging.INFO):
        result = run(tmp_path, date(2031, 1, 1), period_range=("2027-01", "2027-12"))

    assert (result.stopped_because, result.resume_from, result.fault) == (
        StopReason.DEFERRED,
        "2026",
        GardenerFault.RANGE_STARTS_LATE,
    )
    refused = the_event(caplog.records, PeriodRefused)
    assert (refused.ledger, refused.step, refused.period, refused.fault) == (
        VISUALS,
        CompactionStep.EXPIRE_YEARS,
        "2026",
        GardenerFault.RANGE_STARTS_LATE,
    )
    assert (refused.ledger_fault, refused.error, refused.where) == (None, None, None)
    assert [
        record.levelno
        for record in caplog.records
        if isinstance(event_log.payload(record), PeriodRefused)
    ] == [logging.WARNING], "a refusal that defers the pass is a warning, never an error"
    assert events(caplog.records, ExpiredYearsChosen) == []
    assert said_as_text(caplog.records) == []
    assert all(path.exists() for path in paths.values())
    assert not result.taken


def test_cap_empty_entries_and_restart_after_every_entry_is_deleted(tmp_path: Path) -> None:
    paths = indexed_years(tmp_path, ("2024", "2025", "2026"))
    paths["2025"].unlink()
    index_entries(
        tmp_path,
        Period.YEARLY,
        [
            CompactEntry(covers="2024", rows=1, bytes=paths["2024"].stat().st_size),
            CompactEntry(covers="2025", rows=0, bytes=0, state=EntryState.EMPTY),
            CompactEntry(covers="2026", rows=1, bytes=paths["2026"].stat().st_size),
        ],
    )
    first = run(tmp_path, max_periods_per_run=1)
    assert first.stopped_because is StopReason.CEILING
    assert first.resume_from == "2025"
    assert not paths["2024"].exists() and paths["2026"].exists()
    run(tmp_path, max_periods_per_run=1)
    run(tmp_path, max_periods_per_run=1)
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY))
    assert held.entries == [] and held.expired_through == "2026"
    assert marks_on_disk(state(tmp_path), VISUALS)[Period.YEARLY] == "2026"
    again = run(tmp_path, max_periods_per_run=1)
    assert not any("/yearly/" in path for path in again.written)
    disabled = run(tmp_path, max_periods_per_run=1, yearly_prune_enable=False)
    assert not any("/yearly/" in path for path in disabled.written)
    assert (
        CompactIndex.read(
            ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY)
        ).expired_through
        == "2026"
    )


def test_all_formats_are_deleted_but_unindexed_files_are_not_walked(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    paths = [
        ledger.compact_path(state(tmp_path), VISUALS, Period.YEARLY, "2026", fmt=fmt)
        for fmt in Format
    ]
    for path in paths:
        path.write_bytes(b"unread rows")
    other = ledger.compact_path(state(tmp_path), VISUALS, Period.YEARLY, "2025")
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"not indexed")
    result = run(tmp_path)
    assert all(not path.exists() for path in paths)
    assert other.exists()
    assert all(path.relative_to(tmp_path).as_posix() in result.taken for path in paths)


def test_missing_yearly_index_fails_by_name_and_new_tree_initializes(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    index = ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY)
    index.unlink()
    with pytest.raises(ValueError, match=r"index/yearly.json is missing"):
        run(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    run(empty)
    for period in Period:
        held = CompactIndex.read(ledger.compact_index_path(state(empty), VISUALS, period))
        assert held.entries == [] and held.expired_through is None
    fresh = tmp_path / "new"
    from .test_compaction import a_pass, filed

    filed(fresh, a_pass("2029-12-29"))
    run(fresh)
    assert (
        CompactIndex.read(
            ledger.compact_index_path(state(fresh), VISUALS, Period.YEARLY)
        ).expired_through
        is None
    )


def test_corrupt_index_is_not_guessed_empty(tmp_path: Path) -> None:
    paths = indexed_years(tmp_path, ("2026",))
    ledger.compact_index_path(state(tmp_path), VISUALS, Period.YEARLY).write_bytes(b"not json")
    with pytest.raises(ValueError):
        run(tmp_path)
    assert paths["2026"].exists()


def test_authoritative_legacy_tree_onboards_only_with_pruning_explicitly_disabled(
    tmp_path: Path,
) -> None:
    """A trusted pre-expiry tree may rebuild its missing index before enabling deletion."""
    root = a_finished_year(tmp_path)
    index = ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    index.unlink()
    with pytest.raises(ValueError, match=r"index/yearly\.json is missing"):
        run(root, date(2027, 4, 5))
    run(root, date(2027, 4, 5), yearly_prune_enable=False)
    held = CompactIndex.read(index)
    assert held.expired_through is None
    assert [entry.covers for entry in held.entries] == ["2026"]
    run(root, date(2027, 4, 5))
    assert CompactIndex.read(index) == held


def test_recovery_never_adopts_expired_months(tmp_path: Path) -> None:
    indexed_years(tmp_path, ("2026",))
    run(tmp_path)
    stale = ledger.compact_path(state(tmp_path), VISUALS, Period.MONTHLY, "2026-12")
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"must not be adopted")
    ledger.compact_index_path(state(tmp_path), VISUALS, Period.MONTHLY).unlink()
    run(tmp_path)
    held = CompactIndex.read(ledger.compact_index_path(state(tmp_path), VISUALS, Period.MONTHLY))
    assert not any(entry.covers.startswith("2026") for entry in held.entries)
    assert stale.exists()


def test_old_indexes_migrate_and_expiry_only_belongs_to_yearly() -> None:
    held = CompactIndex.model_validate(
        {"version": "2026-10-04", "ledger": VISUALS, "period": "yearly", "entries": []}
    )
    assert held.expired_through is None
    assert "expired_through" not in held.model_dump(mode="json")
    marked = CompactIndex.model_validate(
        {**held.model_dump(mode="json"), "expired_through": "2026"}
    )
    assert CompactIndex.from_json(marked.to_json()).expired_through == "2026"
    for period in (Period.DAILY, Period.MONTHLY):
        with pytest.raises(ValueError, match="may not set expired_through"):
            CompactIndex(
                version=CompactIndex.schema_version(),
                ledger=VISUALS,
                period=period,
                entries=[],
                expired_through="2026",
            )
    with pytest.raises(ValueError, match="at or before expired_through"):
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=VISUALS,
            period=Period.YEARLY,
            entries=[CompactEntry(covers="2026", rows=0, bytes=0, state=EntryState.EMPTY)],
            expired_through="2026",
        )


def test_manual_pruning_preserves_the_expiry_mark(tmp_path: Path) -> None:
    root = a_finished_year(tmp_path)
    compact(
        root,
        date(2027, 4, 5),
        monthly_window={"unit": "forever"},
        monthly_keep_days=93,
    )
    path = ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    held = CompactIndex.read(path)
    assert held.entries
    path.write_bytes(held.model_copy(update={"expired_through": "2025"}).to_json().encode("ascii"))
    take_days(
        state(root),
        VISUALS,
        since="2026-01-05",
        until="2026-01-05",
        ceiling=1,
        dry_run=False,
        identity=COMPACTION,
    )
    assert CompactIndex.read(path).expired_through == "2025"


def test_reader_floor_is_finite_and_toggle_restores_forever(tmp_path: Path) -> None:
    policy = context_for(TASK, tmp_path).policy
    assert isinstance(policy, CompactionPolicy)
    policy = CompactionPolicy.model_validate(
        {
            **policy.model_dump(mode="json"),
            "monthly_window": {"unit": "forever"},
            "monthly_keep_days": 93,
            "yearly_keep_months": 36,
            "yearly_prune_enable": True,
        }
    )
    for days in (90, 366, 730, 36 * 28):
        assert config.compaction_reaches(policy, DaysWindow(unit="days", value=days))
    assert not config.compaction_reaches(policy, DaysWindow(unit="days", value=36 * 28 + 1))
    assert not config.compaction_reaches(policy, ForeverWindow(unit="forever"))
    assert config.compaction_reaches(policy, MonthsWindow(unit="months", value=36))
    assert not config.compaction_reaches(policy, MonthsWindow(unit="months", value=37))
    disabled = CompactionPolicy.model_validate(
        {**policy.model_dump(mode="json"), "yearly_prune_enable": False}
    )
    assert config.compaction_reaches(disabled, ForeverWindow(unit="forever"))
