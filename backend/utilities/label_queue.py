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

**One scorer, and the pipeline reported beside it.** A draw comes from exactly
one `scorer_version`, because the cuts being calibrated live inside that string
and a row read by another instrument answers a different question. The pipeline
fingerprint is a covariate: it is printed per stratum with every draw, and it is
a filter only when `--pipeline-fingerprint` names one. Requiring both made the
gate unreachable - the stamp moves on any of seventeen inputs, a sanitizer fix
among them, and no pair has ever held for more than three consecutive run-days.
A scorer the ledger does not hold prints what the ledger does hold and exits
non-zero.

**A mixed pool is a prior, not a calibration, and this says so every time.** Rows
several producers wrote confound between-pipeline variance into the estimate.
The mix is printed with the draw, a stratum under
`evaluation.label_min_stratum_rows` is marked too thin to cut on, and the report
refuses to call the result a calibration.

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

**A draw only reaches the months still at full grain.** `state/scores/` keeps
`observability.scores_full_grain_months` months of item-level rows and then
becomes a summary, and a summary holds no row to label. So the report prints the
months the draw could see and the months that have aged out, and a run against a
ledger with no full-grain month left refuses instead of reporting a draw of
zero.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from idhazh import config  # noqa: E402
from idhazh.contracts.label_row import LabelRow, LabelTag, LabelVerdict  # noqa: E402
from idhazh.evals import archive, evidence, labels  # noqa: E402
from idhazh.evals.writer import LEDGER_RELDIR as SCORES_RELDIR  # noqa: E402
from idhazh.evals.writer import records as _score_records  # noqa: E402
from idhazh.ledger import STATE_DIRNAME  # noqa: E402
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


def _ledger(state_dir: Path) -> list[dict[str, str]]:
    """Every committed row, oldest month first. The ledger is a directory now.

    A ledger with no full-grain month left is refused by name rather than
    reported as an empty draw. The two look identical from the row count and
    need opposite actions: one waits for the pipeline to run, the other cannot
    be fixed by waiting at all.
    """
    rows = list(_score_records(state_dir))
    if not rows:
        summarised = archive.archived_months(state_dir)
        if summarised:
            raise SystemExit(
                f"every month of {(state_dir / SCORES_RELDIR).as_posix()} has aged out of "
                f"the full-grain window - {', '.join(summarised)} exist only as summaries "
                f"under {archive.ARCHIVE_RELDIR}/, and a summary holds no row to label. "
                f"{archive.RAW_WINDOW_NOTE}"
            )
        raise SystemExit(f"no eval ledger under {(state_dir / SCORES_RELDIR).as_posix()}")
    return rows


def _live_scorer(records: Sequence[dict[str, str]]) -> str:
    """The instrument the newest row was scored with."""
    if not records:
        raise SystemExit("the eval ledger is empty")
    return records[-1]["scorer_version"]


def refuse(records: Sequence[dict[str, str]], *, scorer: str, pipeline: str, reason: str) -> int:
    """Say the draw is empty, then say what the ledger does hold.

    An empty pool with no inventory beside it leaves the operator guessing
    whether the gate is one run-day away or unreachable. Printing every pair with
    its rows and dates answers that in one screen, and it is the only thing this
    tool can honestly offer when the scorer it was asked for holds nothing.
    """
    print(RULE)
    print("NOTHING TO DRAW")
    print(RULE)
    print(f"scorer_version   {scorer}")
    print(f"pipeline         {pipeline or 'every pipeline at this scorer'}")
    print("eligible rows    0")
    print(f"reason           {reason}")
    print(RULE)
    print()
    print(f"{SCORES_RELDIR} holds these pairs. Only a pair at the scorer above can be drawn:")
    for pair in labels.pairs(records):
        here = "   <- this scorer" if pair.scorer_version == scorer else ""
        print()
        print(f"  {pair.rows} rows, {pair.first_date} to {pair.last_date}")
        print(f"    scorer    {pair.scorer_version}{here}")
        print(f"    pipeline  {pair.pipeline_fingerprint}")
    print()
    print("Run the pipeline until the scorer above has rows.")
    return 1


def report(
    queue: list[dict[str, str]],
    records: list[dict[str, str]],
    settings: config.Settings,
    *,
    scorer: str,
    pipeline: str | None,
    archived: Sequence[str] = (),
) -> None:
    """What the draw holds and what is still missing, both stated plainly."""
    evaluation = settings.app.evaluation
    pool = labels.eligible(records, scorer_version=scorer, pipeline_fingerprint=pipeline)
    days = sorted(labels.run_days(records, scorer_version=scorer, pipeline_fingerprint=pipeline))
    missing = labels.shortfalls(queue, per_decile=evaluation.label_draw_per_decile)
    mix = labels.strata(queue)

    print(RULE)
    print(f"scorer_version   {scorer}")
    print(f"pipeline         {pipeline or 'all at this scorer - reported, not filtered'}")
    print(f"eligible rows    {len(pool)}")
    print(f"run-days         {len(days)} of {evaluation.label_min_run_days} -> {', '.join(days)}")
    print(f"drawn            {len(queue)} of {evaluation.label_draw_per_decile * labels.DECILES}")
    if missing:
        short = ", ".join(f"decile {index}: {count} short" for index, count in missing.items())
        print(f"shortfall        {short}")
    if archived:
        # Named, because a draw cannot reach these months and the row count
        # above gives no hint that they were ever there.
        print(f"aged out         {', '.join(archived)} - summarised, no row left to label")
    print(RULE)

    if mix:
        print("pipelines in this draw - report any result split by these, never pooled:")
        for one in mix:
            thin = (
                "  <- too thin to cut on"
                if one.rows < evaluation.label_min_stratum_rows
                else ""
            )
            print(
                f"  {one.rows:>4} rows  {one.first_date} to {one.last_date}  "
                f"{one.pipeline_fingerprint[:12]}{thin}"
            )
        print(RULE)

    if len(days) < evaluation.label_min_run_days:
        # Stated rather than blocked. Labelling early is not wrong; treating a
        # one-day draw as if it spoke for the corpus would be.
        print(
            f"NOT YET RECALIBRATABLE: {evaluation.label_min_run_days - len(days)} more run-days "
            f"needed at this scorer. A day at another scorer does not count."
        )
    elif len(mix) > 1:
        print(
            f"PRIOR, NOT A CALIBRATION: {len(mix)} pipelines wrote these rows, so part of any "
            "spread is the producer rather than the cut. Report per stratum, with wide bounds."
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
    ap.add_argument(
        "--pipeline-fingerprint",
        default="",
        help="Narrow the draw to one producer. Default is every pipeline at the live scorer.",
    )
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
    state_dir = REPO_ROOT / STATE_DIRNAME
    records = _ledger(state_dir)
    archived = archive.archived_months(state_dir)
    scorer = _live_scorer(records)

    pipeline = args.pipeline_fingerprint or None
    if not labels.eligible(records, scorer_version=scorer, pipeline_fingerprint=pipeline):
        reason = (
            "no row carries this pair"
            if pipeline
            else "no row carries this scorer, which cannot happen for the live one"
        )
        return refuse(records, scorer=scorer, pipeline=pipeline or "", reason=reason)

    draw_id = args.draw_id or f"{records[-1]['date']}-decile-{evaluation.label_draw_per_decile}"

    queue = labels.draw(
        records,
        draw_id=draw_id,
        scorer_version=scorer,
        pipeline_fingerprint=pipeline,
        per_decile=evaluation.label_draw_per_decile,
    )
    report(queue, records, settings, scorer=scorer, pipeline=pipeline, archived=archived)

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
                "source_seen_word_count": int(item["source_seen_word_count"]),
                "scorer_version": item["scorer_version"],
                "hhem_at_label": float(item["hhem"]),
                "band_at_label": item["band"],
                "verdict": verdict,
                "tag": tag,
                "labeller": args.labeller,
                "labelled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "seconds_spent": max(1, round(time.monotonic() - started)),
                "note": note or None,
                # Copied off the score row now, not re-joined later. The row this
                # was drawn from lives fourteen months; the label lives for ever,
                # and these three are what its tag vocabulary is measured against.
                "unsupported_numbers": int(item["unsupported_numbers"] or 0),
                "hedge_dropped": item["hedge_dropped"].strip().lower() == "true",
                "extraction_suspect": item["extraction_suspect"].strip().lower() == "true",
            }
        )
        written += labels.append(path, [row])

    print(f"\n{written} label(s) written to {labels.LEDGER_RELPATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
