"""How often does an article write a total that its own parts add up to?

`pie` may only be drawn against a whole the article **declared**, never one the
planner summed (`docs/architecture/publishing/visuals.md`). Nobody had counted
how often an article declares one, so the template was about to be sized against
a guess. This is that count, and **the definition it counts against is the
artefact** rather than the number - a later count can then be compared to this
one instead of merely disagreeing with it.

The definition, in plain English
--------------------------------

An article states a whole when all five of these are true:

1. It writes a total and, in the same unit, writes two to five parts.
2. The written parts add up to the written total, inside a stated tolerance.
3. Every part is larger than nothing and smaller than the total.
4. The total and every part sit inside one window of characters, so a reader
   meets them together.
5. One of the article's own joining words sits between the first of them and the
   last - `comprises`, `of which`, `plus`, `made up of`, `out of`, `the rest`,
   and the rest of the closed list below.

Every number is the article's own characters. Nothing is converted between
units, nothing is inferred, and no model reads anything: the test is arithmetic
over numbers a regular expression found, plus a word list.

It counts::

    "The Rs 1,757 crore issue is a Rs 900 crore fresh issue and a Rs 857
    crore offer for sale."   ->   900 + 857 = 1,757, same unit, two parts,
    one sentence, and "is a ... and a" reads as composition.

It does not count::

    "The Rs 650 crore IPO has a GMP of Rs 321 against an issue price of
    Rs 300."   ->   three amounts in one unit and none is the sum of the
    others, so no whole was declared.

    "Cities are the source of more than 70% of emissions ... About 40% of
    India's population lives within 100 km of the coast ... 30% ..."
    ->   40 + 30 = 70 is arithmetic, but the three figures are two thousand
    characters apart and describe three different subjects. Rule 4 refuses
    it, and the null arm below is how we know a rule like it is needed.

**Rule 5 is a proximity test and not an attachment test**, and that is its
weakness rather than a detail: the check is that a joining word falls somewhere
inside the span, never that it joins these particular numbers. A paragraph that
says "total" about something else still passes it.

**Rule 5 was added after the first run**, when the arithmetic-only screen turned
out to be mostly coincidence. The list itself was written in one pass from what
composition means and has not been changed since - no entry was added to rescue
a hit the screen was missing. That is the difference between a definition and a
filter tuned on its own output, and it is written here because only the author
knows which one happened (Andre, 2026-09-13).

Three arms, and none of them is added to another
------------------------------------------------

**stated** is the definition above: the total is a number the article wrote.
This is the one `pie` needs.

**implied percent** also counts two to five percentages that add up to 100 when
the article never writes "100 percent" - the unit declares the whole instead of
the sentence. **It is measured and it is not part of the definition.** Under 600
characters it finds fewer articles than its own null does, and treating an
unwritten 100 as declared is the planner asserting exhaustiveness the article did
not, which is plan 16's own escalation trigger reached by a side door. It stays
in the instrument so a later reader can check that refusal rather than take it on
trust (Editor, 2026-09-13).

**null** is the coincidence floor. An article carries several quantities, so
some subset of them adds up to another one by chance. The null arm re-runs the
same test over values dealt out across articles at random, which holds every
unit, every character position, every article's quantity count and every joining
word fixed and destroys only which value sat where - the one thing the measured
arm claims. `--seed` makes a null run reproducible.

**The null is a floor on chance and not an estimate of it.** Inside one article
the quantities of a unit have correlated magnitudes - twenty-one IPO premiums are
all small percentages - and drawing replacements from the whole corpus breaks
that correlation, so a null article is arithmetically harder than a real one.
Every ratio this prints is therefore an upper bound on the signal, and the
measured rate is an upper bound on the true rate (Andre, 2026-09-13).

This is a growing read
----------------------

`CLAUDE.md` Guardrail #12, taken under its escape hatch: this opens every row of
`corpus/corpus.jsonl`, it is run by hand, it is not on the daily path, and no
test repeats it. A bounded input cannot answer it - the question is the rate over
the whole window, so a sample would answer a different question and carry a
spread nobody asked for.

Usage, from the root of a checkout::

    python backend/utilities/measure_declared_wholes.py
    python backend/utilities/measure_declared_wholes.py --sweep
    python backend/utilities/measure_declared_wholes.py --examples 8 --json

Exit code 1 when there is no corpus to read, so a shell can tell "nothing to
read" from "read it, here are the numbers".
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: Relative and POSIX-separated, because it is quoted in a report (CLAUDE.md section 2).
CORPUS_RELPATH: Final = "corpus/corpus.jsonl"

#: The fence `sanitize.untrusted_block` puts the article inside. The body is what
#: sits between the two markers; the `Source form:` line before it is ours.
FENCE_OPEN: Final = "<<<UNTRUSTED_SOURCE_TEXT>>>"
FENCE_CLOSE: Final = "<<<END_UNTRUSTED_SOURCE_TEXT>>>"

#: Five parts or fewer, because beyond that an angle is unreadable and `pie` is
#: refused anyway (plan 16 row #3, `docs/architecture/publishing/visuals.md`).
MAX_PARTS: Final = 5

#: Two or more, because one part and a total is not a composition.
MIN_PARTS: Final = 2

#: How far the parts may miss the total, as a fraction of the total. Articles
#: round their own figures - three shares written to one decimal need not total
#: exactly - so zero would refuse compositions a reader can see. `--tolerance`
#: moves it, because what it costs in coincidences is a thing to measure rather
#: than a thing to assert.
TOLERANCE: Final = 0.005

#: The total and its parts must sit inside this many characters of each other.
#: Read off the sweep rather than picked: 600 is where the measured rate stands
#: furthest above the null rate, and it is about a paragraph of news prose, which
#: is as far apart as two figures can sit and still be read as one statement.
#: Because it is the best of the five swept, the ratio at 600 is a maximum over a
#: family and flatters the signal a little.
WINDOW: Final = 600

#: Windows `--sweep` walks. 0 means the whole article, which is rule 4 switched
#: off and is in the sweep to show what removing it costs.
SWEEP_WINDOWS: Final = (150, 300, 600, 1200, 0)

#: Past this many quantities in one unit the subset search is skipped and the
#: group is counted as capped rather than as a miss. A group of 30 has 174,436
#: subsets of five or fewer, and the report prints how often the cap bit so a
#: reader can see whether it could have changed the answer.
GROUP_CAP: Final = 24

_NUMBER: Final = re.compile(r"(?<![\w.,])(\d[\d,]*)(?:\.(\d+))?(?![\w,]|\.\d)")

#: A currency mark immediately before the number. The value stays in that
#: currency's own units and is never converted, so two currencies never mix.
_CURRENCY: Final = re.compile(r"(?:(\$|\u20b9|\u00a3|\u20ac)|\b(rs|inr|usd|eur|gbp)\.?)\s*$", re.I)
_CURRENCY_CODE: Final = {
    "$": "usd",
    "\u20b9": "inr",
    "\u00a3": "gbp",
    "\u20ac": "eur",
    "rs": "inr",
    "inr": "inr",
    "usd": "usd",
    "eur": "eur",
    "gbp": "gbp",
}

#: A scale word immediately after the number, folded into its value so that
#: `$1.2 billion` and `$400 million` share a unit and can be added.
_SCALE: Final = {
    "hundred": 1e2,
    "thousand": 1e3,
    "lakh": 1e5,
    "lakhs": 1e5,
    "million": 1e6,
    "mn": 1e6,
    "crore": 1e7,
    "crores": 1e7,
    "billion": 1e9,
    "bn": 1e9,
    "trillion": 1e12,
    "tn": 1e12,
}

_PERCENT: Final = re.compile(r"\s*(%|per\s?cents?\b|percents?\b)", re.I)

#: The article's own words for joining a total to its parts. A closed list, and
#: short on purpose: every entry is a word that can only be read as composition,
#: so a longer list would buy coverage by admitting words that mean other things.
#: `total` is here and `and` is not, which is where that line falls.
_CUE: Final = re.compile(
    r"\b(?:compris\w*|consist\w*|of which|includ\w*|made up of|make[sd]? up|"
    r"split|divid\w*|breakdown|broken down|allocat\w*|apportion\w*|"
    r"plus|combined|together with|total\w*|sum(?:med|ming)?|subtotal|"
    r"remainder|the rest|the balance|respectively|out of|accounted for|"
    r"share of|balance of|rest of)\b",
    re.I,
)

#: A word after a number that names no unit, so the number counts nothing and is
#: dropped. Grammar, months, and the time words - a duration is a position on a
#: clock rather than a part of anything, so "three years and two years" is not a
#: composition, and this list is where that ruling lives.
_NOT_A_UNIT: Final = frozenset(
    """
    a an and are as at be been but by for from had has have he her his in into is it its
    of on or she that the their there they this to was were which who will with
    about after against all also although among another any because before being
    below between both during each either even every few following how however if
    less like many more most much near no nor not now off once only other our out
    over per same since so some still such than then these those though through under
    until up very what when where while why would you your
    january february march april may june july august september october november december
    jan feb mar apr jun jul aug sep sept oct nov dec
    year years month months week weeks day days hour hours minute minutes second seconds
    am pm ist utc gmt et pt
    """.split()
)

ARMS: Final = ("stated", "implied_percent", "null_stated", "null_implied_percent")


@dataclass(frozen=True)
class Quantity:
    """One number the article wrote, with the unit it wrote beside it."""

    value: float
    unit: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Finding:
    """One total and the parts that add up to it, as the article wrote them."""

    unit: str
    whole: Quantity
    parts: tuple[Quantity, ...]
    implied: bool


def body(user_turn: str) -> str:
    """The article's own characters, between the fence markers and nothing else."""
    start = user_turn.find(FENCE_OPEN)
    if start < 0:
        return user_turn
    end = user_turn.find(FENCE_CLOSE, start)
    return user_turn[start + len(FENCE_OPEN) : end if end >= 0 else len(user_turn)]


def quantities(text: str) -> list[Quantity]:
    """Every number that carries a unit. A number with no unit is not a quantity."""
    found: list[Quantity] = []
    for match in _NUMBER.finditer(text):
        digits, decimals = match.group(1), match.group(2)
        try:
            value = float(digits.replace(",", "") + ("." + decimals if decimals else ""))
        except ValueError:
            continue
        head, tail = text[max(0, match.start() - 12) : match.start()], text[match.end() :]
        currency = _CURRENCY.search(head)
        percent = _PERCENT.match(tail)
        word = re.match(r"[\s-]*([A-Za-z][A-Za-z-]*)", tail)
        token = word.group(1).lower() if word else ""
        scale = _SCALE.get(token)
        if currency is not None:
            unit = _CURRENCY_CODE[(currency.group(1) or currency.group(2)).lower()]
            value *= scale or 1.0
        elif percent is not None:
            unit = "percent"
        elif scale is not None:
            # A scale word with no currency and no noun after it - "2 million" -
            # counts nothing in particular, so it is not a quantity.
            continue
        elif token and token not in _NOT_A_UNIT:
            unit = token.rstrip("s") or token
        else:
            continue
        end = match.end() + (percent.end() if percent is not None else 0)
        found.append(Quantity(value, unit, match.start(), end, text[match.start() : end]))
    return found


def cue_positions(text: str) -> tuple[int, ...]:
    """Where the article uses one of its own words for joining a total to its parts."""
    return tuple(match.start() for match in _CUE.finditer(text))


def _span(quants: tuple[Quantity, ...]) -> tuple[int, int]:
    """The first and last character the article spends on this set of quantities."""
    placed = [q for q in quants if q.start >= 0]
    if not placed:
        return 0, 0
    return min(q.start for q in placed), max(q.end for q in placed)


def _is_a_composition(parts: tuple[Quantity, ...], total: float) -> bool:
    """Rule 3: every part is larger than nothing and smaller than the total.

    The tolerance is what makes this a real check rather than a tautology. Two
    parts summing to the total are each smaller than it by construction - but
    `85% = 85% + 0.26%` also lands inside a half-percent tolerance, and that is
    a composition of nothing.
    """
    return all(0 < q.value < total for q in parts)


@dataclass(frozen=True)
class Group:
    """Every quantity in one unit, with each subset of two to five totalled once.

    The table is built once an article and read once a window, because a sweep
    that rebuilt it would spend all its time on arithmetic it had already done.
    """

    unit: str
    members: tuple[Quantity, ...]
    totals: tuple[float, ...]
    combos: tuple[tuple[Quantity, ...], ...]


def group(unit: str, members: list[Quantity]) -> Group:
    rows = sorted(
        (
            (sum(q.value for q in combo), combo)
            for size in range(MIN_PARTS, MAX_PARTS + 1)
            for combo in combinations(members, size)
        ),
        key=lambda row: row[0],
    )
    return Group(
        unit, tuple(members), tuple(row[0] for row in rows), tuple(row[1] for row in rows)
    )


def groups_of(quants: list[Quantity]) -> tuple[list[Group], int]:
    """One group per unit, and how many the size cap refused to search."""
    by_unit: dict[str, list[Quantity]] = defaultdict(list)
    for quantity in quants:
        by_unit[quantity.unit].append(quantity)
    built: list[Group] = []
    capped = 0
    for unit, members in by_unit.items():
        if len(members) > GROUP_CAP:
            capped += 1
        elif len(members) >= MIN_PARTS:
            built.append(group(unit, members))
    return built, capped


def _parts_for(
    unit_group: Group,
    total: float,
    *,
    whole: Quantity | None,
    window: int,
    tolerance: float,
    cues: tuple[int, ...],
) -> tuple[Quantity, ...] | None:
    """The first subset of this group that adds up to `total` under all five rules."""
    if total <= 0:
        return None
    low, high = total * (1 - tolerance), total * (1 + tolerance)
    for index in range(
        bisect_left(unit_group.totals, low), bisect_right(unit_group.totals, high)
    ):
        combo = unit_group.combos[index]
        if whole is not None and any(q.start == whole.start for q in combo):
            continue
        if not _is_a_composition(combo, total):
            continue
        reach = (whole, *combo) if whole is not None else combo
        first, last = _span(reach)
        if window and last - first > window:
            continue
        if cues and bisect_left(cues, first) >= bisect_right(cues, last):
            continue
        return combo
    return None


def declared_wholes(
    built: list[Group], *, implied: bool, window: int, tolerance: float, cues: tuple[int, ...]
) -> list[Finding]:
    """Every whole these groups declare, under the arm and the window asked for."""
    findings: list[Finding] = []
    for unit_group in built:
        if implied:
            if unit_group.unit != "percent":
                continue
            combo = _parts_for(
                unit_group,
                100.0,
                whole=None,
                window=window,
                tolerance=tolerance,
                cues=cues,
            )
            if combo is not None:
                findings.append(
                    Finding(
                        unit_group.unit,
                        Quantity(100.0, unit_group.unit, -1, -1, "100%"),
                        combo,
                        True,
                    )
                )
            continue
        for whole in unit_group.members:
            combo = _parts_for(
                unit_group,
                whole.value,
                whole=whole,
                window=window,
                tolerance=tolerance,
                cues=cues,
            )
            if combo is not None:
                findings.append(Finding(unit_group.unit, whole, combo, False))
                break
    return findings


def deal_out(per_article: list[list[Quantity]], seed: int) -> list[list[Quantity]]:
    """The same articles, with every value re-dealt from the pool for its own unit.

    Every position stays where the article put it and every unit stays on the
    quantity that carried it, so an article that crowds nine percentages into one
    paragraph still crowds nine percentages into one paragraph. The magnitudes
    are the corpus's own. The only thing destroyed is which value sat at which
    position - the one thing the measured arm claims.

    Re-dealing positions instead, at some average spacing, would have been the
    easier null and a badly wrong one: real articles cluster their numbers, an
    evenly spread null fits fewer of them inside a window, and the coincidence
    floor would come out too low and the measured rate too impressive.
    """
    pool: dict[str, list[float]] = defaultdict(list)
    for article in per_article:
        for quantity in article:
            pool[quantity.unit].append(quantity.value)
    rng = random.Random(seed)
    for values in pool.values():
        rng.shuffle(values)
    cursor: Counter[str] = Counter()
    dealt: list[list[Quantity]] = []
    for article in per_article:
        swapped: list[Quantity] = []
        for quantity in article:
            value = pool[quantity.unit][cursor[quantity.unit]]
            cursor[quantity.unit] += 1
            swapped.append(
                Quantity(value, quantity.unit, quantity.start, quantity.end, f"{value:g}")
            )
        dealt.append(swapped)
    return dealt


def read_articles(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        return [body(json.loads(line)["messages"][1]["content"]) for line in handle if line.strip()]


def _rate(hits: int, total: int) -> float:
    return 100.0 * hits / total if total else 0.0


def _example(text: str, finding: Finding) -> str:
    low, high = _span((finding.whole, *finding.parts))
    excerpt = " ".join(text[max(0, low - 40) : min(len(text), high + 40)].split())
    total = " + ".join(q.text for q in finding.parts)
    return f"{finding.whole.text} = {total}  [{finding.unit}]  ... {excerpt} ..."


def one_arm(
    population: list[tuple[list[Group], int]],
    *,
    implied: bool,
    window: int,
    tolerance: float,
    cues: list[tuple[int, ...]],
    articles: list[str] | None,
    examples: int,
) -> dict[str, Any]:
    """One arm over one population, at one window."""
    hits = 0
    capped = 0
    units: Counter[str] = Counter()
    sizes: Counter[int] = Counter()
    shown: list[str] = []
    started = time.perf_counter()
    for index, (built, group_capped) in enumerate(population):
        capped += group_capped
        findings = declared_wholes(
            built, implied=implied, window=window, tolerance=tolerance, cues=cues[index]
        )
        if not findings:
            continue
        hits += 1
        units[findings[0].unit] += 1
        sizes[len(findings[0].parts)] += 1
        if articles is not None and len(shown) < examples:
            shown.append(_example(articles[index], findings[0]))
    return {
        "articles_with_a_whole": hits,
        "percent": round(_rate(hits, len(population)), 2),
        "capped_groups": capped,
        "by_unit": dict(units.most_common()),
        "by_part_count": dict(sorted(sizes.items())),
        "seconds": round(time.perf_counter() - started, 2),
        "examples": shown,
    }


def report(
    path: Path, *, seed: int, examples: int, windows: tuple[int, ...], tolerance: float
) -> dict[str, Any]:
    started = time.perf_counter()
    articles = read_articles(path)
    per_article = [quantities(text) for text in articles]
    cues = [cue_positions(text) for text in articles]
    read_seconds = time.perf_counter() - started
    measured = [groups_of(quants) for quants in per_article]
    null = [groups_of(quants) for quants in deal_out(per_article, seed)]

    result: dict[str, Any] = {
        "corpus": CORPUS_RELPATH,
        "bytes": path.stat().st_size,
        "articles": len(articles),
        "quantities": sum(len(q) for q in per_article),
        "cues": sum(len(c) for c in cues),
        "read_seconds": round(read_seconds, 2),
        "tolerance": tolerance,
        "min_parts": MIN_PARTS,
        "max_parts": MAX_PARTS,
        "group_cap": GROUP_CAP,
        "seed": seed,
        "windows": {},
    }
    for window in windows:
        result["windows"][str(window)] = {
            "stated": one_arm(
                measured,
                implied=False,
                window=window,
                tolerance=tolerance,
                cues=cues,
                articles=articles,
                examples=examples,
            ),
            "implied_percent": one_arm(
                measured,
                implied=True,
                window=window,
                tolerance=tolerance,
                cues=cues,
                articles=articles,
                examples=examples,
            ),
            "null_stated": one_arm(
                null,
                implied=False,
                window=window,
                tolerance=tolerance,
                cues=cues,
                articles=None,
                examples=0,
            ),
            "null_implied_percent": one_arm(
                null,
                implied=True,
                window=window,
                tolerance=tolerance,
                cues=cues,
                articles=None,
                examples=0,
            ),
        }
    return result


def _print(result: dict[str, Any], examples: int) -> None:
    print(
        f"{result['articles']:,} articles, {result['quantities']:,} quantities, "
        f"{result['bytes']:,} bytes, read in {result['read_seconds']} s"
    )
    print(
        f"{MIN_PARTS} to {MAX_PARTS} parts, adding up within "
        f"{result['tolerance'] * 100:.2f} percent of the total, "
        f"unit groups over {GROUP_CAP} skipped"
    )
    print()
    print(f"{'window':>9}  {'stated':>14}  {'null':>14}  {'implied %':>14}  {'null':>14}")
    for window, arms in result["windows"].items():
        label = "article" if window == "0" else f"{window} ch"
        cells = "  ".join(
            f"{arms[arm]['articles_with_a_whole']:>6} {arms[arm]['percent']:>6.2f}%" for arm in ARMS
        )
        print(f"{label:>9}  {cells}")
    print()
    chosen = str(WINDOW) if str(WINDOW) in result["windows"] else next(iter(result["windows"]))
    arm = result["windows"][chosen]["stated"]
    print(f"at a {chosen}-character window the stated arm splits by unit as {arm['by_unit']},")
    print(f"by part count as {arm['by_part_count']}, with {arm['capped_groups']} capped groups")
    print()
    for line in arm["examples"][:examples]:
        print(f"  {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Count how often an article states a whole its parts add up to."
    )
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT / CORPUS_RELPATH)
    parser.add_argument("--seed", type=int, default=20260913, help="makes the null reproducible")
    parser.add_argument("--window", type=int, default=WINDOW, help="0 means the whole article")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE, help="0 means exact")
    parser.add_argument("--sweep", action="store_true", help="walk every window in SWEEP_WINDOWS")
    parser.add_argument("--examples", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.corpus.exists():
        print(f"no corpus at {args.corpus}", file=sys.stderr)
        return 1

    windows = SWEEP_WINDOWS if args.sweep else (args.window,)
    result = report(
        args.corpus,
        seed=args.seed,
        examples=args.examples,
        windows=windows,
        tolerance=args.tolerance,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print(result, args.examples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
