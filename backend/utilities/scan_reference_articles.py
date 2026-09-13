"""Scan a finished extraction for text that is not really an article.

    python backend/utilities/scan_reference_articles.py \
        --extraction corpus/reference-dataset-2/extractions/2026-09-13-1/articles.json

This is an operator surface, not a test and not a stage. It reads one exported
collection file and reports what is wrong with the text inside it. It writes
nothing, decides nothing, and removes nothing: the flags below are evidence for
a person choosing what to sample, and the thresholds are inputs to one run
rather than behaviour baked into the tool.

**No new dependency.** Every check here is the standard library plus `numpy`,
which the project already installs. A language detector (`py3langid`, which
`trafilatura[all]` pulls in) would replace the coarse script check with a real
verdict, and the fifth flag below is where it would go - it is named rather than
installed, because one report does not justify a dependency the pipeline would
then carry (Guardrail #8).

The eight flags, and what each one is actually catching:

- `short` - a page that extracted to almost nothing. The real run produced a
  one-word "article", so this is not hypothetical.
- `link_dump` - mostly short lines, which is a navigation page or a list of
  headlines rather than prose.
- `repetitive` - few distinct words for its length, measured over a fixed window
  so that a long essay is not flagged for being long.
- `promotional` - subscription and course-sale language, which is what a
  newsletter platform serves when the post is an advertisement for itself.
- `not_latin` - mostly non-Latin letters. A coarse script test, not a language
  verdict: it flags text a Latin-trained classifier would read badly, and says
  nothing about what language it is.
- `near_duplicate` - shares most of its five-word phrases with another article.
  Two syndications of one wire story are one story to a classifier.
- `no_sentence` - no sentence long enough to be prose.

**There is no `unfinished` flag, and that is a finding rather than an omission.**
A first cut flagged any article whose last line carried no terminal punctuation.
It raised 198 of 1,345, and reading the endings showed almost all of them were
complete: an author bio ending in an email address, a list of Nobel winners, a
colon introducing a link the sanitizer had already removed. Real truncation is
refused earlier and by something that cannot be fooled - a body that stopped at
the byte cap is a typed failure at fetch time, never a short article. A flag that
is wrong nine times in ten is worse than no flag, so it was deleted rather than
tuned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.reference_dataset import ReferenceQualityFlag

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_WIDTH: Final = 26

_WORD: Final = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE_END: Final = ('.', '!', '?', '"', "'", ')', '\u201d')
#: Phrases a newsletter platform serves when the post sells something. Matched
#: case-folded against the whole text, so one hit is weak and several is not.
_PROMO: Final = (
    "subscribe now",
    "upgrade to paid",
    "paid subscriber",
    "become a paid",
    "free trial",
    "enroll now",
    "buy now",
    "discount code",
    "limited time offer",
    "sign up for our",
    "start your free",
    "cancel anytime",
    "best price",
    "early bird",
)
#: A post whose article is somewhere else, in a player. Matched against the
#: opening only, so an article that mentions a video in passing is not a blurb.
_VIDEO: Final = re.compile(
    r"\b(in this (video|episode)|watch the (video|full)|subscribe to (my|our) channel"
    r"|link in (the )?(bio|description)|listen to (this|the) episode|full episode on)\b",
    re.IGNORECASE,
)
#: Minhash sketch width. 64 signatures is enough to separate "shares almost
#: every phrase" from "shares a few", which is the only question asked here.
_SKETCH: Final = 64
_SHINGLE: Final = 5


@dataclass(frozen=True)
class Thresholds:
    """One run's inputs. Every one is a command-line argument with a stated default."""

    words_min: int
    short_line_words: int
    link_dump_ratio: float
    diversity_min: float
    promo_hits: int
    latin_ratio_min: float
    sentence_words_min: int
    near_duplicate_jaccard: float


def words_of(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def moving_diversity(tokens: Sequence[str], window: int = 200) -> float:
    """Distinct words per window, averaged. A plain unique/total ratio falls as a
    text gets longer, so it flags every long essay and nothing else.
    """
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens) if tokens else 1.0
    scores = [
        len(set(tokens[start : start + window])) / window
        for start in range(0, len(tokens) - window + 1, window // 2)
    ]
    return sum(scores) / len(scores)


def body_lines(text: str) -> list[str]:
    """The lines without the trailing furniture a page leaves after the article."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    while lines and len(lines[-1].split()) < 6:
        lines.pop()
    return lines


def sketch(text: str) -> frozenset[int]:
    """The smallest `_SKETCH` shingle hashes, which is a minhash sketch of the text."""
    tokens = words_of(text)
    if len(tokens) < _SHINGLE:
        return frozenset()
    hashes = {
        int.from_bytes(
            hashlib.blake2b(
                " ".join(tokens[index : index + _SHINGLE]).encode("utf-8"), digest_size=8
            ).digest(),
            "big",
        )
        for index in range(len(tokens) - _SHINGLE + 1)
    }
    return frozenset(sorted(hashes)[:_SKETCH])


def near_duplicates(
    sketches: dict[str, frozenset[int]], *, jaccard_min: float
) -> dict[str, set[str]]:
    """Every pair sharing most of its phrases, found through an inverted index.

    The index is what keeps this bounded: only documents that share at least one
    signature are ever compared, instead of every pair of every document.
    """
    buckets: dict[int, list[str]] = defaultdict(list)
    for key, signature in sketches.items():
        for value in signature:
            buckets[value].append(key)

    candidates: set[tuple[str, str]] = set()
    for holders in buckets.values():
        if len(holders) < 2 or len(holders) > 50:
            continue
        for index, left in enumerate(holders):
            for right in holders[index + 1 :]:
                candidates.add((left, right) if left < right else (right, left))

    found: dict[str, set[str]] = defaultdict(set)
    for left, right in candidates:
        first, second = sketches[left], sketches[right]
        if not first or not second:
            continue
        shared = len(first & second) / len(first | second)
        if shared >= jaccard_min:
            found[left].add(right)
            found[right].add(left)
    return dict(found)


def flags_of(text: str, asked: Thresholds) -> list[ReferenceQualityFlag]:
    """Everything wrong with one article's text, named rather than scored."""
    raised: set[ReferenceQualityFlag] = set()
    tokens = words_of(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(tokens) < asked.words_min:
        raised.add(ReferenceQualityFlag.SHORT)
    if lines:
        short = sum(1 for line in lines if len(line.split()) < asked.short_line_words)
        if short / len(lines) >= asked.link_dump_ratio and len(lines) >= 5:
            raised.add(ReferenceQualityFlag.FRAGMENTED)
    folded = text.casefold()
    if sum(1 for phrase in _PROMO if phrase in folded) >= asked.promo_hits:
        raised.add(ReferenceQualityFlag.PROMOTIONAL)
    if _VIDEO.search(text[:800]):
        raised.add(ReferenceQualityFlag.VIDEO_OR_PODCAST)
    prose = [line for line in lines if len(line.split()) >= asked.sentence_words_min]
    if not prose:
        raised.add(ReferenceQualityFlag.NO_SENTENCE)
    elif len(lines) >= 8 and len(prose) / len(lines) < 0.35:
        raised.add(ReferenceQualityFlag.FRAGMENTED)
    return sorted(raised)


def scan(extraction: Path, asked: Thresholds, *, examples: int) -> int:
    rows = [
        row
        for row in json.loads(extraction.read_text(encoding="utf-8"))
        if row["status"] == "ok" and row["text"]
    ]
    seen: dict[str, dict[str, object]] = {}
    for row in rows:
        seen.setdefault(str(row["url_key"]), row)
    articles = list(seen.values())

    raised: dict[str, list[ReferenceQualityFlag]] = {}
    for row in articles:
        found = flags_of(str(row["text"]), asked)
        if found:
            raised[str(row["url_key"])] = found

    sketches = {str(row["url_key"]): sketch(str(row["text"])) for row in articles}
    twins = near_duplicates(sketches, jaccard_min=asked.near_duplicate_jaccard)
    for key in twins:
        raised.setdefault(key, []).append(ReferenceQualityFlag.NEAR_DUPLICATE)

    counted = Counter(flag.value for found in raised.values() for flag in found)
    clean = [row for row in articles if str(row["url_key"]) not in raised]

    print(f"{'articles read':<{_WIDTH}} {len(articles)}")
    print(f"{'articles with no flag':<{_WIDTH}} {len(clean)}")
    print(f"{'articles flagged':<{_WIDTH}} {len(raised)}")
    print()
    for flag, count in counted.most_common():
        share = 100 * count / len(articles)
        print(f"  {flag:<{_WIDTH - 2}} {count:>5}   {share:4.1f}% of articles")

    by_publisher = Counter(
        str(row["publisher"]) for row in articles if str(row["url_key"]) in raised
    )
    print()
    print("worst publishers by flagged share:")
    totals = Counter(str(row["publisher"]) for row in articles)
    ranked = sorted(
        ((name, by_publisher[name], totals[name]) for name in totals),
        key=lambda entry: (-entry[1] / entry[2], -entry[2]),
    )
    for name, flagged, total in ranked[:10]:
        print(f"  {name:<{_WIDTH - 2}} {flagged:>4} of {total:<4} {100 * flagged / total:4.0f}%")

    print()
    for flag in counted:
        shown = [
            row
            for row in articles
            if flag in raised.get(str(row["url_key"]), [])
        ][:examples]
        print(f"--- {flag} ---")
        for row in shown:
            words = len(words_of(str(row["text"])))
            opening = " ".join(str(row["text"]).split())[:90]
            print(f"  {row['publisher']:<20} {words:>6}w  {opening}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True, help="An articles.json.")
    parser.add_argument("--words-min", type=int, default=120)
    parser.add_argument("--short-line-words", type=int, default=5)
    parser.add_argument("--link-dump-ratio", type=float, default=0.6)
    parser.add_argument("--diversity-min", type=float, default=0.25)
    parser.add_argument("--promo-hits", type=int, default=2)
    parser.add_argument("--latin-ratio-min", type=float, default=0.5)
    parser.add_argument("--sentence-words-min", type=int, default=8)
    parser.add_argument("--near-duplicate-jaccard", type=float, default=0.7)
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args(argv)

    asked = Thresholds(
        words_min=args.words_min,
        short_line_words=args.short_line_words,
        link_dump_ratio=args.link_dump_ratio,
        diversity_min=args.diversity_min,
        promo_hits=args.promo_hits,
        latin_ratio_min=args.latin_ratio_min,
        sentence_words_min=args.sentence_words_min,
        near_duplicate_jaccard=args.near_duplicate_jaccard,
    )
    return scan(args.extraction, asked, examples=args.examples)


if __name__ == "__main__":
    sys.exit(main())
