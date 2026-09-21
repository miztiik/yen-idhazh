"""Choose the borderline pairs worth labelling, and lay them out so a labeller can read them.

Every other surface in the same-story feature is a number. A number says the
line sits at 0.94 and 580 pairs cleared it; it never says whether *this* pair was
one story. This builds the place to answer that, one pair at a time, with both
headlines and both summaries side by side.

It calls no model, opens no socket and decides nothing. Nothing in the pipeline
reads what it writes. The labels a reader produces from it are pasted back into
`state/content-similarity-judge/holdout-pairs.csv`, which the console's holdout panel
draws and which nothing else consumes.

**It samples across the line, not across the four judged cells.** The sheet the
plan first described sorted pairs by where the judge and the line disagreed,
which needs a verdict on every row. No day has been judged, so there are no
verdicts - producing the labels IS the job here. What the draw does give is a
score and a line, so the four bands below are where a pair sits relative to the
line rather than what any model said about it.

**Bands say ELIGIBLE, never MERGED.** A score at or above the line makes a pair
eligible to merge and nothing more. Whether the day actually merged it depends on
two things no drawn row can see: a group is refused unless every pair in it
clears the line, and two items on different published days never fold at all. A
band labelled MERGED would overstate what happened, which is the class of defect
this sheet exists to catch.

Operator tooling. It is not a stage, has no `idhazh` verb, and never writes into
the published tree.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from idhazh.contracts.base import derive_url_key

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
LOG: Final = logging.getLogger("idhazh")

DEFAULT_OUT: Final = Path("test-results/similarity-pairs-to-label")
DEFAULT_DIGEST_ROOT: Final = Path("frontend/public/digest")
PUBLISHED_TREES: Final = (Path("frontend/public"), Path("frontend/build"))

#: How wide either side of the line counts as "just". A pair inside this corridor
#: is one a small move in the line would reclassify, which is what makes it worth
#: a labeller's attention ahead of a pair at 0.99.
DEFAULT_CORRIDOR: Final = 0.02

#: `0.94 + 0.02` is not 0.96 in binary, so a pair exactly on the corridor edge
#: files one band out without this. The same reason `fold.SLOT_TOLERANCE` exists.
EDGE_TOLERANCE: Final = 1e-9


class Band(StrEnum):
    """Where a pair sits relative to the line the day was built with."""

    JUST_ABOVE = "just-above"
    JUST_BELOW = "just-below"
    WELL_ABOVE = "well-above"
    WELL_BELOW = "well-below"


#: Worst-error-first. The two corridor bands come first because a label there can
#: move the line; the two outer bands anchor the benchmark so a model is not
#: measured only on its hardest cases.
BAND_ORDER: Final = (Band.JUST_ABOVE, Band.JUST_BELOW, Band.WELL_ABOVE, Band.WELL_BELOW)


@dataclass(frozen=True)
class Article:
    """One side of a pair, as a labeller needs to see it."""

    url: str
    title: str
    summary: str
    source: str
    #: The published day this article is on, which is not always the draw's date.
    date: str


@dataclass(frozen=True)
class Pair:
    """One drawn pair, resolved against the two days it came from."""

    date: str
    pair_key: str
    score: float
    cosine: float
    key_point: float
    headline: bool
    band: Band
    left: Article
    right: Article


def band_of(score: float, line: float, *, corridor: float) -> Band:
    """Which side of the line a score falls, and whether it is close to it."""
    if score >= line:
        return Band.JUST_ABOVE if score - line <= corridor + EDGE_TOLERANCE else Band.WELL_ABOVE
    return Band.JUST_BELOW if line - score <= corridor + EDGE_TOLERANCE else Band.WELL_BELOW


def distance(score: float, line: float) -> float:
    """How far a score sits from the line. Nearest first is the reading order."""
    return abs(score - line)


def _spread_order(pairs: list[Pair]) -> list[Pair]:
    """Re-order a sorted band so that ANY prefix of it covers the whole range.

    Taking the front of a band sorted by distance gave a sheet running 0.9187 to
    0.9719 - a benchmark whose easiest case is a hundredth from its hardest
    cannot tell a wrong model from an ambiguous pair.

    Truncating the band to a fixed share instead was worse: it caps what the band
    can give, so a draw that filled only one band returned a quarter of the sheet
    that was asked for. This orders rather than truncates. Repeated bisection,
    widest gap first, so the first pick is the middle of the band, the next two
    are its quarters, and the caller stops whenever it has enough.
    """
    out: list[Pair] = []
    queue: deque[tuple[int, int]] = deque([(0, len(pairs) - 1)])
    while queue:
        low, high = queue.popleft()
        if low > high:
            continue
        mid = (low + high) // 2
        out.append(pairs[mid])
        queue.append((low, mid - 1))
        queue.append((mid + 1, high))
    return out


def select(pairs: Sequence[Pair], *, line: float, total: int) -> list[Pair]:
    """Round robin over the bands, corridor bands first.

    Round robin rather than a quota: a quota on an empty band wastes its slots,
    and the bands are never evenly filled - 771 of the 1,197 unique pairs drawn
    over 29 days were well below the line and 105 just above it. Taking one from
    each band in turn spends every slot and still gives the corridor bands first
    refusal.

    Inside a band, the corridor two are ordered nearest the line first, because a
    label there can move the line. The outer two are ordered to cover their range
    at any prefix length, so the benchmark carries easy cases as well as hard
    ones however many slots that band ends up with.

    No seed anywhere. Ties break on `pair_key` ascending, so two runs over one
    draw produce the same sheet and a labeller can be handed a diff.
    """
    queues: dict[Band, list[Pair]] = {band: [] for band in BAND_ORDER}
    for pair in pairs:
        queues[pair.band].append(pair)

    for band in BAND_ORDER:
        queues[band].sort(key=lambda pair: (distance(pair.score, line), pair.pair_key))
        if band in (Band.WELL_ABOVE, Band.WELL_BELOW):
            queues[band] = _spread_order(queues[band])

    taken: list[Pair] = []
    cursors = dict.fromkeys(BAND_ORDER, 0)
    while len(taken) < total:
        moved = False
        for band in BAND_ORDER:
            if len(taken) == total:
                break
            at = cursors[band]
            if at < len(queues[band]):
                taken.append(queues[band][at])
                cursors[band] = at + 1
                moved = True
        if not moved:
            break
    return taken


def articles(day: dict[str, object], date: str) -> dict[str, Article]:
    """Every item in a day payload, keyed by its recomputed url key.

    Recomputed rather than read off the row: a key is identity, and taking it
    from the same function the draw used is what makes the two sides agree.
    """
    found: dict[str, Article] = {}
    items = day.get("items")
    if not isinstance(items, list):
        return found
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("source_url") or "")
        if not url:
            continue
        found[derive_url_key(url)] = Article(
            url=url,
            title=str(item.get("title") or ""),
            summary=str(item.get("summary") or ""),
            source=str(item.get("source_name") or ""),
            date=date,
        )
    return found


def index(digest_root: Path) -> dict[str, Article]:
    """Every published article, keyed by url key, across every committed day.

    **One index, not one day.** A drawn pair's two items are not always on the
    draw's own date: the same story stays one story for 36 hours, so a pair can
    straddle midnight. Resolving against the draw date alone lost 2,035 of the
    2,804 pairs drawn over 29 days. It is the same reason the holdout contract
    carries `left_date` and `right_date` as separate columns.

    A later day wins a key it shares with an earlier one: an article carried on
    a second day is the same article, and the newer payload is the one a reader
    would open.
    """
    found: dict[str, Article] = {}
    for path in sorted(digest_root.rglob("digest.json")):
        date = "-".join(path.parts[-4:-1])
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            found.update(articles(loaded, date))
    return found


def _day_path(digest_root: Path, date: str) -> Path:
    year, month, day = date.split("-")
    return digest_root / year / month / day / "digest.json"


def _load_day(digest_root: Path, date: str) -> dict[str, object]:
    path = _day_path(digest_root, date)
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _drawn_rows(draw_root: Path) -> Iterator[dict[str, str]]:
    for path in sorted(draw_root.rglob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle)


def resolve(
    draw_root: Path, digest_root: Path, *, line: float, corridor: float
) -> tuple[list[Pair], dict[str, int]]:
    """Every drawn pair whose two articles are both still on the published day.

    A pair that cannot be resolved is counted by reason rather than dropped in
    silence. A sheet that quietly shrinks is a sheet nobody can check.

    **One row a pair, whatever the draw did.** A pair whose two articles sit on
    different published days is drawn on both of those days, so its `pair_key`
    arrives twice. Labelling the same two headlines twice wastes a slot and
    would double-count that pair in any rate measured off the sheet.
    """
    refused = {"no-article": 0, "no-score": 0, "already-drawn": 0}
    resolved: list[Pair] = []
    seen: set[str] = set()
    by_key = index(digest_root)

    for row in _drawn_rows(draw_root):
        date = row.get("date") or ""
        key = row.get("pair_key") or ""
        if key in seen:
            refused["already-drawn"] += 1
            continue
        left = by_key.get(row.get("left_url_key") or "")
        right = by_key.get(row.get("right_url_key") or "")
        if left is None or right is None:
            refused["no-article"] += 1
            continue
        raw = row.get("composite_score") or ""
        try:
            score = float(raw)
        except ValueError:
            refused["no-score"] += 1
            continue
        seen.add(key)
        resolved.append(
            Pair(
                date=date,
                pair_key=key,
                score=score,
                cosine=float(row.get("cosine") or 0.0),
                key_point=float(row.get("key_point") or 0.0),
                headline=(row.get("headline") or "").lower() == "true",
                band=band_of(score, line, corridor=corridor),
                left=left,
                right=right,
            )
        )
    return resolved, refused


def as_json(pairs: Sequence[Pair], *, line: float, corridor: float) -> str:
    """The file a labeller writes into. One object a pair, `same_story` unset.

    `same_story` is absent rather than null so a sheet that comes back with a row
    untouched is a parse failure rather than a silent "two stories".
    """
    return json.dumps(
        {
            "line": line,
            "corridor": corridor,
            "instructions": (
                "Set same_story to true where both articles report the SAME news "
                "event, and false where they are different events. A shared topic "
                "is not a shared story."
            ),
            "pairs": [
                {
                    "pair_key": pair.pair_key,
                    "date": pair.date,
                    "score": round(pair.score, 4),
                    "band": str(pair.band),
                    "left_url": pair.left.url,
                    "left_date": pair.left.date,
                    "left_title": pair.left.title,
                    "left_summary": pair.left.summary,
                    "right_url": pair.right.url,
                    "right_date": pair.right.date,
                    "right_title": pair.right.title,
                    "right_summary": pair.right.summary,
                }
                for pair in pairs
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def as_markdown(pairs: Sequence[Pair], *, line: float, refused: dict[str, int]) -> str:
    """The same pairs, laid out to be read rather than parsed."""
    counts = {band: sum(1 for pair in pairs if pair.band is band) for band in BAND_ORDER}
    lines = [
        "# Borderline pairs to label",
        "",
        f"The line is {line:.3f}. A pair at or above it is ELIGIBLE to merge - "
        "whether the day merged it depends on the whole group and on both items "
        "being on one day, neither of which a row here can see.",
        "",
        "| Band | Pairs |",
        "| --- | --- |",
    ]
    lines += [f"| {band} | {counts[band]} |" for band in BAND_ORDER]
    lines += ["", f"Refused: {refused}", ""]
    for index, pair in enumerate(pairs, start=1):
        lines += [
            f"## {index}. {pair.score:.4f} - {pair.band} - {pair.date}",
            "",
            f"- **A** [{pair.left.title}]({pair.left.url}) ({pair.left.source})",
            f"  - {pair.left.summary}",
            f"- **B** [{pair.right.title}]({pair.right.url}) ({pair.right.source})",
            f"  - {pair.right.summary}",
            "",
            f"`{pair.pair_key}` cosine {pair.cosine:.4f}, key points "
            f"{pair.key_point:.4f}, headline match {pair.headline}",
            "",
        ]
    return "\n".join(lines) + "\n"


def _refuse_a_published_tree(out_root: Path) -> None:
    resolved = out_root.resolve()
    for tree in PUBLISHED_TREES:
        published = (REPO_ROOT / tree).resolve()
        if resolved == published or published in resolved.parents:
            raise SystemExit(
                f"--out is {resolved.as_posix()}, which is inside {tree.as_posix()} - "
                "the sheet is a working artifact and a published one would put "
                "unlabelled pairs on the site"
            )


def as_holdout_rows(
    pairs: Sequence[Pair],
    labels: Mapping[str, bool],
    *,
    labelled_on: str,
    labeller: str,
) -> list[dict[str, str]]:
    """Every labelled pair, as rows of `SimilarityHoldoutPair`.

    **Joined on `pair_key` against the whole drawn population, not against the
    current sheet.** A mark belongs to a pair, not to a slot in a sheet. Harvesting
    from the sheet meant that re-drawing it - or changing how pairs are chosen -
    silently dropped every mark whose pair no longer made the cut: one selection
    change here turned 200 labelled pairs into 129. The benchmark accumulates.

    `note` carries who labelled it. A mark is worth what its labeller is worth,
    and a file that does not say cannot be audited later.
    """
    rows: list[dict[str, str]] = []
    for pair in sorted(pairs, key=lambda item: item.pair_key):
        mark = labels.get(pair.pair_key)
        if mark is None:
            continue
        rows.append(
            {
                "version": labelled_on,
                "left_url": pair.left.url,
                "right_url": pair.right.url,
                "left_date": pair.left.date,
                "right_date": pair.right.date,
                "left_title": pair.left.title,
                "right_title": pair.right.title,
                "same_story": "true" if mark else "false",
                "marked_on": labelled_on,
                "note": f"{labeller} at score {pair.score:.4f}",
            }
        )
    return rows


def write(
    draw_root: Path,
    digest_root: Path,
    out_root: Path,
    *,
    line: float,
    corridor: float,
    total: int,
) -> int:
    _refuse_a_published_tree(out_root)
    pairs, refused = resolve(draw_root, digest_root, line=line, corridor=corridor)
    chosen = select(pairs, line=line, total=total)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "pairs.json").write_text(
        as_json(chosen, line=line, corridor=corridor), encoding="utf-8", newline=""
    )
    (out_root / "pairs.md").write_text(
        as_markdown(chosen, line=line, refused=refused), encoding="utf-8", newline=""
    )
    LOG.info(
        "sample_sheet resolved %d pairs, refused %s, wrote %d to %s",
        len(pairs),
        refused,
        len(chosen),
        out_root.as_posix(),
    )
    return len(chosen)


def harvest(
    sheet_root: Path,
    out_csv: Path,
    pairs: Sequence[Pair],
    *,
    labeller: str,
    labelled_on: str,
) -> int:
    """Turn every label made so far into the holdout file the console panel reads."""
    labels: dict[str, bool] = {}
    for batch in sorted(sheet_root.glob("labels-batch-*.json")):
        loaded = json.loads(batch.read_text(encoding="utf-8"))
        labels.update(loaded["by_pair_key"])
    rows = as_holdout_rows(pairs, labels, labelled_on=labelled_on, labeller=labeller)
    missing = len(labels) - len(rows)
    columns = list(rows[0]) if rows else []
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    LOG.info(
        "sample_sheet harvested %d labelled pairs to %s, %d labels matched no drawn pair",
        len(rows),
        out_csv.as_posix(),
        missing,
    )
    return len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw-root", type=Path)
    parser.add_argument("--digest-root", type=Path, default=REPO_ROOT / DEFAULT_DIGEST_ROOT)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / DEFAULT_OUT)
    parser.add_argument("--line", type=float)
    parser.add_argument("--corridor", type=float, default=DEFAULT_CORRIDOR)
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument(
        "--harvest",
        type=Path,
        help="read the labels beside --out and write holdout rows to this path",
    )
    parser.add_argument("--labeller", default="")
    parser.add_argument("--labelled-on", default="")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if args.draw_root is None or args.line is None:
        parser.error("--draw-root and --line are always required")
    if args.harvest is not None:
        if not args.labeller or not args.labelled_on:
            parser.error("--harvest needs --labeller and --labelled-on")
        pairs, _ = resolve(
            args.draw_root, args.digest_root, line=args.line, corridor=args.corridor
        )
        harvest(
            args.out,
            args.harvest,
            pairs,
            labeller=args.labeller,
            labelled_on=args.labelled_on,
        )
        return 0
    write(
        args.draw_root,
        args.digest_root,
        args.out,
        line=args.line,
        corridor=args.corridor,
        total=args.total,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
