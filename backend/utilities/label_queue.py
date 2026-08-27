"""Draw and label the faithfulness queue, locally, one row at a time.

Runs on a developer machine against the committed ledger. It is not a stage, not
a workflow, and not a page on the published site - the site has no writer
(Rule #1).

**Two modes, and the split is the control.**

`--draw` reports the queue and the collection requirement. It reads only, so
anyone can run it and nobody can pollute the ledger with it.

`--label` shows one item and takes one keystroke. It is human-paced by
construction: there is no `--from-file`, no `--model`, no stdin path, and no way
to write more than one row per prompt. Producing labels from a model would mean
writing a second writer, which is a new module in a diff in a pull request -
which is the point (`CLAUDE.md` section 0a).

**What the labeller sees and does not see.** They see the summary as published,
the source's own headline, the date, the link, and the extracted article text -
the same text the scorer read. They never see `hhem`, the band, any
counterweight, the scorer version, the decile, another row's label, or the tally
so far. Somebody shown `unsupported_numbers = 1` will find an unsupported number.

**The extracted text is the authority for the verdict; the link exists to decide
whether that text is the article at all.** URL alone would have the labeller
judging a page that has since changed, so their answer and the scorer's number
would be about different documents. Extracted text alone would hide the case
where the extractor grabbed navigation chrome, which is what `not_the_article`
is for.

**The text comes from an evidence package, and a row without one is refused.**
The committed ledger holds digests, never text, so the article and the summary
travel out of the run in `backend/var/evidence/`, which is gitignored, and reach
another machine as a workflow artifact. `--evidence` names the copy to read. A
row whose premise cannot be proved to be the one the scorer read is skipped with
the reason printed, because a labeller reading different text from the scorer
measures nothing. That includes every row scored before 2026-08-27, when no run
recorded a premise at all.

Both the summary and the article body are untrusted (Rule #11). They print as
inert terminal text and are sanitized on the way to the note field.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from idhazh import config  # noqa: E402
from idhazh.contracts.label_row import LabelRow, LabelTag, LabelVerdict  # noqa: E402
from idhazh.evals import evidence, labels  # noqa: E402
from idhazh.evals.writer import LEDGER_RELPATH as SCORES_RELPATH  # noqa: E402
from idhazh.sanitize import sanitize  # noqa: E402

RULE: Final = "-" * 72

#: One keystroke per tag, in the order a labeller meets them.
TAG_KEYS: Final[dict[str, LabelTag]] = {
    "i": LabelTag.INVENTED_FACT,
    "n": LabelTag.WRONG_NUMBER,
    "o": LabelTag.OVERSTATED,
    "w": LabelTag.WRONG_SUBJECT,
    "c": LabelTag.NOT_THE_ARTICLE,
    "x": LabelTag.UNJUDGEABLE,
}


#: What `_prompt` returns when the labeller passes on a row without judging it.
SKIP: Final = object()


def _ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"no eval ledger at {path.as_posix()}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _live_scorer(records: Sequence[dict[str, str]]) -> str:
    """The instrument the newest row was scored with."""
    if not records:
        raise SystemExit("the eval ledger is empty")
    return records[-1]["scorer_version"]


def report(
    queue: list[dict[str, str]], records: list[dict[str, str]], settings: config.Settings
) -> None:
    """What the draw holds and what is still missing, both stated plainly."""
    evaluation = settings.app.evaluation
    scorer = _live_scorer(records)
    days = sorted(labels.run_days(records, scorer_version=scorer))
    fingerprints = {
        row["pipeline_fingerprint"]
        for row in labels.eligible(records, scorer_version=scorer)
    }
    missing = labels.shortfalls(queue, per_decile=evaluation.label_draw_per_decile)

    print(RULE)
    print(f"scorer_version   {scorer}")
    print(f"eligible rows    {len(labels.eligible(records, scorer_version=scorer))}")
    print(f"run-days         {len(days)} of {evaluation.label_min_run_days} -> {', '.join(days)}")
    print(f"fingerprints     {len(fingerprints)}")
    print(f"drawn            {len(queue)} of {evaluation.label_draw_per_decile * labels.DECILES}")
    if missing:
        short = ", ".join(f"decile {index}: {count} short" for index, count in missing.items())
        print(f"shortfall        {short}")
    print(RULE)

    if len(days) < evaluation.label_min_run_days:
        # Stated rather than blocked. Labelling early is not wrong; treating a
        # one-day draw as if it spoke for the corpus would be.
        print(
            f"NOT YET RECALIBRATABLE: {evaluation.label_min_run_days - len(days)} more run-days "
            f"needed at this scorer_version, and they only count while the "
            f"pipeline_fingerprint also holds."
        )
    if len(fingerprints) > 1:
        print(
            f"WARNING: {len(fingerprints)} pipeline fingerprints in the pool. A producer change "
            "is a covariate, not noise."
        )


def package_report(
    queue: Sequence[dict[str, str]], package: dict[str, Path], *, where: str
) -> None:
    """How much of the draw can be judged at all, counted before anybody starts.

    Said once and up front. The alternative is a labeller meeting the same
    refusal sixty times and inferring the answer from the pattern, which is
    slower and is how somebody talks themselves into judging a row anyway.
    """
    reasons: dict[str, int] = {}
    for record in queue:
        refusal = evidence.look_up(package, record).refusal
        if refusal:
            reasons[refusal] = reasons.get(refusal, 0) + 1
    blocked = sum(reasons.values())

    print(f"evidence         {where} -> {len(package)} file(s)")
    print(f"labellable       {len(queue) - blocked} of {len(queue)}")
    for refusal, count in sorted(reasons.items()):
        print(f"  {count} skipped: {refusal}")
    print(RULE)


def _prompt(
    item: dict[str, str], found: evidence.Evidence, *, index: int, total: int
) -> tuple[LabelVerdict, LabelTag] | object | None:
    """Show one item and take one answer. `None` stops, `SKIP` passes on the row."""
    print()
    print(RULE)
    print(f"[{index}/{total}]  {item['date']}  {item['source_url']}")
    print(RULE)
    if found.item is None:
        print(f"NOT LABELLABLE: {found.refusal}.")
        print("Nothing recorded for this row.")
        return SKIP
    print(f"Source headline: {item['title']}")
    print()
    print("THE ARTICLE, as the scorer read it")
    print(found.item.premise)
    print()
    print("OUR SUMMARY")
    print(found.item.summary)
    print()
    print("Does this assert anything the article does not support?")
    print("  [y] yes   [n] no   [s] skip   [q] stop")
    answer = input("> ").strip().lower()
    if answer in {"q", ""}:
        return None
    if answer == "s":
        return SKIP
    if answer == "n":
        return (LabelVerdict.SUPPORTED, LabelTag.NONE)
    if answer != "y":
        print("not one of the options; nothing recorded")
        return _prompt(item, found, index=index, total=total)

    print("Which defect?")
    for key, tag in TAG_KEYS.items():
        print(f"  [{key}] {tag.value}")
    tag_key = input("> ").strip().lower()
    while tag_key not in TAG_KEYS:
        print("not one of the options")
        tag_key = input("> ").strip().lower()
    return (LabelVerdict.UNSUPPORTED, TAG_KEYS[tag_key])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draw-id", default="", help="Defaults to <today>-decile-<n>.")
    ap.add_argument("--label", action="store_true", help="Label the queue, one row at a time.")
    ap.add_argument("--labeller", default="", help="Your name. Must be in evaluation.labellers.")
    ap.add_argument(
        "--evidence",
        default="",
        help=(
            "The evidence package to read the article and the summary from. Defaults to "
            f"{evidence.EVIDENCE_ROOT_RELPATH}, which a local run writes. Point it at a "
            "downloaded artifact directory for a day CI produced."
        ),
    )
    args = ap.parse_args()

    settings = config.load(REPO_ROOT / "config")
    evaluation = settings.app.evaluation
    records = _ledger(REPO_ROOT / SCORES_RELPATH)
    scorer = _live_scorer(records)
    draw_id = args.draw_id or f"{records[-1]['date']}-decile-{evaluation.label_draw_per_decile}"

    queue = labels.draw(
        records,
        draw_id=draw_id,
        scorer_version=scorer,
        per_decile=evaluation.label_draw_per_decile,
    )
    report(queue, records, settings)

    named = Path(args.evidence) if args.evidence else REPO_ROOT / evidence.EVIDENCE_ROOT_RELPATH
    package = evidence.index(named)
    package_report(queue, package, where=evidence.posix_relpath(named, base=REPO_ROOT))

    if not args.label:
        print("\nread-only. Pass --label --labeller <name> to record verdicts.")
        return 0

    if args.labeller not in evaluation.labellers:
        raise SystemExit(
            f"{args.labeller!r} is not in evaluation.labellers. A label needs a human name, "
            "and the list is what keeps one there."
        )

    import time
    from datetime import UTC, datetime

    path = REPO_ROOT / labels.LEDGER_RELPATH
    done = labels.recorded(path)
    written = 0
    for index, item in enumerate(queue, start=1):
        if (item["label_id"], args.labeller) in done:
            continue
        started = time.monotonic()
        answer = _prompt(item, evidence.look_up(package, item), index=index, total=len(queue))
        if answer is None:
            break
        if answer is SKIP:
            continue
        assert isinstance(answer, tuple)
        verdict, tag = answer
        note = sanitize(input("note (enter to skip): ").strip())[:300]
        row = LabelRow.model_validate(
            {
                "label_id": item["label_id"],
                "draw_id": draw_id,
                "url_key": item["url_key"],
                "source_url": item["source_url"],
                "date": item["date"],
                "run_id": item["run_id"],
                "output_digest": item["output_digest"],
                "pipeline_fingerprint": item["pipeline_fingerprint"],
                "summary_word_count": int(item["summary_word_count"]),
                "source_word_count": int(item["source_word_count"]),
                "scorer_version": item["scorer_version"],
                "hhem_at_label": float(item["hhem"]),
                "band_at_label": item["band"],
                "verdict": verdict,
                "tag": tag,
                "labeller": args.labeller,
                "labelled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "seconds_spent": max(1, round(time.monotonic() - started)),
                "note": note or None,
            }
        )
        written += labels.append(path, [row])

    print(f"\n{written} label(s) written to {labels.LEDGER_RELPATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
