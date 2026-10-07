"""What one shard did, as Markdown for the job's summary page.

GitHub shows each job's summary on its run's page, under the job's own name, so
a person reads a shard there at a glance instead of in its log. The summary is
rendered from the shard's own events and nothing else - `ShardPublished`, the
publisher's last word on the shard, and the `TaskFinished` of each task that
ran, in the order the tasks ran - so it cannot say anything the log does not.

Top to bottom:

- one heading, the lede: what the exit code means, which tasks a code defect
  stopped and which were deferred, then the exit code;
- where the record went, or why nothing landed;
- what the tasks downloaded against their budget, when something measured it;
- one row a task: how it ended and what it did;
- what each word in that table means and what happens next, once a word;
- what the tasks handled without stopping, one line a task and note.

**It holds no text the gardener read** (Guardrail #11): closed words, counts,
periods, member ids, paths the gardener named, an exception's type and its code
place, and the fixed sentences the events carry. Every sentence is escaped for
Markdown, so `<task>` in one shows as written. A name a person types - a task,
a path, a setting, an exception's type, a place in the code - is code; a word
being defined is italic; and only `failed` is bold.

A compaction's old months and raw days are said as found past the keep line,
because its record lists them whether its monthly window deleted them or only
reported them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from idhazh.contracts.gardener_events import (
    FoldSettled,
    PeriodsTaken,
    ShardPublished,
    ShardStop,
    TaskFinished,
    TaskOutcome,
)
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import PrunableCollection
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import report
from idhazh.site_weight import BYTES_PER_MB

#: What one member of what a task takes is called: a file, unless the task takes
#: from one of GitHub's collections.
_NOUNS: Final[Mapping[PrunableCollection | None, str]] = {
    None: "file",
    PrunableCollection.WORKFLOW_RUNS: "run",
    PrunableCollection.WORKFLOW_ARTIFACTS: "artifact",
}

#: Each character Markdown would read as markup, and what shows it as written.
_MARKDOWN: Final = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\\": "\\\\",
        "`": "\\`",
        "*": "\\*",
        "_": "\\_",
        "[": "\\[",
        "]": "\\]",
        "|": "\\|",
    }
)

#: The bytes in a kilobyte, the unit below `BYTES_PER_MB`.
_BYTES_PER_KB: Final = 1024


def markdown(published: ShardPublished, finished: Sequence[TaskFinished]) -> str:
    """The whole summary of one shard, as Markdown ending in a line break."""
    blocks = [
        _lede(published, finished),
        _where_it_went(published, finished),
        *_downloads(published),
        *_table(finished),
        *_words(finished),
        *_handled(finished),
    ]
    return "\n\n".join(blocks) + "\n"


def _lede(published: ShardPublished, finished: Sequence[TaskFinished]) -> str:
    """The one heading: what the exit code means, who a code defect or a deferral names."""
    said = _escaped(published.means[:1].upper() + published.means[1:])
    if published.failed_tasks:
        said += f"; a code defect stopped {_names(published.failed_tasks)}"
    deferred = [each.task for each in finished if each.outcome is TaskOutcome.DEFERRED]
    if deferred:
        said += f"; deferred: {_names(deferred)}"
    return f"### {said} (exit {published.exit_code})"


def _where_it_went(published: ShardPublished, finished: Sequence[TaskFinished]) -> str:
    """Where the record went, or why nothing landed, in one paragraph."""
    record = "" if published.record is None else _code(published.record)
    tries = published.push_tries
    match published.landing:
        case ShardLanding.LANDED:
            return (
                f"The shard's changes and its record landed on main on try "
                f"{published.push_try} of up to {tries}: {record}."
            )
        case ShardLanding.ALREADY_ON_MAIN:
            return (
                "A previous try in this job had already landed the shard's changes and its "
                f"record: {record}."
            )
        case ShardLanding.STALE:
            first, *rest = published.stale_paths
            more = f" and {len(rest)} more of the shard's files" if rest else ""
            return (
                f"Nothing landed, not even the record (stale): main changed {_code(first)}"
                f"{more} after the commit the shard ran on. The next wake does the work again."
            )
        case ShardLanding.LOST:
            return (
                f"Nothing landed (lost): all {tries} tries failed, and main changed during the "
                "last one, so other writers were landing first. The next wake does the work "
                "again."
            )
        case ShardLanding.REFUSED:
            return (
                f"Nothing landed (refused): main did not change during try {published.push_try} "
                f"of {tries}, so no other writer beat that push, and main refused it. The next "
                "wake tries again."
            )
    return _why_nothing_landed(published, finished, record)


def _why_nothing_landed(
    published: ShardPublished, finished: Sequence[TaskFinished], record: str
) -> str:
    """Why a shard that never came to rest on main stopped, from its own word."""
    match published.stopped_because:
        case ShardStop.LISTING_FAILED:
            return (
                "No task ran and nothing landed: the shard could not list the files its tasks "
                f"work on ({_thrown(published)}). The next wake tries again."
            )
        case ShardStop.CRASHED:
            return (
                f"The shard crashed on {_thrown(published)}. This summary cannot say what ran "
                "or what landed; the log holds the rest."
            )
    if record:
        return (
            f"The tasks ran, but nothing landed, not even the record ({record}). The log says "
            "which check refused it."
        )
    if finished:
        return (
            "The tasks ran, but the shard wrote no record and nothing landed. The log says "
            "which check refused it."
        )
    return (
        "The shard stopped before its first task, so no task ran and nothing landed. The log "
        "says why."
    )


def _downloads(published: ShardPublished) -> list[str]:
    """What the tasks downloaded against their budget, when something measured it."""
    if published.downloaded_bytes is None:
        return []
    downloaded = published.downloaded_bytes / BYTES_PER_MB
    budget = published.max_downloaded_mb
    if not published.over_budget:
        return [
            f"The tasks downloaded {downloaded:.1f} MB of their {budget} MB budget "
            "(`max_downloaded_mb`)."
        ]
    return [
        f"The tasks downloaded {downloaded:.1f} MB, {downloaded - budget:.1f} MB over the "
        f"shard's {budget} MB budget (`max_downloaded_mb`). A task did not fit its work to the "
        "budget: a code defect that repeats at every wake until a person fixes it. The log "
        "names the heaviest folders."
    ]


def _table(finished: Sequence[TaskFinished]) -> list[str]:
    """One row a task, in the order they ran: how it ended and what it did."""
    if not finished:
        return []
    rows = ["| Task | How it ended | What it did |", "| --- | --- | --- |"]
    rows += [f"| {_code(each.task)} | {_ended(each)} | {_did(each)} |" for each in finished]
    return ["\n".join(rows)]


def _ended(each: TaskFinished) -> str:
    """How a task ended: its word, bold when it failed, and the fault that stopped it."""
    word = f"**{each.outcome}**" if each.outcome is TaskOutcome.FAILED else str(each.outcome)
    return word if each.fault is None else f"{word} ({each.fault})"


def _did(each: TaskFinished) -> str:
    """What a task did, or would do on a dry run, and what stopped it."""
    actions = [*_work(each), *_folded(each.fold)]
    found = [] if each.periods is None else _found(each.periods)
    said = "; ".join(part for part in (", ".join(actions), ", ".join(found)) if part)
    stop = _stop(each)
    if not said:
        return "nothing" if stop is None else stop
    return said if stop is None else f"{said}, then {stop}"


def _work(each: TaskFinished) -> list[str]:
    """What the pass did, each part with its count, the first one after `would` on a dry run."""
    live = not each.dry_run
    if each.periods is not None:
        counted = _periods_work(each.periods)
    else:
        noun = _NOUNS[each.collection]
        counted = [
            ("delete", "deleted", len(each.taken), noun, f"{noun}s"),
            ("write", "wrote", len(each.written), "file", "files"),
        ]
    parts = [
        f"{past if live else base} {_count(count, one, many)}"
        for base, past, count, one, many in counted
        if count
    ]
    if each.periods is None and each.bytes_freed:
        parts.append(f"{'freed' if live else 'free'} {_size(each.bytes_freed)}")
    if parts and not live:
        parts[0] = f"would {parts[0]}"
    return parts


def _periods_work(periods: PeriodsTaken) -> list[tuple[str, str, int, str, str]]:
    """A compaction's work, period by period: each verb's two forms, its count and noun."""
    return [
        ("pack", "packed", len(periods.days_packed), "day", "days"),
        ("re-pack", "re-packed", len(periods.days_retaken), "day", "days"),
        ("close", "closed", len(periods.months_closed), "month", "months"),
        ("pack", "packed", len(periods.years_packed), "year", "years"),
        ("record", "recorded", len(periods.empty_periods), "empty period", "empty periods"),
        ("record", "recorded", len(periods.lost_days), "lost day", "lost days"),
        (
            "set aside",
            "set aside",
            len(periods.set_aside_paths),
            "unreadable file",
            "unreadable files",
        ),
    ]


def _found(periods: PeriodsTaken) -> list[str]:
    """The old months and raw days a compaction found past its keep line."""
    named = [
        _count(len(listed), one, many)
        for listed, one, many in (
            (periods.months_dropped, "old month", "old months"),
            (periods.raw_days_dropped, "old raw day", "old raw days"),
        )
        if listed
    ]
    return [f"found {' and '.join(named)} past the keep line"] if named else []


def _folded(fold: FoldSettled | None) -> list[str]:
    """What a retention task's fold merged, on its own switch."""
    if fold is None or not fold.settled:
        return []
    merged = "would merge" if fold.dry_run else "merged"
    days = _count(len(fold.settled), "finished day or month", "finished days or months")
    return [f"{merged} {days} into one file each, replacing {_count(fold.replaced, 'file')}"]


def _stop(each: TaskFinished) -> str | None:
    """What stopped a failed or deferred task, and what it worked on; None with nothing to say."""
    if each.outcome not in (TaskOutcome.FAILED, TaskOutcome.DEFERRED):
        return None
    said = ""
    if each.error is not None:
        place = "" if each.where is None else f" at {_code(each.where)}"
        said += f" by {_code(each.error)}{place}"
    if each.resume_from is not None:
        said += f" while it worked on {_escaped(each.resume_from)}"
    return f"stopped{said}" if said else None


def _words(finished: Sequence[TaskFinished]) -> list[str]:
    """Each word the table shows once, with what it means and what happens next.

    The word that chose a task's sentence is its fault when one stopped it, as
    `report.next_step` chooses, and its outcome otherwise.
    """
    meant: dict[str, str] = {}
    for each in finished:
        meant.setdefault(str(each.fault or each.outcome), each.next)
    if not meant:
        return []
    lines = [f"- *{word}*: {_escaped(sentence)}" for word, sentence in meant.items()]
    return ["What the words mean, and what happens next:", "\n".join(lines)]


def _handled(finished: Sequence[TaskFinished]) -> list[str]:
    """What each task handled without stopping: one line a task and note, the first it named."""
    lines: list[str] = []
    for each in finished:
        subjects: dict[RecoveryNote, list[str]] = {}
        for recovery in each.recovered:
            subjects.setdefault(recovery.note, []).append(recovery.subject)
        for note, named in subjects.items():
            first, *rest = named
            more = f" and {len(rest)} more" if rest else ""
            lines.append(
                f"- {_code(each.task)}, {_escaped(first)}{more}: "
                f"{_escaped(report.NOTED[note])} ({note})"
            )
    if not lines:
        return []
    return ["Handled without stopping:", "\n".join(lines)]


def _thrown(published: ShardPublished) -> str:
    """The exception that stopped the shard, by its type and, when known, its place.

    The event names the type whenever a listing failed or a crash stopped the shard.
    """
    place = "" if published.where is None else f" at {_code(published.where)}"
    return f"{_code(str(published.error))}{place}"


def _names(tasks: Sequence[str]) -> str:
    """Task names as code, separated by commas."""
    return ", ".join(_code(task) for task in tasks)


def _count(count: int, one: str, many: str | None = None) -> str:
    """A count beside its noun, the noun plural unless the count is one."""
    return f"{count} {one if count == 1 else many or f'{one}s'}"


def _size(size: int) -> str:
    """A size in bytes, KB or MB, each unit 1024 of the one below."""
    if size < _BYTES_PER_KB:
        return _count(size, "byte")
    if size < BYTES_PER_MB:
        return f"{size / _BYTES_PER_KB:.1f} KB"
    return f"{size / BYTES_PER_MB:.1f} MB"


def _code(text: str) -> str:
    """A name a person types, as code. Every such name's pattern holds no backtick."""
    return f"`{text}`"


def _escaped(text: str) -> str:
    """Text as Markdown shows it as written: each markup character escaped."""
    return text.translate(_MARKDOWN)
