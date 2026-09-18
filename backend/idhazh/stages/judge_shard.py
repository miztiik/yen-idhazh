"""The judging leg: one draw and one shard number in, one verdict file out.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").

This leg opens no ledger, commits nothing, and decides nothing about the line. It
reads the draw the scoring stage wrote, judges the rows this shard owns, and
leaves one file behind for the fold to pick up.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from idhazh import assemble, config
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.llm.server import DEFAULT_ENDPOINT, completion_url, post, token_ids
from idhazh.similarity import judge, prompt
from idhazh.stages.assemble import _earlier_days
from idhazh.stages.common import LOG, _load_day

#: What the scoring stage leaves behind, and what a leg reads.
DRAW_FILENAME: Final = "draw.csv"

#: One file a leg, named for the leg. Four legs writing four paths is what makes
#: a merge driver unnecessary here: no two processes ever write one file.
VERDICTS_DIRNAME: Final = "verdicts"


@dataclass(frozen=True, slots=True)
class ShardReport:
    """What one leg did, for its log line and for the operator reading it."""

    date: str
    shard: int
    owned: int
    judged: int
    usable: int
    path: Path


def stage_judge_shard(
    date: str,
    *,
    shard: int,
    shards: int,
    settings: config.Settings,
    digest_root: Path,
    run_dir: Path,
    base_url: str = DEFAULT_ENDPOINT,
) -> ShardReport:
    """Judge the rows this leg owns and write them once.

    `shards` is read rather than ignored. A draw taken at eight legs and judged
    by four would leave half its pairs unread, every leg would report success,
    and the day would fold as though the missing pairs had never been drawn.

    `digest_root` and the window days resolve against the same tree: the earlier
    days come through `_earlier_days`, which reads `common.PUBLIC_ROOT`. A caller
    pointing one somewhere else has to move the other with it.
    """
    entry = settings.models.summarize
    timeout = entry.inference.request_timeout_minutes * 60.0
    drawn = _rows_this_leg_owns(run_dir / DRAW_FILENAME, shard=shard, shards=shards)
    # Asked once a leg, before any pair is judged. A vocabulary that opens two of
    # the three words with one token costs nothing visible and makes
    # `first_token_margin` meaningless for the whole day, so it is a precondition
    # rather than a per-call check.
    prompt.first_token_ids(partial(token_ids, base_url, timeout=timeout))
    client = partial(post, endpoint=completion_url(base_url), timeout=timeout)
    items = _items_by_url_key(
        date,
        digest_root=digest_root,
        window_hours=settings.app.assemble.same_story_window_hours,
    )

    judged: list[StorySimilarityPair] = []
    unreadable = 0
    for row in drawn:
        left = items.get(row.left_url_key)
        right = items.get(row.right_url_key)
        if left is None or right is None:
            unreadable += 1
            continue
        verdicts = judge.judge_pair(left, right, client=client, settings=settings)
        judged.append(_with_the_verdict(row, verdicts, judge_model=entry.id))

    if unreadable:
        LOG.warning(
            "judge shard=%s date=%s skipped %s drawn pair(s) whose items the window no "
            "longer reaches",
            shard,
            date,
            unreadable,
        )

    path = run_dir / VERDICTS_DIRNAME / f"{shard}.csv"
    assemble.write_atomic(path, _as_csv(judged))
    report = ShardReport(
        date=date,
        shard=shard,
        owned=len(drawn),
        judged=len(judged),
        usable=sum(1 for row in judged if row.usable),
        path=path,
    )
    LOG.info(
        "judge shard=%s date=%s owned=%s judged=%s usable=%s",
        report.shard,
        report.date,
        report.owned,
        report.judged,
        report.usable,
    )
    return report


def _rows_this_leg_owns(
    path: Path, *, shard: int, shards: int
) -> list[StorySimilarityPair]:
    """The draw, filtered to this leg, in the order it was drawn in.

    Read through the contract rather than by column index, so a draw written by a
    build that had one more column is refused here rather than judged under a
    shifted reading of what the score was.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist, so this leg has nothing to judge. The scoring "
            "stage writes it, and a leg that ran before it has nothing to read"
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [StorySimilarityPair.from_csv_row(cells) for cells in csv.DictReader(handle)]
    beyond = sorted({row.shard for row in rows if row.shard >= shards})
    if beyond:
        raise ValueError(
            f"{path.name} was drawn for more legs than this run has: it carries "
            f"shard(s) {beyond} and this run judges {shards}. Those pairs would never "
            "be read and the day would fold as though they had never been drawn"
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
    drawn: StorySimilarityPair, verdicts: judge.Judged, *, judge_model: str
) -> StorySimilarityPair:
    """The drawn row with the eight judging columns filled in.

    Rebuilt through the contract rather than copied, so the rule that a verdict
    arrives with the judge that produced it is applied to what this leg wrote
    rather than to what the draw already carried.
    """
    return StorySimilarityPair.model_validate(
        drawn.model_dump(mode="json")
        | {
            "verdict": verdicts.verdict.value,
            "verdict_swapped": verdicts.verdict_swapped.value,
            "usable": verdicts.usable,
            "first_token_margin": verdicts.first_token_margin,
            "judge_model": judge_model,
            "prompt_digest": prompt.prompt_digest(),
            "grammar_digest": prompt.grammar_digest(),
            "decode_seconds": verdicts.decode_seconds,
        }
    )


def _as_csv(rows: list[StorySimilarityPair]) -> str:
    """The leg's whole file, header first, written even when the leg judged nothing.

    An empty file with a header is what says the leg ran and found no pair it
    owned. A missing file says the leg died, and the fold refuses a day that is
    missing one - so the two have to look different.
    """
    columns = StorySimilarityPair.csv_columns()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.csv_row())
    return buffer.getvalue()
