"""Look at the training corpus, split its holdout, repair it, and fill it.

Six verbs and no seventh. Routine data movement is not here: the harvest and the
roll run in CI on a schedule, where a failure has an alarm on it, and a local
utility has none. What this owns is the work a person does deliberately, before
or after a training session.

    python backend/utilities/data_wrangler.py stats
    python backend/utilities/data_wrangler.py split --holdout-days 14
    python backend/utilities/data_wrangler.py verify
    python backend/utilities/data_wrangler.py verify --tokens
    python backend/utilities/data_wrangler.py backfill --items-dir <dir>
    python backend/utilities/data_wrangler.py refill --limit 200
    python backend/utilities/data_wrangler.py remove --url-key <sha256>

`backfill` and `refill` are the two that mean a corpus does not have to start
empty and fill at one run a week. They differ in where the article body comes
from, and that is the only way they differ:

- `backfill` replays a finished run's `items-*` artifact. The body is the exact
  text the scorer read, so a backfilled row and a harvested row are the same
  bytes. It reaches only as far back as the artifact retention.
- `refill` re-fetches the source address the ledger recorded. It reaches every
  day the repository still remembers, at the cost of a network round trip per
  item and of dropping whatever the open web no longer serves.

`refill` and `verify --tokens` are the two subcommands that reach the network,
and they are here rather than in a test for that reason (Rule #7). `verify
--tokens` downloads the tokenizer named by `models.<role>.hf_base_repo` and
answers the question a session needs before it spends an hour and a half: do
these rows fit `finetune.sequence_length`?
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final, NamedTuple

from idhazh import assemble, cli, config, corpus, extract, summarize, tag
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.corpus import CorpusMeta, CorpusRow
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier
from idhazh.evals import archive, writer
from idhazh.ledger import STATE_DIRNAME

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
#: What a table is padded to. A number nobody can line up is a number nobody reads.
_WIDTH: Final = 26
#: How often a long re-fetch commits what it has rebuilt, and says so. The window
#: is rewritten whole each time, so this trades disk against work lost to a
#: interruption. Measured 2026-08-29: a fetch is 1.36 s and the rewrite of a
#: 2000-row window is far under that, so 25 costs well below one percent and
#: bounds the loss at about 30 seconds.
_COMMIT_EVERY: Final = 25


def _quantile(values: Sequence[int], fraction: float) -> int:
    """The value at `fraction` of a sorted series. Nearest-rank, so it is a real row."""
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def _spread(label: str, values: Sequence[int]) -> str:
    if not values:
        return f"{label:<{_WIDTH}} none"
    return (
        f"{label:<{_WIDTH}} min {min(values)}, median {_quantile(values, 0.5)}, "
        f"p90 {_quantile(values, 0.9)}, max {max(values)}, n={len(values)}"
    )


def _load(corpus_dir: Path) -> list[CorpusRow]:
    rows = corpus.read_rows(corpus_dir)
    if not rows:
        print(f"{corpus.rows_path(corpus_dir).as_posix()} holds no rows")
    return rows


def stats(corpus_dir: Path, settings: config.Settings) -> int:
    """What is in the window, and whether it is still the pipeline's window.

    Printed before a session, because the two ways a session is wasted are
    training on 400 rows while believing there were 4000, and training on rows
    the prompt has moved out from under.
    """
    rows = _load(corpus_dir)
    meta = corpus.read_meta(corpus_dir)
    holdout = corpus.read_holdout(corpus_dir)
    finetune = settings.app.finetune

    print(f"{'rows':<{_WIDTH}} {len(rows)} of a {finetune.corpus_rows}-row window")
    print(f"{'dates':<{_WIDTH}} {meta.first_date or '-'} to {meta.last_date or '-'}")
    print(f"{'last harvested':<{_WIDTH}} {meta.harvested_date or 'never'}")
    print(f"{'last pruned':<{_WIDTH}} {meta.pruned_date or 'never'}")
    print(_spread("source words", [row.source_words for row in rows]))
    print(_spread("target characters", [len(row.assistant) for row in rows]))

    trainable = [row for row in rows if row.url_key not in holdout]
    drawn = min(finetune.train_rows, len(trainable))
    print(f"{'held out':<{_WIDTH}} {len(rows) - len(trainable)}")
    print(
        f"{'a session would draw':<{_WIDTH}} {drawn} "
        f"(train_rows {finetune.train_rows} is a ceiling, not a demand)"
    )
    if len(rows) < finetune.min_rows:
        print(f"below finetune.min_rows ({finetune.min_rows}) - nothing should train on this")

    for label, counts in (("vertical", meta.verticals), ("model", meta.models)):
        for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
            share = 100 * count / len(rows) if rows else 0.0
            print(f"  {label} {name:<20} {count:>5}  {share:5.1f}%")

    live = derive_text_digest(summarize.prompt_inputs(settings.app.summarize))
    if meta.prompt_digest is None:
        print("the window records no prompt digest, so it predates this check")
    elif meta.prompt_digest != live:
        print(
            f"the prompt has moved since this window was harvested "
            f"({meta.prompt_digest[:12]} -> {live[:12]}): these rows train a prompt "
            "production no longer sends"
        )
    return 0


def split(corpus_dir: Path, settings: config.Settings, *, holdout_days: int | None) -> int:
    """Hold out the trailing days, by date and never at random.

    Production always runs on tomorrow's news. A random split puts the same story
    from three feeds on both sides of the line and then reports memorisation as
    success.

    Only `url_key` values are written, so no article text leaves the window.
    """
    rows = _load(corpus_dir)
    if not rows:
        return 1
    days = holdout_days if holdout_days is not None else settings.app.finetune.holdout_days
    dates = sorted({row.date for row in rows})
    cut = dates[-days:] if days < len(dates) else dates
    held = sorted({row.url_key for row in rows if row.date in cut})

    path = corpus.holdout_path(corpus_dir)
    path.write_text("".join(f"{key}\n" for key in held), encoding="ascii", newline="\n")
    print(f"held out {len(held)} of {len(rows)} rows over {len(cut)} of {len(dates)} days")
    print(f"trailing days: {cut[0]} to {cut[-1]}")
    print(f"wrote {path.as_posix()}")
    if len(held) == len(rows):
        print("every row is held out - the window is shorter than finetune.holdout_days")
    return 0


def verify(corpus_dir: Path, settings: config.Settings, *, tokens: bool) -> int:
    """Catch a corrupt window before a session spends two hours on it.

    The offline half is the escaping rule of the format: one physical line per
    row, every line loading, and the file re-serializing to the bytes it already
    holds. The `--tokens` half needs a tokenizer, which needs the network.
    """
    path = corpus.rows_path(corpus_dir)
    if not path.is_file():
        print(f"{path.as_posix()} does not exist")
        return 1

    raw = path.read_bytes()
    problems: list[str] = []
    if b"\r\n" in raw:
        problems.append("the file carries CRLF line endings, so a reader will see a stray \\r")
    if raw and not raw.endswith(b"\n"):
        problems.append("the last row has no newline, so an append would join two rows")

    lines = raw.decode("utf-8").splitlines()
    rows: list[CorpusRow] = []
    for number, line in enumerate(lines, start=1):
        try:
            rows.append(corpus.from_line(line))
        except Exception as error:
            # The report IS the product here: one bad line must not hide the rest.
            problems.append(f"line {number} does not load: {type(error).__name__}: {error}")

    if len(rows) == len(lines):
        rewritten = "".join(corpus.to_line(row) for row in rows)
        if rewritten.encode("utf-8") != raw:
            problems.append("the file does not re-serialize to its own bytes")

    keys = [row.url_key for row in rows]
    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} rows share a url_key with another row")

    holdout = corpus.read_holdout(corpus_dir)
    overlap = holdout & set(keys[: len(keys)])
    trainable = [row for row in rows if row.url_key not in holdout]
    print(f"{'lines':<{_WIDTH}} {len(lines)}")
    print(f"{'rows that load':<{_WIDTH}} {len(rows)}")
    print(f"{'held out':<{_WIDTH}} {len(overlap)} present, {len(trainable)} trainable")

    if tokens:
        problems.extend(_token_report(rows, settings))

    for problem in problems:
        print(f"PROBLEM: {problem}")
    print("verified" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


def _token_report(rows: Sequence[CorpusRow], settings: config.Settings) -> list[str]:
    """How long these rows really are, measured with the tokenizer that will read them.

    `finetune.sequence_length` is derived from a worst case in words. This is the
    check that the derivation still holds, and it is the one thing a session
    cannot find out cheaply once it has started.
    """
    role = settings.app.finetune.teacher
    base = getattr(settings.app.models, role).hf_base_repo
    if not base:
        return [f"models.{role}.hf_base_repo is not set, so there is no tokenizer to load"]
    try:
        from tokenizers import Tokenizer
    except ImportError:  # pragma: no cover - tokenizers is a declared dependency
        return ["tokenizers is not installed"]

    print(f"{'tokenizer':<{_WIDTH}} {base}")
    tokenizer = Tokenizer.from_pretrained(base)
    lengths = [
        sum(
            len(tokenizer.encode(turn.content, add_special_tokens=False).ids)
            for turn in row.messages
        )
        for row in rows
    ]
    print(_spread("tokens per row", lengths))

    ceiling = settings.app.finetune.sequence_length
    over = [length for length in lengths if length > ceiling]
    print(f"{'over sequence_length':<{_WIDTH}} {len(over)} of {len(lengths)} at {ceiling}")
    if over:
        return [
            f"{len(over)} rows are longer than finetune.sequence_length ({ceiling}); "
            f"the longest is {max(over)} tokens and would be silently truncated"
        ]
    return []


def backfill(corpus_dir: Path, settings: config.Settings, *, items_dir: Path) -> int:
    """Replay a finished run's items artifact into the window, today.

    The scheduled harvest only fires every `finetune.harvest_every_days`, and it
    only ever sees the run it is part of - so a corpus starts empty and fills at
    one day a week. This is the same harvest pointed at a directory somebody
    downloaded, which is what turns "wait a week for the first rows" into "have
    them now".

    It reads the exact three payloads the live harvest reads and calls the exact
    same function, so a backfilled row and a harvested row are the same bytes.
    Nothing is re-fetched: the premise is the text the scorer really read, and
    re-fetching the address would return a different article.

    Get a directory with:

        gh run download <run-id> --repo <owner/repo> --pattern 'items-*' --dir <dir>

    `items-*` carries a 1-day retention, so this reaches the last day or two of
    runs and no further. `evidence-*` lives 14 days but carries neither
    `source_form` nor `brief` nor the key points, so a row rebuilt from it would
    have a system prompt that is a guess - which is the one thing this corpus
    exists to make impossible.
    """
    if not items_dir.is_dir():
        print(f"{items_dir.as_posix()} is not a directory")
        return 1

    scored = corpus.scored_from_items(items_dir)
    if not scored:
        print(f"no complete items under {items_dir.as_posix()}")
        return 1

    before = len(corpus.read_rows(corpus_dir))
    finetune = settings.app.finetune
    meta = corpus.harvest(
        corpus_dir,
        scored,
        date=_newest_date(scored),
        finetune=finetune,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    print(f"{'items read':<{_WIDTH}} {len(scored)}")
    print(f"{'rows before':<{_WIDTH}} {before}")
    print(f"{'rows now':<{_WIDTH}} {meta.rows} of a {finetune.corpus_rows}-row window")
    print(f"{'days covered':<{_WIDTH}} {meta.first_date or '-'} to {meta.last_date or '-'}")
    for name, count in sorted(meta.verticals.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  vertical {name:<20} {count:>5}")
    if meta.rows < finetune.min_rows:
        print(f"still {finetune.min_rows - meta.rows} short of finetune.min_rows")
    return 0


def _newest_date(scored: Sequence[corpus.Scored]) -> str:
    """The fallback date for an item with no eval row.

    Every row that survives the filter is dated by its own eval row, so this only
    ever labels an item the filter is about to drop. It is the newest date in the
    batch rather than today, so a replay of an old run cannot stamp old work with
    the day somebody happened to run the replay.
    """
    dates = sorted(item.row.date for item in scored if item.row is not None)
    return dates[-1] if dates else "1970-01-01"


# --- refill ----------------------------------------------------------------


class _Entry(NamedTuple):
    """What one committed digest item contributes to a rebuild."""

    published: corpus.Published
    source_id: str
    source_form: SourceForm
    published_at: str | None


class _Rebuildable(NamedTuple):
    """One item the ledger and the committed digest agree on, ready to re-fetch."""

    recorded: EvalRow
    entry: _Entry


def _ledger_rows(state_dir: Path) -> list[EvalRow]:
    """Every scored row the committed ledger holds, across every month shard.

    An empty CSV cell is dropped rather than passed as an empty string, so an
    optional column that was blank when the row was written reads back as the
    default it was written with instead of failing validation.
    """
    return [
        EvalRow.model_validate({key: value for key, value in raw.items() if value != ""})
        for raw in writer.records(state_dir)
    ]


def _digest_items(digest_root: Path) -> dict[str, _Entry]:
    """The assistant turn for every published item, keyed by `item_id`.

    An item with no title or no summary contributes nothing a row could teach,
    so it never enters the map and is counted as unjoinable rather than as a
    fetch that failed.
    """
    found: dict[str, _Entry] = {}
    for path in cli.published_days(digest_root):
        day = DigestDay.from_json(path.read_text(encoding="utf-8"))
        for item in day.items:
            if not item.title or not item.summary:
                continue
            found[item.item_id] = _Entry(
                published=corpus.Published(
                    title=item.title,
                    summary=item.summary,
                    key_points=tuple(item.key_points),
                ),
                source_id=item.source_id,
                source_form=item.source_form,
                published_at=item.published_at,
            )
    return found


def _planned(candidate: _Rebuildable, *, tiers: dict[str, SourceTier]) -> PlannedItem:
    """The plan entry the extractor needs, rebuilt from what the run recorded.

    `rank_score` is zero because ranking already chose this item once and cannot
    reach the prompt - `summarize.user_turn` reads the source form, the title and
    the body, and nothing else. The tier is looked up so the payload is
    well-formed, and falls back to the weakest tier for a source that has since
    been retired out of `config/sources.json`.

    `canonical_url` is the ledger's `source_url` because that column IS the
    canonical address: `evals.score.to_eval_row` writes `item.canonical_url`
    into it. The caller has already checked that it still derives the row's
    `url_key`, which is the identity `extract` refuses to proceed without.
    """
    row, entry = candidate
    return PlannedItem(
        item_id=row.item_id,
        url_key=row.url_key,
        source_url=row.source_url,
        canonical_url=row.source_url,
        source_id=entry.source_id,
        tier=tiers.get(entry.source_id, SourceTier.COMMUNITY),
        source_form=entry.source_form,
        vertical=row.vertical,
        title=row.title,
        published_at=entry.published_at,
        rank_score=0.0,
    )


def _commit(
    corpus_dir: Path, batch: Sequence[corpus.Scored], *, settings: config.Settings
) -> CorpusMeta:
    """Fold one batch of rebuilt rows into the window, through the shipped harvest.

    Called every `_COMMIT_EVERY` items rather than once at the end, because a
    re-fetch of the whole ledger runs for tens of minutes and holding it all in
    memory means an interruption throws every fetch away. `corpus.write` is
    temp-file-plus-rename, so a batch either lands whole or not at all, and the
    roll deduplicates by `url_key` - which is what lets the next run skip what
    this one already committed (`CLAUDE.md` section 1a).
    """
    return corpus.harvest(
        corpus_dir,
        batch,
        date=_newest_date(batch),
        finetune=settings.app.finetune,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )


def refill(
    corpus_dir: Path,
    settings: config.Settings,
    *,
    state_dir: Path,
    digest_root: Path,
    limit: int | None,
    read_url: cli.Fetcher | None = None,
) -> int:
    """Rebuild rows from the source address, for runs whose artifacts have expired.

    `backfill` can only reach a run whose `items-*` artifact still exists, which
    is the last few days. This reaches every day the repository still remembers,
    because the committed ledger and the committed digest hold between them every
    half of a training row except the article body - and the body has an address.

    Nothing is assumed about the page that answers. The body is re-extracted
    through the extractor a run uses, so `brief`, the source form and the length
    band are computed rather than guessed, and `corpus.rescored` measures every
    counterweight again against that body. An article edited past its summary
    fails the same gate a live run applies; an article that has moved, gone
    behind a paywall or started refusing robots is dropped and counted.

    The join is checked and not assumed. `output_digest` covers exactly the
    title, the summary and the key points, so a digest entry is paired with a
    ledger row only when it recomputes to the value that row recorded.

    A pair the run itself rejected is dropped before the fetch, on both counts
    that matter. It saves the round trip, and it is the more correct answer: the
    only way such a pair could pass on re-measurement is if the page changed
    under it, and a row that needs the article to have moved is not a row worth
    teaching.

    **How far back it reaches is now a configured number.** Every candidate comes
    from a ledger row, and `state/scores/` keeps
    `observability.scores_full_grain_months` months of rows before a month
    becomes a summary. A summarised month carries no address and no digest, so
    there is nothing to re-fetch and nothing to join - those months are counted
    and named rather than left as a gap in the ledger count above.
    """
    summarised = archive.archived_months(state_dir)
    if not writer.ledger_shards(state_dir):
        where = (state_dir / writer.LEDGER_DIRNAME).as_posix()
        if summarised:
            print(
                f"{where} holds no month shard - {', '.join(summarised)} have aged out of "
                f"the full-grain window and a summary carries no address to re-fetch. "
                f"{archive.RAW_WINDOW_NOTE}"
            )
        else:
            print(f"{where} holds no month shard")
        return 1
    if not digest_root.is_dir():
        print(f"{digest_root.as_posix()} is not a directory")
        return 1

    finetune = settings.app.finetune
    held = corpus.read_rows(corpus_dir)
    before = len(held)
    have = {row.url_key for row in held}
    entries = _digest_items(digest_root)
    recorded = _ledger_rows(state_dir)

    candidates: list[_Rebuildable] = []
    claimed: set[str] = set()
    counts: Counter[str] = Counter()
    for row in sorted(recorded, key=lambda item: item.date, reverse=True):
        if row.url_key in have or row.url_key in claimed:
            counts["already in the window"] += 1
            continue
        entry = entries.get(row.item_id)
        if entry is None:
            counts["no published item"] += 1
            continue
        if not corpus.published_is_the_scored_one(entry.published, recorded=row):
            counts["published output is a different one"] += 1
            continue
        if not corpus.keeps_its_counterweights(row, evaluation=settings.app.evaluation):
            counts["the run that made it already rejected it"] += 1
            continue
        if derive_url_key(row.source_url) != row.url_key:
            counts["address no longer proves its identity"] += 1
            continue
        claimed.add(row.url_key)
        candidates.append(_Rebuildable(recorded=row, entry=entry))

    room = max(0, finetune.corpus_rows - before)
    wanted = room if limit is None else min(limit, room)
    queued = candidates[:wanted]

    print(f"{'ledger rows':<{_WIDTH}} {len(recorded)}")
    if summarised:
        print(f"{'months aged out':<{_WIDTH}} {', '.join(summarised)} - no row to re-fetch")
    print(f"{'rows before':<{_WIDTH}} {before}")
    for reason, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  skipped {reason:<38} {count:>5}")
    print(f"{'rebuildable':<{_WIDTH}} {len(candidates)}")
    print(f"{'queued to re-fetch':<{_WIDTH}} {len(queued)} (window has room for {room})")
    if not queued:
        return 0

    read = read_url or cli.live_fetcher(settings)
    tiers = {feed.id: feed.tier for feed in settings.sources.feeds}
    meta = corpus.read_meta(corpus_dir)
    pending: list[corpus.Scored] = []
    rebuilt = 0
    dropped: Counter[str] = Counter()
    for index, candidate in enumerate(queued, start=1):
        item = _planned(candidate, tiers=tiers)
        article, full_text = extract.to_article_with_source(
            item,
            read(item.canonical_url),
            config=settings.app.extract,
            fetched_at=assemble.utc_now(),
        )
        if article.status is not ArticleStatus.OK:
            code = article.failure_code.value if article.failure_code else article.status.value
            dropped[code] += 1
        else:
            article = tag.tagged(
                article, taxonomy=settings.taxonomy, watchlist=settings.watchlist
            )
            pending.append(
                corpus.rescored(
                    article,
                    full_text,
                    recorded=candidate.recorded,
                    published=candidate.entry.published,
                )
            )
        if index % _COMMIT_EVERY == 0 or index == len(queued):
            rebuilt += len(pending)
            if pending:
                meta = _commit(corpus_dir, pending, settings=settings)
                pending = []
            print(f"  ... {index}/{len(queued)} fetched, {meta.rows} rows committed")

    print(f"{'bodies re-fetched':<{_WIDTH}} {rebuilt} of {len(queued)}")
    for reason, count in sorted(dropped.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  no body {reason:<38} {count:>5}")
    print(f"{'rows now':<{_WIDTH}} {meta.rows} of a {finetune.corpus_rows}-row window")
    print(f"{'days covered':<{_WIDTH}} {meta.first_date or '-'} to {meta.last_date or '-'}")
    for name, count in sorted(meta.verticals.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  vertical {name:<20} {count:>5}")
    if meta.rows < finetune.min_rows:
        print(f"still {finetune.min_rows - meta.rows} short of finetune.min_rows")
    return 0


def remove(
    corpus_dir: Path, settings: config.Settings, *, url_keys: Sequence[str], yes: bool
) -> int:
    """Drop named rows, after saying which ones and how far below the floor it lands."""
    rows = _load(corpus_dir)
    if not rows:
        return 1
    targets = set(url_keys)
    doomed = [row for row in rows if row.url_key in targets]
    missing = targets - {row.url_key for row in doomed}
    for key in sorted(missing):
        print(f"no row holds url_key {key}")
    if not doomed:
        return 1

    for row in doomed:
        print(
            f"would remove {row.url_key[:12]} {row.date} {row.vertical} "
            f"({row.source_words} words)"
        )

    floor = settings.app.finetune.min_rows
    remaining = len(rows) - len(doomed)
    if remaining < floor:
        print(
            f"refusing: this would leave {remaining} rows, "
            f"{floor - remaining} below finetune.min_rows ({floor})"
        )
        return 1
    if not yes:
        print(f"{len(doomed)} rows would go, leaving {remaining}. Re-run with --yes to do it.")
        return 0

    kept = [row for row in rows if row.url_key not in targets]
    meta = corpus.census(
        kept,
        previous=corpus.read_meta(corpus_dir),
        prompt_digest=derive_text_digest(summarize.prompt_inputs(settings.app.summarize)),
    )
    corpus.write(corpus_dir, kept, meta)
    print(f"removed {len(doomed)} rows, {len(kept)} remain")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=REPO_ROOT / corpus.CORPUS_ROOT_RELPATH,
        help="The training window. Never the hand-authored reference set.",
    )
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    verbs = parser.add_subparsers(dest="verb", required=True)

    verbs.add_parser("stats", help="What the window holds, and whether the prompt moved.")

    holdout = verbs.add_parser("split", help="Write the trailing-days holdout.")
    holdout.add_argument(
        "--holdout-days",
        type=int,
        default=None,
        help="Defaults to finetune.holdout_days.",
    )

    checked = verbs.add_parser("verify", help="Escaping, line count, and optionally tokens.")
    checked.add_argument(
        "--tokens",
        action="store_true",
        help="Also measure tokens per row. Downloads the base model's tokenizer.",
    )

    filled = verbs.add_parser(
        "backfill", help="Replay a downloaded run's items artifact into the window."
    )
    filled.add_argument(
        "--items-dir",
        type=Path,
        required=True,
        help="A directory holding <item>.article.json and friends, at any nesting.",
    )

    refilled = verbs.add_parser(
        "refill", help="Re-fetch source addresses the ledger remembers. Reaches the network."
    )
    refilled.add_argument(
        "--state",
        type=Path,
        default=REPO_ROOT / STATE_DIRNAME,
        help="The state directory. Its monthly eval shards name every address ever scored.",
    )
    refilled.add_argument(
        "--digest-root",
        type=Path,
        default=REPO_ROOT / assemble.PUBLIC_ROOT,
        help="The committed day payloads. They hold the published summaries.",
    )
    refilled.add_argument(
        "--limit",
        type=int,
        default=None,
        help="How many addresses to re-fetch. Defaults to whatever the window has room for.",
    )

    dropped = verbs.add_parser("remove", help="Drop named rows. Prints first, asks second.")
    dropped.add_argument("--url-key", action="append", default=[], required=True)
    dropped.add_argument("--yes", action="store_true", help="Actually do it.")

    args = parser.parse_args(argv)
    settings = config.load(args.config)

    if args.verb == "stats":
        return stats(args.corpus_dir, settings)
    if args.verb == "split":
        return split(args.corpus_dir, settings, holdout_days=args.holdout_days)
    if args.verb == "verify":
        return verify(args.corpus_dir, settings, tokens=args.tokens)
    if args.verb == "backfill":
        return backfill(args.corpus_dir, settings, items_dir=args.items_dir)
    if args.verb == "refill":
        return refill(
            args.corpus_dir,
            settings,
            state_dir=args.state,
            digest_root=args.digest_root,
            limit=args.limit,
        )
    return remove(args.corpus_dir, settings, url_keys=args.url_key, yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
