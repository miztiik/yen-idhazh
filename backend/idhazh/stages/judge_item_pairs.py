"""Are these item pairs the same story? One shard's answers, one verdict file out.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

This shard opens no ledger, commits nothing, and decides nothing about the line. It
reads the draw the scoring stage wrote, judges the rows this shard owns, and
leaves one file behind for the collecting job to pick up.

It is handed the instant it must stop by. Where stopping is safe is this shard's
own answer, because only it knows what a unit of work is here, and the file is
written as the shard goes so that stopping early costs the pairs it never started
rather than the ones it had already read.
"""

from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from idhazh import assemble, config
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
    completion_url,
    derive_turn_markers,
    post,
    token_pieces,
)
from idhazh.similarity import judge, prompt, stamps
from idhazh.stages.assemble import _earlier_days
from idhazh.stages.common import LOG, _load_day

#: What the scoring stage leaves behind, and what a shard reads.
DRAW_FILENAME: Final = "draw.csv"

#: One file a shard, named for the shard. Four shards writing four paths is what makes
#: a merge driver unnecessary here: no two processes ever write one file.
VERDICTS_DIRNAME: Final = "verdicts"


@dataclass(frozen=True, slots=True)
class ShardReport:
    """What one shard did, for its log line and for the operator reading it."""

    date: str
    shard: int
    owned: int
    judged: int
    usable: int
    path: Path

    #: How the shard ended. Reported rather than inferred: a shard that stopped on
    #: its clock and a shard that finished both leave a readable file, and only the
    #: shard knows which of the two it was.
    outcome: ShardOutcome


def stage_judge_item_pairs(
    date: str,
    *,
    shard: int,
    shards: int,
    settings: config.Settings,
    digest_root: Path,
    run_dir: Path,
    deadline: float,
    base_url: str = DEFAULT_ENDPOINT,
) -> ShardReport:
    """Judge the rows this shard owns and write them as they are judged.

    `shards` is read rather than ignored. A draw taken at eight shards and judged
    by four would leave half its pairs unread, every shard would report success,
    and the day would be counted as though the missing pairs had never been drawn.

    `deadline` is a `time.monotonic()` instant the caller hands over, and this
    shard reads no clock knob of its own. It is checked before a pair and never
    between that pair's two readings: a pair stopped halfway has one reading and
    no agreement, so it would count as neither read nor abandoned and the day's
    funnel would stop adding up.

    `digest_root` and the window days resolve against the same tree: the earlier
    days come through `_earlier_days`, which reads `common.PUBLIC_ROOT`. A caller
    pointing one somewhere else has to move the other with it.
    """
    entry = judge.entry_of(settings)
    timeout = entry.inference.request_timeout_minutes * 60.0
    stamp = stamps.judge_inputs(settings)
    flush_every = settings.app.assemble.same_story.judging_knobs().flush_every_pairs
    drawn = _rows_this_shard_owns(run_dir / DRAW_FILENAME, shard=shard, shards=shards)
    # Asked once a shard, before any pair is judged. A verdict every returned token
    # could belong to another verdict too can never take any of the window's
    # mass, so `first_token_margin` reports a gap between the other two as though
    # that one had been weighed - which costs nothing visible and makes the
    # column wrong for the whole day. It is a precondition rather than a
    # per-call check.
    prompt.first_token_openings(partial(token_pieces, base_url, timeout=timeout))
    markers = derive_turn_markers(base_url, entry=entry, timeout=timeout)
    client = partial(post, endpoint=completion_url(base_url), timeout=timeout)
    items = _items_by_url_key(
        date,
        digest_root=digest_root,
        window_hours=settings.app.assemble.same_story_window_hours,
    )

    path = run_dir / VERDICTS_DIRNAME / f"{shard}.csv"
    judged: list[StorySimilarityPair] = []
    unreadable = 0
    outcome = ShardOutcome.COMPLETED if drawn else ShardOutcome.NOTHING_TO_DO
    for row in drawn:
        if time.monotonic() >= deadline:
            outcome = ShardOutcome.STOPPED_ON_DEADLINE
            LOG.warning(
                "judge-item-pairs shard=%s date=%s stopped on its deadline with %s of %s "
                "pair(s) judged",
                shard,
                date,
                len(judged),
                len(drawn),
            )
            break
        left = items.get(row.left_url_key)
        right = items.get(row.right_url_key)
        if left is None or right is None:
            unreadable += 1
            continue
        verdicts = judge.judge_pair(
            left, right, client=client, settings=settings, markers=markers
        )
        judged.append(_with_the_verdict(row, verdicts, stamp=stamp))
        if len(judged) % flush_every == 0:
            assemble.write_atomic(path, _as_csv(judged))

    if unreadable:
        LOG.warning(
            "judge-item-pairs shard=%s date=%s skipped %s drawn pair(s) whose items the "
            "window no longer reaches",
            shard,
            date,
            unreadable,
        )

    # A refused pair is judged, written and counted here, and left out of the
    # record later for having no agreed verdict. It is warned about because the
    # shard is the only place that sees them arriving one after another: a
    # decoder that came loose refuses every pair after it, and that is worth
    # reading in the run's log rather than only in the file afterwards.
    refused = sum(1 for row in judged if row.grammar_applied is False)
    if refused:
        LOG.warning(
            "judge-item-pairs shard=%s date=%s recorded %s of %s judged pair(s) whose "
            "decode did not open inside the grammar",
            shard,
            date,
            refused,
            len(judged),
        )

    # Unconditional, and after the loop as well as inside it. It is what leaves a
    # header for a shard that judged nothing, and what catches the pairs of a group
    # the cadence had not closed.
    assemble.write_atomic(path, _as_csv(judged))
    report = ShardReport(
        date=date,
        shard=shard,
        owned=len(drawn),
        judged=len(judged),
        usable=sum(1 for row in judged if row.usable),
        path=path,
        outcome=outcome,
    )
    LOG.info(
        "judge-item-pairs shard=%s date=%s owned=%s judged=%s usable=%s outcome=%s",
        report.shard,
        report.date,
        report.owned,
        report.judged,
        report.usable,
        report.outcome.value,
    )
    return report


def _rows_this_shard_owns(
    path: Path, *, shard: int, shards: int
) -> list[StorySimilarityPair]:
    """The draw, filtered to this shard, in the order it was drawn in.

    Read through the contract rather than by column index, so a draw written by a
    build that had one more column is refused here rather than judged under a
    shifted reading of what the score was.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist, so this shard has nothing to judge. The scoring "
            "stage writes it, and a shard that ran before it has nothing to read"
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [StorySimilarityPair.from_csv_row(cells) for cells in csv.DictReader(handle)]
    beyond = sorted({row.shard for row in rows if row.shard >= shards})
    if beyond:
        raise ValueError(
            f"{path.name} was drawn for more shards than this run has: it carries "
            f"shard(s) {beyond} and this run judges {shards}. Those pairs would never "
            "be read and the day would be counted as though they had never been drawn"
        )
    return [row for row in rows if row.shard == shard]


def _items_by_url_key(
    date: str, *, digest_root: Path, window_hours: float
) -> dict[str, DigestItem]:
    """Every item a drawn pair can name, keyed by the address key the row carries.

    **Guardrail #12 declaration.** Today's published day plus the days the
    same-story window still reaches, which is `ceil(window_hours / 24)` of them -
    one at the 36-hour default. It is the same work on the thousandth day as on
    the third, and it is exactly the read the draw was taken over: a pair the
    draw could name is a pair these days hold.

    Today wins a repeated address. One address published twice is one story, and
    the pair was drawn against today's copy of it.
    """
    found: dict[str, DigestItem] = {}
    for earlier in _earlier_days(date, window_hours=window_hours):
        for item in earlier.items:
            found[derive_url_key(item.source_url)] = item
    today = _load_day(assemble.day_dir(digest_root, date) / "digest.json")
    for item in today.items if today else ():
        found[derive_url_key(item.source_url)] = item
    return found


def _with_the_verdict(
    drawn: StorySimilarityPair, verdicts: judge.Judged, *, stamp: stamps.JudgeStamp
) -> StorySimilarityPair:
    """The drawn row with the judging columns filled in, config stamp and all.

    Rebuilt through the contract rather than copied, so the rule that a verdict
    arrives with the judge that produced it is applied to what this shard wrote
    rather than to what the draw already carried.

    **Every value that describes the ask comes off one stamp.** The stamp reads
    the same entry the shard decodes with, so a row cannot name one model and be
    judged under another, and the temperature written here is the number that
    went out rather than the number the config holds.

    **A refused reading writes an empty verdict rather than raising.** The row
    still carries its clock, its window and `grammar_applied` false, and that is
    the whole point of recording the refusal: a shard that raised here left the
    pair absent, and absent already means nothing drew it.
    """
    return StorySimilarityPair.model_validate(
        drawn.model_dump(mode="json")
        | {
            "verdict": _word(verdicts.verdict),
            "verdict_swapped": _word(verdicts.verdict_swapped),
            "usable": verdicts.usable,
            "first_token_margin": verdicts.first_token_margin,
            "judge_model": stamp.judge_model,
            "prompt_digest": stamp.prompt_digest,
            "grammar_digest": stamp.grammar_digest,
            "decode_seconds": verdicts.decode_seconds,
            "judge_temperature": stamp.judge_temperature,
            "grammar_applied": verdicts.grammar_applied,
            "first_token_probabilities": verdicts.first_token_window or None,
            "thinking_spans": verdicts.thinking_spans,
        }
    )


def _word(verdict: SameStoryVerdict | None) -> str | None:
    """The verdict as the column holds it, and empty where there is none.

    A reading the grammar did not hold has no verdict, and reaching for `.value`
    on it would raise in the one place that exists to write the refusal down.
    """
    return None if verdict is None else verdict.value


def _as_csv(rows: list[StorySimilarityPair]) -> str:
    """The shard's whole file, header first, written even when the shard judged nothing.

    An empty file with a header is what says the shard ran and found no pair it
    owned. A missing file says the shard died, and a day with a missing shard is
    not counted into the record at all - so the two have to look different.
    """
    columns = StorySimilarityPair.csv_columns()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.csv_row())
    return buffer.getvalue()
