"""The arithmetic of archive search: ranking, recall, and what a corpus means.

The published surface ranks with `frontend/src/lib/assist/search.ts`. This
module is its twin: the same floor, the same slot count, the same tie-break,
all three read from `config/idhazh.json`.

**This module is read by two different callers with two different jobs.**
`backend/tests/test_retrieval_eval.py` proves the arithmetic on hand-built
vectors and `tmp_path` fixtures - ranking order, the capped denominator, a miss
versus an absence - and never opens the committed archive or runs the real
encoder. Whether the archive's search is actually any GOOD is a quality
measurement on published data, not code behaviour (CLAUDE.md section 13 rule
2), so it is an operator's job, run by hand with `backend/utilities/measure_retrieval.py`
and never gated in a test run. The five-query Playwright fixture stays the
wiring check it always was.

**Every loader here takes the set it reads by name.** `load_corpus` takes the
exact days to open; `load_index_corpus` takes the exact month shards. Neither
lists a directory or globs a tree, and neither is ever handed "the whole
archive" - an evaluation set is a value named once (by a caller, or by a
test's own fixture), and the cost of reading it is the size of that name,
never the size of the published archive (CLAUDE.md Guardrail #12). The one
caller that genuinely needs every committed day and every committed month
shard - `measure_retrieval.py`'s membership check - names them itself with one
directory listing apiece, and pays that cost because that is the question it
was built to answer.

**recall at the slot count is the number.** Reciprocal rank is computed and
reported and is a diagnostic only: the surface is a flat capped list with no
rank cue, so rewarding first place would measure a claim the product does not
make.

**The denominator is capped at the slots that exist.** A topic query has more
right answers than the list can hold, so `found / len(gold)` would report a
retriever that filled every slot correctly as a failure and would make the score
a function of how generous the labeller was. `found / min(gold, slots)` asks the
question the surface can answer: of the right answers you could have shown in
the slots you have, how many did you show. The uncapped figure is reported
beside it so nothing is hidden.

**A miss and an absence are different failures.** An item with no vector cannot
be retrieved at any threshold, and counting that as a ranking failure would
blame the encoder for a gap in coverage. Every result carries both.

**The number is a lower bound, not recall.** The labels were pooled from an
index that could see 44.5 percent of the corpus, so a right answer that carried
no vector on labelling day could not be labelled. It can be retrieved now, and
this metric counts it as a wrong answer. Every result therefore also carries
`unlabelled` - how many of the slots a query filled with an item nobody judged.
That is the blindness, printed rather than argued about.
"""

from __future__ import annotations

import base64
import json
import math
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, dequantise

#: Where the pipeline writes the days the published site reads, one day's
#: directory built straight from its own `YYYY-MM-DD`, never a glob.
DIGEST_RELDIR: Final = "frontend/public/digest"
#: Where the pipeline writes the month shards a reader's tab actually searches.
INDEX_RELDIR: Final = "frontend/public/assist/index"
#: One month shard, `YYYY-MM.json`, beside its `.bin` of vectors.
INDEX_SHARD_GLOB: Final = "[0-9][0-9][0-9][0-9]-[0-9][0-9].json"
#: The committed query set, relative to the repository root.
QUERY_SET_RELPATH: Final = "tests/fixtures/search/retrieval-queries.json"


@dataclass(frozen=True, slots=True)
class CorpusItem:
    """One published item as the search surface sees it.

    `date` is part of the address: an item id is unique within a day and is
    reused across days, so an id alone names two different stories.
    """

    date: str
    item_id: str
    entities: tuple[str, ...]
    vector: tuple[float, ...] | None

    @property
    def address(self) -> tuple[str, str]:
        return (self.date, self.item_id)


@dataclass(frozen=True, slots=True)
class Corpus:
    items: tuple[CorpusItem, ...]

    @property
    def searchable(self) -> tuple[CorpusItem, ...]:
        return tuple(item for item in self.items if item.vector is not None)

    @property
    def coverage(self) -> float:
        """Share of published items a reader could reach through search at all."""
        if not self.items:
            return 0.0
        return len(self.searchable) / len(self.items)


@dataclass(frozen=True, slots=True)
class LabelledQuery:
    """One question and every published item that answers it. Binary relevance."""

    id: str
    query: str
    intent: str
    relevant: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Hit:
    date: str
    item_id: str
    score: float

    @property
    def address(self) -> tuple[str, str]:
        return (self.date, self.item_id)


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    """What one query found, and why it missed what it missed."""

    query_id: str
    gold: int
    gold_with_vector: int
    found: int
    slots: int
    reciprocal_rank: float
    #: Slots filled by an item no labeller ever judged. Not a failure - a blind spot.
    unlabelled: int = 0

    @property
    def recall(self) -> float:
        """The gate metric: found over the right answers the slots could hold."""
        ceiling = min(self.gold, self.slots)
        return self.found / ceiling if ceiling else 0.0

    @property
    def recall_uncapped(self) -> float:
        return self.found / self.gold if self.gold else 0.0

    @property
    def recall_reachable(self) -> float:
        """Found over the right answers that carry a vector at all.

        The ranking question with the coverage question taken out of it. An
        item with no vector is invisible to every threshold, so counting it as
        a ranking miss blames the encoder for a gap in the pipeline.
        """
        ceiling = min(self.gold_with_vector, self.slots)
        return self.found / ceiling if ceiling else 0.0

    @property
    def unreachable(self) -> int:
        """Gold items with no vector. Not a ranking failure - nothing to rank."""
        return self.gold - self.gold_with_vector


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    """The measurement, with everything needed to read it honestly."""

    outcomes: tuple[QueryOutcome, ...]
    corpus_items: int
    corpus_searchable: int
    result_limit: int
    similarity_floor: float

    @property
    def n(self) -> int:
        return len(self.outcomes)

    @property
    def recall(self) -> float:
        return statistics.fmean(o.recall for o in self.outcomes) if self.outcomes else 0.0

    @property
    def recall_uncapped(self) -> float:
        if not self.outcomes:
            return 0.0
        return statistics.fmean(o.recall_uncapped for o in self.outcomes)

    @property
    def answerable(self) -> tuple[QueryOutcome, ...]:
        """Queries with at least one right answer that carries a vector.

        A query whose whole gold set is unembedded measures the coverage gap and
        nothing else. It stays in `outcomes`, because a reader who types it gets
        nothing back and that is a real result; it is excluded here, because the
        ranking cannot be judged on a question the index cannot answer.
        """
        return tuple(o for o in self.outcomes if o.gold_with_vector)

    @property
    def recall_reachable(self) -> float:
        rows = self.answerable
        return statistics.fmean(o.recall_reachable for o in rows) if rows else 0.0

    @property
    def standard_error_reachable(self) -> float:
        rows = self.answerable
        if len(rows) < 2:
            return 0.0
        return statistics.stdev(o.recall_reachable for o in rows) / math.sqrt(len(rows))

    @property
    def unanswerable(self) -> int:
        """Queries no threshold could ever answer, because no answer was embedded."""
        return self.n - len(self.answerable)

    @property
    def standard_error(self) -> float:
        """Of the mean, over queries. Two queries cannot have a spread worth quoting."""
        if self.n < 2:
            return 0.0
        return statistics.stdev(o.recall for o in self.outcomes) / math.sqrt(self.n)

    @property
    def mean_reciprocal_rank(self) -> float:
        """Diagnostic only. Never a gate - see the module docstring."""
        if not self.outcomes:
            return 0.0
        return statistics.fmean(o.reciprocal_rank for o in self.outcomes)

    @property
    def gold_coverage(self) -> float:
        """Share of labelled right answers that carry a vector at all."""
        gold = sum(o.gold for o in self.outcomes)
        if not gold:
            return 0.0
        return sum(o.gold_with_vector for o in self.outcomes) / gold

    @property
    def unlabelled_share(self) -> float:
        """Share of filled slots holding an item nobody judged either way.

        Every one of them is counted as a wrong answer, and some of them are
        right answers the labeller could not see. This is how far the number
        below could be from the truth, in the direction of too low.
        """
        filled = sum(o.found + o.unlabelled for o in self.outcomes)
        if not filled:
            return 0.0
        return sum(o.unlabelled for o in self.outcomes) / filled

    def summary(self) -> str:
        return (
            f"recall@{self.result_limit} {self.recall:.3f} "
            f"+/- {self.standard_error:.3f} (n={self.n}); "
            f"reachable-only {self.recall_reachable:.3f} "
            f"+/- {self.standard_error_reachable:.3f} (n={len(self.answerable)}); "
            f"{self.unanswerable} queries have no embedded answer at all; "
            f"MRR {self.mean_reciprocal_rank:.3f} (diagnostic); "
            f"gold coverage {self.gold_coverage:.1%}; "
            f"{self.unlabelled_share:.1%} of filled slots hold an unjudged item, "
            f"so this is a lower bound; "
            f"corpus {self.corpus_searchable}/{self.corpus_items} items carry a vector; "
            f"floor {self.similarity_floor}"
        )


def load_corpus(root: Path, days: Sequence[str]) -> Corpus:
    """Exactly the named days, decoded the way the browser decodes it.

    `days` is `YYYY-MM-DD` strings; each becomes one path under
    `DIGEST_RELDIR`, built directly from the name rather than found by listing
    a directory. A day with no published `digest.json` is skipped rather than
    raised: an evaluation set named ahead of time can outlive a day that was
    pruned or never published, and that is the caller's question to answer, not
    this loader's. The cost of this read is `len(days)`, named once by the
    caller, never the size of the published archive (CLAUDE.md Guardrail #12).

    A day whose embedding block names another encoder, another width or another
    dtype contributes no vectors. That is `searchable()` in `search.ts`: a
    payload from a different encoder decodes perfectly into a different space,
    so every score it produces still looks like a score and means nothing.
    """
    items: list[CorpusItem] = []
    for day in days:
        year, month, day_of_month = day.split("-")
        path = root / DIGEST_RELDIR / year / month / day_of_month / "digest.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        block = payload.get("embeddings") or {}
        usable = (
            block.get("model_id") == EMBEDDER_ID
            and block.get("dtype") == DTYPE
            and block.get("dimensions") == DIMENSIONS
        )
        vectors: dict[str, str] = block.get("vectors", {}) if usable else {}
        for item in payload["items"]:
            encoded = vectors.get(item["item_id"])
            items.append(
                CorpusItem(
                    date=payload["date"],
                    item_id=item["item_id"],
                    entities=tuple(item.get("entities") or ()),
                    vector=(
                        tuple(dequantise(base64.b64decode(encoded)))
                        if encoded is not None
                        else None
                    ),
                )
            )
    return Corpus(items=tuple(items))


def index_months(root: Path) -> tuple[str, ...]:
    """The month stems the archive has committed, oldest first.

    One directory listing. No shard is opened, so a question about which months
    exist costs the same on the thousandth month as on the second.
    """
    directory = root / INDEX_RELDIR
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.stem for path in directory.glob(INDEX_SHARD_GLOB)))


def digest_days(root: Path) -> tuple[str, ...]:
    """The `YYYY-MM-DD` days the archive has committed, oldest first.

    One directory listing - the day names, read off the path a digest already
    sits at - and no `digest.json` is opened. This is `load_corpus`'s one
    accepted "name everything" cost (CLAUDE.md Guardrail #12): a caller that
    genuinely needs every published day, such as `measure_retrieval.py`'s
    membership check, lists the names once here and hands them to `load_corpus`
    explicitly, rather than `load_corpus` globbing the tree itself.
    """
    directory = root / DIGEST_RELDIR
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            f"{path.parent.parent.parent.name}-{path.parent.parent.name}-{path.parent.name}"
            for path in directory.glob("*/*/*/digest.json")
        )
    )


def load_index_corpus(root: Path, months: Sequence[str]) -> Corpus:
    """The same corpus, read the way a reader's tab now reads it.

    `load_corpus` above reads the day payloads. The published archive stopped
    carrying them: the page fetches `index/<YYYY-MM>.json` and its
    sibling `.bin`, and ranks over that. The two loaders exist so one question
    can be asked with everything else held still - did moving to the index cost
    any recall - and the answer is a comparison rather than an argument.

    `months` is the exact `YYYY-MM` stems to read, named by the caller rather
    than found by listing a directory or selected by a trailing-window knob.
    That selection - how many shards a reader's tab reads, and the one extra
    shard a thin month earns - is `readScope` in
    `frontend/src/lib/assist/search.ts`, fully covered there and in
    `frontend/tests/archive-scope.spec.ts`; duplicating it here would be a
    second copy of a rule with one home. A month with no committed shard is
    skipped rather than raised, for the same reason a missing day is skipped in
    `load_corpus`.

    A shard whose header names another encoder, another width or another dtype
    contributes no vectors, exactly as a day payload does above. The header's
    own `scale` decodes the bytes, rather than a constant here, because that is
    what `search.ts` does and a decoder that ignores the scale would rank a
    re-quantised shard as plausible nonsense.
    """
    directory = root / INDEX_RELDIR
    items: list[CorpusItem] = []
    for month in months:
        path = directory / f"{month}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        usable = (
            payload.get("model_id") == EMBEDDER_ID
            and payload.get("dtype") == DTYPE
            and payload.get("dimensions") == DIMENSIONS
        )
        raw = path.with_suffix(".bin").read_bytes() if usable else b""
        scale = float(payload.get("scale", 0.0))
        for entry in payload["entries"]:
            offset = entry.get("vector")
            vector: tuple[float, ...] | None = None
            if raw and offset is not None:
                block = raw[offset : offset + DIMENSIONS]
                if len(block) == DIMENSIONS:
                    vector = tuple(_scaled(block, scale))
            items.append(
                CorpusItem(
                    date=entry["date"],
                    item_id=entry["item_id"],
                    entities=(),
                    vector=vector,
                )
            )
    return Corpus(items=tuple(items))


def _scaled(raw: bytes, scale: float) -> list[float]:
    """int8 back to a unit vector, using the scale the shard states."""
    signed = [(byte - 256 if byte > 127 else byte) * scale for byte in raw]
    length = math.sqrt(sum(value * value for value in signed)) or 1.0
    return [value / length for value in signed]


def load_queries(root: Path) -> tuple[LabelledQuery, ...]:
    payload = json.loads((root / QUERY_SET_RELPATH).read_text(encoding="utf-8"))
    return tuple(
        LabelledQuery(
            id=row["id"],
            query=row["query"],
            intent=row["intent"],
            relevant=tuple((entry["date"], entry["item_id"]) for entry in row["relevant"]),
        )
        for row in payload["queries"]
    )


def entity_queries(corpus: Corpus, min_items: int) -> tuple[LabelledQuery, ...]:
    """The free tier: one query per entity slug carried by enough items.

    Nobody labels anything here. The relevant set is exactly the items that
    already carry the slug, so the tier costs nothing, cannot be biased by a
    labeller, and fires the moment the encoder or the vectors break.

    It yields nothing today, and that is a finding rather than a bug in this
    function: no published item carries an entity slug. `DigestItem.entities`
    is copied from `Article.entities`, and nothing in the pipeline ever writes
    that field. The tier is built to the specification so that it becomes the
    instrument it was meant to be on the day entities are populated, and until
    then the report says `n=0` instead of pretending.
    """
    counts: Counter[str] = Counter()
    for item in corpus.items:
        for slug in set(item.entities):
            counts[slug] += 1

    queries: list[LabelledQuery] = []
    for slug, count in sorted(counts.items()):
        if count < min_items:
            continue
        relevant = tuple(item.address for item in corpus.items if slug in item.entities)
        queries.append(
            LabelledQuery(
                id=f"entity-{slug}",
                query=slug.replace("-", " "),
                intent=f"Every item tagged with the entity {slug}.",
                relevant=relevant,
            )
        )
    return tuple(queries)


def rank(corpus: Corpus, query: list[float], limit: int, floor: float) -> list[Hit]:
    """The browser's ranking, in Python. Any change here is a change there.

    Score, then most recent, then item id - the last key is what makes two
    identical searches return identical lists. Three stable sorts rather than
    one composite key, because a composite key has to negate a string to sort
    it backwards and there is no honest way to do that.
    """
    hits = [
        Hit(date=item.date, item_id=item.item_id, score=_dot(query, item.vector))
        for item in corpus.searchable
        if item.vector is not None
    ]
    hits = [hit for hit in hits if hit.score >= floor]
    hits.sort(key=lambda hit: hit.item_id)
    hits.sort(key=lambda hit: hit.date, reverse=True)
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]


def _dot(left: list[float], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def embed_queries(root: Path, queries: tuple[LabelledQuery, ...]) -> list[list[float]]:
    """One forward pass per query, through the weights the browser downloads.

    The same file, so a vector committed by the pipeline and a query embedded
    here come from identical weights. Nothing here reaches the network: the
    encoder is committed under `frontend/static/`.
    """
    embedder = Embedder(root)
    if not embedder.available:
        raise FileNotFoundError("the committed encoder is missing; the measurement cannot run")
    embedder.load()
    return embedder.encode([query.query for query in queries])


def evaluate(
    corpus: Corpus,
    queries: tuple[LabelledQuery, ...],
    embedded: list[list[float]],
    limit: int,
    floor: float,
) -> RetrievalReport:
    """Rank every query and count what came back."""
    reachable = {item.address for item in corpus.searchable}
    outcomes: list[QueryOutcome] = []
    for query, vector in zip(queries, embedded, strict=True):
        hits = rank(corpus, vector, limit, floor)
        gold = set(query.relevant)
        found = [index for index, hit in enumerate(hits, start=1) if hit.address in gold]
        outcomes.append(
            QueryOutcome(
                query_id=query.id,
                gold=len(gold),
                gold_with_vector=len(gold & reachable),
                found=len(found),
                slots=limit,
                reciprocal_rank=1.0 / found[0] if found else 0.0,
                unlabelled=len(hits) - len(found),
            )
        )
    return RetrievalReport(
        outcomes=tuple(outcomes),
        corpus_items=len(corpus.items),
        corpus_searchable=len(corpus.searchable),
        result_limit=limit,
        similarity_floor=floor,
    )


def null_scores(
    corpus: Corpus,
    queries: tuple[LabelledQuery, ...],
    embedded: list[list[float]],
) -> list[float]:
    """Every score an item that is NOT an answer earns. The floor's evidence.

    An off-domain query set would answer a different and easier question. These
    pairs are same-domain noise: a real question against a real item from the
    same corpus that happens not to answer it. A floor that does not clear this
    distribution lets the empty state make a promise it cannot keep.
    """
    scores: list[float] = []
    for query, vector in zip(queries, embedded, strict=True):
        gold = set(query.relevant)
        for item in corpus.searchable:
            if item.address in gold or item.vector is None:
                continue
            scores.append(_dot(vector, item.vector))
    scores.sort()
    return scores


def quantile(sorted_scores: list[float], fraction: float) -> float:
    """Nearest-rank, so the answer is always a value that was actually observed."""
    if not sorted_scores:
        return 0.0
    index = max(0, min(len(sorted_scores) - 1, round(fraction * (len(sorted_scores) - 1))))
    return sorted_scores[index]
