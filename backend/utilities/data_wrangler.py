"""Look at the training corpus, split its holdout, repair it, and fill it.

Five verbs and no sixth. Routine data movement is not here: the harvest and the
roll run in CI on a schedule, where a failure has an alarm on it, and a local
utility has none. What this owns is the work a person does deliberately, before
or after a training session.

    python backend/utilities/data_wrangler.py stats
    python backend/utilities/data_wrangler.py split --holdout-days 14
    python backend/utilities/data_wrangler.py verify
    python backend/utilities/data_wrangler.py verify --tokens
    python backend/utilities/data_wrangler.py backfill --items-dir <dir>
    python backend/utilities/data_wrangler.py remove --url-key <sha256>

`backfill` is the one that means a corpus does not have to start empty and fill
at one day a week. It replays a finished run's `items-*` artifact through the
same harvest the schedule runs, so a backfilled row and a harvested row are the
same bytes.

`verify --tokens` is the one subcommand that reaches the network, and it is here
rather than in a test for that reason (Rule #7). It downloads the tokenizer named
by `models.<role>.hf_base_repo` and answers the question a session needs before
it spends an hour and a half: do these rows fit `finetune.sequence_length`?
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from idhazh import config, corpus, summarize
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.corpus import CorpusRow

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
#: What a table is padded to. A number nobody can line up is a number nobody reads.
_WIDTH: Final = 26


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
    return remove(args.corpus_dir, settings, url_keys=args.url_key, yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
