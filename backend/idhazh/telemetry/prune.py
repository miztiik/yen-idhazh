"""Which store does an operator delete from, and over which days?

The other half of `docs/architecture/publishing/retention.md`. The scheduled
prune deletes what a window has aged out; this deletes what a person names -
one store, one range of days, because that day was published in error, or a
source asked to be removed, or a run wrote rows nobody wants kept.

    idhazh telemetry prune --target item-health --since 2026-08-24 --until 2026-08-26

**It reports and removes nothing until it is told twice.** `--dry-run` is on by
default and `--no-dry-run` is the second word. The reason is
`.github/workflows/prune.yml`: it squashes and force-pushes `main` on a
schedule, so a state file deleted here stops being recoverable from history once
that prune passes over the range (CLAUDE.md section 8). `git revert` is not a
recovery path for a file older than `finetune.prune_keep_days`. The precedent is
the fold step in `.github/workflows/digest.yml`, which ships `idhazh
prune-state --dry-run` for exactly that reason and has never removed a file.

**`--target` names a store, never a path.** The vocabulary below is closed, and
a word outside it is refused with the whole list rather than resolved against
the file system. A path argument would be a deletion primitive pointed at the
repository, and fetched text may never become a file path (Guardrail #11) - so
there is no argument here a path could travel through.

**Both ends of the range are named.** `--since 2026-08-24 --until 2026-08-26` is
three days, and `--since X --until X` is one. That is the arithmetic
`day_partition.days_in_window` already uses, where a cover of `n` days returns
`n + 1` dates, and the two agree on purpose.

**Atomic per store, through the rename the rest of this repository writes with.**
Every selected file is moved into a scratch directory beside the stores - one
rename each, on the same file system - and only once every one has moved is that
directory removed. A rename that fails part way puts back the ones already
moved and raises, so the tree is exactly as it was found. A prune that deleted
three day files and then raised would have left an archive nobody can reason
about, which is the state this shape exists to make unreachable.

The scratch directory is created and removed inside one call, in a `finally`,
whether the moves succeeded or were rolled back. Its name starts with a dot, so
a leftover from a process somebody killed reads as scratch rather than as a
store nobody recognises.

**Bounded by the range it is handed** (Guardrail #12). The walk is one store's
day tree, and the work is the days inside the range - neither grows because
another store did.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import day_partition, ledger
from idhazh.evals import writer as score_writer

#: Every store this command may delete from, alphabetically.
#:
#: The word an operator types IS the directory name under `state/`, taken from
#: the module that owns the store rather than spelled again here - so a store
#: that is renamed renames its target with it, and neither can drift from the
#: other (Guardrail #6).
#:
#: The rule that decides membership is one line: a store files
#: `<YYYY>/<MM>/<DD>.csv` day files, and is not one of the two stores below.
#: `state/day-metrics/` and `state/traces/` are day-shaped and are deliberately
#: absent - they file `.json` and `<DD>-<run>-<shard>.jsonl`, which
#: `day_partition.day_files` refuses, and a second walker here would be a second
#: answer to what a day file is. Bringing either in means teaching that one
#: walker its suffix, which is where the question belongs.
#:
#: **`scores` and `score-index` are one pair.** `evals.writer` refuses a repeat
#: measurement by reading the index rather than the rows, so a range taken out of
#: one and left in the other puts the two out of step: an index whose rows are
#: gone refuses a measurement nothing can produce, and rows whose index is gone
#: are re-measurable as if new. Prune both over the same range, or repair with
#: `idhazh rebuild-score-index --month <YYYY-MM>` afterwards. The dry run is
#: where that is read, which is why it is the default.
TARGETS: Final[tuple[str, ...]] = tuple(
    sorted(
        {
            ledger.COUNTERFACTUAL_SCORES_DIRNAME,
            ledger.HEALTH_DIRNAME,
            ledger.ITEM_HEALTH_DIRNAME,
            ledger.VISUAL_PRUNES_DIRNAME,
            score_writer.INDEX_DIRNAME,
            score_writer.LEDGER_DIRNAME,
        }
    )
)


#: The two stores this refuses by name, each with the reason it is refused.
#:
#: Named rather than left out of the list above, because a store missing from a
#: vocabulary reads as an oversight and a store refused with a sentence reads as
#: a decision. Somebody who types one of these is holding a real question, and
#: the answer they need is why the answer is no.
REFUSED: Final[Mapping[str, str]] = {
    ledger.PUBLISHED_DIRNAME: (
        "it is the guard against publishing one story twice and it has no window "
        "at all - collect.published_window_days is -1, so every row in it is a row "
        "that must never be deleted. A store that forgets cannot be that guard"
    ),
    ledger.SEEN_DIRNAME: (
        "it is what the planner remembers having already seen, so removing a day "
        "from it lets the next run rediscover every address it holds - one "
        "operator command becomes a loop"
    ),
}


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one prune selected, what it weighed, and whether it happened.

    `removed` is the POSIX `state/<store>/<YYYY>/<MM>/<DD>.csv` form, oldest
    first, and it is the same list on both sides of `dry_run` - named before
    anything is moved, so the list a dry run prints is the list a live run
    removes, file for file. That list is the deliverable of a dry run, which is
    why a count would not do.
    """

    target: str
    since: str
    until: str
    removed: tuple[str, ...]
    kept: int
    bytes_freed: int
    dry_run: bool

    @property
    def changed(self) -> bool:
        return bool(self.removed) and not self.dry_run


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """The flags this subcommand takes, declared beside the code that reads them.

    `--target` is deliberately not an argparse `choices` list. A word outside the
    vocabulary and a word this refuses by name are different answers, and
    `resolve` below is the one place that distinction is drawn - a `choices`
    list would collapse both into "invalid choice" and lose the reason, which is
    the only useful half of a refusal.

    `--dry-run` is on by default and `--no-dry-run` is how a person turns it off,
    so deleting takes a word nobody types by accident.
    """
    parser.add_argument(
        "--target",
        required=True,
        metavar="STORE",
        help=(
            "Which store to delete from. One of "
            + ", ".join(TARGETS)
            + ". Never a path: "
            + " and ".join(REFUSED)
            + " are refused by name."
        ),
    )
    parser.add_argument(
        "--since", required=True, metavar="YYYY-MM-DD", help="The oldest day to remove."
    )
    parser.add_argument(
        "--until",
        required=True,
        metavar="YYYY-MM-DD",
        help="The newest day to remove. Both ends are named, so --since X --until X is one day.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Report what a live run would remove and remove nothing. On by "
            "default, because prune.yml force-pushes main and a file deleted "
            "here stops being recoverable once that prune passes over it. Pass "
            "--no-dry-run to delete."
        ),
    )


def resolve(target: str) -> str:
    """The store this target names, or a refusal that says why.

    One place the vocabulary is checked, so the parser, the body and any later
    caller cannot disagree about which words are stores.
    """
    if target in TARGETS:
        return target
    if target in REFUSED:
        raise ValueError(
            f"--target {target} is refused: {REFUSED[target]}. "
            f"The stores this prunes are {', '.join(TARGETS)}"
        )
    raise ValueError(
        f"--target takes the name of a store, not {target!r}. A path is never a "
        f"target here, because a deletion primitive pointed at the repository is "
        f"the one accident nobody can undo. The stores this prunes are "
        f"{', '.join(TARGETS)}; {', '.join(REFUSED)} are refused by name"
    )


def _day(value: str, flag: str) -> str:
    """One `YYYY-MM-DD` day, refused unless it is exactly that.

    The width is checked as well as the parse. `date.fromisoformat` accepts
    `20260824` from Python 3.11, and a range compared as text - which is what
    every other date comparison in this tree does, because an ISO day sorts
    chronologically - would then put that day outside every range it belongs in.
    """
    try:
        if len(value) != 10:
            raise ValueError(value)
        date_type.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{flag} takes a YYYY-MM-DD day, not {value!r}") from None
    return value


def _park(day: Path, parked: Path) -> None:
    """Move one day file out of its store, so that removing it is a rename.

    The one place a file moves, so the rollback below has one thing to undo and
    a test has one place to fail the move from.
    """
    day.rename(parked)


def _relpath(state_root: Path, day: Path) -> str:
    """`state/<store>/<YYYY>/<MM>/<DD>.csv`, read off the path the walk found.

    Derived rather than spelled, so this does not become a second description of
    where a day file lives. The prefix is the committed tree's own name whatever
    root a caller handed in, which is what makes the list a person reads the
    same whether it came from the repository or from a test's own tree - the
    same form `ledger.seen_relpath` and its siblings return.
    """
    return f"{ledger.STATE_DIRNAME}/{day.relative_to(state_root).as_posix()}"


def prune_range(
    state_root: Path,
    *,
    target: str,
    since: str,
    until: str,
    dry_run: bool = True,
) -> Outcome:
    """Remove one store's day files between two days, both ends named.

    Selection first, then the move, and nothing in between. `day_files` refuses
    a name it cannot place, so a store holding something this walk cannot read
    stops the prune before a single file has moved - which is the right way
    round: a tree nobody can describe is not a tree to start deleting from.
    """
    store = resolve(target)
    first = _day(since, "--since")
    last = _day(until, "--until")
    if first > last:
        raise ValueError(
            f"--since {first} is after --until {last}, so the range names no day. "
            "Both ends are named, so the oldest day comes first"
        )

    chosen: list[Path] = []
    kept = 0
    for day in day_partition.day_files(state_root / store):
        if first <= day_partition.date_of(day) <= last:
            chosen.append(day)
        else:
            kept += 1

    # Weighed before anything moves, so a dry run reports the bytes a live run
    # frees rather than the bytes it happens to have reached.
    freed = sum(day.stat().st_size for day in chosen)
    removed = tuple(_relpath(state_root, day) for day in chosen)

    if chosen and not dry_run:
        _remove(state_root, chosen)

    return Outcome(
        target=store,
        since=first,
        until=last,
        removed=removed,
        kept=kept,
        bytes_freed=freed,
        dry_run=dry_run,
    )


def _remove(state_root: Path, chosen: list[Path]) -> None:
    """Move every chosen file out, then drop them together - or put them all back.

    Two phases, because a loop of `unlink` calls cannot be undone. A rename
    inside one file system is atomic and reversible, so the first phase is
    reversible and the second phase cannot half-happen: by the time the scratch
    directory is removed, the store no longer holds any of these files.

    The scratch directory sits beside the stores rather than in the system
    temporary directory, so every move is a rename within one file system - a
    cross-device move is a copy, which is neither atomic nor cheap. The `finally`
    removes it whichever way the moves went, and its name starts with a dot so
    that one left by a killed process reads as scratch rather than as a store.
    """
    staging = Path(tempfile.mkdtemp(prefix=".prune-", dir=state_root))
    moved: list[tuple[Path, Path]] = []
    try:
        for index, day in enumerate(chosen):
            # Numbered, because two stores' day files share a name and a flat
            # staging directory would have one overwrite the other.
            parked = staging / f"{index:04d}-{day.name}"
            _park(day, parked)
            moved.append((day, parked))
    except BaseException:
        for day, parked in reversed(moved):
            parked.rename(day)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    for day, _parked in moved:
        day_partition.drop_empty_day_dirs(day)


def report(outcome: Outcome) -> list[str]:
    """What happened, as the lines the command prints, one file per line.

    A count says a deletion happened and nothing about what it took. This list
    is what a person reads before passing `--no-dry-run`, so it is the paths
    themselves - the same rule `stages/prune_state.py` states for the scheduled
    pass.
    """
    span = f"{outcome.since} to {outcome.until}"
    verb = "would remove" if outcome.dry_run else "removed"
    if not outcome.removed:
        return [
            f"{span}: {outcome.target} has no day file in that range, so nothing "
            f"was removed - {outcome.kept} day files are outside it"
        ]

    lines = [
        f"{span}: {outcome.target} {verb} {len(outcome.removed)} day files, "
        f"{outcome.bytes_freed} bytes, keeping {outcome.kept} outside the range"
    ]
    lines += [f"  {relpath}" for relpath in outcome.removed]
    if outcome.dry_run:
        lines.append("  nothing was removed - pass --no-dry-run to delete these")
    return lines
