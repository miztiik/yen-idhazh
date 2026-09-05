"""Build the training window from what a run just produced, and roll it.

The pipeline scores 600-730 articles a day and then throws the pair away: the
article lives in a shard checkout that is deleted when the job ends, and the
committed ledger keeps only digests. This module is what keeps a sample of those
pairs, because they are training data for the exact job we run.

**It composes; it never writes a second copy of anything.** The three turns come
from `idhazh.summarize` by CALLING the functions the run itself calls -
`system_prompt` for the system turn and `user_turn` for the article - rather than
by rebuilding an approximation of them. That is the whole oracle: a corpus built
from the prompt builder cannot train on a prompt we do not serve, and there is no
token diff to run because there is nothing to diff. When the prompt moves, the
rows harvested after it move with it and `CorpusMeta.prompt_digest` says which
side of the move a file is on.

**The assistant turn is the published output, re-validated through the decoder's
own rail.** `draft_model` is the shape the constrained decoder is held to, so a
row that would not survive it is dropped rather than taught: a target the
decoder would reject teaches the model to be rejected. Its field order is the
order the grammar emits, so the target is spelled the way the model has to spell
it - which `canonical_json`'s sorted keys would have silently reversed.

**The roll is the part that can lose data, so it is a pure function.** It takes
the rows it has and the rows it was given and returns the rows to keep. It opens
no file, and it names only `corpus/corpus.jsonl` when a caller writes what it
returns - which is what keeps it structurally unable to reach the hand-authored
reference set under `tests/fixtures/reference/`.

**Serialization is the repository's, not the format's.** `compact_json` escapes
non-ASCII, exactly as every other persisted payload here does, so the corpus
diffs and round-trips under the same rule as the digest. The plan that asked for
this preferred raw UTF-8 for its byte count; the difference survives gzip almost
entirely, and one serialization convention is worth more than that.

**A row can also be rebuilt from the address, once the artifact has expired.**
`rescored` pairs the published summary with the body a re-fetch just returned,
and measures every counterweight again against that body rather than trusting
the numbers the ledger recorded against a body this process never saw. That is
what makes the rebuild safe on a page that has been edited since: a summary the
article no longer supports now fails the same gate a live run applies, so it is
dropped instead of taught.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from datetime import date as _day
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import ValidationError

from idhazh import assemble, summarize
from idhazh.contracts.app_config import EvaluationConfig, FinetuneConfig, SummarizeConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import compact_json, derive_output_digest, derive_text_digest
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals import metrics

LOG: Final = logging.getLogger(__name__)

#: Relative and POSIX-separated, because these are quoted in logs, in two
#: workflows and in the operator how-to (`CLAUDE.md` section 2).
CORPUS_ROOT_RELPATH: Final = "corpus"
ROWS_FILENAME: Final = "corpus.jsonl"
META_FILENAME: Final = "corpus.meta.json"
HOLDOUT_FILENAME: Final = "holdout.txt"


def rows_path(corpus_dir: Path) -> Path:
    return corpus_dir / ROWS_FILENAME


def meta_path(corpus_dir: Path) -> Path:
    return corpus_dir / META_FILENAME


def holdout_path(corpus_dir: Path) -> Path:
    return corpus_dir / HOLDOUT_FILENAME


# --- Serialization ---------------------------------------------------------


def to_line(row: CorpusRow) -> str:
    """One row as one physical line, newline included.

    `compact_json` sorts keys and escapes every control character, so a title
    carrying a newline, a tab or a lone quote cannot break the line in two.
    """
    return compact_json(row.model_dump(mode="json"))


def from_line(line: str) -> CorpusRow:
    return CorpusRow.from_json(line)


def read_rows(corpus_dir: Path) -> list[CorpusRow]:
    """Every row in the window. A missing file is an empty window, not an error."""
    path = rows_path(corpus_dir)
    if not path.is_file():
        return []
    return [
        from_line(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_meta(corpus_dir: Path) -> CorpusMeta:
    """The committed census and schedule state, or a fresh one when there is none."""
    path = meta_path(corpus_dir)
    if not path.is_file():
        return CorpusMeta(version=CorpusMeta.schema_version())
    return CorpusMeta.from_json(path.read_text(encoding="utf-8"))


def read_holdout(corpus_dir: Path) -> frozenset[str]:
    """The url_keys never trained on. A missing file is an empty holdout."""
    path = holdout_path(corpus_dir)
    if not path.is_file():
        return frozenset()
    return frozenset(
        line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def census(rows: Sequence[CorpusRow], *, previous: CorpusMeta, prompt_digest: str) -> CorpusMeta:
    """Recount the window from the window. Never incremented, so it cannot drift."""
    dates = sorted(row.date for row in rows)
    verticals: dict[str, int] = {}
    models: dict[str, int] = {}
    for row in rows:
        verticals[row.vertical] = verticals.get(row.vertical, 0) + 1
        models[row.model_id] = models.get(row.model_id, 0) + 1
    return previous.model_copy(
        update={
            "version": CorpusMeta.schema_version(),
            "rows": len(rows),
            "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
            "verticals": dict(sorted(verticals.items())),
            "models": dict(sorted(models.items())),
            "prompt_digest": prompt_digest,
        }
    )


# --- The due checks --------------------------------------------------------


def _days_between(earlier: str, later: str) -> int:
    return (_day.fromisoformat(later) - _day.fromisoformat(earlier)).days


def harvest_is_due(meta: CorpusMeta, *, date: str, every_days: int) -> bool:
    """Whether the run for `date` should harvest.

    A corpus that has never been harvested is always due. Otherwise the gap is
    counted in days between two committed date strings, so the answer does not
    depend on when the job happened to wake or on which clock it read.
    """
    if meta.harvested_date is None:
        return True
    return _days_between(meta.harvested_date, date) >= every_days


def prune_is_due(meta: CorpusMeta, *, date: str, every_days: int) -> bool:
    """Whether `prune.yml` should squash today.

    A repository that has never been pruned is due the first time this is asked,
    which is why the stamp is written even when the squash finds nothing to do -
    without it the check fires again tomorrow, and every day after that.
    """
    if meta.pruned_date is None:
        return True
    return _days_between(meta.pruned_date, date) >= every_days


# --- The harvest -----------------------------------------------------------


class Scored(NamedTuple):
    """One item's three payloads, as the run left them in `items/`."""

    article: Article
    summary: Summary
    row: EvalRow | None


def scored_from_items(items_dir: Path) -> list[Scored]:
    """Every complete item under a run's items directory, in a stable order.

    Recursive, because the same directory arrives in two shapes. A live run has
    one flat directory; a downloaded artifact set arrives as one subdirectory per
    shard, and both are the same run. `rglob` reads them identically, the way
    `evals.evidence.index` already reads a downloaded evidence package.

    The directory is the record of what was worked, so nothing here reads the run
    plan. That is what lets a backfill replay a finished run from its artifacts
    alone, months after the plan artifact expired.
    """
    found: list[Scored] = []
    for path in sorted(items_dir.rglob("*.article.json")):
        item_id = path.name.removesuffix(".article.json")
        summary_path = path.with_name(f"{item_id}.summary.json")
        if not summary_path.is_file():
            continue
        eval_path = path.with_name(f"{item_id}.eval.json")
        found.append(
            Scored(
                article=Article.read(path),
                summary=Summary.read(summary_path),
                row=(
                    EvalRow.read(eval_path)
                    if eval_path.is_file()
                    else None
                ),
            )
        )
    return found


# --- Rebuilding one item from its address ----------------------------------


class Published(NamedTuple):
    """One item's assistant turn, as the committed digest holds it."""

    title: str
    summary: str
    key_points: tuple[str, ...]


def published_is_the_scored_one(published: Published, *, recorded: EvalRow) -> bool:
    """Does this published item prove it is the output the ledger row scored?

    `output_digest` is taken over exactly the title, the summary and the key
    points, so recomputing it here is a real join check rather than a plausible
    one. A digest payload and an eval row can share a `url_key` and still be two
    different summaries of one article - a re-run makes that ordinary - and
    pairing the wrong one with a re-fetched body would teach a summary nobody
    ever published.
    """
    recomputed = derive_output_digest(
        published.summary, list(published.key_points), title=published.title
    )
    return recomputed == recorded.output_digest


def rescored(
    article: Article, full_text: str, *, recorded: EvalRow, published: Published
) -> Scored:
    """One item measured again, against the body a re-fetch just returned.

    Every counterweight is measured here rather than read off `recorded`, and
    that is the entire reason this function exists. The recorded numbers scored
    a body this process has not seen. A page edited since would keep a coverage
    figure that waves through a summary its own article no longer supports, so
    re-measuring is what lets `keeps_its_counterweights` judge the exact pair the
    row is about to teach.

    `determinism_violation` is the one measure carried across untouched. It is a
    property of two decodes of one prompt rather than of the text, so a re-fetch
    learns nothing new about it, and recomputing it as False would silently
    un-fail an item the run had already caught.

    The row it returns is a gate input and never a ledger row: `hhem` and its two
    companions still describe the old body, because nothing here can rescore
    faithfulness without the model. Writing this row to `state/scores.csv` would
    put a stale faithfulness score under a fresh `source_digest`.
    """
    text = published.summary
    row = EvalRow.model_validate(
        {
            **recorded.model_dump(mode="json"),
            "coverage": metrics.lead_coverage(text, full_text),
            "compression": metrics.compression(text, full_text),
            "extractiveness": metrics.extractiveness(text, full_text),
            "verbatim_run": metrics.verbatim_run(text, full_text),
            "unsupported_numbers": metrics.unsupported_numbers(text, full_text),
            "hedge_dropped": metrics.hedge_dropped(text, full_text),
            "self_repetition": metrics.self_repetition(text),
            "evidential_density": metrics.evidential_density(full_text),
            "speculative_density": metrics.speculative_density(full_text),
            "summary_word_count": metrics.word_count(text),
            "truncation_flagged": article.truncated,
            "source_word_count": article.source_word_count,
            "source_seen_word_count": article.word_count,
            "source_digest": derive_text_digest(article.text or ""),
        }
    )
    summary = Summary(
        version=Summary.schema_version(),
        item_id=recorded.item_id,
        url_key=recorded.url_key,
        title=published.title,
        summary=text,
        key_points=list(published.key_points),
        pipeline_fingerprint=recorded.pipeline_fingerprint,
        output_digest=recorded.output_digest,
        model_id=recorded.model_id,
        attempt=recorded.attempt,
        source_truncated=article.truncated,
        generated_at=recorded.scored_at,
        status=SummaryStatus.OK,
    )
    return Scored(article=article, summary=summary, row=row)


def _target(
    summary: Summary,
    *,
    prompt_config: SummarizeConfig,
    evaluation: EvaluationConfig,
) -> str | None:
    """The assistant turn: the published output, spelled the way the grammar emits it.

    Built through `draft_model` so the row clears the same rail the decoder is
    held to, and dumped in field order rather than in sorted order because field
    order IS decode order - a target that puts the summary before the title
    teaches a sequence the model is not allowed to produce.
    """
    if summary.title is None or summary.summary is None:
        return None
    shape = summarize.draft_model(prompt_config, evaluation)
    try:
        draft = shape(
            title=summary.title,
            summary=summary.summary,
            key_points=list(summary.key_points),
        )
    except ValidationError:
        return None
    return json.dumps(draft.model_dump(), ensure_ascii=False, separators=(", ", ": "))


def keeps_its_counterweights(row: EvalRow, *, evaluation: EvaluationConfig) -> bool:
    """Rejection sampling on the measures a model cannot game by copying.

    Never on the faithfulness score. That scorer is the alarm this project reads
    a run by, and a corpus filtered on it trains a model against its own monitor -
    after which the monitor is measuring something it helped shape.
    """
    return (
        not row.hedge_dropped
        and row.unsupported_numbers == 0
        and not row.extraction_suspect
        and not row.determinism_violation
        and row.coverage >= evaluation.lead_coverage_min
        and row.extractiveness < evaluation.verbatim_reject_ceiling
        and row.compression < evaluation.verbatim_reject_ceiling
    )


def harvest_rows(
    items: Iterable[Scored],
    *,
    date: str,
    prompt_config: SummarizeConfig,
    evaluation: EvaluationConfig,
) -> list[CorpusRow]:
    """The rows one run earned. Pure: no disk, no network, no clock.

    An item is dropped rather than degraded here, because a corpus is a set of
    examples and a bad example is worse than a missing one.

    A row is dated by its own eval row rather than by the `date` argument, which
    is only the fallback for an item that was never scored. That is what lets one
    backfill replay several runs at once and still file every row under the day
    it was really produced.
    """
    harvested: list[CorpusRow] = []
    for scored in items:
        article, summary = scored.article, scored.summary
        if article.status is not ArticleStatus.OK or summary.status is not SummaryStatus.OK:
            continue
        if scored.row is None or not keeps_its_counterweights(
            scored.row, evaluation=evaluation
        ):
            continue
        target = _target(summary, prompt_config=prompt_config, evaluation=evaluation)
        if target is None:
            continue
        system = summarize.system_prompt(
            prompt_config, source_words=article.band_source_words, brief=article.brief
        )
        harvested.append(
            CorpusRow(
                version=CorpusRow.schema_version(),
                messages=[
                    ChatTurn(role=ChatRole.SYSTEM, content=system),
                    ChatTurn(role=ChatRole.USER, content=summarize.user_turn(article)),
                    ChatTurn(role=ChatRole.ASSISTANT, content=target),
                ],
                url_key=article.url_key,
                date=scored.row.date,
                model_id=summary.model_id,
                vertical=article.vertical,
            )
        )
    return harvested


# --- The roll --------------------------------------------------------------


def roll(
    existing: Sequence[CorpusRow], incoming: Sequence[CorpusRow], *, window: int
) -> list[CorpusRow]:
    """The window after one harvest: new rows in, oldest out, one row per article.

    Three properties, and each one is a way the naive version loses data.

    Oldest-first eviction is what pairs with a date-trailing holdout: a held-out
    row is by definition among the newest, so the roll can never quietly shrink
    the test set from underneath a comparison nobody re-checks.

    An article already in the window keeps its ORIGINAL row rather than being
    replaced. A re-run of the same day would otherwise rewrite every row it
    touched, and a corpus that changes when nothing changed cannot be diffed.

    Order is by date and then by url_key, never by arrival, so two runs that
    harvest the same items in a different order write the same file.
    """
    if window < 1:
        raise ValueError("the corpus window must be at least one row")
    seen = {row.url_key for row in existing}
    merged = [*existing, *(row for row in incoming if row.url_key not in seen)]
    merged.sort(key=lambda row: (row.date, row.url_key))
    return merged[-window:] if len(merged) > window else merged


def write(corpus_dir: Path, rows: Sequence[CorpusRow], meta: CorpusMeta) -> None:
    """Both files, each written temp-then-rename.

    An interrupted write can never leave half a training set that still loads
    for its first N lines, and `write_atomic` opens with `newline="\\n"`, which
    is what keeps a corpus written on Windows byte-identical to one written in
    CI.
    """
    corpus_dir.mkdir(parents=True, exist_ok=True)
    assemble.write_atomic(rows_path(corpus_dir), "".join(to_line(row) for row in rows))
    assemble.write_atomic(meta_path(corpus_dir), meta.to_json())


def harvest(
    corpus_dir: Path,
    items: Iterable[Scored],
    *,
    date: str,
    finetune: FinetuneConfig,
    prompt_config: SummarizeConfig,
    evaluation: EvaluationConfig,
) -> CorpusMeta:
    """Read the window, add what this run earned, roll it, and write both files."""
    incoming = harvest_rows(
        items, date=date, prompt_config=prompt_config, evaluation=evaluation
    )
    existing = read_rows(corpus_dir)
    kept = roll(existing, incoming, window=finetune.corpus_rows)
    meta = census(
        kept,
        previous=read_meta(corpus_dir).model_copy(update={"harvested_date": date}),
        prompt_digest=derive_text_digest(summarize.prompt_inputs(prompt_config)),
    )
    write(corpus_dir, kept, meta)
    LOG.info(
        "harvested date=%s offered=%s kept=%s window=%s evicted=%s",
        date,
        len(incoming),
        len(kept),
        finetune.corpus_rows,
        max(0, len(existing) + len(incoming) - len(kept)),
    )
    return meta


def stamp_prune(corpus_dir: Path, *, date: str) -> CorpusMeta:
    """Record that the prune ran, without recounting anything.

    Written even when the squash found nothing older than the boundary. Without
    the stamp the due-check fires again tomorrow and every day after that, which
    is a force-push a day rather than one a month.
    """
    meta = read_meta(corpus_dir).model_copy(
        update={"version": CorpusMeta.schema_version(), "pruned_date": date}
    )
    corpus_dir.mkdir(parents=True, exist_ok=True)
    assemble.write_atomic(meta_path(corpus_dir), meta.to_json())
    return meta
