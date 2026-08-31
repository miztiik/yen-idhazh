"""How many days we mention a registry name on, and how long we go quiet about it.

Read-only, offline, and not a stage. It answers one question a half-life is a
judgement about: **how many days of silence does a subject in our own registry
actually get?** A half-life shorter than a subject's own observed gap has
already expired by the time the next instalment arrives, so it does nothing.

The number is also the baseline any later entity recogniser is scored against.
A model that finds more names but splits one subject across three - "the export
controls", "chip export curbs", "the export ban" - raises coverage and makes
continuity worse. Coverage alone would call that a win, so this tool reports the
gap beside the day count and neither figure is quoted without the other.

**One matcher, two haystacks, and the difference is stated rather than hidden.**
The vocabulary is `Watchlist.entity_terms()` and the matcher is `tag.tags` - the
same function and the same terms the pipeline tags an item with. Two haystacks,
because the committed record disagrees with itself:

- **As published** reads the `entities` list a run wrote onto its own item, over
  the article's title and its whole body. It is the pipeline's own answer and
  the exact input a heat ledger would read. It is also empty on every day
  published before the field went live, and a zero there is an instrument that
  was switched off, not a subject nobody mentioned.
- **Re-matched** runs the same matcher over the words a reader is served - the
  title, the summary and the key points. It covers the whole record, and it
  reads far less text than the pipeline did, so it is a floor: it can miss a
  name the body carried and the summary dropped. It never invents one, because
  the vocabulary is closed.

Where both arms are live they are reported against each other, so the price of
the smaller haystack is a measured number rather than a claim.

**Nothing here is a rate this repository can set.** A median gap of 1 day means
we mention the name on consecutive days - zero days of silence - and a half-life
has nothing to bite on. The longest gap the record can express is the span of
the record itself, so a rate longer than that is unsupported by it whatever the
table says.

The report carries no clock and no host, so the same tree always prints the same
bytes and a re-run is a check rather than a new reading. Rule #10's hardware and
date belong beside the figure in `docs/reference/measurements.md`, where a reader
looks the number up.

Usage, from the root of a checkout:

    python backend/utilities/entity_gap.py

Exit code 1 when no committed day is there to read, so a shell can tell "nothing
to read" from "read it, here are the numbers".
"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Final

from idhazh import config, tag
from idhazh.config import REPO_ROOT
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.watchlist import EntityKind, Watchlist

#: Where the pipeline commits a published day. Relative and POSIX, per CLAUDE.md
#: section 2.
DIGEST_RELDIR: Final = "frontend/public/digest"

#: A term the matcher is handed. `Watchlist.entity_terms()` returns this shape.
Vocabulary = Mapping[str, Sequence[str]]

#: What one item was seen to mention. Two arms supply this, and the report says
#: which one every figure came from.
Seen = Callable[[DigestItem], Iterable[str]]


def day_paths(root: Path) -> list[Path]:
    """Every committed day payload, oldest first."""
    return sorted((root / DIGEST_RELDIR).glob("*/*/*/digest.json"))


def read_days(root: Path) -> list[DigestDay]:
    return [DigestDay.from_json(path.read_text(encoding="utf-8")) for path in day_paths(root)]


def as_published(item: DigestItem) -> Iterable[str]:
    """The entity ids the run itself wrote onto this item."""
    return item.entities


def rematched(vocabulary: Vocabulary) -> Seen:
    """The pipeline's matcher over the words a reader is served.

    The title, the summary and the key points - never the article body, which no
    published payload carries. Fewer words than the pipeline read, so this arm
    can only under-count.
    """

    def seen(item: DigestItem) -> Iterable[str]:
        return tag.tags(vocabulary, item.title, item.summary, *item.key_points)

    return seen


@dataclass(frozen=True, slots=True)
class Appearances:
    """The published days one registry entry was mentioned on, oldest first."""

    entity_id: str
    days: tuple[date, ...]

    @property
    def gaps(self) -> tuple[int, ...]:
        """Days between consecutive mentions. `1` is back to back - no silence at all.

        `n` mentions give `n - 1` gaps, so an entry mentioned once has none and
        an entry never mentioned has none for a different reason. Both are
        counted separately in the report rather than folded into an average.
        """
        return tuple((later - earlier).days for earlier, later in pairwise(self.days))

    @property
    def median_gap_days(self) -> float | None:
        """None when the entry has fewer than two mentions, because then there is no gap."""
        gaps = self.gaps
        return statistics.median(gaps) if gaps else None

    @property
    def longest_gap_days(self) -> int | None:
        gaps = self.gaps
        return max(gaps) if gaps else None


@dataclass(frozen=True, slots=True)
class DayCoverage:
    """How much of one published day the registry sees at all."""

    day: date
    items: int
    items_with_an_entity: int


def appearances(
    days: Sequence[DigestDay], entity_ids: Sequence[str], seen: Seen
) -> list[Appearances]:
    """One row per registry entry, in id order, whether or not it was ever mentioned."""
    stamps: dict[str, list[date]] = {entity_id: [] for entity_id in sorted(entity_ids)}
    for day in days:
        on_this_day = {slug for item in day.items for slug in seen(item)}
        published_on = date.fromisoformat(day.date)
        for entity_id, seen_on in stamps.items():
            if entity_id in on_this_day:
                seen_on.append(published_on)
    return [Appearances(entity_id=entity_id, days=tuple(on)) for entity_id, on in stamps.items()]


def coverage(days: Sequence[DigestDay], seen: Seen) -> list[DayCoverage]:
    """Items carrying at least one registry name, per day.

    This is the bound on everything else here. A subject the registry does not
    name cannot appear in any gap above, and no tool in this repository can find
    one, so the honest statement is how much of the record the registry sees.
    """
    return [
        DayCoverage(
            day=date.fromisoformat(day.date),
            items=len(day.items),
            items_with_an_entity=sum(1 for item in day.items if any(seen(item))),
        )
        for day in days
    ]


def unregistered_ids(days: Sequence[DigestDay], entity_ids: Sequence[str]) -> list[str]:
    """Any id a committed item carries that the registry no longer names.

    "For every name in the registry" is only a complete count while the record
    holds no name outside it. A published id with no entry is a vocabulary that
    has drifted from the payloads it wrote.
    """
    known = set(entity_ids)
    return sorted({slug for day in days for item in day.items for slug in item.entities} - known)


def live_days(days: Sequence[DigestDay], seen: Seen) -> list[date]:
    """The published days on which this arm sees anything at all."""
    return [
        date.fromisoformat(day.date)
        for day in days
        if any(slug for item in day.items for slug in seen(item))
    ]


def agreement(days: Sequence[DigestDay], vocabulary: Vocabulary) -> tuple[int, int, int]:
    """Item-entity pairs both arms found, only the run found, and only the re-match found.

    Taken over the days the published field is live on, because a day where it
    is empty says nothing about either arm.
    """
    matcher = rematched(vocabulary)
    both = run_only = rematch_only = 0
    for day in days:
        if not any(item.entities for item in day.items):
            continue
        for item in day.items:
            written = set(item.entities)
            found = set(matcher(item))
            both += len(written & found)
            run_only += len(written - found)
            rematch_only += len(found - written)
    return both, run_only, rematch_only


def _share(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f} percent" if whole else "no denominator"


def _gap_cells(row: Appearances) -> tuple[str, str, str]:
    median = row.median_gap_days
    longest = row.longest_gap_days
    return (
        str(len(row.days)),
        "-" if median is None else f"{median:.1f}",
        "-" if longest is None else str(longest),
    )


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    widths = [max(len(str(cell)) for cell in column) for column in zip(header, *rows, strict=True)]
    ruled = [header, ["-" * width for width in widths], *rows]
    return ["  ".join(cell.ljust(width) for cell, width in zip(line, widths, strict=True)).rstrip()
            for line in ruled]


def _record_lines(days: Sequence[DigestDay], watchlist: Watchlist) -> list[str]:
    stamps = [date.fromisoformat(day.date) for day in days]
    span = (stamps[-1] - stamps[0]).days
    holes = span + 1 - len(stamps)
    kinds = Counter(entity.kind for entity in watchlist.entities)
    orphans = unregistered_ids(days, [entity.id for entity in watchlist.entities])
    return [
        "The record this was taken over",
        f"  published days      {len(days)}, {stamps[0]} to {stamps[-1]}",
        f"  missing days        {holes} calendar days in that range published nothing",
        f"  items               {sum(len(day.items) for day in days)}",
        f"  registry entries    {len(watchlist.entities)}"
        f" ({kinds[EntityKind.ORGANISATION]} organisation,"
        f" {kinds[EntityKind.SUBJECT]} subject)",
        f"  matchable entries   {len(watchlist.entity_terms())} - a retired entry stops matching",
        f"  published ids the registry does not name: {', '.join(orphans) or 'none'}",
        f"  the longest gap this record can express is {span} days,"
        " so no rate above that is supported by it",
    ]


def _arm_lines(days: Sequence[DigestDay], rows: Sequence[Appearances], live: Sequence[date]) -> str:
    if not live:
        return f"  live on 0 of {len(days)} published days - this arm has nothing to report"
    with_a_gap = [row for row in rows if row.gaps]
    return (
        f"  live on {len(live)} of {len(days)} published days, {live[0]} to {live[-1]};"
        f" {len(with_a_gap)} of {len(rows)} entries were mentioned twice or more"
        " and so have a gap at all"
    )


def report(root: Path, watchlist: Watchlist) -> str:
    """The whole measurement as text. A pure function of the tree, so a re-run is a check."""
    days = read_days(root)
    if not days:
        raise ValueError(f"no committed days under {DIGEST_RELDIR}")
    vocabulary = watchlist.entity_terms()
    entity_ids = [entity.id for entity in watchlist.entities]
    matcher = rematched(vocabulary)

    published_rows = appearances(days, entity_ids, as_published)
    rematched_rows = appearances(days, entity_ids, matcher)

    lines = [*_record_lines(days, watchlist), ""]
    lines += [
        "As published - the entities list each run wrote onto its own item",
        _arm_lines(days, published_rows, live_days(days, as_published)),
        "",
        "Re-matched - the same matcher over the title, summary and key points",
        _arm_lines(days, rematched_rows, live_days(days, matcher)),
        "",
        "Per entry. A gap of 1 day means consecutive days - we went quiet for none of it.",
    ]
    table_rows = [
        [row.entity_id, *_gap_cells(row), *_gap_cells(other)]
        for row, other in zip(published_rows, rematched_rows, strict=True)
    ]
    lines += _table(
        ["entity", "pub days", "pub median", "pub longest", "re days", "re median", "re longest"],
        table_rows,
    )

    published_gaps = Counter(gap for row in published_rows for gap in row.gaps)
    rematched_gaps = Counter(gap for row in rematched_rows for gap in row.gaps)
    published_total = sum(published_gaps.values())
    rematched_total = sum(rematched_gaps.values())
    lines += [
        "",
        f"Every gap pooled - {published_total} as published, {rematched_total} re-matched",
    ]
    lines += _table(
        ["gap in days", "days of silence", "pub count", "pub share", "re count", "re share"],
        [
            [
                str(gap),
                str(gap - 1),
                str(published_gaps[gap]),
                _share(published_gaps[gap], published_total),
                str(rematched_gaps[gap]),
                _share(rematched_gaps[gap], rematched_total),
            ]
            for gap in sorted(set(published_gaps) | set(rematched_gaps))
        ],
    )

    covered = coverage(days, matcher)
    seen_items = sum(row.items_with_an_entity for row in covered)
    all_items = sum(row.items for row in covered)
    lines += [
        "",
        "How much of the record the registry sees. Everything above is bounded by this:",
        f"  {seen_items} of {all_items} items carry a registry name -"
        f" {_share(seen_items, all_items)}."
        " A subject in the rest cannot appear in any gap above,",
        "  and nothing here can find one.",
    ]
    lines += _table(
        ["day", "items", "with a registry name", "share"],
        [
            [
                str(row.day),
                str(row.items),
                str(row.items_with_an_entity),
                _share(row.items_with_an_entity, row.items),
            ]
            for row in covered
        ],
    )

    both, run_only, rematch_only = agreement(days, vocabulary)
    lines += [
        "",
        "What the smaller haystack costs, over the days the published field is live on",
        f"  both arms      {both} item-entity pairs",
        f"  run only       {run_only} - the body carried the name and the summary dropped it"
        f" ({_share(run_only, both + run_only)} of what the run wrote)",
        f"  re-match only  {rematch_only} - published without the name the summary carries",
        "  A dropped mention lengthens a gap, so the re-matched column above is the longer",
        "  of the two readings, not the shorter one.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to read.")
    args = parser.parse_args()
    root: Path = args.root
    if not day_paths(root):
        parser.error(f"no committed days under {DIGEST_RELDIR}")
    print(report(root, config.load(root / "config").watchlist))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
