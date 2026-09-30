"""Move the three console ledgers off their CSV day trees onto the ledger door, and prove it.

Removal condition: delete when every `state/item-health`, `state/scores` and
`state/host-fingerprint` CSV is gone from `main`.

`item-health`, `scores` and `host-fingerprint` were CSV day trees:
`<ledger>/<YYYY>/<MM>/<DD>/` held one file per writer, and every reader settled
a day on read. For each ledger and each day that tree holds, this takes the rows
today's reader returns for that day (`day_shards.settled_day`), folds them onto
any rows the door already holds for that day exactly as a writer's file beside a
settled file is folded, and files the answer as one raw file through the door.
Then the compaction's own daily step packs every day its rule admits - each
day's file, `index/daily.json` and the daily watermark, written as a live pass
writes them - so a compaction turned on later resumes from the right day. A day
the rule does not admit yet stays a raw file.

    python backend/utilities/migrate_to_parquet.py --state-dir state
        --run-id <YYYY-MM-DD-NNNN> --git-sha <sha> [--ledger <name>] [--check]

| Exit | Meaning |
| --- | --- |
| 0 | Every CSV day moved and read back, or there was none. A second run writes nothing |
| 1 | A day would not read or did not read back, or `--check` found a CSV. No CSV was deleted |

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

**The CSV addresses are spelled here, and nowhere else.** The registry describes
where each ledger sits now, so it no longer names where it sat: `<ledger>/` at
the top of the state tree.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final

from idhazh import config, day_partition, day_shards, ledger
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN, ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName

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

type Row = ItemHealthRow | EvalRow | HostFingerprintRow

#: Each ledger this moves, and the contract and key its rows were settled by.
LEDGERS: Final[dict[LedgerName, tuple[type[Row], tuple[str, ...]]]] = {
    LedgerName.ITEM_HEALTH: (ItemHealthRow, ledger.ITEM_HEALTH_KEY),
    LedgerName.SCORES: (EvalRow, ledger.OBSERVATION_KEY),
    LedgerName.HOST_FINGERPRINT: (HostFingerprintRow, ledger.HOST_FINGERPRINT_KEY),
}


class NotProvenError(Exception):
    """A day would not read, or did not come across whole, so nothing is deleted. Exit 1."""


def csv_root(state_dir: Path, which: LedgerName) -> Path:
    """Where this ledger's CSV day tree sat: `<ledger>/` at the top of the state tree."""
    return state_dir / which.value


def csv_days(state_dir: Path, which: LedgerName) -> dict[str, list[Path]]:
    """Every day the CSV tree still holds, to the files in it, oldest day first.

    A tree that holds a name it cannot place is refused, through `day_shards`,
    rather than leaving a file unmoved and unmentioned.
    """
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
    models: list[Row]
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
    model, _ = LEDGERS[which]
    return [row.csv_row() for row in ledger.load_days(state_dir, which, [day], model=model)]


def _plan(state_dir: Path, which: LedgerName) -> dict[str, _Day]:
    """Every CSV day of this ledger, folded onto what the door holds for it. Nothing written.

    Everything that can refuse a day's rows refuses here, before the first
    write: a row that will not parse, a row dated another day, and a folded row
    the contract will not take. A fold joins cells from two files, and nothing
    checks the joined row until the door files it.
    """
    model, key = LEDGERS[which]
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
            models = [model.from_csv_row(cells) for cells in rows] if changed else []
        except ValueError as refusal:
            raise NotProvenError(
                f"{which.value} {day}: a settled row is not a {model.__name__} the door can "
                f"file: {refusal}"
            ) from refusal
        planned[day] = _Day(files=files, rows=rows, models=models, changed=changed)
    return planned


def _policy(which: LedgerName, config_dir: Path) -> CompactionPolicy:
    """This ledger's declared compaction, taken live and unbounded for this one pass."""
    declared = config.load_gardener(config_dir).tasks.get(f"compact-{which.value}")
    if not isinstance(declared, CompactionPolicy):
        raise NotProvenError(
            f"config/gardener/compact-{which.value}.json does not declare a compaction, so "
            "nothing can say which days the packing rule admits"
        )
    return declared.model_copy(update={"dry_run": False, "max_periods_per_run": PACK_EVERY_DAY})


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
    tree = CompactTree.read(state_dir, which)
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
    _, key = LEDGERS[which]
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
    no CSV of any ledger. Raises `NotProvenError` naming the first day that did
    not come across.
    """
    identity = _identity(run_id, git_sha)
    planned = {name: _plan(state_dir, name) for name in which}
    policies = {name: _policy(name, config_dir) for name, days in planned.items() if days}
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
        if days:
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
        choices=[name.value for name in LEDGERS],
        default=None,
        help="One ledger to migrate. All three when absent.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Write nothing. Exit 1 if any CSV file remains."
    )
    args = parser.parse_args(argv)
    state_dir: Path = args.state_dir
    which = [LedgerName(args.ledger)] if args.ledger else list(LEDGERS)

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
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
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
