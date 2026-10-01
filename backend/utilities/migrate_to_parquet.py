"""Move a ledger's CSV onto the ledger door, prove every row, then delete the CSV.

Removal condition: delete this module and its tests with `CSV_LEDGERS`, when no
ledger is left on CSV.

`CSV_LEDGERS` records how each ledger was filed before it moved to the door, and
how long it was kept there. One layout is read: the CSV day tree,
`<prefix>/<YYYY>/<MM>/<DD>/`, which held one file per writer and was settled by
every reader on read. For each day a tree holds, this takes the rows today's
reader returns for that day (`day_shards.settled_day`), folds them onto any rows
the door already holds for that day exactly as a writer's file beside a settled
file is folded, and files the answer as one raw file through the door. In the
state tree beside `config/`, the compaction's own daily step then packs every day
its rule admits - each day's file, `index/daily.json` and the daily watermark,
written as a live pass writes them - so a compaction turned on later resumes
from the right day. A day the rule does not admit yet stays a raw file. Any other
root, such as a trial run's tree inside `state/`, is filed raw and never packed:
nothing reads a packed trial root, and the trials task empties it.

    python backend/utilities/migrate_to_parquet.py --state-dir state
        --run-id <YYYY-MM-DD-NNNN> --git-sha <sha> [--ledger <name> ...] [--check]

With no `--ledger`, a run or a check takes every ledger in the table that
`config/ledgers.json` files as `raw-and-compact`. A run is refused before
anything is read or written when a ledger it names is still filed as CSV there,
has no `compact-<ledger>` declaration, or has one that keeps less than its CSV
was kept.

| Exit | Meaning |
| --- | --- |
| 0 | Every CSV day moved and read back, or there was none. A second run writes nothing |
| 1 | Refused, a day not read or not read back, or `--check` found a CSV. No CSV deleted |

A malformed `--run-id` or `--git-sha` is refused by the argument parser with its
own usage message, before anything is read.

**Nothing is deleted until everything is proven.** A run takes four steps, and
each covers every ledger it was given before the next one starts: read and fold
every CSV day, file and pack, read every day back, delete. A day is read back
through the door's own bounded reader, from whichever file now serves it, and
compared cell for cell with the rows it was built from. So a refusal at any
step deletes no CSV of any ledger. A refusal in the first step - a row that
will not parse, a name the tree cannot place, a row dated another day - writes
nothing either. What the door already holds is kept, and a second run starts
from it.

**Running it again is safe by construction, and is how a late CSV file moves.**
Every file carries `WriterIdentity(run_id, attempt=1, job=migrate, shard=0,
producer=utilities.migrate_to_parquet, git_sha)`, so a second run with the same
`--run-id` files a day under the same work unit, and a later write of one unit
replaces the earlier one. A day with nothing new is not written again. A CSV file
that lands after the first run - a run created before the merge, pushing after
it - is folded onto what the door holds for its day and packed again.

**Where each ledger's CSV sat is spelled here, and nowhere else.** The registry
says where a ledger sits now, so once a ledger moves it no longer names where it
sat, and `CSV_LEDGERS` keeps that. A ledger's row contract and key are the door
table's, in `ledger/keys.py`, so the table holds neither.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import MappingProxyType
from typing import Final, NamedTuple, cast

from idhazh import config, day_partition, day_shards, ledger
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN, Contract, ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    ForeverWindow,
    MonthsWindow,
    Window,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry
from idhazh.gardener.file_listing import FileListing

# The compaction's own daily step, reached into on purpose: the packing a person
# chose for this one move is the packing a live pass does, and a copy of it here
# would be a second answer to when a day is packed.
from idhazh.gardener.tasks import _daily_period, _monthly_period
from idhazh.gardener.tasks._compact_tree import CompactTree

#: The name every file this writes carries as its producer.
PRODUCER: Final = "utilities.migrate_to_parquet"

#: A person runs this, so it is the first and only attempt, as one shard.
ATTEMPT: Final = 1
SHARD: Final = 0

#: How many days one packing pass may take here. The declared budget paces a
#: daily wake; this pass takes every day the rule admits, once.
PACK_EVERY_DAY: Final = 100_000

EXIT_MIGRATED: Final = 0
EXIT_NOT_PROVEN: Final = 1


class CsvLedger(NamedTuple):
    """How one ledger was filed before it moved to the door, and how long it was kept."""

    old_entry: LedgerEntry
    old_window: Window


def _tree(name: LedgerName, folder: str | None = None) -> LedgerEntry:
    """A CSV day tree, one file a writer a day, under its own name unless it sat elsewhere."""
    return LedgerEntry(name=name, grain=Grain.DAY_TREE, prefix=(folder or name.value,))


def _day_file(name: LedgerName) -> LedgerEntry:
    """One shared CSV file a day, under the ledger's own name."""
    return LedgerEntry(name=name, grain=Grain.DAY_FILE, prefix=(name.value,), suffix=".csv")


#: Every ledger that was, or still is, filed as CSV, with where its CSV sat and
#: how long a task kept it there. A ledger still on CSV has its registry entry and
#: the window its retention task keeps today, so its move changes neither. A moved
#: ledger keeps the entry `config/ledgers.json` held before it moved, and the
#: window its compaction must still reach.
#:
#: Removal condition: the table, this module and its tests are deleted when no
#: ledger is left on CSV - every entry in `config/ledgers.json` is
#: `raw-and-compact`, and `--check` finds no CSV file under any root.
CSV_LEDGERS: Final[Mapping[LedgerName, CsvLedger]] = MappingProxyType(
    {
        # The full-grain series of the telemetry-aggregate task deleted it.
        LedgerName.ITEM_HEALTH: CsvLedger(
            _tree(LedgerName.ITEM_HEALTH), MonthsWindow(unit="months", value=14)
        ),
        # Filed under `scores/`, its name before it was renamed. No eval row is deleted.
        LedgerName.SUMMARY_QUALITY_EVALS: CsvLedger(
            _tree(LedgerName.SUMMARY_QUALITY_EVALS, "scores"), ForeverWindow(unit="forever")
        ),
        # The host-fingerprint retention task deleted it, until its compaction took over.
        LedgerName.HOST_FINGERPRINT: CsvLedger(
            _tree(LedgerName.HOST_FINGERPRINT), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.COUNTERFACTUAL_SCORES: CsvLedger(
            _tree(LedgerName.COUNTERFACTUAL_SCORES), DaysWindow(unit="days", value=30)
        ),
        # Nothing deletes a candidate's verdict.
        LedgerName.CANDIDATE_MODELS: CsvLedger(
            _tree(LedgerName.CANDIDATE_MODELS), ForeverWindow(unit="forever")
        ),
        LedgerName.FEED_HEALTH: CsvLedger(
            _tree(LedgerName.FEED_HEALTH), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.SEEN: CsvLedger(_day_file(LedgerName.SEEN), DaysWindow(unit="days", value=90)),
        # Nothing deletes a published record: forgetting one republishes it.
        LedgerName.PUBLISHED: CsvLedger(
            _day_file(LedgerName.PUBLISHED), ForeverWindow(unit="forever")
        ),
    }
)


class NotProvenError(Exception):
    """A day would not read, or did not come across whole, so nothing is deleted. Exit 1."""


class RefusedError(Exception):
    """A ledger the run names cannot move yet, so nothing is read or written. Exit 1."""


def csv_root(state_dir: Path, which: LedgerName) -> Path:
    """Where this ledger's CSV sat under a state root: the prefix its old entry names."""
    return state_dir.joinpath(*CSV_LEDGERS[which].old_entry.prefix)


def door_ledgers() -> list[LedgerName]:
    """Every ledger in the table that `config/ledgers.json` files through the door now."""
    return [name for name in CSV_LEDGERS if ledger.entry(name).grain is Grain.RAW_AND_COMPACT]


def _row_contract(which: LedgerName) -> type[ledger.CsvContract]:
    """The door's row contract for this ledger, as the CSV reader takes it.

    The door table pairs a ledger with a `Contract`, and every ledger that was ever
    filed as CSV has one that also reads and writes a CSV row. The types cannot say
    the second of a `Contract` in general, so it is said here, once.
    """
    return cast("type[ledger.CsvContract]", ledger.door_contract(which))


def csv_days(state_dir: Path, which: LedgerName) -> dict[str, list[Path]]:
    """Every day this ledger's CSV still holds, to the files in it, oldest day first.

    Only the day tree is read: one file a writer under each day. A ledger that sat
    in another layout is refused by name rather than read as holding nothing, and
    a tree that holds a name it cannot place is refused, through `day_shards`,
    rather than leaving a file unmoved and unmentioned.
    """
    sat = CSV_LEDGERS[which].old_entry.grain
    if sat is not Grain.DAY_TREE:
        raise NotProvenError(
            f"{which.value} sat in the {sat.value} layout, and this reads only the "
            f"{Grain.DAY_TREE.value} layout, one CSV file a writer under each day"
        )
    root = csv_root(state_dir, which)
    if not root.is_dir():
        return {}
    try:
        days = sorted(
            day for dates in day_shards.dates_by_month(root, days=UNBOUNDED_WINDOW).values()
            for day in dates
        )
        return {day: day_shards.one_day(root, day) for day in days}
    except ValueError as refusal:
        raise NotProvenError(f"{which.value}: {refusal}") from refusal


def _shown(state_dir: Path, path: Path) -> str:
    """A path as it may leave the process: relative, POSIX (CLAUDE.md section 2)."""
    return f"{ledger.STATE_DIRNAME}/{path.relative_to(state_dir).as_posix()}"


def _key_of(cells: dict[str, str], key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(cells[name] for name in key)


def folded(
    held: Sequence[dict[str, str]], arriving: Sequence[dict[str, str]], key: tuple[str, ...]
) -> list[dict[str, str]]:
    """The rows the door holds for a day, with the CSV's rows for it folded on.

    The fold today's reader applies to a settled file and a writer's file beside
    it: the door's rows stand where the settled file stood, and the CSV's rows
    arrive after them, so a cell only one side filled is joined and a cell both
    filled goes to the later side unless the key declares a preference.
    """
    prefers = ledger.preference_for(key)
    records: dict[tuple[str, ...], day_shards.Held] = {}
    for cells in held:
        records[_key_of(cells, key)] = day_shards.Held(0, dict(cells))
    for number, cells in enumerate(arriving):
        record = _key_of(cells, key)
        if record not in records:
            records[record] = day_shards.Held(1, dict(cells))
            continue
        day_shards.settle(
            records[record], day_shards.Waiting(Path(), 1, number, dict(cells)), key, prefers
        )
    return [entry.cells for entry in records.values()]


@dataclass(slots=True)
class _Day:
    """One day of one ledger: what the door will hold, and the CSV files it came from."""

    files: list[Path]
    rows: list[dict[str, str]]
    #: The same rows read by the contract, for a day that files anything new; else empty.
    models: list[Contract]
    changed: bool


@dataclass(slots=True)
class Moved:
    """What one ledger's migration did, in the numbers a reviewer asks for."""

    which: LedgerName
    csv_files: int = 0
    csv_bytes: int = 0
    days: int = 0
    rows: int = 0
    filed: int = 0
    packed: list[str] = field(default_factory=list)


def _door_rows(state_dir: Path, which: LedgerName, day: str) -> list[dict[str, str]]:
    rows = ledger.load_days(state_dir, which, [day], model=ledger.door_contract(which))
    return [cast("ledger.CsvRecord", row).csv_row() for row in rows]


def _plan(state_dir: Path, which: LedgerName) -> dict[str, _Day]:
    """Every CSV day of this ledger, folded onto what the door holds for it. Nothing written.

    Everything that can refuse a day's rows refuses here, before the first
    write: a row that will not parse, a row dated another day, and a folded row
    the contract will not take. A fold joins cells from two files, and nothing
    checks the joined row until the door files it.
    """
    model, key = _row_contract(which), ledger.door_key(which)
    root = csv_root(state_dir, which)
    planned: dict[str, _Day] = {}
    for day, files in csv_days(state_dir, which).items():
        try:
            arriving = day_shards.settled_day(root, day, key, model)
        except ValueError as refusal:
            raise NotProvenError(f"{which.value} {day}: {refusal}") from refusal
        stray = sorted({cells["date"] for cells in arriving} - {day})
        if stray:
            raise NotProvenError(
                f"{which.value} {day}: the CSV day holds rows dated {stray}, and the door "
                "files a row under its own date, so this day would not read back"
            )
        held = _door_rows(state_dir, which, day)
        rows = folded(held, arriving, key)
        changed = rows != held
        try:
            models = (
                [cast("Contract", model.from_csv_row(cells)) for cells in rows] if changed else []
            )
        except ValueError as refusal:
            raise NotProvenError(
                f"{which.value} {day}: a settled row is not a {model.__name__} the door can "
                f"file: {refusal}"
            ) from refusal
        planned[day] = _Day(files=files, rows=rows, models=models, changed=changed)
    return planned


def _spelled(window: Window) -> str:
    """A window as a refusal quotes it."""
    return "forever" if isinstance(window, ForeverWindow) else f"{window.value} {window.unit}"


def _declared(
    which: Sequence[LedgerName], config_dir: Path
) -> dict[LedgerName, CompactionPolicy]:
    """Each ledger's compaction, taken live and unbounded for this one pass, or a refusal.

    Asked before anything is read or written. A ledger `config/ledgers.json` still
    files as CSV has no door to move into; one with no compaction has nothing to
    say which days are packed; and a compaction that keeps less than the CSV was
    kept would delete, at its first live pass, days the CSV still held.
    """
    tasks = config.load_gardener(config_dir).tasks
    declared: dict[LedgerName, CompactionPolicy] = {}
    for name in which:
        grain = ledger.entry(name).grain
        if grain is not Grain.RAW_AND_COMPACT:
            raise RefusedError(
                f"config/ledgers.json files {name.value} as {grain.value}, so it has no door "
                f"to move into yet: its entry becomes {Grain.RAW_AND_COMPACT.value} in the "
                "change that moves its writers and readers"
            )
        task = f"compact-{name.value}"
        policy = tasks.get(task)
        if not isinstance(policy, CompactionPolicy):
            raise RefusedError(
                f"config/gardener/{task}.json does not declare a compaction, so nothing can "
                "say which days the packing rule admits"
            )
        kept = CSV_LEDGERS[name].old_window
        if not config.compaction_reaches(policy, kept):
            raise RefusedError(
                f"config/gardener/{task}.json keeps daily_keep_days {policy.daily_keep_days} "
                f"and monthly_window {_spelled(policy.monthly_window)}, which does not reach "
                f"the {_spelled(kept)} {name.value} was kept on CSV, so its first live pass "
                "would delete days the CSV still held"
            )
        declared[name] = policy.model_copy(
            update={"dry_run": False, "max_periods_per_run": PACK_EVERY_DAY}
        )
    return declared


def packs_here(state_dir: Path, config_dir: Path) -> bool:
    """Whether this root is the state tree the declarations in `config_dir` govern.

    Only `state/` beside `config/` is packed. Any other root - a trial run's tree
    inside it - is filed raw: nothing reads a packed trial root, and the trials
    task empties it.
    """
    return state_dir.resolve() == (config_dir.parent / ledger.STATE_DIRNAME).resolve()


def _pack(
    state_dir: Path,
    which: LedgerName,
    identity: WriterIdentity,
    *,
    policy: CompactionPolicy,
    today: date,
) -> list[str]:
    """Run the compaction's daily step live over this ledger, and name the days it packed."""
    now = datetime.combine(today, time.min, tzinfo=UTC)
    listing = FileListing.from_disk(state_dir.parent, policy.owns or ())
    tree = CompactTree.read(state_dir, which, listing)
    before = dict(tree.daily)
    first_kept = _monthly_period.first_kept_month(
        now=now, daily_keep_days=policy.daily_keep_days, window=policy.monthly_window
    )
    stops = _daily_period.compact(
        tree,
        policy,
        now=now,
        stamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        identity=identity,
        first_kept=first_kept,
    )
    failed = [stop.resume_from for stop in stops if stop.because is StopReason.FAILED]
    if failed:
        raise NotProvenError(
            f"{which.value}: the packing refused {failed}; the raw files are kept and no "
            "CSV is deleted"
        )
    tree.apply()
    return sorted(day for day, entry in tree.daily.items() if before.get(day) != entry)


def prove(state_dir: Path, which: LedgerName, day: str, rows: Sequence[dict[str, str]]) -> None:
    """The day reads back through the door as exactly these rows, cell for cell, or a refusal."""
    key = ledger.door_key(which)
    back = {_key_of(cells, key): cells for cells in _door_rows(state_dir, which, day)}
    wanted = {_key_of(cells, key): cells for cells in rows}
    if back.keys() != wanted.keys():
        raise NotProvenError(
            f"{which.value} {day} reads back {len(back)} rows where {len(wanted)} were filed; "
            f"missing {sorted(wanted.keys() - back.keys())[:3]}, "
            f"invented {sorted(back.keys() - wanted.keys())[:3]}"
        )
    for record, cells in wanted.items():
        for column, cell in cells.items():
            if back[record].get(column) != cell:
                raise NotProvenError(
                    f"{which.value} {day} row {','.join(record)} reads back "
                    f"{column}={back[record].get(column)!r} where {cell!r} was filed"
                )


def _identity(run_id: str, git_sha: str) -> WriterIdentity:
    return WriterIdentity(
        run_id=run_id,
        attempt=ATTEMPT,
        job=ServerJob.MIGRATE,
        shard=SHARD,
        producer=PRODUCER,
        git_sha=git_sha,
    )


def migrate(
    state_dir: Path,
    which: Sequence[LedgerName],
    *,
    run_id: str,
    git_sha: str,
    today: date,
    config_dir: Path = config.DEFAULT_CONFIG_DIR,
) -> list[Moved]:
    """Move these ledgers' CSV days onto the door, pack what the rule admits, prove, then delete.

    Each step covers every ledger before the next starts, so a refusal deletes
    no CSV of any ledger. Raises `RefusedError` before anything is read when a
    ledger cannot move yet, and `NotProvenError` naming the first day that did not
    come across. Only the state tree beside `config_dir` is packed.
    """
    identity = _identity(run_id, git_sha)
    policies = _declared(which, config_dir)
    packing = packs_here(state_dir, config_dir)
    planned = {name: _plan(state_dir, name) for name in which}
    moved: list[Moved] = []
    for name, days in planned.items():
        report = Moved(which=name, days=len(days))
        for day, held in days.items():
            report.csv_files += len(held.files)
            report.csv_bytes += sum(path.stat().st_size for path in held.files)
            report.rows += len(held.rows)
            if held.changed:
                ledger.persist(state_dir, held.models, ledger=name, covers=day, identity=identity)
                report.filed += 1
        if days and packing:
            report.packed = _pack(state_dir, name, identity, policy=policies[name], today=today)
        moved.append(report)
    for name, days in planned.items():
        for day, held in days.items():
            prove(state_dir, name, day, held.rows)
    for name, days in planned.items():
        for held in days.values():
            for path in held.files:
                path.unlink()
                day_partition.drop_empty_day_dirs(path)
        root = csv_root(state_dir, name)
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
    return moved


def left(state_dir: Path, which: Sequence[LedgerName]) -> list[Path]:
    """Every CSV file of these ledgers still on disk."""
    return [
        path for name in which for files in csv_days(state_dir, name).values() for path in files
    ]


def _pattern(pattern: str, what: str) -> Callable[[str], str]:
    """An argument type that takes only a value matching this pattern."""

    def take(value: str) -> str:
        if re.fullmatch(pattern, value) is None:
            raise argparse.ArgumentTypeError(f"{value!r} is not {what}")
        return value

    return take


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--state-dir", required=True, type=Path, help="The tree to migrate.")
    parser.add_argument(
        "--run-id",
        required=True,
        type=_pattern(RUN_ID_PATTERN, "a run id, <YYYY-MM-DD>-<number>"),
        help="The run every file names. Use the same one on a second run.",
    )
    parser.add_argument(
        "--git-sha",
        required=True,
        type=_pattern(COMMIT_SHA_PATTERN, "the forty hex digits of a commit"),
        help="The commit this checkout is at, which every file names: git rev-parse HEAD.",
    )
    parser.add_argument(
        "--ledger",
        action="append",
        choices=[name.value for name in CSV_LEDGERS],
        default=None,
        help=(
            "A ledger to migrate or check; repeat it for more. Without it, every ledger "
            "in the table that config/ledgers.json files as raw-and-compact."
        ),
    )
    parser.add_argument(
        "--check", action="store_true", help="Write nothing. Exit 1 if any CSV file remains."
    )
    args = parser.parse_args(argv)
    state_dir: Path = args.state_dir
    which = (
        list(dict.fromkeys(LedgerName(value) for value in args.ledger))
        if args.ledger
        else door_ledgers()
    )

    if args.check:
        try:
            remaining = left(state_dir, which)
        except NotProvenError as refusal:
            print(f"a CSV tree cannot be read: {refusal}", file=sys.stderr)
            return EXIT_NOT_PROVEN
        for path in remaining:
            print(f"{_shown(state_dir, path)} is still a CSV")
        print(f"{len(remaining)} CSV file(s) left")
        return EXIT_NOT_PROVEN if remaining else EXIT_MIGRATED

    try:
        moved = migrate(
            state_dir,
            which,
            run_id=args.run_id,
            git_sha=args.git_sha,
            today=datetime.now(UTC).date(),
        )
    except RefusedError as refusal:
        print(f"refused, nothing written: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    if not packs_here(state_dir, config.DEFAULT_CONFIG_DIR):
        print("this root is not the state tree beside config/, so every day is filed raw")
    for each in moved:
        print(
            f"{each.which.value}: {each.csv_files} CSV file(s), {each.csv_bytes} bytes, over "
            f"{each.days} day(s) -> {each.rows} row(s); {each.filed} day(s) filed, "
            f"{len(each.packed)} day(s) packed ({each.packed[0] if each.packed else '-'} to "
            f"{each.packed[-1] if each.packed else '-'}); every CSV file deleted"
        )
    return EXIT_MIGRATED


if __name__ == "__main__":
    raise SystemExit(main())
