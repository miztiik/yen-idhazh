"""Which ledger does an operator delete from, and over which days?

The other half of `docs/architecture/publishing/retention.md`. The scheduled
prune deletes what a window has aged out; this deletes what a person names -
one ledger, one range of days, because that day was published in error, or a
source asked to be removed, or a run wrote rows nobody wants kept.

    idhazh telemetry prune --target feed-health --since 2026-08-24 --until 2026-08-26

**It reports and removes nothing until it is told twice.** `--dry-run` is on by
default and `--no-dry-run` is the second word. The reason is the history job of
`.github/workflows/idhazh-gardener.yml`: it squashes and force-pushes `main` on a
schedule, so a state file deleted here stops being recoverable from history once
that squash passes over the range (CLAUDE.md section 8). `git revert` is not a
recovery path for a file older than the squash's window in
`config/gardener/corpus-squash.json`. The precedent is the gardener's
retention tasks, each of which ships with `dry_run: true` in its own
declaration for exactly that reason.

**`--target` names a ledger, never a path.** The vocabulary below is closed, and
a word outside it is refused with the whole list rather than resolved against
the file system. A path argument would be a deletion primitive pointed at the
repository, and fetched text may never become a file path (Guardrail #11) - so
there is no argument here a path could travel through.

**Every target is a ledger the door files.** A ledger the registry files as
`raw-and-compact`, through the ledger door under `state/raw/` and
`state/compact/`, keeps a day's rows in the raw files its writers left or in a
daily, monthly or yearly file that holds other days as well, so `door_prune`
takes the day out of each of those. Whether this may take any day of such a
ledger is its compaction declaration's `prune_refusal`, beside the windows a
person reads in `config/gardener/compact-<folder>.json`, where `<folder>` is
the door folder with `/` written `-`: null lets it, and a sentence refuses the
ledger with that sentence. A live pass rewrites files, and each names the run
and the commit that wrote it, so `--no-dry-run` needs `--run-id` and
`--commit`.

**Both ends of the range are named.** `--since 2026-08-24 --until 2026-08-26` is
three days, and `--since X --until X` is one. That is the arithmetic
`day_partition.days_in_window` already uses, where a cover of `n` days returns
`n + 1` dates, and the two agree on purpose.

**One file at a time.** `door_prune` deletes each raw file with one `unlink` and
writes each rebuilt file whole, so a pass interrupted part way leaves every file
either as it was or as the pass left it, and the same command finishes it.

Until 2026-09-17 this collected the whole range, renamed every file into a
scratch directory beside the ledgers, and removed that directory once every
rename had worked - all of them or none of them, with a rollback if a rename
failed. The scratch directory is gone with it. What that shape bought was "the
tree is exactly as you found it" after a failure; what it cost was a second
write path that could itself fail while undoing, and a range that had to be
collected before the first file could move. An operator who now has to re-run a
pass reads which files went from the record, which is a cheaper answer than a
rollback nobody could test in production.

**Bounded by the range it is handed, and by a ceiling inside it** (Guardrail
#12). A pass takes at most the days the range names, or the `--max-deletes` an
operator asked for. When a ceiling stops a pass, the report says which day the
next pass resumes at.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as date_type
from pathlib import Path
from types import MappingProxyType
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN, ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy, TaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.gardener import one_at_a_time
from idhazh.telemetry import door_prune

#: The core's own interruption, named here so a caller of this module imports
#: one thing. A pass that failed part way - a delete, a write, or the walk
#: itself - raises it, and the record it carries says which files had already
#: changed.
PruneInterruptedError = one_at_a_time.PruneInterruptedError

#: Every ledger the registry files as `raw-and-compact`, by the word an operator
#: types, alphabetically. Read off `config/ledgers.json` rather than listed, so a
#: ledger the door files is a target in the commit that onboards it, with nothing
#: here to edit. Whether this may take its days is its compaction declaration's
#: to say, in `door_refusals`.
#:
#: The word is built from the ledger's registry prefix, never spelled again
#: here - so a ledger that moves moves its target with it, and neither can drift
#: from the other (Guardrail #6). A ledger that is its own family's word IS its
#: folder. A NESTED ledger's word joins its folders with a hyphen, because a
#: slash in a word turns a closed vocabulary into something that looks like a
#: path - and a deletion primitive that resolved its argument against the file
#: system is the one accident nobody can undo.
DOOR_LEDGERS: Final[Mapping[str, LedgerName]] = MappingProxyType(
    dict(
        sorted(
            ("-".join(ledger.entry(name).prefix), name)
            for name in LedgerName
            if ledger.entry(name).grain is Grain.RAW_AND_COMPACT
        )
    )
)


def door_refusals(tasks: Mapping[str, TaskPolicy]) -> dict[str, str]:
    """Each ledger on the door this refuses, by word, with the sentence that says why.

    A ledger's compaction declaration says it in `prune_refusal`, beside the
    windows that bound the same rows. A ledger on the door that no compaction
    declares is refused too: nothing then says whether its days may go, and a
    delete is the one answer that cannot be taken back.
    """
    refused: dict[str, str] = {}
    for word, name in DOOR_LEDGERS.items():
        policy = tasks.get(config.compaction_task(name))
        if not isinstance(policy, CompactionPolicy) or policy.ledger is not name:
            policy = None
        if policy is None:
            refused[word] = (
                "no compaction under config/gardener/ declares it, so nothing says whether "
                "a range of its days may be taken out"
            )
        elif policy.prune_refusal is not None:
            refused[word] = policy.prune_refusal
    return refused


#: What a file rebuilt on the door names as the module that wrote it.
PRODUCER: Final = __name__.partition(".")[2]

#: The run number and the commit a dry run builds its files under when it is not
#: told them. No file a dry run builds is written; the commit is the same stand-in
#: every pipeline verb takes when it is not told one.
_DRY_RUN_NUMBER: Final = 0
_DRY_RUN_COMMIT: Final = "0" * 40


def identify_writer(run_id: str | None, commit: str | None, *, dry_run: bool) -> WriterIdentity:
    """Who a file rebuilt on the door says wrote it, or a refusal before any file is read.

    A live pass needs both: a rebuilt file is committed, and its envelope is how
    a later reader traces it to the run and the code that wrote it. The job is
    `migrate`, the one that files rows again rather than recording new ones. A
    dry run writes nothing, so it builds under what it is told and a stand-in
    for what it is not, and its byte counts then differ from a live pass's by the
    few bytes the two identities differ by.
    """
    if not dry_run and (run_id is None or commit is None):
        raise ValueError(
            "--no-dry-run on a ledger on the door rewrites the files that hold the days, and "
            "each rewritten file names the run and the commit that wrote it: pass --run-id "
            "YYYY-MM-DD-N and --commit with the full sha the checkout is at"
        )
    today = datetime.now(UTC).date().isoformat()
    run = run_id if run_id is not None else f"{today}-{_DRY_RUN_NUMBER}"
    sha = commit if commit is not None else _DRY_RUN_COMMIT
    if not re.fullmatch(RUN_ID_PATTERN, run):
        raise ValueError(f"--run-id takes YYYY-MM-DD-N, not {run!r}")
    if not re.fullmatch(COMMIT_SHA_PATTERN, sha):
        raise ValueError(f"--commit takes the full forty-character sha, not {sha!r}")
    return WriterIdentity(
        run_id=run,
        attempt=1,
        job=ServerJob.MIGRATE,
        shard=0,
        producer=PRODUCER,
        git_sha=sha,
    )


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one prune selected, what it weighed, and whether it happened.

    `removed` is every file deleted, as the POSIX `state/...` form, and
    `rewritten` every file written again in place. Both are the same lists on
    both sides of `dry_run` - named before anything changes, so the list a dry
    run prints is the list a live run carries out, file for file. That list is
    the deliverable of a dry run, which is why a count would not do. `kept`
    counts the days the ledger holds outside the range.
    """

    target: str
    since: str
    until: str
    removed: tuple[str, ...]
    rewritten: tuple[str, ...]
    kept: int
    bytes_freed: int
    dry_run: bool
    resume_from: str | None = None

    @property
    def changed(self) -> bool:
        return bool(self.removed or self.rewritten) and not self.dry_run

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

    The ledgers on the door are named from the registry, and which of them a
    pass may take days from is read from their declarations when it runs, so the
    help names them all and says what decides.
    """
    parser.add_argument(
        "--target",
        required=True,
        metavar="LEDGER",
        help=(
            "Which ledger to delete from. One of "
            + ", ".join(DOOR_LEDGERS)
            + ", unless its compaction declaration under config/gardener/ sets a "
            "prune_refusal. Never a path."
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
            "How many days this pass may take before it stops and says which day the "
            "next one resumes at, taking every file that holds each day. Defaults to "
            "every day the range names, so the range an operator typed is its own "
            "ceiling."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Report what a live run would remove and remove nothing. On by "
            "default, because the gardener's history job force-pushes main and a "
            "file deleted here stops being recoverable once that squash passes over "
            "it. Pass --no-dry-run to delete."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        metavar="YYYY-MM-DD-N",
        help=(
            "The run each file rebuilt on a ledger on the door names as its writer. "
            "Required, with --commit, beside --no-dry-run on such a ledger; a dry run "
            "needs neither, and builds exactly what the live pass would when given both."
        ),
    )
    parser.add_argument(
        "--commit",
        default=None,
        metavar="SHA",
        help="The full sha the checkout is at, which a rebuilt file names beside --run-id.",
    )


def resolve(target: str, tasks: Mapping[str, TaskPolicy]) -> str:
    """The word of the ledger this target names, or a refusal that says why.

    One place the vocabulary is checked, so the parser, the body and any later
    caller cannot disagree about which words are ledgers. The distinction between
    an unknown word and a refused one is drawn by `one_at_a_time.refuse_by_name`,
    which the GitHub collections use as well - two vocabularies, one rule about
    what a refusal owes the person reading it.

    `tasks` is every gardener declaration, which is where a ledger on the door
    says whether its days may go. The word comes back rather than a path: a
    ledger on the door has two folders rather than one.
    """
    refused = door_refusals(tasks)
    allowed = sorted(word for word in DOOR_LEDGERS if word not in refused)
    return one_at_a_time.refuse_by_name(target, allowed=allowed, refused=refused, noun="ledger")


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


def prune_range(
    state_root: Path,
    *,
    target: str,
    since: str,
    until: str,
    tasks: Mapping[str, TaskPolicy],
    dry_run: bool = True,
    max_deletes: int | None = None,
    run_id: str | None = None,
    commit: str | None = None,
) -> Outcome:
    """Take one ledger's days between two days, both ends named, and say what changed.

    `tasks` is every gardener declaration, which says whether a ledger on the
    door may give up its days. The days go through `door_prune`, and every file
    it rebuilds names the writer `run_id` and `commit` give, so a live pass
    without them is refused before any file is read.

    `max_deletes` defaults to every day the range names, so an operator who
    typed a range gets that range and a caller who wants a smaller bite asks for
    one. That default is a real bound rather than a number somebody picked: a
    range of `n` days cannot take more than `n` days, so the ceiling is the
    operator's own arithmetic.
    """
    word = resolve(target, tasks)
    first = _day(since, "--since")
    last = _day(until, "--until")
    if first > last:
        raise ValueError(
            f"--since {first} is after --until {last}, so the range names no day. "
            "Both ends are named, so the oldest day comes first"
        )

    days_named = (date_type.fromisoformat(last) - date_type.fromisoformat(first)).days + 1
    ceiling = days_named if max_deletes is None else max_deletes
    taken = door_prune.take_days(
        state_root,
        DOOR_LEDGERS[word],
        since=first,
        until=last,
        ceiling=ceiling,
        dry_run=dry_run,
        identity=identify_writer(run_id, commit, dry_run=dry_run),
    )
    return as_outcome(word, first, last, taken)


def as_outcome(ledger: str, first: str, last: str, taken: one_at_a_time.Pass) -> Outcome:
    """The core's record in the words this command has always used.

    `kept` is the days the pass saw that the range did not hold.
    """
    return Outcome(
        target=ledger,
        since=first,
        until=last,
        removed=taken.taken,
        rewritten=taken.written,
        kept=taken.seen - taken.selected,
        bytes_freed=taken.bytes_freed,
        dry_run=taken.dry_run,
        resume_from=taken.resume_from,
    )


def report(outcome: Outcome) -> list[str]:
    """What happened, as the lines the command prints, one file per line.

    A count says a deletion happened and nothing about what it took. This list
    is what a person reads before passing `--no-dry-run`, so it is the paths
    themselves - the same rule the gardener holds its scheduled tasks to: a pass
    hands back every file it took, by name. A pass also rewrites files, so each
    line says which verb its path takes.
    """
    span = f"{outcome.since} to {outcome.until}"
    if not outcome.removed and not outcome.rewritten:
        return [
            f"{span}: {outcome.target} holds no row in that range, so nothing was removed "
            f"or rewritten - it holds {outcome.kept} days outside it"
        ]
    removes, rewrites = (
        ("would remove", "would rewrite") if outcome.dry_run else ("removed", "rewrote")
    )
    lines = [
        f"{span}: {outcome.target} {removes} {len(outcome.removed)} files and {rewrites} "
        f"{len(outcome.rewritten)}, freeing {outcome.bytes_freed} bytes, keeping "
        f"{outcome.kept} days outside the range"
    ]
    lines += [f"  remove {relpath}" for relpath in outcome.removed]
    lines += [f"  rewrite {relpath}" for relpath in outcome.rewritten]
    lines += _resume_line(outcome)
    if outcome.dry_run:
        lines.append(
            "  nothing was changed - pass --no-dry-run, with --run-id and --commit, "
            "to make these changes"
        )
    return lines


def _resume_line(outcome: Outcome) -> list[str]:
    """The line that says a ceiling left days in the range, or none."""
    if not outcome.more_to_do:
        return []
    return [
        f"  the ceiling stopped this pass at {outcome.resume_from} - there is more "
        "in the range, so run it again"
    ]
