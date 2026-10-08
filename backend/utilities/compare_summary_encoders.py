"""Rank sentence encoders on this project's own summaries.

The pipeline needs one encoder to decide whether two summaries report the same
event. No paper read for plan 63 chooses one, and the search surface's encoder
answers a different question - it embeds a reader's query in a browser tab and
is sized for what a visitor downloads. So the choice is measured here.

There are no labels, so the run builds a stand-in from a signal the encoders
never see: the generated title. A title in this pipeline is actor plus action
with the hype removed, so two titles from different outlets on the same day that
share most of their content words are very likely one event, and two drawn at
random from one day are very likely not. That stand-in is not truth. It is the
same stand-in for every encoder, which is what makes the ranking fair even
though it cannot score any single encoder absolutely.

The reading is the chance that an encoder scores a likely-same pair above a
likely-different one. No difference in similarity scale can distort it, which a
gap between two averages cannot claim.

Three stages, because every encoder has to score the identical pairs:

    pairs    build the pair set once, from a named range of published days
    score    one encoder, reading that set, writing one reading
    collect  merge the readings, write the manifest and the table
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import re
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

STOP = frozenset(
    """a an the of in on for to and or with at by from as is are was were be been
    has have had it its this that these those after before over under new says
    say said will would can could may might more most than then up down out
    about against amid into near off per via vs""".split()
)


def read_config(path: Path) -> dict[str, Any]:
    """Load the comparison settings, refusing a missing key by name."""
    settings = json.loads(path.read_text(encoding="utf-8"))
    for key in ("pair_build", "encode", "encoders"):
        if key not in settings:
            raise SystemExit(f"{path}: no {key}")
    return settings


def content_words(text: str) -> set[str]:
    """The words of a title that carry its subject."""
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP and len(word) > 2
    }


def named_days(start: str, end: str) -> list[date]:
    """Every day in a closed range.

    A computed range and not a directory listing: a read whose cost grows with
    the archive is forbidden (CLAUDE.md Guardrail #12).
    """
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first:
        raise SystemExit(f"{end} is before {start}")
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def read_published_items(digest_root: Path, days: list[date]) -> list[dict[str, Any]]:
    """One record an article, from the named published days.

    A day with no file is a day that did not publish, which is not a fault.
    """
    seen: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for day in days:
        payload = digest_root / f"{day:%Y/%m/%d}" / "digest.json"
        if not payload.is_file():
            missing.append(f"{day:%Y-%m-%d}")
            continue
        published = json.loads(payload.read_text(encoding="utf-8"))
        for item in published.get("items", []):
            url = item.get("source_url") or ""
            summary = item.get("summary") or ""
            title = item.get("title") or ""
            if not url or not summary or not title:
                continue
            if url in seen:
                continue
            domain = url.split("/")[2].lower().removeprefix("www.") if url.count("/") > 2 else ""
            seen[url] = {
                "url": url,
                "domain": domain,
                "title": title,
                "summary": summary,
                "day": f"{day:%Y-%m-%d}",
            }
    if missing:
        print(f"days that published nothing: {len(missing)}", file=sys.stderr)
    return list(seen.values())


def build_pairs(items: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    """Sort near-neighbour pairs into three buckets by what their titles share.

    Three, not two. A comparison that only asks an encoder to tell an obvious
    match from an obvious mismatch is one every encoder passes, and it would
    repeat the fault this project already found in its own judge: that judge is
    shown only pairs above cosine 0.88, so it never sees the error that matters.

    The middle band is where the decision actually sits. It is scored but it is
    never counted as right or wrong, because nobody knows which it is. What it
    reports is a lean: an encoder that pushes the middle band up against the
    matching pairs will over-merge, and one that pushes it down will fragment.

    Likely-same wants two outlets on one story, so a pair from one domain is
    dropped: the same outlet repeating itself is a different question.
    """
    floor = settings["title_overlap_floor"]
    middle = settings["ambiguous_floor"]
    reach = settings["next_day_window"]
    least_words = settings["min_title_words"]
    cap = settings["max_pairs_a_side"]
    middle_cap = settings["max_ambiguous_pairs"]

    for item in items:
        item["words"] = content_words(item["title"])

    by_day: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(items):
        by_day[item["day"]].append(index)

    same: list[tuple[int, int]] = []
    ambiguous: list[tuple[int, int]] = []
    related: list[tuple[int, int]] = []
    for day, members in sorted(by_day.items()):
        later: list[int] = []
        for ahead in range(1, reach + 1):
            next_day = date.fromisoformat(day) + timedelta(days=ahead)
            later.extend(by_day.get(f"{next_day:%Y-%m-%d}", []))
        for position, left in enumerate(members):
            if len(items[left]["words"]) < least_words:
                continue
            for right in members[position + 1:] + later:
                if len(items[right]["words"]) < least_words:
                    continue
                union = items[left]["words"] | items[right]["words"]
                shared = len(items[left]["words"] & items[right]["words"]) / len(union)
                if items[left]["domain"] == items[right]["domain"]:
                    # One outlet writing twice about one subject on one day.
                    # Usually a correction or a follow-up, and a word-overlap
                    # rule cannot say which - the titles match either way. Kept
                    # out of the scored buckets and reported on its own.
                    if shared >= floor:
                        related.append((left, right))
                    continue
                if shared >= floor:
                    same.append((left, right))
                elif shared >= middle:
                    ambiguous.append((left, right))

    rng = random.Random(settings["seed"])
    rng.shuffle(same)
    rng.shuffle(ambiguous)
    rng.shuffle(related)
    same = same[:cap]
    ambiguous = ambiguous[:middle_cap]
    related = related[:settings["max_related_pairs"]]

    days = [day for day, members in by_day.items() if len(members) > 1]
    different: list[tuple[int, int]] = []
    attempts = 0
    while len(different) < len(same) and attempts < len(same) * 200:
        attempts += 1
        members = by_day[rng.choice(days)]
        left, right = rng.sample(members, 2)
        if items[left]["domain"] == items[right]["domain"]:
            continue
        union = items[left]["words"] | items[right]["words"]
        if not union:
            continue
        if len(items[left]["words"] & items[right]["words"]) / len(union) < middle:
            different.append((left, right))

    every_pair = same + different + ambiguous + related
    touched = sorted({index for pair in every_pair for index in pair})
    slot_of = {index: slot for slot, index in enumerate(touched)}
    return {
        "texts": [items[index]["summary"] for index in touched],
        "same": [[slot_of[a], slot_of[b]] for a, b in same],
        "different": [[slot_of[a], slot_of[b]] for a, b in different],
        "ambiguous": [[slot_of[a], slot_of[b]] for a, b in ambiguous],
        "related": [[slot_of[a], slot_of[b]] for a, b in related],
    }


def stage_pairs(args: argparse.Namespace) -> None:
    settings = read_config(args.config)
    days = named_days(args.start, args.end)
    items = read_published_items(args.digest_root, days)
    built = build_pairs(items, settings["pair_build"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "version": settings["version"],
                "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "days_named": len(days),
                "first_day": args.start,
                "last_day": args.end,
                "articles_read": len(items),
                "articles_encoded": len(built["texts"]),
                "same_pairs": len(built["same"]),
                "different_pairs": len(built["different"]),
                "ambiguous_pairs": len(built["ambiguous"]),
                "related_pairs": len(built["related"]),
                "pair_build": settings["pair_build"],
                **built,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"days named          {len(days)}")
    print(f"articles read       {len(items)}")
    print(f"articles to encode  {len(built['texts'])}")
    print(f"likely-same pairs   {len(built['same'])}")
    print(f"likely-different    {len(built['different'])}")
    print(f"uncertain middle    {len(built['ambiguous'])}")
    print(f"same outlet again   {len(built['related'])}")
    print(f"wrote               {args.out}")


def stage_score(args: argparse.Namespace) -> None:
    """Encode in batches, writing the reading after every one.

    The write is atomic - a temporary file and a rename - so a shard killed
    mid-write leaves the previous whole reading rather than half a file.
    """
    settings = read_config(args.config)
    chosen = next((e for e in settings["encoders"] if e["slug"] == args.slug), None)
    if chosen is None:
        raise SystemExit(f"no encoder named {args.slug} in {args.config}")

    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    texts = [chosen["prefix"] + text for text in pairs["texts"]]

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idhazh.contracts.encoder_reading import (
        EncoderReading,
        PairCounts,
        ReadingState,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)

    def now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    reading = EncoderReading(
        slug=chosen["slug"],
        model_id=chosen["model_id"],
        parameters_millions=chosen["parameters_millions"],
        prefix=chosen["prefix"],
        why=chosen["why"],
        state=ReadingState.LOADING,
        written_at=now(),
        articles_to_encode=len(texts),
        pairs=PairCounts(
            same=len(pairs["same"]),
            different=len(pairs["different"]),
            ambiguous=len(pairs.get("ambiguous", [])),
            related=len(pairs.get("related", [])),
        ),
    )

    def save() -> None:
        """Write the reading where a reader can only ever see a whole one."""
        reading.written_at = now()
        beside = args.out.with_suffix(".json.part")
        beside.write_text(reading.model_dump_json(indent=1), encoding="utf-8")
        beside.replace(args.out)

    def peak_memory_gb() -> float | None:
        try:
            import resource

            return round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 2
            )
        except (ImportError, AttributeError):
            return None

    save()
    print(f"{chosen['slug']}: loading {chosen['model_id']}", flush=True)

    import numpy as np
    import torch
    from sklearn.metrics import roc_auc_score

    torch.set_num_threads(settings["encode"]["threads"])

    try:
        from sentence_transformers import SentenceTransformer

        loading = time.monotonic()
        model = SentenceTransformer(chosen["model_id"], device="cpu")
        model.max_seq_length = settings["encode"]["max_sequence_length"]
        reading.load_seconds = round(time.monotonic() - loading, 1)
    except Exception as failure:  # noqa: BLE001 - a model that will not load is a reading
        reading.state = ReadingState.UNAVAILABLE
        reading.reason = f"{type(failure).__name__}: {failure}"[:300]
        reading.peak_memory_gb = peak_memory_gb()
        save()
        print(f"{chosen['slug']}: {reading.reason}", flush=True)
        return

    reading.state = ReadingState.ENCODING
    save()
    print(f"{chosen['slug']}: loaded in {reading.load_seconds}s, encoding "
          f"{len(texts)} articles", flush=True)

    batch = settings["encode"]["batch_size"]
    checkpoint_every = settings["encode"]["checkpoint_every_articles"]
    encoded: list[Any] = []
    since_checkpoint = 0
    started = time.monotonic()

    try:
        for start in range(0, len(texts), batch):
            encoded.append(
                model.encode(
                    texts[start:start + batch],
                    batch_size=batch,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).astype(np.float32)
            )
            reading.articles_done = min(start + batch, len(texts))
            reading.encode_seconds = round(time.monotonic() - started, 1)
            reading.numbers_an_article = int(encoded[0].shape[1])
            since_checkpoint += batch
            if since_checkpoint >= checkpoint_every:
                since_checkpoint = 0
                reading.articles_a_second = round(
                    reading.articles_done / max(reading.encode_seconds, 0.1), 1
                )
                reading.peak_memory_gb = peak_memory_gb()
                save()
                print(f"{chosen['slug']}: {reading.articles_done}/{len(texts)} "
                      f"at {reading.articles_a_second}/s", flush=True)
    except Exception as failure:  # noqa: BLE001 - a stopped encode is still a reading
        reading.state = ReadingState.STOPPED
        reading.reason = f"{type(failure).__name__}: {failure}"[:300]
        reading.peak_memory_gb = peak_memory_gb()
        save()
        print(f"{chosen['slug']}: stopped - {reading.reason}", flush=True)
        return

    vectors = np.concatenate(encoded)

    def score(pairs_list: list[list[int]]) -> Any:
        left = vectors[[p[0] for p in pairs_list]]
        right = vectors[[p[1] for p in pairs_list]]
        return np.sum(left * right, axis=1)

    same_scores, different_scores = score(pairs["same"]), score(pairs["different"])
    truth = np.concatenate([np.ones(len(same_scores)), np.zeros(len(different_scores))])

    per_second = len(texts) / max(reading.encode_seconds or 0.1, 0.1)
    reading.separation = round(
        float(roc_auc_score(truth, np.concatenate([same_scores, different_scores]))), 4
    )
    reading.same_mean = round(float(same_scores.mean()), 3)
    reading.different_mean = round(float(different_scores.mean()), 3)
    reading.spread = round(
        float(same_scores.mean() - different_scores.mean()), 3
    )
    reading.articles_a_second = round(per_second, 1)
    reading.minutes_for_whole_archive = round(
        settings["corpus"]["published_articles"] / per_second / 60, 1
    )
    reading.minutes_for_one_day = round(
        settings["corpus"]["articles_a_day"] / per_second / 60, 2
    )

    # Where the uncertain pairs land. Nobody knows whether they match, so this
    # is never scored right or wrong - it reports a lean. An encoder that puts
    # the middle band up against the matching pairs will join too much; one
    # that puts it down among the mismatches will leave one story in pieces.
    halfway = (float(same_scores.mean()) + float(different_scores.mean())) / 2
    if pairs.get("ambiguous"):
        middle = score(pairs["ambiguous"])
        reading.ambiguous_mean = round(float(middle.mean()), 3)
        reading.ambiguous_lean = round(float((middle > halfway).mean()), 3)

    # One outlet's second piece on one subject in one day. A different question
    # from the one separation answers, and kept out of it for that reason: an
    # encoder scoring these as high as genuine matches cannot tell a follow-up
    # from a new story.
    if pairs.get("related"):
        second = score(pairs["related"])
        reading.related_mean = round(float(second.mean()), 3)
        reading.related_lean = round(float((second > halfway).mean()), 3)

    reading.peak_memory_gb = peak_memory_gb()
    reading.state = ReadingState.MEASURED
    save()
    print(f"{chosen['slug']:22} separation {reading.separation:.4f}  "
          f"spread {reading.spread:.3f}  "
          f"middle lean {reading.ambiguous_lean}  "
          f"{reading.articles_a_second:.1f} articles a second", flush=True)


def stage_collect(args: argparse.Namespace) -> None:
    """Merge the readings into one table and one manifest.

    The readings directory holds one file a shard, each written by this run, so
    listing it is bounded by the matrix and not by the repository.
    """
    settings = read_config(args.config)
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))

    readings = []
    for encoder in settings["encoders"]:
        reading_path = args.readings_from / f"{encoder['slug']}.json"
        if reading_path.is_file():
            readings.append(json.loads(reading_path.read_text(encoding="utf-8")))
        else:
            readings.append(
                {"slug": encoder["slug"], "model_id": encoder["model_id"],
                 "state": "did not report", "why": encoder["why"]}
            )

    measured = [r for r in readings if r.get("state") == "measured"]
    measured.sort(key=lambda r: -r["separation"])
    ordered = measured + [r for r in readings if r.get("state") != "measured"]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "encoders.json").write_text(
        json.dumps({"version": settings["version"], "encoders": ordered},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    lines = [
        "# Encoder readings",
        "",
        f"Taken {time.strftime('%Y-%m-%d', time.gmtime())} on a GitHub "
        "`ubuntu-latest` runner: 4 processor threads, 16 GB, no graphics card.",
        "",
        "**Separation** is the chance this encoder scores a likely-same pair above "
        "a likely-different one. 1.0 is perfect, 0.5 is a coin toss. No difference "
        "in similarity scale can distort it.",
        "",
        "**Spread** is how far apart the two averages sit. A wide spread leaves "
        "more room for a decision to sit between them.",
        "",
        "**Middle lean** is the share of uncertain pairs - the ones whose titles "
        "share something but not much - that this encoder scores above the "
        "halfway mark between matching and mismatching. Nobody knows whether "
        "those pairs match, so this is never right or wrong. High means the "
        "encoder will join too much; low means it will leave one story in "
        "pieces.",
        "",
        "**Second-piece lean** is the same reading for one outlet's second "
        "article on one subject in one day - a correction or a follow-up. Near "
        "one means this encoder cannot tell an update from a new story.",
        "",
        "| Encoder | Numbers | Size | Separation | Spread | Same | Different | "
        "Middle | Middle lean | Second piece | Second-piece lean | "
        "Articles a second | 15,122 take | A day takes | Peak memory |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | ---: |",
    ]
    for reading in ordered:
        if reading.get("state") != "measured":
            got = reading.get("articles_done", 0)
            asked = reading.get("articles_to_encode", 0)
            progress = f"{got}/{asked}" if asked else ""
            lines.append(
                f"| `{reading['slug']}` | | | {reading.get('state', '?')} "
                f"{progress} | | | | | | | | | | | |"
            )
            continue
        memory = f"{reading['peak_memory_gb']} GB" if reading.get("peak_memory_gb") else ""

        def shown(value: object) -> str:
            return f"{value:.3f}" if isinstance(value, (int, float)) else ""

        lines.append(
            f"| `{reading['slug']}` | {reading['numbers_an_article']} | "
            f"{reading['parameters_millions']}M | **{reading['separation']:.4f}** | "
            f"{reading['spread']:.3f} | {reading['same_mean']:.3f} | "
            f"{reading['different_mean']:.3f} | "
            f"{shown(reading.get('ambiguous_mean'))} | "
            f"{shown(reading.get('ambiguous_lean'))} | "
            f"{shown(reading.get('related_mean'))} | "
            f"{shown(reading.get('related_lean'))} | "
            f"{reading['articles_a_second']:.1f} | "
            f"{reading['minutes_for_whole_archive']:.1f} min | "
            f"{reading['minutes_for_one_day']:.2f} min | {memory} |"
        )
    lines += ["", "Why each encoder is in the list:", ""]
    for reading in ordered:
        lines.append(f"- **`{reading['slug']}`** - {reading.get('why', '')}")
    lines.append("")
    (args.out / "encoders.md").write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "version": settings["version"],
        "taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": args.commit,
        "workflow_run": args.run_url,
        "runner": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor_threads": settings["encode"]["threads"],
        },
        "input": {
            "first_day": pairs["first_day"],
            "last_day": pairs["last_day"],
            "days_named": pairs["days_named"],
            "articles_read": pairs["articles_read"],
            "articles_encoded": pairs["articles_encoded"],
            "same_pairs": pairs["same_pairs"],
            "different_pairs": pairs["different_pairs"],
            "ambiguous_pairs": pairs.get("ambiguous_pairs", 0),
            "pair_build": pairs["pair_build"],
        },
        "encode": settings["encode"],
        "encoders_asked": len(settings["encoders"]),
        "encoders_measured": len(measured),
        "encoders_unavailable": [
            r["slug"] for r in readings if r.get("state") != "measured"
        ],
    }
    (args.out.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print(f"measured {len(measured)} of {len(settings['encoders'])} encoders")
    for reading in measured:
        print(f"  {reading['slug']:22} {reading['separation']:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/encoder-comparison.json"))
    stages = parser.add_subparsers(dest="stage", required=True)

    build = stages.add_parser("pairs", help="build the pair set once")
    build.add_argument("--digest-root", type=Path, default=Path("frontend/public/digest"))
    build.add_argument("--start", required=True)
    build.add_argument("--end", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.set_defaults(run=stage_pairs)

    one = stages.add_parser("score", help="score one encoder")
    one.add_argument("--slug", required=True)
    one.add_argument("--pairs", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    one.set_defaults(run=stage_score)

    merge = stages.add_parser("collect", help="merge the readings")
    merge.add_argument("--pairs", type=Path, required=True)
    merge.add_argument("--readings-from", type=Path, required=True)
    merge.add_argument("--out", type=Path, required=True)
    merge.add_argument("--commit", default="")
    merge.add_argument("--run-url", default="")
    merge.set_defaults(run=stage_collect)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
