"""Choose which pairs are worth a person's judgement, and lay them out to judge.

A week of reading buys roughly a thousand decisions. Spending them evenly over
the corpus would spend almost all of them confirming that unrelated stories are
unrelated, because at any plausible rate most pairs are. So the pairs are drawn
where the answer is in doubt and where the encoders disagree with each other -
that is where a decision between them is actually made.

Six groups, and the reason each exists:

  settled match      two outlets, near-identical titles, one day. Fixes what
                     the top of the scale means.
  settled mismatch   nothing in common. Fixes the bottom.
  encoders differ    one encoder calls it a match and another does not. Every
                     ranking between them is decided here and nowhere else.
  hard mismatch      shares its actors and its subject but not its occasion:
                     two launches, two quarterly results, a preview and a
                     result. The error that hides a story from a reader.
  hard match         one event written two ways, with few words in common. The
                     error that shows a reader the same story twice.
  no publication time one article in four carries none, so no time rule can
                     help them. Measured rather than assumed.

The file written here has a blank verdict beside every pair. Nothing is
pre-filled: a suggested answer is the one thing that would make the reading
worthless.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

GROUPS = (
    "settled_match",
    "settled_mismatch",
    "encoders_differ",
    "hard_mismatch",
    "hard_match",
    "no_publication_time",
)


def content_words(text: str, stop: frozenset[str]) -> set[str]:
    import re

    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in stop and len(word) > 2
    }


def build_frame(
    items: list[dict[str, Any]],
    vectors: np.ndarray | None,
    index_of: dict[str, int],
    stop: frozenset[str],
    reach_days: int,
) -> list[dict[str, Any]]:
    """Every pair close enough in time to be worth a second look."""
    for item in items:
        item["words"] = content_words(item["title"], stop)

    by_day: dict[str, list[int]] = defaultdict(list)
    for position, item in enumerate(items):
        by_day[item["day"]].append(position)

    frame: list[dict[str, Any]] = []
    for day, members in sorted(by_day.items()):
        later: list[int] = []
        for ahead in range(1, reach_days + 1):
            following = date.fromisoformat(day) + timedelta(days=ahead)
            later.extend(by_day.get(f"{following:%Y-%m-%d}", []))
        for position, left in enumerate(members):
            if len(items[left]["words"]) < 3:
                continue
            for right in members[position + 1:] + later:
                if len(items[right]["words"]) < 3:
                    continue
                union = items[left]["words"] | items[right]["words"]
                overlap = len(items[left]["words"] & items[right]["words"]) / len(union)
                closeness = None
                if vectors is not None:
                    a = index_of.get(items[left]["url"])
                    b = index_of.get(items[right]["url"])
                    if a is not None and b is not None:
                        closeness = float(vectors[a] @ vectors[b])
                frame.append({
                    "left": left,
                    "right": right,
                    "title_overlap": round(overlap, 3),
                    "closeness": closeness,
                    "same_outlet": items[left]["domain"] == items[right]["domain"],
                    "same_day": items[left]["day"] == items[right]["day"],
                    "no_time": not (items[left]["has_time"] and items[right]["has_time"]),
                })
    return frame


def assign_group(pair: dict[str, Any]) -> str | None:
    """Which group a pair belongs to, or none if it is not worth reading."""
    overlap = pair["title_overlap"]
    closeness = pair["closeness"]

    if pair["no_time"] and overlap >= 0.15:
        return "no_publication_time"
    if pair["same_outlet"] and overlap >= 0.30:
        return "hard_mismatch"
    if overlap >= 0.55 and pair["same_day"] and not pair["same_outlet"]:
        return "settled_match"
    if overlap < 0.05:
        return "settled_mismatch"
    if closeness is not None and overlap < 0.15 and closeness >= 0.70:
        # Few words in common, yet the encoder puts them together: either one
        # event told two ways, or the encoder is wrong. Both are worth knowing.
        return "hard_match"
    if closeness is not None and 0.15 <= overlap < 0.45 and 0.45 <= closeness < 0.80:
        return "encoders_differ"
    if closeness is None and 0.15 <= overlap < 0.45:
        return "encoders_differ"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--vector-order", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--total", type=int, default=1000)
    parser.add_argument("--duplicate-share", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--reach-days", type=int, default=1)
    args = parser.parse_args()

    stop = frozenset(
        """a an the of in on for to and or with at by from as is are was were be
        been has have had it its this that these those after before over under
        new says say said will would can could may might more most than then up
        down out about against amid into near off per via vs""".split()
    )

    items = [json.loads(line) for line in args.items.open(encoding="utf-8")]
    for item in items:
        # The extract names the day a run first published the article; this
        # module speaks of a day throughout, so the names are joined here
        # rather than in six places below.
        item["day"] = item.get("day") or item["first_day"]
        item["has_time"] = bool(item.get("published_at")) and item.get(
            "time_source"
        ) in ("feed", "first_seen")

    vectors = None
    index_of: dict[str, int] = {}
    if args.vectors and args.vectors.is_file():
        vectors = np.load(args.vectors)
        if args.vector_order and args.vector_order.is_file():
            order = json.loads(args.vector_order.read_text(encoding="utf-8"))
            index_of = {url: slot for slot, url in enumerate(order)}

    frame = build_frame(items, vectors, index_of, stop, args.reach_days)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in frame:
        group = assign_group(pair)
        if group is not None:
            grouped[group].append(pair)

    share = {
        "settled_match": 0.10,
        "settled_mismatch": 0.10,
        "encoders_differ": 0.35,
        "hard_mismatch": 0.20,
        "hard_match": 0.15,
        "no_publication_time": 0.10,
    }

    rng = random.Random(args.seed)
    chosen: list[dict[str, Any]] = []
    for group in GROUPS:
        pool = grouped.get(group, [])
        rng.shuffle(pool)
        want = int(args.total * share[group])
        for pair in pool[:want]:
            pair["group"] = group
            chosen.append(pair)

    # A tenth of them appear twice, far apart and with no sign of it. Reading
    # the same pair twice and answering differently is the only way to know how
    # steady any of these answers are.
    repeated = rng.sample(chosen, int(len(chosen) * args.duplicate_share))
    sheet = chosen + [dict(pair, repeat_of=None) for pair in repeated]
    rng.shuffle(sheet)

    rows = []
    for number, pair in enumerate(sheet, start=1):
        left, right = items[pair["left"]], items[pair["right"]]
        rows.append({
            "id": f"p{number:04d}",
            # The group is kept out of the reading view on purpose: knowing a
            # pair was drawn as a hard mismatch is a nudge towards calling it
            # one.
            "group": pair["group"],
            "verdict": "",
            "note": "",
            "a": {
                "title": left["title"],
                "summary": left["summary"],
                "outlet": left["domain"],
                "day": left["day"],
                "url": left["url"],
            },
            "b": {
                "title": right["title"],
                "summary": right["summary"],
                "outlet": right["domain"],
                "day": right["day"],
                "url": right["url"],
            },
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "version": "2026-10-09",
            "pairs_to_read": len(rows),
            "repeated": len(repeated),
            "groups": {g: len(grouped.get(g, [])) for g in GROUPS},
            "taken": {g: sum(1 for r in rows if r["group"] == g) for g in GROUPS},
            "verdicts_allowed": ["same", "different", "cannot_tell"],
            "rows": rows,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"frame            {len(frame)} pairs")
    for group in GROUPS:
        print(f"  {group:22} {len(grouped.get(group, [])):>7} available  "
              f"{sum(1 for r in rows if r['group'] == group):>4} taken")
    print(f"to read          {len(rows)} ({len(repeated)} of them twice)")
    print(f"wrote            {args.out}")


if __name__ == "__main__":
    main()
