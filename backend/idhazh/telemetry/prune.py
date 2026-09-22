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

**Atomic per day file, one delete at a time.** Every selected file is removed on
its own, oldest first, through `idhazh.prune.one_at_a_time` - the same core the
GitHub collections are pruned with. A pass interrupted after the third file
leaves three files gone and the rest exactly as they were. Nothing is half-done,
because one `unlink` is the unit and a file is either there or it is not.

Until 2026-09-17 this collected the whole range, renamed every file into a
scratch directory beside the stores, and removed that directory once every
rename had worked - all of them or none of them, with a rollback if a rename
failed. The scratch directory is gone with it. What that shape bought was "the
tree is exactly as you found it" after a failure; what it cost was a second
write path that could itself fail while undoing, and a range that had to be
collected before the first file could move. An operator who now has to re-run a
pass reads which files went from the record, which is a cheaper answer than a
rollback nobody could test in production.

**Bounded by the range it is handed, and by a ceiling inside it** (Guardrail
#12). The walk is one store's day tree, and a pass deletes at most the days the
range names, or the `--max-deletes` an operator asked for. When a ceiling stops
a pass, the report says which day the next pass resumes at.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from types import MappingProxyType
from typing import Final

from idhazh import day_partition, day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.evals import writer as score_writer
from idhazh.prune import one_at_a_time

#: The core's own interruption, named here so a caller of this module imports
#: one thing. A delete that failed raises it, and the record it carries says
#: which day files had already gone.
PruneInterruptedError = one_at_a_time.PruneInterruptedError

#: Every store this command may delete from, and where each one lives under
#: `state/`, alphabetically.
#:
#: The word an operator types is built from the directory names the module that
#: owns the store declares, never spelled again here - so a store that is renamed
#: renames its target with it, and neither can drift from the other (Guardrail
#: #6). A flat store's word IS its directory. A NESTED store's word joins its two
#: segments with a hyphen, because a slash in a word turns a closed vocabulary
#: into something that looks like a path - and a deletion primitive that resolved
#: its argument against the file system is the one accident nobody can undo.
#:
#: The rule that decides membership is one line: a store files
#: `<YYYY>/<MM>/<DD>.csv` day files, and is not one of the two stores below.
#: `state/day-metrics/` and `state/traces/` are day-shaped and are deliberately
#: absent - they file `.json` and `<DD>-<run>-<shard>.jsonl`, which
#: `day_shards.shard_files` refuses, and a second walker here would be a second
#: answer to what a day file is. Bringing either in means teaching that one
#: walker its suffix, which is where the question belongs. `state/span-rollup/`
#: files by month and `state/segments/` is scratch the compaction drains, so
#: neither is a day store at all.
#:
#: **`host-fingerprint` is what a day taken off the site owes its machine rows.**
#: It filed by day from 2026-09-16 and was missing from this list until
#: 2026-09-19, so an operator could take a day's census, scores and feeds back
#: and leave the machines that produced them standing. The published machine
#: shard is folded from this tree, so a day removed here is also a month to
#: republish - `docs/architecture/publishing/retention.md` carries that pairing.
#:
#: **`scores` and `score-index` are one pair.** `evals.writer` refuses a repeat
#: measurement by reading the index rather than the rows, so a range taken out of
#: one and left in the other puts the two out of step: an index whose rows are
#: gone refuses a measurement nothing can produce, and rows whose index is gone
#: are re-measurable as if new. Prune both over the same range, or repair with
#: `idhazh rebuild-score-index --month <YYYY-MM>` afterwards. The dry run is
#: where that is read, which is why it is the default.
#:
#: **`content-similarity-judge-scored-pairs` and
#: `content-similarity-judge-fitted-thresholds` are
#: not a pair.** The pairs are folded into `score-distribution.json` once and
#: never read again, so deleting a day of them takes nothing away from the fit;
#: deleting a fitted row takes a day out of the guard's median and out of what
#: step 4 compares against. Either can go on its own.
#:
#: **`llm-council-shard-outcomes` is here before anything writes it.** The shape
#: and the path land ahead of the step that appends to them (Guardrail #3), and a
#: store an operator cannot name is a store a day cannot be taken out of. A range
#: over a store with no file selects nothing and says so. The four
#: `content-similarity-judge` stores are here for the same reason, and they are
#: the judge's rather than the council's: what a reading is about decides where
#: it is filed, never what executed it.
TARGETS: Final[Mapping[str, str]] = MappingProxyType(
    dict(
        sorted(
            {
                ledger.COUNTERFACTUAL_SCORES_DIRNAME: ledger.COUNTERFACTUAL_SCORES_DIRNAME,
                ledger.HEALTH_DIRNAME: ledger.HEALTH_DIRNAME,
                ledger.HOST_FINGERPRINT_DIRNAME: ledger.HOST_FINGERPRINT_DIRNAME,
                ledger.ITEM_HEALTH_DIRNAME: ledger.ITEM_HEALTH_DIRNAME,
                ledger.VISUAL_PRUNES_DIRNAME: ledger.VISUAL_PRUNES_DIRNAME,
                score_writer.INDEX_DIRNAME: score_writer.INDEX_DIRNAME,
                score_writer.LEDGER_DIRNAME: score_writer.LEDGER_DIRNAME,
                f"{ledger.COUNCIL_DIRNAME}-{ledger.SHARD_OUTCOMES_DIRNAME}": (
                    f"{ledger.COUNCIL_DIRNAME}/{ledger.SHARD_OUTCOMES_DIRNAME}"
                ),
                (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}-"
                    f"{ledger.JUDGE_METRICS_DIRNAME}"
                ): (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}/"
                    f"{ledger.JUDGE_METRICS_DIRNAME}"
                ),
                (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}-"
                    f"{ledger.MERGE_LINE_HOLDOUT_SCORES_DIRNAME}"
                ): (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}/"
                    f"{ledger.MERGE_LINE_HOLDOUT_SCORES_DIRNAME}"
                ),
                f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}-{ledger.SCORED_PAIRS_DIRNAME}": (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}/{ledger.SCORED_PAIRS_DIRNAME}"
                ),
                (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}-"
                    f"{ledger.FITTED_THRESHOLDS_DIRNAME}"
                ): (
                    f"{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}/"
                    f"{ledger.FITTED_THRESHOLDS_DIRNAME}"
                ),
            }.items()
        )
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
    resume_from: str | None = None

    @property
    def changed(self) -> bool:
        return bool(self.removed) and not self.dry_run

    @property
    def more_to_do(self) -> bool:
        """Whether a ceiling stopped this pass with days still inside the range."""
        return self.resume_from is not None


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
        "--max-deletes",
        type=int,
        default=None,
        metavar="COUNT",
        help=(
            "How many day files this pass may delete before it stops and says which "
            "day the next one resumes at. Defaults to every day the range names, so "
            "the range an operator typed is its own ceiling."
        ),
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
    """The store this target names, as a path under `state/`, or a refusal that says why.

    One place the vocabulary is checked, so the parser, the body and any later
    caller cannot disagree about which words are stores. The distinction between
    an unknown word and a refused one is drawn by `one_at_a_time.refuse_by_name`,
    which the GitHub collections use as well - two vocabularies, one rule about
    what a refusal owes the person reading it.

    What comes back is the path rather than the word, because a nested store's
    two are not the same string. Every caller wants the path.
    """
    return TARGETS[
        one_at_a_time.refuse_by_name(
            target, allowed=tuple(TARGETS), refused=REFUSED, noun="store"
        )
    ]


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


def _delete(day: Path) -> None:
    """Remove one day file, and the month and year directory it may have emptied.

    The one place a file goes, so a test has one place to fail a delete from and
    the core above has one call to make. `unlink` is the whole of it: a file is
    either there or it is not, which is what makes a pass resumable without a
    rollback.
    """
    day.unlink()
    day_partition.drop_empty_day_dirs(day)


def _relpath(state_root: Path, day: Path) -> str:
    """`state/<store>/<YYYY>/<MM>/<DD>.csv`, read off the path the walk found.

    Derived rather than spelled, so this does not become a second description of
    where a day file lives. The prefix is the committed tree's own name whatever
    root a caller handed in, which is what makes the list a person reads the
    same whether it came from the repository or from a test's own tree - the
    same form `ledger.seen_relpath` and its siblings return.
    """
    return f"{ledger.STATE_DIRNAME}/{day.relative_to(state_root).as_posix()}"


def day_collection(state_root: Path, store: str) -> one_at_a_time.Collection[Path]:
    """One store's day tree, as the three callables the core deletes through.

    The listing is `day_shards.shard_files`, which is a generator, so a store
    of any size is walked one path at a time and never held. It also refuses a
    name it cannot place, which means a store holding something this walk cannot
    read stops the pass at that file rather than deleting round it. It reads a
    `<DD>.csv` day file and a `<DD>/` day directory of writer-owned files alike,
    so a store that changes shape needs nothing here.

    Unbounded because the range an operator typed is the cover: the walk finds
    what the range names, and a window over it would hide the older half of the
    range the operator asked for (Guardrail #12).
    """

    def describe(day: Path) -> one_at_a_time.Member:
        return one_at_a_time.Member(
            id=_relpath(state_root, day),
            day=day_shards.date_of(day),
            size_bytes=day.stat().st_size,
            label=day.name,
        )

    return one_at_a_time.Collection(
        name=store,
        listing=lambda: day_shards.shard_files(state_root / store, days=UNBOUNDED_WINDOW),
        describe=describe,
        delete=_delete,
    )


def prune_range(
    state_root: Path,
    *,
    target: str,
    since: str,
    until: str,
    dry_run: bool = True,
    max_deletes: int | None = None,
) -> Outcome:
    """Remove one store's day files between two days, both ends named, one at a time.

    `max_deletes` defaults to every day the range names, so an operator who
    typed a range gets that range and a caller who wants a smaller bite asks for
    one. That default is a real bound rather than a number somebody picked: a
    range of `n` days cannot delete more than `n` files, so the ceiling is the
    operator's own arithmetic.
    """
    store = resolve(target)
    first = _day(since, "--since")
    last = _day(until, "--until")
    if first > last:
        raise ValueError(
            f"--since {first} is after --until {last}, so the range names no day. "
            "Both ends are named, so the oldest day comes first"
        )

    days_named = (date_type.fromisoformat(last) - date_type.fromisoformat(first)).days + 1
    outcome = one_at_a_time.take(
        day_collection(state_root, store),
        window=one_at_a_time.Window(since=first, until=last),
        ceiling=days_named if max_deletes is None else max_deletes,
        dry_run=dry_run,
    )
    return as_outcome(store, first, last, outcome)


def as_outcome(store: str, first: str, last: str, taken: one_at_a_time.Pass) -> Outcome:
    """The core's record in the words this command has always used.

    `kept` is the day files the walk saw and the range did not hold. A pass that
    stopped on its ceiling stopped walking too, so the number is what this pass
    read rather than what the store holds - which is the honest reading, and the
    reason the resume point is printed beside it.
    """
    return Outcome(
        target=store,
        since=first,
        until=last,
        removed=taken.taken,
        kept=taken.seen - taken.selected,
        bytes_freed=taken.bytes_freed,
        dry_run=taken.dry_run,
        resume_from=taken.resume_from,
    )


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
    if outcome.more_to_do:
        lines.append(
            f"  the ceiling stopped this pass at {outcome.resume_from} - there is more "
            "in the range, so run it again"
        )
    if outcome.dry_run:
        lines.append("  nothing was removed - pass --no-dry-run to delete these")
    return lines
