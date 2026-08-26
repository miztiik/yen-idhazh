"""Measure what the encoder's token cap actually drops, before anyone moves it.

The cap was set to the number the encoder was trained at and never checked
against real text. A character-count proxy said "about 18 percent of items run
over", which is an estimate and may not justify a change on its own (Rule #10).
This tool counts the tokens the encoder itself produces, over every day the
repository has published, and reports the distribution the cap has to answer to.

It also measures what the encoder cannot read. The committed weights carry an
English uncased vocabulary, so an item written in another script still produces
a confident unit vector - one that says more about which characters appeared
than about the story.

Two traps, both found by running this, both worth keeping written down:

1. The committed `tokenizer.json` carries `truncation: 128` and a fixed
   `padding: 128` in the file itself. Ask it how long a text is and every answer
   is 128. `raw_tokenizer` turns both off, which is the only way a length
   measurement means anything.
2. The unknown-token share does NOT detect an unreadable item. The vocabulary
   holds single Devanagari, Arabic and Cyrillic characters as subword pieces, so
   a Hindi sentence tokenises to an unknown share of 0.008 and an Arabic one to
   0.000 - each is spelled out one character at a time and almost no `[UNK]` is
   emitted. What the vocabulary lacks is the WORDS, not the letters. So the
   readable share is measured over letters, not over unknown tokens.

Read-only. It touches no network, writes no payload, and reports counts only -
never the text it counted.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from idhazh.config import REPO_ROOT
from idhazh.contracts.digest_day import DigestDay
from idhazh.embed import TOKENIZER_RELPATH, readable_share, text_for

# Where the pipeline commits a published day. Relative and POSIX, per CLAUDE.md
# section 2.
DIGEST_RELDIR = "frontend/public/digest"

# The caps worth a truncation share. 256 is what the model was trained at and
# what the runner uses today; 512 is the ceiling its position table allows.
REPORTED_CAPS = (128, 256, 320, 384, 448, 512)

# The readable-share cuts worth counting items under, so a threshold is picked
# off the corpus rather than out of the air.
REPORTED_CUTS = (0.25, 0.5, 0.75, 0.9)


def raw_tokenizer(root: Path) -> Any:
    """The tokenizer with truncation and padding both off. See trap 1 above."""
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(root / TOKENIZER_RELPATH))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer


def digest_paths(root: Path) -> list[Path]:
    return sorted((root / DIGEST_RELDIR).glob("*/*/*/digest.json"))


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


def measure_day(path: Path, tokenizer: Any) -> list[dict[str, Any]]:
    day = DigestDay.from_json(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in day.items:
        text = text_for(item)
        rows.append(
            {
                "date": str(day.date),
                "item_id": item.item_id,
                "tokens": len(tokenizer.encode(text).ids),
                "characters": len(text),
                "readable_share": round(readable_share(text), 4),
            }
        )
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = [int(row["tokens"]) for row in rows]
    total = len(counts)
    written = sum(counts)

    def at_cap(cap: int) -> dict[str, Any]:
        dropped = [count - cap for count in counts if count > cap]
        read = sum(min(count, cap) for count in counts)
        return {
            "cap": cap,
            "n_over": len(dropped),
            "share_over": round(len(dropped) / total, 4) if total else 0.0,
            "dropped_p50": percentile(dropped, 0.50),
            "dropped_p95": percentile(dropped, 0.95),
            "dropped_max": max(dropped) if dropped else 0,
            "dropped_mean": round(statistics.fmean(dropped), 1) if dropped else 0.0,
            "tokens_read_share": round(read / written, 4) if written else 0.0,
        }

    # A percentile needs an ordering, so the shares are counted in basis points
    # and divided back afterwards.
    shares = [round(float(row["readable_share"]) * 10000) for row in rows]
    return {
        "n_items": total,
        "n_days": len({row["date"] for row in rows}),
        "tokens": {
            "mean": round(statistics.fmean(counts), 1) if counts else 0.0,
            "stddev": round(statistics.stdev(counts), 1) if len(counts) > 1 else 0.0,
            "min": min(counts) if counts else 0,
            "p50": percentile(counts, 0.50),
            "p90": percentile(counts, 0.90),
            "p95": percentile(counts, 0.95),
            "p99": percentile(counts, 0.99),
            "max": max(counts) if counts else 0,
        },
        "caps": [at_cap(cap) for cap in REPORTED_CAPS],
        "readable_share": {
            "min": (min(shares) / 10000) if shares else 0.0,
            "p01": percentile(shares, 0.01) / 10000,
            "p05": percentile(shares, 0.05) / 10000,
            "p50": percentile(shares, 0.50) / 10000,
            "n_below": {
                str(cut): sum(1 for share in shares if share < cut * 10000) for cut in REPORTED_CUTS
            },
        },
    }


def hardware() -> dict[str, Any]:
    """Rule #10: a number without its hardware and date is not a measurement."""
    return {
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to read committed days and the tokenizer from.",
    )
    parser.add_argument(
        "--longest",
        type=int,
        default=0,
        help="Also print this many of the longest items, so an outlier can be looked at.",
    )
    parser.add_argument(
        "--least-readable",
        type=int,
        default=0,
        help="Also print this many of the least readable items.",
    )
    parser.add_argument(
        "--min-readable",
        type=float,
        default=0.0,
        help=(
            "Drop items below this readable share before summarising, which is the "
            "distribution the cap actually has to answer to once the unreadable ones "
            "stop being embedded."
        ),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paths = digest_paths(root)
    if not paths:
        parser.error(f"no committed days under {DIGEST_RELDIR}")
    tokenizer = raw_tokenizer(root)

    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(measure_day(path, tokenizer))
    kept = [row for row in rows if float(row["readable_share"]) >= args.min_readable]

    report: dict[str, Any] = {
        "hardware": hardware(),
        "days": [path.relative_to(root).as_posix() for path in paths],
        "min_readable": args.min_readable,
        "n_excluded_as_unreadable": len(rows) - len(kept),
        "summary": summarise(kept),
    }
    if args.longest:
        report["longest"] = sorted(rows, key=lambda row: -int(row["tokens"]))[: args.longest]
    if args.least_readable:
        report["least_readable"] = sorted(rows, key=lambda row: float(row["readable_share"]))[
            : args.least_readable
        ]
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
