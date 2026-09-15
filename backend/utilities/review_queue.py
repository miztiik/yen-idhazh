"""Build a day's review tree: every visual decision, laid out so a person can look.

The question is the one nothing has asked yet - **is the visual the machine kept
the visual a human would have kept?** This builds the place to ask it. It gates
nothing: no publish decision reads the tree, and nothing here selects what
publishes (`CLAUDE.md` section 0a).

Operator tooling. It is not a stage, not a page on the published site, and it
never writes into the published tree.

**The tree is a build artifact.** It lands under `backend/var/review/<date>/`,
which `.gitignore` covers at `backend/var/`, and reaches a person as a workflow
artifact. Three things keep it out of the published site and only one of them is
a scan: `--out` is refused when it resolves inside `frontend/public/` or
`frontend/build/`; nothing under either tree names this directory; and the site
build stages `static/` from an explicit list this is not on.

**Two doors, and they produce the same tree.** Download the `review` artifact
from the run that built the day, or point this at a day you produced yourself.
There is no dispatch of its own: a `Content refresh` run is most of three hours
and a queued dispatch is cancelled without an error by the next scheduled run,
a bad way to obtain a contact sheet the scheduled runs already produce. Ruled by
Carmack and Fowler, 2026-09-13. The reviewer's steps are in
`docs/concepts/evaluation.md`.

**Three populations, because three have a producer.** A fourth - a second
configuration's render of the same day - is named by the plan that asked for
this surface and nothing in this build can produce one, so there is no member
for it and no empty section pretending otherwise. It arrives with the row that
builds the second case.

**A refused draft has no picture to show, and that is a fact about the
contract rather than a gap here.** `VisualDecision` refuses a spec on an item
decided to nothing, so a plan the validator threw out survives as
`drafted_chart` and a `none_reason` and never as a drawing. The rejected card
says which gate refused it; it cannot say what the drawing would have looked
like.

**The tree degrades rather than failing.** The job that builds it also
publishes the day, so a budget the tree exceeds caps every population in
proportion and records both numbers. Truncating one population's tail would
produce an artifact that looks complete and is a biased sample, which is worse
than a smaller honest one because nobody can see it happened.

Every string that reaches the HTML came off the open web or out of a model
(Guardrail #11). It is escaped on the way in, and a drawing is referenced through an
`img` rather than inlined, for the reason the published page uses one: an SVG
inside an `img` cannot reach the document around it.

**That is history since 2026-09-13.** Nothing draws an SVG any more - the
reader's browser draws the chart and the pipeline publishes marks - so the sheet
draws its own bars out of the same published file, as three divs and a width.
A reviewer has to see the comparison to judge it, and a sheet that listed the
figures in prose would be asking them to do the drawing in their head.
"""

from __future__ import annotations

import argparse
import html
import logging
import shutil
import sys
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from idhazh.assemble import PUBLIC_ROOT, day_dir, write_atomic  # noqa: E402
from idhazh.contracts.digest_day import DigestDay, DigestItem  # noqa: E402
from idhazh.contracts.review_queue import (  # noqa: E402
    ReviewCensus,
    ReviewPopulation,
    ReviewQueue,
    ReviewRow,
)
from idhazh.contracts.visual_data import VisualData  # noqa: E402
from idhazh.contracts.visual_decision import (  # noqa: E402
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)

LOG: Final = logging.getLogger("idhazh")

#: Where a local run writes, and the directory the workflow uploads. One path,
#: so the artifact door and the local door cannot hand a reviewer two shapes.
DEFAULT_OUT: Final = Path("backend/var/review")
#: Where the run's per-item payloads sit. The decisions are here and nowhere
#: else: the published day carries `visual: null` for every item without a
#: picture, so from it alone a refused chart and an undrafted one look the same.
DEFAULT_RUN_ROOT: Final = Path("backend/var/run")

#: What one day's tree may weigh. Worst case measured from the shape rather than
#: from a run: `run.safety_ceiling_per_run` is 80 items a run and five runs a
#: day, and a published day's whole rendered set has measured 324,580 bytes
#: (docs/concepts/adaptive-pruning.md, 2026-09-13). Five megabytes is several
#: times that, so the bound fires when the shape of the tree changes and never
#: on a busy day. Carmack, 2026-09-13.
DEFAULT_BUDGET_MB: Final = 5

#: What one card costs in the sheet, for weighing the tree before it is written.
#: A generous round number rather than a measurement: it only has to stop a
#: population of cards being counted as free beside the drawings.
CARD_BYTES: Final = 1_000

#: Trees this must never write into. Being under either is the failure the whole
#: surface is arranged against, so it is a refusal at the boundary rather than a
#: scan somebody runs afterwards.
PUBLISHED_TREES: Final = (Path("frontend/public"), Path("frontend/build"))

_STYLE: Final = """
:root { color-scheme: light dark; }
body { font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 60rem; padding: 2rem 1rem; }
h1 { margin-bottom: 0; }
.census { color: #666; margin: .25rem 0 2rem; }
section { margin-bottom: 3rem; }
article { border-top: 1px solid #8884; padding: 1rem 0; }
article h3 { font-size: 1rem; margin: 0 0 .25rem; }
/* Capped, so several drawings fit one screen and a reviewer compares them
   rather than scrolling between them. The white ground is the page the
   renderer drew for: an SVG authored light and shown on a dark body loses its
   axis labels. */
article .bars { display: grid; gap: 0.3rem; margin: 0.6rem 0; }
article .bar { align-items: center; display: grid; gap: 0.5rem;
  grid-template-columns: 10rem 1fr auto; }
article .bar b { background: #4c6ef5; border-radius: 2px; font-size: 0; height: 1rem; }
article .bar span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.why { color: #666; font-size: .875rem; margin: .25rem 0; }
.empty { color: #666; font-style: italic; }
"""

#: One line a reviewer reads before the cards, so a section they are looking at
#: says what it is for rather than making them hold the vocabulary.
_BLURB: Final[dict[ReviewPopulation, str]] = {
    ReviewPopulation.PUBLISHED: "A chart was drawn and the day publishes it.",
    ReviewPopulation.REJECTED: (
        "A chart was drafted and the item carries none anyway. There is no drawing to "
        "show: a decision that came to nothing carries no plan."
    ),
    ReviewPopulation.NONE: "No chart was drafted. This is the majority answer by design.",
}


def _decisions(items_dir: Path) -> Iterator[VisualDecision]:
    """This day's decisions, in a stable order.

    One day's directory, never a walk over what the pipeline has piled up
    (Guardrail #12): the cost follows the day being reviewed and not the archive
    behind it.
    """
    for path in sorted(items_dir.glob(f"*{PAYLOAD_SUFFIX}")):
        yield VisualDecision.read(path)


def population_of(decision: VisualDecision) -> ReviewPopulation:
    """Which of the three outcomes this decision landed in.

    `drafted_chart` is what separates the two kinds of `none`, and a render that
    failed after the plan passed is a rejection too - the machine chose a
    drawing and the reader got none either way, which is the thing a reviewer is
    being asked about.
    """
    if decision.visual_state is VisualState.RENDERED:
        return ReviewPopulation.PUBLISHED
    if decision.kind is not VisualKind.NONE or decision.drafted_chart:
        return ReviewPopulation.REJECTED
    return ReviewPopulation.NONE


def keep_counts(
    seen: dict[ReviewPopulation, int], *, budget_bytes: int, weighed: int
) -> dict[ReviewPopulation, int]:
    """How many rows each population keeps once the tree is over budget.

    Proportional, so no population is silently emptied to save another, and at
    least one row of any population that has one - a section that disappears
    reads as an outcome that did not happen.
    """
    if weighed <= budget_bytes or sum(seen.values()) == 0:
        return dict(seen)
    share = budget_bytes / weighed
    return {
        population: (min(count, max(1, int(count * share))) if count else 0)
        for population, count in seen.items()
    }


def _bars(data: VisualData) -> str:
    """One item's marks as bars a reviewer can compare at a glance.

    Widths are a share of the longest bar, which is the one comparison a
    reviewer is being asked to judge. Every name is escaped on the way in: it is
    a model's cut of a stranger's page (Guardrail #11).
    """
    held = {mark.mark_id: mark for mark in data.marks}
    names = [held[mark_id].text or "" for mark_id in data.encoding.category]
    figures = [Decimal(held[mark_id].value or "0") for mark_id in data.encoding.quantity]
    longest = max((abs(figure) for figure in figures), default=Decimal(0))
    if not names or len(names) != len(figures) or longest == 0:
        return ""
    rows = [
        f'    <div class="bar"><span>{html.escape(name)}</span>'
        f'<b style="width:{abs(figure) / longest:.1%}">.</b>'
        f"<i>{html.escape(format(figure.normalize(), ',f'))}</i></div>"
        for name, figure in zip(names, figures, strict=True)
    ]
    return '  <div class="bars">\n' + "\n".join(rows) + "\n  </div>"


def _card(row: ReviewRow, bars: str) -> str:
    """One item, with every untrusted string escaped on the way in."""
    parts = [
        "<article>",
        f"  <h3>{html.escape(row.title or row.item_id)}</h3>",
        f'  <p class="why"><a href="{html.escape(row.source_url, quote=True)}"'
        ' rel="noreferrer noopener">the source</a>'
        f" &middot; {html.escape(row.item_id)}</p>",
    ]
    if bars:
        parts.append(bars)
    if row.alt_text is not None:
        parts.append(f'  <p class="why">{html.escape(row.alt_text)}</p>')
    if row.none_reason is not None:
        parts.append(f'  <p class="why">gate: {html.escape(row.none_reason.value)}</p>')
    if row.rationale is not None:
        parts.append(f'  <p class="why">{html.escape(row.rationale)}</p>')
    parts.append("</article>")
    return "\n".join(parts)


def _sheet(
    date: str,
    census: Sequence[ReviewCensus],
    rows: Sequence[ReviewRow],
    bars: Mapping[str, str],
) -> str:
    """The contact sheet, one page a reviewer scrolls."""
    counted = {entry.population: entry for entry in census}
    summary = ", ".join(
        f"{counted[population].kept} of {counted[population].seen} {population.value}"
        for population in ReviewPopulation
    )
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Visual review - {html.escape(date)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>Visual review - {html.escape(date)}</h1>",
        f'<p class="census">{html.escape(summary)}. This page judges nothing and'
        " publishes nothing.</p>",
    ]
    for population in ReviewPopulation:
        entry = counted[population]
        parts.append(f'<section id="{population.value}">')
        parts.append(f"<h2>{population.value} ({entry.kept} of {entry.seen})</h2>")
        parts.append(f'<p class="why">{html.escape(_BLURB[population])}</p>')
        shown = [row for row in rows if row.population is population]
        if not shown:
            parts.append('<p class="empty">Nothing in this population today.</p>')
        parts.extend(_card(row, bars.get(row.item_id, "")) for row in shown)
        parts.append("</section>")
    parts.extend(["</body>", "</html>", ""])
    return "\n".join(parts)


def _tree_bytes(out_dir: Path) -> int:
    """What the sheet and its drawings weigh. One directory, so the cost follows the day."""
    return sum(path.stat().st_size for path in out_dir.rglob("*") if path.is_file())


def _refuse_a_published_tree(out_root: Path) -> None:
    resolved = out_root.resolve()
    for tree in PUBLISHED_TREES:
        published = tree.resolve()
        if resolved == published or published in resolved.parents:
            raise SystemExit(
                f"--out is {resolved.as_posix()}, which is inside {tree.as_posix()} - the "
                "review tree is a build artifact, and a published one is the failure this "
                "surface exists to prevent"
            )


def build(
    *,
    date: str,
    digest_root: Path,
    run_root: Path,
    out_root: Path,
    budget_bytes: int,
) -> ReviewQueue:
    """Write one day's review tree and return the queue it holds."""
    _refuse_a_published_tree(out_root)

    published_day = day_dir(digest_root, date)
    payload = published_day / "digest.json"
    if not payload.is_file():
        raise SystemExit(f"no published day at {payload.as_posix()} - build the day first")
    day = DigestDay.read(payload)
    by_id: dict[str, DigestItem] = {item.item_id: item for item in day.items}

    items_dir = run_root / date / "items"
    if not items_dir.is_dir():
        raise SystemExit(
            f"no run payloads under {items_dir.as_posix()} - the decisions live here and "
            "nowhere else, so download the run's items artifact or point --run-root at a "
            "day you produced yourself"
        )

    # `data_path` is relative to the published root, and the digest tree is one
    # directory inside it.
    public_root = digest_root.parent
    found: dict[ReviewPopulation, list[tuple[VisualDecision, DigestItem]]] = {
        population: [] for population in ReviewPopulation
    }
    for decision in _decisions(items_dir):
        item = by_id.get(decision.item_id)
        if item is None:
            # A decision for a story the day did not publish. The question is
            # about the visuals a reader met, so it is not one of them.
            continue
        found[population_of(decision)].append((decision, item))

    seen = {population: len(rows) for population, rows in found.items()}
    drawings = [
        public_root / decision.data_path
        for decision, _ in found[ReviewPopulation.PUBLISHED]
        if decision.data_path is not None
    ]
    weighed = sum(path.stat().st_size for path in drawings if path.is_file())
    weighed += CARD_BYTES * sum(seen.values())
    keep = keep_counts(seen, budget_bytes=budget_bytes, weighed=weighed)

    out_dir = out_root / date
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)

    rows: list[ReviewRow] = []
    bars: dict[str, str] = {}
    for population in ReviewPopulation:
        for decision, item in found[population][: keep[population]]:
            asset_relpath: str | None = None
            if decision.data_path is not None:
                source = public_root / decision.data_path
                if source.is_file():
                    asset_relpath = f"assets/{decision.item_id}{source.suffix}"
                    shutil.copyfile(source, out_dir / asset_relpath)
                    bars[decision.item_id] = _bars(VisualData.read(source))
            rows.append(
                ReviewRow(
                    item_id=decision.item_id,
                    url_key=decision.url_key,
                    population=population,
                    title=item.title,
                    source_url=item.source_url,
                    visual_state=decision.visual_state,
                    none_reason=decision.none_reason,
                    rationale=decision.rationale,
                    alt_text=decision.alt_text,
                    asset_relpath=asset_relpath,
                )
            )

    census = [
        ReviewCensus(population=population, seen=seen[population], kept=keep[population])
        for population in ReviewPopulation
    ]
    write_atomic(out_dir / "index.html", _sheet(date, census, rows, bars))
    # Measured before the queue file is written, because a byte count inside a
    # document cannot include its own length.
    queue = ReviewQueue(
        version=ReviewQueue.schema_version(),
        date=date,
        built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        budget_bytes=budget_bytes,
        bytes_written=_tree_bytes(out_dir),
        census=census,
        rows=rows,
    )
    write_atomic(out_dir / "queue.json", queue.to_json())
    return queue


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a day's visual review tree.")
    parser.add_argument("--date", required=True, help="the published day to review, YYYY-MM-DD")
    parser.add_argument("--digest-root", type=Path, default=PUBLIC_ROOT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--budget-mb",
        type=int,
        default=DEFAULT_BUDGET_MB,
        help="what the tree may weigh before every population is capped in proportion",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    queue = build(
        date=args.date,
        digest_root=args.digest_root,
        run_root=args.run_root,
        out_root=args.out,
        budget_bytes=args.budget_mb * 1_000_000,
    )
    for entry in queue.census:
        LOG.info(
            "review %s: %s, kept %s of %s",
            queue.date,
            entry.population.value,
            entry.kept,
            entry.seen,
        )
    cut = [entry for entry in queue.census if entry.kept < entry.seen]
    if cut:
        short = ", ".join(f"{entry.population.value} {entry.kept}/{entry.seen}" for entry in cut)
        print(
            f"::warning::review tree for {queue.date} was capped at "
            f"{args.budget_mb} MB - {short}"
        )
    LOG.info(
        "review %s: %s bytes under %s",
        queue.date,
        queue.bytes_written,
        (args.out / args.date).as_posix(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
