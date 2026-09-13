"""Build `corpus/reference-dataset-1/`, the frozen set every classification number is taken on.

Four verbs, and the order is the order:

    python backend/utilities/build_reference_dataset.py plan
    python backend/utilities/build_reference_dataset.py fetch
    python backend/utilities/build_reference_dataset.py split
    python backend/utilities/build_reference_dataset.py verify

`plan` reads the committed archive once and writes a candidate list. `fetch`
takes the article text a candidate at a time, honouring robots, and is resumable.
`split` draws the split and refuses to write a set that fails any floor or any
leakage check. `verify` re-runs every check over what is committed, and is the
operator surface for the question "is this set still what it says it is".

**The whole tool exists to stop a number flattering us.** Two articles from one
outlet share boilerplate, a house style and often a wire original, so a random
split puts near-duplicates on both sides and every accuracy figure comes out
better than the classifier is. So the split is drawn on the **registrable
domain**: an outlet lands wholly on one side or wholly on the other, and
`split` refuses if any domain reaches both.

**A disjointness check passes on an empty set**, which is why the floors are
checked in the same breath. A builder that wrote every article to `dev.txt` and
left `test.txt` empty would satisfy "no domain on both sides" perfectly.

**Three collections must not overlap this one**, and each is a different door to
the same contamination:

- `corpus/corpus.jsonl` is the rolling fine-tuning window. An article in both was
  trained on and then measured on.
- `corpus/holdout.txt` is the set the fine-tune never trains on. An article in
  both spends a holdout twice.
- `dev` and `test` are each other's. A key on both sides is the plain case.

The intersections are on `url_key` and never on article text. A near-duplicate two
collections hold under two addresses is a different problem, and this tool does
not claim to catch it.

**`plan` is the one growing read, it runs by hand, and its cost is written down.**
It walks every committed day under `frontend/public/digest/`. Measured
2026-09-13 on an Intel Core i7-1265U: 23 days, 24,244,409 bytes, 9,278 items,
1.3 seconds. That rises by about one day and 1 MB every day the pipeline runs,
which is exactly what `CLAUDE.md` Guardrail #12 is about - so it is a verb a
person types once rather than a step anything schedules, and no test repeats it
(`CLAUDE.md` section 13). `verify` reads only the frozen set and the capped
corpus window, both of which are fixed in size.

**Fetched text is data.** It crosses the trust boundary exactly once, through
`extract.extract_text`, which is the same trafilatura-plus-sanitizer path the
pipeline uses (Guardrail #11). Filenames come from `url_key`, which is recomputed
from the canonical URL, and never from anything a page said.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from courlan import extract_domain

from idhazh import config, corpus, extract, fetch
from idhazh.contracts.app_config import ExtractConfig, ReferenceDatasetConfig
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import RobotsOutcome
from idhazh.contracts.reference_dataset import ReferenceDatasetRow, ReferenceSplit
from idhazh.discover import canonicalise
from idhazh.sanitize import SANITIZER_VERSION

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATASET_RELPATH: Final = "corpus/reference-dataset-1"
DIGEST_RELPATH: Final = "frontend/public/digest"
WORK_RELPATH: Final = "backend/var/reference-dataset-1"

ARTICLES_DIRNAME: Final = "articles"
SPLITS_DIRNAME: Final = "splits"
DATASET_FILENAME: Final = "dataset.jsonl"
CANDIDATES_FILENAME: Final = "candidates.jsonl"
#: What a printed table is padded to, matching the other utilities here.
_WIDTH: Final = 30


@dataclass(frozen=True)
class Candidate:
    """One archive item that might become a reference row.

    `domain` is the registrable domain and not the host. Two articles on
    `economictimes.indiatimes.com` and `timesofindia.indiatimes.com` are one
    publisher group sharing a template and often the same wire copy, so grouping
    at the host would put them on opposite sides of the split and call it
    disjoint.
    """

    url_key: str
    canonical_url: str
    source_url: str
    domain: str
    source_id: str
    vertical: str
    published_date: str
    title: str

    def to_payload(self) -> dict[str, str]:
        return {
            "url_key": self.url_key,
            "canonical_url": self.canonical_url,
            "source_url": self.source_url,
            "domain": self.domain,
            "source_id": self.source_id,
            "vertical": self.vertical,
            "published_date": self.published_date,
            "title": self.title,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, str]) -> Candidate:
        return cls(
            url_key=payload["url_key"],
            canonical_url=payload["canonical_url"],
            source_url=payload["source_url"],
            domain=payload["domain"],
            source_id=payload["source_id"],
            vertical=payload["vertical"],
            published_date=payload["published_date"],
            title=payload["title"],
        )


def shown(path: Path) -> str:
    """Repo-relative and POSIX where it can be (`CLAUDE.md` section 2)."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def registrable_domain(url: str) -> str:
    """The unit the split is drawn on: the domain somebody registered.

    `courlan.extract_domain` reads the public suffix list that ships with `tld`,
    so `bbc.co.uk` stays whole and `aleximas.substack.com` collapses to
    `substack.com`. Collapsing is the conservative direction: grouping two
    outlets together can only move articles off one side of the split, never
    spread one outlet across both.
    """
    found = extract_domain(url, fast=False)
    if found:
        return str(found).lower()
    host = url.split("/")[2].lower() if "//" in url else url.lower()
    return host.removeprefix("www.")


# --- plan ------------------------------------------------------------------


def archive_candidates(digest_dir: Path) -> list[Candidate]:
    """Every published item, as a candidate. The one growing read - see the module docstring."""
    found: dict[str, Candidate] = {}
    for path in sorted(digest_dir.rglob("digest.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        for item in day.get("items", []):
            source_url = item.get("source_url")
            title = item.get("title")
            if not source_url or not title:
                continue
            canonical = canonicalise(source_url)
            key = derive_url_key(canonical)
            found.setdefault(
                key,
                Candidate(
                    url_key=key,
                    canonical_url=canonical,
                    source_url=source_url,
                    domain=registrable_domain(canonical),
                    source_id=str(item.get("source_id") or "unknown"),
                    vertical=str(item.get("vertical") or "unknown"),
                    published_date=str(day.get("date") or ""),
                    title=str(title),
                ),
            )
    return sorted(found.values(), key=lambda c: c.url_key)


def spread_across_domains(
    candidates: Sequence[Candidate], *, per_domain: int
) -> list[Candidate]:
    """Round-robin across domains so no outlet dominates, capped at `per_domain` each.

    Deterministic: domains in sorted order, candidates sorted by `url_key` inside
    each, and no random number anywhere. Re-running `plan` on an unchanged
    archive returns the same list, which is what lets a fetch be resumed rather
    than reshuffled.
    """
    buckets: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate.domain].append(candidate)
    for bucket in buckets.values():
        bucket.sort(key=lambda c: c.url_key)

    picked: list[Candidate] = []
    for depth in range(per_domain):
        for domain in sorted(buckets):
            bucket = buckets[domain]
            if depth < len(bucket):
                picked.append(bucket[depth])
    return picked


def plan(
    dataset_dir: Path,
    work_dir: Path,
    digest_dir: Path,
    corpus_dir: Path,
    asked: ReferenceDatasetConfig,
) -> int:
    """Choose the candidate pool, minus every collection this set must not overlap."""
    started = time.monotonic()
    everything = archive_candidates(digest_dir)
    trained_on = {row.url_key for row in corpus.read_rows(corpus_dir)}
    held_out = corpus.read_holdout(corpus_dir)
    already = {row.url_key for row in read_dataset(dataset_dir)}

    free = [
        candidate
        for candidate in everything
        if candidate.url_key not in trained_on
        and candidate.url_key not in held_out
        and candidate.url_key not in already
    ]
    picked = spread_across_domains(free, per_domain=asked.rows_per_domain_max)

    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / CANDIDATES_FILENAME
    _write_atomically(
        path,
        "".join(
            json.dumps(candidate.to_payload(), sort_keys=True) + "\n" for candidate in picked
        ),
    )

    print(f"{'archive items read':<{_WIDTH}} {len(everything)}")
    print(f"{'in the fine-tuning window':<{_WIDTH}} {len(trained_on)}")
    print(f"{'in the fine-tuning holdout':<{_WIDTH}} {len(held_out)}")
    print(f"{'free to use':<{_WIDTH}} {len(free)}")
    print(f"{'candidates, capped per domain':<{_WIDTH}} {len(picked)}")
    print(f"{'domains they cover':<{_WIDTH}} {len({c.domain for c in picked})}")
    print(f"{'this read took':<{_WIDTH}} {time.monotonic() - started:.1f} s")
    print(f"wrote {shown(path)}")
    return 0 if picked else 1


# --- fetch -----------------------------------------------------------------


def read_candidates(work_dir: Path) -> list[Candidate]:
    path = work_dir / CANDIDATES_FILENAME
    if not path.is_file():
        return []
    return [
        Candidate.from_payload(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def article_path(dataset_dir: Path, url_key: str) -> Path:
    """`articles/<url_key>.txt`. The name is recomputed identity, never source text."""
    return dataset_dir / ARTICLES_DIRNAME / f"{url_key}.txt"


def _robots_for(origin_url: str, config_: ExtractConfig) -> fetch.RobotsRules:
    return fetch.robots_rules(
        fetch.fetch(
            fetch.robots_url(origin_url), config=config_, permission=RobotsOutcome.ALLOWED
        )
    )


def fetch_articles(
    dataset_dir: Path,
    work_dir: Path,
    asked: ReferenceDatasetConfig,
    extract_config: ExtractConfig,
    *,
    limit: int | None,
) -> int:
    """Take the article text one candidate at a time. Resumable, and polite by construction."""
    candidates = read_candidates(work_dir)
    if not candidates:
        print(f"no candidates under {shown(work_dir)}. Run `plan` first")
        return 1

    rules: dict[str, fetch.RobotsRules] = {}
    kept = refused = 0
    attempted = 0
    for candidate in candidates:
        target = article_path(dataset_dir, candidate.url_key)
        if target.is_file():
            kept += 1
            continue
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        origin = fetch.origin(candidate.canonical_url)
        if origin not in rules:
            rules[origin] = _robots_for(candidate.canonical_url, extract_config)
            time.sleep(asked.request_delay_seconds)
        permission = rules[origin].permits(extract_config.user_agent, candidate.canonical_url)
        result = fetch.fetch(
            candidate.canonical_url, config=extract_config, permission=permission
        )
        time.sleep(asked.request_delay_seconds)
        text = _usable_text(result, extract_config, words_min=asked.article_words_min)
        if text is None:
            refused += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_atomically(target, text)
        kept += 1
        if kept % 25 == 0:
            print(f"  {kept} kept, {refused} refused", flush=True)

    print(f"{'candidates':<{_WIDTH}} {len(candidates)}")
    print(f"{'articles on disk':<{_WIDTH}} {kept}")
    print(f"{'refused this pass':<{_WIDTH}} {refused}")
    print(f"{'still to fetch':<{_WIDTH}} {len(candidates) - kept - refused}")
    return 0


def _usable_text(
    result: fetch.FetchResult, config_: ExtractConfig, *, words_min: int
) -> str | None:
    """The sanitized article, or None with the reason discarded.

    A refusal is not interesting one article at a time - the set is built from
    whatever came back, and `plan` over-samples for exactly that reason.
    """
    if not result.ok:
        return None
    html = result.body.decode("utf-8", errors="replace")
    if extract.is_paywalled(html, config_):
        return None
    body = extract.extract_text(html)
    if body is None or len(body.split()) < words_min:
        return None
    return body if body.endswith("\n") else body + "\n"


# --- split -----------------------------------------------------------------


def assign_domains(counts: Mapping[str, int]) -> dict[str, ReferenceSplit]:
    """Every domain lands wholly on one side, and the two sides come out about level.

    Largest domain first, each one to whichever side is behind. It is the ordinary
    greedy number partition, it is deterministic, and the tie-break is the domain
    name so two runs over the same counts agree.
    """
    sides: dict[ReferenceSplit, int] = {ReferenceSplit.DEV: 0, ReferenceSplit.TEST: 0}
    assigned: dict[str, ReferenceSplit] = {}
    for domain in sorted(counts, key=lambda name: (-counts[name], name)):
        behind = sides[ReferenceSplit.DEV] <= sides[ReferenceSplit.TEST]
        side = ReferenceSplit.DEV if behind else ReferenceSplit.TEST
        assigned[domain] = side
        sides[side] += counts[domain]
    return assigned


def leakage_faults(
    rows: Sequence[ReferenceDatasetRow],
    splits: Mapping[ReferenceSplit, Sequence[str]],
    *,
    trained_on: Set[str],
    held_out: Set[str],
) -> list[str]:
    """Every way this set could flatter a number, checked, and named where it does.

    Order matters to a reader rather than to the code: the two splits first,
    because that is the leak everybody pictures, then the two fine-tuning
    collections, because those are the same contamination arriving by another
    door.
    """
    faults: list[str] = []
    dev, test = set(splits[ReferenceSplit.DEV]), set(splits[ReferenceSplit.TEST])
    by_key = {row.url_key: row for row in rows}

    both = sorted(dev & test)
    if both:
        faults.append(f"{len(both)} url_key on both sides of the split: {both[:3]}")

    domains: dict[str, set[ReferenceSplit]] = defaultdict(set)
    for side, keys in splits.items():
        for key in keys:
            row = by_key.get(key)
            if row is not None:
                domains[row.source_domain].add(side)
    shared = sorted(name for name, sides in domains.items() if len(sides) > 1)
    if shared:
        faults.append(f"{len(shared)} domain on both sides of the split: {shared[:3]}")

    listed = dev | test
    missing = sorted(set(by_key) - listed)
    if missing:
        faults.append(f"{len(missing)} dataset row is in no split: {missing[:3]}")
    unknown = sorted(listed - set(by_key))
    if unknown:
        faults.append(f"{len(unknown)} split key has no dataset row: {unknown[:3]}")

    trained = sorted(set(by_key) & set(trained_on))
    if trained:
        faults.append(
            f"{len(trained)} row is in corpus/corpus.jsonl, so it was trained on "
            f"and then measured on: {trained[:3]}"
        )
    holdout = sorted(set(by_key) & set(held_out))
    if holdout:
        faults.append(
            f"{len(holdout)} row is in corpus/holdout.txt, which spends one holdout "
            f"twice: {holdout[:3]}"
        )
    return faults


def floor_faults(
    rows: Sequence[ReferenceDatasetRow],
    splits: Mapping[ReferenceSplit, Sequence[str]],
    asked: ReferenceDatasetConfig,
) -> list[str]:
    """The floors, because a disjointness check passes on an empty set."""
    faults: list[str] = []
    by_key = {row.url_key: row for row in rows}
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        keys = [key for key in splits[side] if key in by_key]
        domains = {by_key[key].source_domain for key in keys}
        if len(keys) < asked.rows_per_split_min:
            faults.append(
                f"{side.value} holds {len(keys)} rows, under the floor of "
                f"{asked.rows_per_split_min}"
            )
        if len(domains) < asked.domains_per_split_min:
            faults.append(
                f"{side.value} covers {len(domains)} registrable domains, under the "
                f"floor of {asked.domains_per_split_min}"
            )
    return faults


def build_rows(
    candidates: Sequence[Candidate],
    dataset_dir: Path,
    *,
    fetched_on: str,
) -> list[ReferenceDatasetRow]:
    """One row per candidate whose article text is on disk, in `url_key` order."""
    rows: list[ReferenceDatasetRow] = []
    for candidate in sorted(candidates, key=lambda c: c.url_key):
        path = article_path(dataset_dir, candidate.url_key)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rows.append(
            ReferenceDatasetRow(
                version=ReferenceDatasetRow.schema_version(),
                url_key=candidate.url_key,
                canonical_url=candidate.canonical_url,
                source_url=candidate.source_url,
                source_domain=candidate.domain,
                source_id=candidate.source_id,
                vertical=candidate.vertical,
                published_date=candidate.published_date,
                title=candidate.title,
                article_words=len(text.split()),
                article_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                extractor_version=extract.EXTRACTOR_VERSION,
                sanitizer_version=SANITIZER_VERSION,
                fetched_on=fetched_on,
            )
        )
    return rows


def split(
    dataset_dir: Path,
    work_dir: Path,
    corpus_dir: Path,
    asked: ReferenceDatasetConfig,
    *,
    fetched_on: str | None,
) -> int:
    """Draw the split, and refuse to write a set that fails any check."""
    candidates = read_candidates(work_dir)
    if not candidates:
        print(f"no candidates under {shown(work_dir)}. Run `plan` first")
        return 1

    day = fetched_on or datetime.now(UTC).strftime("%Y-%m-%d")
    rows = build_rows(candidates, dataset_dir, fetched_on=day)
    if not rows:
        print("no article text on disk. Run `fetch` first")
        return 1

    by_domain: dict[str, int] = defaultdict(int)
    for row in rows:
        by_domain[row.source_domain] += 1
    sides = assign_domains(by_domain)
    splits: dict[ReferenceSplit, list[str]] = {ReferenceSplit.DEV: [], ReferenceSplit.TEST: []}
    for row in rows:
        splits[sides[row.source_domain]].append(row.url_key)
    for keys in splits.values():
        keys.sort()

    faults = leakage_faults(
        rows,
        splits,
        trained_on={row.url_key for row in corpus.read_rows(corpus_dir)},
        held_out=corpus.read_holdout(corpus_dir),
    ) + floor_faults(rows, splits, asked)

    _report(rows, splits)
    if faults:
        for fault in faults:
            print(f"  REFUSED {fault}")
        print("refusing to write a set that fails a check above")
        return 1

    _write_atomically(
        dataset_dir / DATASET_FILENAME,
        "".join(
            json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n" for row in rows
        ),
    )
    for side, keys in splits.items():
        _write_atomically(
            dataset_dir / SPLITS_DIRNAME / f"{side.value}.txt", "".join(f"{key}\n" for key in keys)
        )
    print(f"wrote {shown(dataset_dir / DATASET_FILENAME)} and both split lists")
    return 0


# --- verify ----------------------------------------------------------------


def read_dataset(dataset_dir: Path) -> list[ReferenceDatasetRow]:
    path = dataset_dir / DATASET_FILENAME
    if not path.is_file():
        return []
    return [
        ReferenceDatasetRow.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_split(dataset_dir: Path, side: ReferenceSplit) -> list[str]:
    path = dataset_dir / SPLITS_DIRNAME / f"{side.value}.txt"
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_faults(rows: Sequence[ReferenceDatasetRow], dataset_dir: Path) -> list[str]:
    """A row whose article file is gone, or no longer the text the label was taken against."""
    faults: list[str] = []
    for row in rows:
        path = article_path(dataset_dir, row.url_key)
        if not path.is_file():
            faults.append(f"{row.url_key[:12]} has no article file")
            continue
        text = path.read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row.article_sha256:
            faults.append(f"{row.url_key[:12]} article text no longer matches its digest")
        elif len(text.split()) != row.article_words:
            faults.append(f"{row.url_key[:12]} article word count no longer matches the row")
    return faults


def verify(dataset_dir: Path, corpus_dir: Path, asked: ReferenceDatasetConfig) -> int:
    """Re-run every check over what is committed. Bounded: the set is frozen."""
    rows = read_dataset(dataset_dir)
    if not rows:
        print(f"no dataset under {shown(dataset_dir)}")
        return 1
    splits = {side: read_split(dataset_dir, side) for side in ReferenceSplit}
    faults = (
        leakage_faults(
            rows,
            splits,
            trained_on={row.url_key for row in corpus.read_rows(corpus_dir)},
            held_out=corpus.read_holdout(corpus_dir),
        )
        + floor_faults(rows, splits, asked)
        + text_faults(rows, dataset_dir)
    )
    _report(rows, splits)
    for fault in faults:
        print(f"  FAULT {fault}")
    print("every check passed" if not faults else f"{len(faults)} checks failed")
    return 1 if faults else 0


# --- shared ----------------------------------------------------------------


def _report(
    rows: Sequence[ReferenceDatasetRow], splits: Mapping[ReferenceSplit, Sequence[str]]
) -> None:
    by_key = {row.url_key: row for row in rows}
    print(f"{'rows':<{_WIDTH}} {len(rows)}")
    print(f"{'registrable domains':<{_WIDTH}} {len({row.source_domain for row in rows})}")
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        keys = [key for key in splits.get(side, ()) if key in by_key]
        domains = {by_key[key].source_domain for key in keys}
        words = sorted(by_key[key].article_words for key in keys)
        median = words[len(words) // 2] if words else 0
        print(
            f"{'  ' + side.value:<{_WIDTH}} {len(keys)} rows, {len(domains)} domains, "
            f"median {median} words"
        )
    labelled = sum(1 for row in rows if not row.labels.is_empty)
    print(f"{'rows a person has labelled':<{_WIDTH}} {labelled}")


def _write_atomically(path: Path, body: str) -> None:
    """Temp-file-plus-rename, so an interrupted write cannot truncate a committed file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(body, encoding="utf-8", newline="")
    temp.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=REPO_ROOT / DATASET_RELPATH)
    parser.add_argument("--work-dir", type=Path, default=REPO_ROOT / WORK_RELPATH)
    parser.add_argument("--digest-dir", type=Path, default=REPO_ROOT / DIGEST_RELPATH)
    parser.add_argument("--corpus-dir", type=Path, default=REPO_ROOT / corpus.CORPUS_ROOT_RELPATH)
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    verbs = parser.add_subparsers(dest="verb", required=True)

    verbs.add_parser("plan", help="Choose the candidate pool. Reads the whole archive, once.")
    fetching = verbs.add_parser("fetch", help="Take the article text. Resumable.")
    fetching.add_argument("--limit", type=int, default=None, help="Stop after this many attempts.")
    splitting = verbs.add_parser("split", help="Draw the split, or refuse and say why.")
    splitting.add_argument("--fetched-on", default=None, help="YYYY-MM-DD. Defaults to today.")
    verbs.add_parser("verify", help="Re-check the committed set.")

    args = parser.parse_args(argv)
    settings = config.load(args.config)
    asked = settings.app.reference_dataset
    if args.verb == "plan":
        return plan(args.dataset_dir, args.work_dir, args.digest_dir, args.corpus_dir, asked)
    if args.verb == "fetch":
        return fetch_articles(
            args.dataset_dir, args.work_dir, asked, settings.app.extract, limit=args.limit
        )
    if args.verb == "split":
        return split(
            args.dataset_dir, args.work_dir, args.corpus_dir, asked, fetched_on=args.fetched_on
        )
    return verify(args.dataset_dir, args.corpus_dir, asked)


if __name__ == "__main__":
    sys.exit(main())
