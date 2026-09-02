"""Collect whatever finished into the published day.

Assemble always runs and always publishes. A run with failures publishes a
digest that says it was partial, because a run that publishes nothing on a bad
day is a run whose bad days are invisible.

A later run appends and never reorders. `introduced_by_run` is a global fact -
true for every reader, asserted without any storage - which is what lets a
returning reader see what is new without the page knowing anything about them.
"""

from __future__ import annotations

import base64
import binascii
import logging
import math
import tempfile
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from operator import mul
from pathlib import Path
from typing import Final, Literal

from idhazh.contracts.app_config import AssembleConfig, UiConfig
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestEmbeddings,
    DigestItem,
    DigestLead,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.route import Route, VisualKind
from idhazh.contracts.run_manifest import (
    ConfigDigest,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
    VerticalCount,
)
from idhazh.contracts.run_plan import PlannedItem, RunPlan, TimeSource, VerticalPlan
from idhazh.contracts.search_index import SearchIndex, SearchIndexEntry
from idhazh.contracts.sources import SourceForm, Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.embed import (
    DIMENSIONS,
    DTYPE,
    EMBEDDER_ID,
    VECTOR_SCALE,
    Embedder,
    text_for,
    to_base64,
)
from idhazh.tag import tags

LOG: Final = logging.getLogger("idhazh")

PUBLIC_ROOT: Final = Path("frontend/public/digest")
INDEX_ROOT: Final = Path("frontend/public/assist/index")
#: The threshold a run uses when nobody configured one, read off the contract so
#: the number exists once. The knob is `assemble.duplicate_similarity_min`.
DUPLICATE_SIMILARITY_MIN: Final = AssembleConfig().duplicate_similarity_min
_UNTITLED: Final = "Untitled item"
_ABSTRACT_NOTE: Final = "This is a summary of the paper's abstract. The full paper is a PDF."
_SHARE_NOTE: Final = "We could only read the first {share} percent of this page."
#: The same fact with the scale dropped, for a page whose length before the cut is unknown.
_TRUNCATED_NOTE: Final = "We could only read the first part of this page."


def day_dir(root: Path, date: str) -> Path:
    """`<YYYY>/<MM>/<DD>` - readable, sortable, and free of any digest."""
    year, month, day = date.split("-")
    return root / year / month / day


def write_atomic(path: Path, text: str) -> None:
    """Temp-then-rename, so a file either exists complete or does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    )
    try:
        with handle:
            handle.write(text)
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """The same guarantee for a file that is not text.

    The vector sibling is raw int8. Writing it through the text path would let a
    host's line-ending rules rewrite bytes inside a vector.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False)
    try:
        with handle:
            handle.write(data)
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def utc_now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_digest_item(
    *,
    article: Article,
    summary: Summary,
    band: ConfidenceBand,
    source_name: str,
    source_kind: SourceKind,
    run_n: int,
    route: Route | None = None,
    band_reason: BandReason | None = None,
    planned: PlannedItem | None = None,
) -> DigestItem:
    """One finished item as a reader consumes it. The link is a first-class element.

    The published title is ours when the summarizer wrote one, and the source's
    when it did not. The fallback runs on a real item whenever a drafted title
    missed the asked range, so it is the normal path and not the error path.

    `planned` is the plan row this item was built from, and it is the only place
    the ranking signal and the clock behind `published_at` still exist by now.
    Without it all five publish as null, which reads as unknown - a caller that
    has no plan row must not be able to publish a 0 that means "no feed carried
    this".
    """
    return DigestItem(
        item_id=summary.item_id,
        vertical=article.vertical,
        title=summary.title or article.title or _UNTITLED,
        source_url=article.canonical_url,
        source_id=article.source_id,
        source_name=source_name,
        source_kind=source_kind,
        published_at=article.published_at,
        # Extract copies the plan row's `published_at` onto the article verbatim,
        # so this label describes the time above and not a second one.
        time_source=planned.time_source if planned is not None else None,
        summary=summary.summary or "",
        key_points=summary.key_points,
        lenses=article.lenses,
        events=article.events,
        entities=article.entities,
        band=band,
        band_reason=band_reason,
        source_form=article.source_form,
        reader_note=reader_note(article),
        truncated=article.truncated,
        introduced_by_run=run_n,
        visual=to_digest_visual(route),
        carried_by=planned.carried_by if planned is not None else None,
        watchlist_hit=planned.watchlist_hit if planned is not None else None,
        on_front_page=planned.on_front_page if planned is not None else None,
        rank_score=planned.rank_score if planned is not None else None,
    )


def read_share(article: Article) -> int | None:
    """How much of the page our summary was drawn from, as a whole percent.

    None where the length before the cut is unknown, or where the share rounds
    to all of it or none of it. A cut page that says "the first 100 percent" is
    worse than one that states no scale at all.
    """
    total = article.source_word_count
    if total is None or total <= 0:
        return None
    percent = round(100 * article.word_count / total)
    return percent if 1 <= percent <= 99 else None


def reader_note(article: Article) -> str | None:
    """Every source limit that would surprise the reader, in one paragraph.

    An abstract that was also cut carries both facts. Returning on the first
    one is the exact shape of a silent cut.

    The cut sentence names its scale, because one word cannot cover a page we
    read almost all of and a page we read a fifth of. Measured over the 22 cut
    items in `state/scores.csv` on 2026-08-29, the loss ran from 1.3 percent
    (25 words of 1,948) to 77.2 percent (6,519 of 8,442).
    """
    notes: list[str] = []
    if article.source_form is SourceForm.ABSTRACT:
        notes.append(_ABSTRACT_NOTE)
    if article.truncated:
        share = read_share(article)
        notes.append(_TRUNCATED_NOTE if share is None else _SHARE_NOTE.format(share=share))
    return " ".join(notes) or None


def to_digest_visual(route: Route | None) -> DigestVisual | None:
    """A routed-to-nothing item carries no visual object at all.

    The absence and the empty object would render identically today, and the
    absence is one fewer thing in every payload for the two items in three that
    correctly get no picture.
    """
    if route is None or route.kind is VisualKind.NONE:
        return None
    return DigestVisual(
        kind=route.kind,
        state=route.visual_state,
        path=route.asset_path,
        alt=route.alt_text,
    )


def source_names(sources: Sources) -> dict[str, str]:
    """Retired feeds included: a published id must still resolve to a name."""
    return {feed.id: feed.title for feed in sources.known_feeds()}


def source_kinds(sources: Sources) -> dict[str, SourceKind]:
    """Retired feeds included. Missing here means published as `reporting`."""
    return {feed.id: feed.kind for feed in sources.known_feeds()}


def vertical_names(taxonomy: Taxonomy) -> dict[str, str]:
    return {vertical.id: vertical.display_name for vertical in taxonomy.verticals}


def build_embeddings(
    items: Sequence[DigestItem], embedder: Embedder, *, batch: int = 16
) -> DigestEmbeddings | None:
    """Vectors for the day's items, or nothing at all.

    Returns `None` rather than raising when the encoder is missing or fails. A
    day that cannot be searched on a device is a day that still publishes; the
    search surface is secondary by construction and removing it must never cost
    a reader a single summary.

    An item the encoder cannot read is skipped rather than embedded, and the
    reason goes to the log the run keeps (section 1b). `vectors` is keyed by
    item id, so a skipped item is simply absent - the reader-side decoder
    already handles a day where not every item has one.
    """
    if not items or not embedder.available:
        return None
    try:
        embedder.load()
        vectors: dict[str, str] = {}
        for start in range(0, len(items), batch):
            window = []
            for item in items[start : start + batch]:
                if embedder.readable(text_for(item)):
                    window.append(item)
                else:
                    LOG.warning(
                        "item %s gets no vector: its text is not in the alphabet the "
                        "encoder was trained on, so any vector would be unretrievable",
                        item.item_id,
                    )
            for item, vector in zip(
                window, embedder.encode([text_for(i) for i in window]), strict=True
            ):
                vectors[item.item_id] = to_base64(vector)
    except (OSError, RuntimeError, ValueError, ImportError):
        return None
    return DigestEmbeddings(
        model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE, vectors=vectors
    )


def merge_embeddings(
    previous: DigestEmbeddings | None, current: DigestEmbeddings | None
) -> DigestEmbeddings | None:
    """Carry the day's earlier vectors forward instead of replacing them.

    Each run only encodes the items it summarized, so a block that replaced its
    predecessor left a day searchable over its last run alone. The committed
    2026-08-24 day carried 145 vectors for 731 items.

    The newer vector wins a collision, because it was encoded from the newer
    text. A block that names another model, width or dtype is not merged at
    all: one map holding two widths is the failure the self-describing block
    exists to prevent, and the reader-side decoder cannot tell them apart.
    """
    if previous is None:
        return current
    if current is None:
        return previous
    if (previous.model_id, previous.dimensions, previous.dtype) != (
        current.model_id,
        current.dimensions,
        current.dtype,
    ):
        return current
    return current.model_copy(update={"vectors": {**previous.vectors, **current.vectors}})


def _norm(vector: array[int]) -> float:
    return math.sqrt(sum(value * value for value in vector)) or 1.0


def cosine_int8(
    left: array[int], right: array[int], *, left_norm: float, right_norm: float
) -> float:
    """Cosine between two stored vectors, without decoding either of them.

    `embed.dequantise` divides by the quantisation scale and then normalises, so
    the scale cancels: the angle between two int8 vectors is the angle between
    the unit vectors they decode to. A test asserts the two agree rather than
    leaving that as a claim.
    """
    dot: int = sum(map(mul, left, right))
    return dot / (left_norm * right_norm)


def _strength_order(item: DigestItem) -> tuple[float, float, int, str]:
    """Strongest first, and settled where nothing separates two items.

    A scored item outranks an unscored one, because `rank_score` is the only
    comparable measure of a story the day carries and an item published before
    it existed has none. Where two items tie, the earlier run wins: a returning
    reader keeps the item they already saw rather than watching the day swap it
    for a copy.
    """
    return (
        0.0 if item.rank_score is not None else 1.0,
        -(item.rank_score or 0.0),
        item.introduced_by_run,
        item.item_id,
    )


def _weakest_link(
    cluster: Sequence[str],
    item_id: str,
    vectors: dict[str, array[int]],
    norms: dict[str, float],
    floor: float,
) -> float | None:
    """How well this item fits the whole group, or nothing if it does not.

    Every pair inside a group clears the threshold, not only each item against
    the one it joined. Single-link grouping chains - A is the same story as B
    and B as C, while A and C are two different stories - and a chained group is
    exactly the false merge this pass may not make.
    """
    weakest = 1.0
    for member in cluster:
        score = cosine_int8(
            vectors[item_id],
            vectors[member],
            left_norm=norms[item_id],
            right_norm=norms[member],
        )
        if score < floor:
            return None
        weakest = min(weakest, score)
    return weakest


def collapse_same_story(
    items: Sequence[DigestItem],
    embeddings: DigestEmbeddings | None,
    *,
    similarity_min: float = DUPLICATE_SIMILARITY_MIN,
) -> list[DigestItem]:
    """Group the day on the vectors it already carries, and keep the strongest.

    Nothing is removed. Every item stays in the published order it was in, with
    its anchor and its archive entry; a grouped item names the one the default
    view draws instead, and every item in a group carries the count of other
    sources so the sentence on it is true whichever one is on screen.

    Runs at build time over the block the payload already holds (Rule #1): the
    browser never computes this, and no encoder is loaded to do it. A day with
    no vectors, and an item without one, come back untouched - both fields stay
    null, which reads as unknown rather than as "only one source carried this".

    **A group is always across sources**, so `also_covered_by` is 1 or more on
    every grouped item and 0 on every other item that carries a vector. One
    outlet publishing twice is a different problem with a different control
    (`collect.max_source_share_per_day`), and grouping it would buy the reader
    nothing - the sentence on the survivor is the one it already had - while
    still costing a story. It is also where the encoder is least trustworthy:
    two press releases from one desk share their boilerplate, so the Federal
    Reserve's June minutes and its July minutes score 0.9867 against each other
    and are two different documents.
    """
    if embeddings is None or not embeddings.vectors:
        return list(items)

    by_id = {item.item_id: item for item in items}
    vectors: dict[str, array[int]] = {}
    norms: dict[str, float] = {}
    for item_id, encoded in embeddings.vectors.items():
        if item_id not in by_id:
            continue
        raw = _vector_bytes(encoded, embeddings.dimensions)
        if raw is None:
            LOG.warning(
                "item %s stores a vector that is not %s bytes wide, so it is not "
                "grouped with anything",
                item_id,
                embeddings.dimensions,
            )
            continue
        vectors[item_id] = array("b", raw)
        norms[item_id] = _norm(vectors[item_id])

    clusters: list[list[str]] = []
    for item in sorted((one for one in items if one.item_id in vectors), key=_strength_order):
        joined: list[str] | None = None
        best = similarity_min
        for cluster in clusters:
            # A group is across sources, so one outlet's second piece never
            # forms a group on its own and never joins a group it is alone in.
            if all(by_id[member].source_id == item.source_id for member in cluster):
                continue
            fit = _weakest_link(cluster, item.item_id, vectors, norms, similarity_min)
            # `>` after the first candidate, so a tie goes to the group that
            # formed first - which is the one built round the stronger story,
            # because the walk is in strength order.
            if fit is not None and (joined is None or fit > best):
                joined, best = cluster, fit
        if joined is None:
            clusters.append([item.item_id])
        else:
            joined.append(item.item_id)

    keeper: dict[str, str | None] = {}
    covered: dict[str, int] = {}
    for cluster in clusters:
        sources = {by_id[member].source_id for member in cluster}
        for position, member in enumerate(cluster):
            keeper[member] = None if position == 0 else cluster[0]
            covered[member] = len(sources - {by_id[member].source_id})

    return [
        item
        if item.item_id not in covered
        else item.model_copy(
            update={
                "also_covered_by": covered[item.item_id],
                "same_story_as": keeper[item.item_id],
            }
        )
        for item in items
    ]


def month_of(date: str) -> str:
    """`<YYYY-MM>` - the shard a published date belongs to."""
    return date[:7]


# --- the day's leading stories ----------------------------------------------
#
# Five stories at the top of the day, chosen across the whole day rather than
# off the head of the published order - that head is the top of whichever desk
# sorted first in run 1, which is an accident and not an edit.
#
# Nothing here removes, hides or re-ranks a story. Every lead is still in
# `items` in the published order, and every story a cap excluded still
# publishes in the stream. The block is a way in, and the arithmetic behind it
# is in docs/architecture/sources/discovery.md.

#: Small counts read as words in a sentence a person reads. Past this the
#: numeral is plainer, which is what ASD-STE100 asks for.
_COUNT_WORDS: Final = (
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)

_SUBJECT_LINE: Final = "{count} of today's stories are about {subject}."
_WATCHLIST_LINE: Final = "{subject} is on our watchlist."
_CARRIED_LINE: Final = "The same report reached us through {count} of our feeds."
_DESK_LINE: Final = "The lead story on our {desk} desk."

#: The band a lead may hold, best first. `low` never leads.
_LEAD_BANDS: Final = (ConfidenceBand.HIGH, ConfidenceBand.MEDIUM)


def _spelled(count: int) -> str:
    return _COUNT_WORDS[count] if 1 <= count < len(_COUNT_WORDS) else str(count)


@dataclass(frozen=True, slots=True)
class SubjectCluster:
    """Every story of one day whose published title names one registry entity.

    `sources` counts one story per source per entity, so a publication that
    filed four pieces on a subject is one source and not four.
    """

    entity: str
    display_name: str
    item_ids: tuple[str, ...]
    sources: frozenset[str]
    holds_reporting: bool

    def qualifies(self, floor: int) -> bool:
        """Whether this cluster is evidence rather than a coincidence.

        Two rules, and the second is the one that matters. Below the floor the
        sources are too few to say a subject is running. And a cluster with no
        reporting in it is a set of announcements about one company, which is a
        press schedule and not a story.
        """
        return len(self.sources) >= floor and self.holds_reporting


def subject_clusters(items: Sequence[DigestItem], watchlist: Watchlist) -> list[SubjectCluster]:
    """The day's shared subjects, matched on our own published titles.

    The title, never the body and never fetched text: the matcher reads words
    we wrote and may only emit a slug the committed registry already holds, so
    a hostile page can win a tag we already publish and can never mint one
    (Rule #11).

    The title alone, and not the summary, because a lead is a claim about what
    the story is about rather than about what our paragraph happened to
    mention. It costs coverage and the number is recorded in the row's own
    measurements.
    """
    terms = watchlist.entity_terms()
    names = {
        entity.id: entity.display_name
        for entity in watchlist.entities
        if entity.status is not LifecycleStatus.RETIRED
    }
    members: dict[str, list[DigestItem]] = {}
    for item in items:
        for entity in tags(terms, item.title):
            members.setdefault(entity, []).append(item)
    return [
        SubjectCluster(
            entity=entity,
            display_name=names.get(entity, entity),
            item_ids=tuple(item.item_id for item in found),
            sources=frozenset(item.source_id for item in found),
            holds_reporting=any(item.source_kind is SourceKind.REPORTING for item in found),
        )
        for entity, found in sorted(members.items())
    ]


@dataclass(frozen=True, slots=True)
class LeadCandidate:
    """One story after the eligibility rules, before any cap has spoken."""

    item: DigestItem
    subjects: tuple[str, ...]
    term: float
    reason: str
    from_desk_fallback: bool

    @property
    def score(self) -> float:
        return (self.item.rank_score or 0.0) + self.term


def _ordered(candidates: Sequence[LeadCandidate]) -> list[LeadCandidate]:
    """Score, then the tie-breakers, in the order Editor set them.

    Higher `carried_by`, then `high` before `medium`, then the newer story,
    then the item id ascending. The id is derived from the address, so it
    cannot be gamed and two builds of one day cannot disagree.

    Sorts are stable, so these compose least-significant first - the same shape
    `rank._ordered` uses on the published order itself.
    """
    ordered = sorted(candidates, key=lambda entry: entry.item.item_id)
    ordered.sort(key=lambda entry: entry.item.published_at or "", reverse=True)
    ordered.sort(key=lambda entry: _LEAD_BANDS.index(entry.item.band))
    ordered.sort(key=lambda entry: entry.item.carried_by or 0, reverse=True)
    ordered.sort(key=lambda entry: entry.score, reverse=True)
    return ordered


def _notable(item: DigestItem, clusters: Sequence[SubjectCluster], floor: int) -> bool:
    """Whether a story's absence from the block has to be explained.

    The two facts a reader could see for themselves: a subject several of our
    sources are writing about, and an address more than two feeds carried.
    """
    if (item.carried_by or 0) >= 3:
        return True
    return any(
        cluster.qualifies(floor) and item.item_id in cluster.item_ids for cluster in clusters
    )


def _reason_for(
    item: DigestItem,
    *,
    clusters_by_item: Mapping[str, tuple[SubjectCluster, ...]],
    floor: int,
    desk_names: Mapping[str, str],
    desk_leads: Mapping[str, str],
) -> tuple[str | None, bool]:
    """The strongest true sentence about this story, and whether it is the fallback.

    Order of preference, and every one of them is checkable against the story
    the reader is looking at. A lead that cannot say anything true is not a
    lead: it stays in the stream like everything else, because a block that
    invents its reasons is worse than no block.

    Two sentences are deliberately absent. Recency gets none, because the rail
    already prints the time. A weighted lens gets none, because it is an
    editorial subsidy for an under-carried theme, and "this is here because it
    mentions tariffs" tells the reader about our config rather than about the
    news.
    """
    named = clusters_by_item.get(item.item_id, ())
    running = [cluster for cluster in named if cluster.qualifies(floor)]
    if running:
        best = max(running, key=lambda cluster: (len(cluster.sources), cluster.entity))
        return (
            _SUBJECT_LINE.format(
                count=_spelled(len(best.item_ids)).capitalize(), subject=best.display_name
            ),
            False,
        )
    if named:
        best = max(named, key=lambda cluster: (len(cluster.sources), cluster.entity))
        return _WATCHLIST_LINE.format(subject=best.display_name), False
    if (item.carried_by or 0) >= 2:
        return _CARRIED_LINE.format(count=_spelled(item.carried_by or 0)), False
    if desk_leads.get(item.vertical) == item.item_id:
        return _DESK_LINE.format(desk=desk_names.get(item.vertical, item.vertical)), True
    return None, False


def _eligible(
    item: DigestItem, *, clusters_by_item: Mapping[str, tuple[SubjectCluster, ...]]
) -> str | None:
    """Why this story may not lead, or None when it may.

    Four rules, applied before any score, and each one excludes whatever the
    story ranked. A story excluded here still publishes, in the stream, marked
    the way every other story is.
    """
    if item.band not in _LEAD_BANDS:
        return "band-low"
    if item.truncated:
        return "truncated"
    if item.time_source is not TimeSource.FEED:
        # A time we inferred is our clock, not the story's. A lead states when
        # something happened, so it may only lead on the feed's own answer.
        return "clock-not-the-feed"
    if item.source_kind is SourceKind.ANNOUNCEMENT and not any(
        cluster.holds_reporting for cluster in clusters_by_item.get(item.item_id, ())
    ):
        # A company announcing itself leads only where somebody reported the
        # same subject. On its own it is a press release at the top of the day.
        return "announcement-uncorroborated"
    return None


def leading_stories(
    items: Sequence[DigestItem],
    *,
    date: str,
    watchlist: Watchlist,
    ui: UiConfig,
    desk_names: Mapping[str, str] | None = None,
) -> list[DigestLead]:
    """The day's leading stories, strongest first, or nothing at all.

    Selection is `rank_score` plus a shared-subject term, across the whole day.
    Not the head of the published order: that head is grouped by run and then
    by desk, so it opens on whichever desk sorted first in run 1.

    Four caps bound the block and each answers a different question. A desk may
    hold `leading_per_desk`. A source may hold one. A subject may hold one - a
    running story crosses desks and sources, so the first three caps do not
    bound it, and two of five about one subject means the day had fewer than
    five distinct stories worth leading. And stories the feed dated to
    yesterday may hold `lead_max_yesterday`.

    Below `leading_min` the block does not render at all. Four real leads beat
    five with one filler, and a day with too few is a day that goes straight to
    the stream.
    """
    clusters = subject_clusters(items, watchlist)
    floor = ui.lead_cluster_floor
    clusters_by_item: dict[str, tuple[SubjectCluster, ...]] = {}
    for cluster in clusters:
        for item_id in cluster.item_ids:
            clusters_by_item[item_id] = (*clusters_by_item.get(item_id, ()), cluster)

    desk_leads = _desk_leads(items)
    omitted: dict[str, str] = {}
    candidates: list[LeadCandidate] = []
    for item in items:
        refusal = _eligible(item, clusters_by_item=clusters_by_item)
        if refusal is None:
            named = clusters_by_item.get(item.item_id, ())
            reason, fallback = _reason_for(
                item,
                clusters_by_item=clusters_by_item,
                floor=floor,
                desk_names=desk_names or {},
                desk_leads=desk_leads,
            )
            if reason is None:
                refusal = "no-true-reason"
            else:
                # The largest weight a story earned, never the sum. Two subjects
                # in one title is not twice the story, and summing would let the
                # registry outweigh the fact that two independent feeds carried
                # an address - the rule the lens bonus already follows.
                candidates.append(
                    LeadCandidate(
                        item=item,
                        subjects=tuple(cluster.entity for cluster in named),
                        term=(
                            ui.lead_shared_subject_weight
                            if any(cluster.qualifies(floor) for cluster in named)
                            else 0.0
                        ),
                        reason=reason,
                        from_desk_fallback=fallback,
                    )
                )
        if refusal is not None and _notable(item, clusters, floor):
            omitted[item.item_id] = refusal

    chosen, capped = _take_leads(_ordered(candidates), date=date, ui=ui)
    for item_id, refusal in capped.items():
        omitted.setdefault(item_id, refusal)

    if len(chosen) < ui.leading_min:
        for candidate in chosen:
            omitted[candidate.item.item_id] = "block-under-leading-min"
        _log_leads(date, [], omitted)
        return []

    _log_leads(date, chosen, omitted)
    return [DigestLead(item_id=entry.item.item_id, reason=entry.reason) for entry in chosen]


def _desk_leads(items: Sequence[DigestItem]) -> dict[str, str]:
    """The highest-scoring story of each desk, by item id.

    It is what makes "The lead story on our Energy desk." a sentence a reader
    can check rather than a phrase every story on that desk could carry.
    """
    def strength(item: DigestItem) -> tuple[float, str]:
        return (-(item.rank_score or 0.0), item.item_id)

    best: dict[str, DigestItem] = {}
    for item in items:
        held = best.get(item.vertical)
        if held is None or strength(item) < strength(held):
            best[item.vertical] = item
    return {vertical: item.item_id for vertical, item in best.items()}


def _take_leads(
    ordered: Sequence[LeadCandidate], *, date: str, ui: UiConfig
) -> tuple[list[LeadCandidate], dict[str, str]]:
    """Walk the order once, take what every cap allows, and say what each cap cost.

    The refusals come back with the block because a cap that turns a story away
    silently is a cap nobody can audit. Only the notable ones are logged, and
    that filter is the caller's.
    """
    yesterday = (date_type.fromisoformat(date) - timedelta(days=1)).isoformat()
    taken: list[LeadCandidate] = []
    refused: dict[str, str] = {}
    per_desk: dict[str, int] = {}
    used_sources: set[str] = set()
    used_subjects: set[str] = set()
    from_yesterday = 0
    for candidate in ordered:
        item = candidate.item
        if len(taken) >= ui.leading_stories:
            refused[item.item_id] = "block-full"
            continue
        if per_desk.get(item.vertical, 0) >= ui.leading_per_desk:
            refused[item.item_id] = f"desk-full:{item.vertical}"
            continue
        if item.source_id in used_sources:
            refused[item.item_id] = f"source-already-leading:{item.source_id}"
            continue
        # Every subject the title names, not only the one that scored. A story
        # about a subject already leading is the same story twice to a reader,
        # whether or not the cluster cleared the floor.
        clashing = [subject for subject in candidate.subjects if subject in used_subjects]
        if clashing:
            refused[item.item_id] = f"subject-already-leading:{clashing[0]}"
            continue
        dated_yesterday = (item.published_at or "").startswith(yesterday)
        if dated_yesterday and from_yesterday >= ui.lead_max_yesterday:
            refused[item.item_id] = "yesterday-full"
            continue
        taken.append(candidate)
        per_desk[item.vertical] = per_desk.get(item.vertical, 0) + 1
        used_sources.add(item.source_id)
        used_subjects.update(candidate.subjects)
        from_yesterday += int(dated_yesterday)
    return taken, refused


def _log_leads(
    date: str, chosen: Sequence[LeadCandidate], omitted: Mapping[str, str]
) -> None:
    """The two counters this block ships with (section 1b).

    Line coverage is the share of leads carrying a real reason rather than the
    desk fallback, and it is a live risk rather than a formality: the matcher
    reads the title alone, and entities fire on 22.1 percent of items on a
    title-plus-body match.

    The omission log is the other half. No story a reader could see the case
    for - a subject several sources are writing about, or an address more than
    two feeds carried - is absent from the block without this line naming which
    rule excluded it.
    """
    real = sum(1 for entry in chosen if not entry.from_desk_fallback)
    LOG.info(
        "leading stories date=%s block=%s real_reasons=%s coverage=%s",
        date,
        len(chosen),
        real,
        f"{real / len(chosen):.2f}" if chosen else "n/a",
    )
    for item_id, refusal in sorted(omitted.items()):
        LOG.info("leading stories date=%s omitted item=%s because=%s", date, item_id, refusal)


def days_in_month(digest_root: Path, month: str) -> list[DigestDay]:
    """Every committed day of one month, oldest first. A month with none gives none."""
    year, month_number = month.split("-")
    paths = sorted((digest_root / year / month_number).glob("*/digest.json"))
    return [DigestDay.from_json(path.read_text(encoding="utf-8")) for path in paths]


def _vector_bytes(encoded: str, dimensions: int) -> bytes | None:
    """The stored vector, or nothing when it is not the width this index names.

    A short vector is the one failure that must never be written: the offsets
    after it would all be wrong by its shortfall, every one of them would decode
    cleanly, and every score would be nonsense.
    """
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == dimensions else None


def build_search_index(month: str, days: Sequence[DigestDay]) -> tuple[SearchIndex, bytes]:
    """One month of published items, and the vector file its offsets point into.

    Built whole from the committed days every time. There is no incremental
    path, so there is no read-modify-write to race with itself across two runs
    of a day and no repair command for when it does. The cost is one pass over a
    month of payloads per assemble run, which is measured in
    `docs/reference/measurements.md`.

    **One index names one encoder.** The header is taken from the newest day
    that carries vectors. A day whose block names another model, width or dtype
    keeps its items in the index with no vector at all - browsable, not
    searchable - because two encoders in one space produce scores that look like
    scores and mean nothing. That is the rule `merge_embeddings` already applies
    inside a day, applied across the days of a month.
    """
    ordered = sorted(days, key=lambda day: day.date)

    model_id: str = EMBEDDER_ID
    dimensions: int = DIMENSIONS
    dtype: Literal["int8"] = DTYPE
    for day in reversed(ordered):
        newest = day.embeddings
        if newest is not None and newest.vectors:
            model_id, dimensions, dtype = newest.model_id, newest.dimensions, newest.dtype
            break

    entries: list[SearchIndexEntry] = []
    vectors = bytearray()
    for day in ordered:
        block = day.embeddings
        named = block is not None and (block.model_id, block.dimensions, block.dtype) == (
            model_id,
            dimensions,
            dtype,
        )
        if block is not None and not named:
            LOG.warning(
                "date=%s holds %s vectors from %s/%s/%s, and this index names %s/%s/%s - "
                "its items stay in the index without one",
                day.date,
                len(block.vectors),
                block.model_id,
                block.dimensions,
                block.dtype,
                model_id,
                dimensions,
                dtype,
            )
        for item in day.items:
            offset: int | None = None
            encoded = block.vectors.get(item.item_id) if named and block is not None else None
            if encoded is not None:
                raw = _vector_bytes(encoded, dimensions)
                if raw is None:
                    LOG.warning(
                        "item %s on %s stores a vector this index cannot lay out at %s "
                        "bytes, so it gets none",
                        item.item_id,
                        day.date,
                        dimensions,
                    )
                else:
                    offset = len(vectors)
                    vectors += raw
            entries.append(
                SearchIndexEntry(
                    date=day.date,
                    item_id=item.item_id,
                    title=item.title,
                    vertical=item.vertical,
                    vector=offset,
                )
            )

    index = SearchIndex(
        version=SearchIndex.schema_version(),
        month=month,
        model_id=model_id,
        dimensions=dimensions,
        dtype=dtype,
        scale=VECTOR_SCALE,
        entries=entries,
    )
    return index, bytes(vectors)


def rebuild_search_index(*, digest_root: Path, index_root: Path, month: str) -> SearchIndex:
    """Regenerate a month's index from the days that are committed right now.

    Every writer of a day payload owes this call. The shard is derived, so a
    deleted day needs no separate cleanup - the next assemble run simply writes
    a shard that no longer names it.
    """
    index, vectors = build_search_index(month, days_in_month(digest_root, month))
    write_atomic(index_root / f"{month}.json", index.to_json())
    write_atomic_bytes(index_root / f"{month}.bin", vectors)
    return index


def desk_ref(
    vertical_id: str,
    *,
    display_name: str,
    count: int,
    planned: VerticalPlan | None,
    earlier: DigestVerticalRef | None,
) -> DigestVerticalRef:
    """One desk of the day, carrying the strongest shortfall any run recorded.

    The strongest and not the sum. A later run drops what the day has already
    published before it counts anything, so it sees a smaller pool of the same
    back-catalogue stories - and adding the runs would count one such story once
    per run and print a number the feeds never offered.

    A desk this run did not plan keeps what an earlier run said about it, which
    is how a desk retired from `config/taxonomy.json` mid-day keeps its
    explanation. A desk no run has ever planned carries nothing, and nothing
    reads as unknown rather than as zero.
    """
    if planned is None:
        considered = earlier.considered if earlier else None
        stale = earlier.too_old if earlier else None
        floored = earlier.below_feed_floor if earlier else None
    elif earlier is None or earlier.considered is None:
        considered = planned.considered
        stale = planned.too_old
        floored = planned.below_feed_floor
    else:
        considered = max(earlier.considered, planned.considered)
        stale = max(earlier.too_old or 0, planned.too_old)
        floored = bool(earlier.below_feed_floor) or planned.below_feed_floor
    return DigestVerticalRef(
        id=vertical_id,
        display_name=display_name,
        count=count,
        considered=considered,
        too_old=stale,
        below_feed_floor=floored,
    )


def build_day(
    *,
    plan: RunPlan,
    items: Sequence[DigestItem],
    previous: DigestDay | None,
    taxonomy: Taxonomy,
    run_n: int,
    generated_at: str,
    retention_window_months: int,
    embeddings: DigestEmbeddings | None = None,
    item_health_rows: Sequence[ItemHealthRow] | None = None,
    watchlist: Watchlist | None = None,
    ui: UiConfig | None = None,
    duplicate_similarity_min: float = DUPLICATE_SIMILARITY_MIN,
) -> DigestDay:
    """Append this run's items to whatever the day already carried.

    An item already published keeps its place. That is not politeness: the
    order is part of what a shared link shows, so moving it would change what
    the recipient sees relative to the sender.

    A run can come back as itself. `cli.stage_assemble` writes the day, then
    builds the manifest, then writes it, so a run that dies in that gap leaves a
    day holding its items and a manifest that never heard of it - and the next
    run reads the same number off the manifest. Replacing the reference rather
    than adding a second one is what makes that replay one run, and the count on
    it is every item the number introduced rather than what this attempt added,
    because that is what `DigestDay` validates it against.

    Two passes read the finished day here, and the order between them is fixed
    rather than incidental. The duplicate pass runs first, then the leading
    block is chosen over what that pass produced. Both run over the whole day
    and not over this run's items, because a later run can publish the same
    story an earlier one already did and can add a story the first run could
    not weigh. Neither moves anything: `items` is still the published order,
    appended to and never re-sorted.

    The duplicate pass is a pure function of the items, their vectors and the
    threshold, so the same day rebuilt reaches the same groups.

    Each desk also carries why it ran what it ran, from this run's plan and
    whatever an earlier run of the day already said. `desk_ref` owns that rule.
    """
    already = {item.item_id for item in (previous.items if previous else [])}
    fresh = [item for item in items if item.item_id not in already]
    combined = [*(previous.items if previous else []), *fresh]
    merged = merge_embeddings(previous.embeddings if previous else None, embeddings)
    # Group first, lead second. The block is a claim about the day as the reader
    # will see it, and grouping is what decides which item of a group the default
    # view draws. Leading first would choose against a day that no longer exists
    # by the time it renders. See docs/architecture/publishing/layout.md.
    combined = collapse_same_story(combined, merged, similarity_min=duplicate_similarity_min)

    runs = list(previous.runs) if previous else []
    runs = [run for run in runs if run.n != run_n]
    runs.append(
        DigestRunRef(
            n=run_n,
            at=generated_at,
            items_added=sum(1 for item in combined if item.introduced_by_run == run_n),
        )
    )
    runs.sort(key=lambda run: run.n)

    names = vertical_names(taxonomy)
    present = sorted({item.vertical for item in combined})
    this_run = {vertical.id: vertical for vertical in plan.verticals}
    already_said = {ref.id: ref for ref in (previous.verticals if previous else [])}
    published = len(combined)
    failed = (
        sum(1 for row in item_health_rows if row.outcome is ItemOutcome.FAILED)
        if item_health_rows is not None
        else max(len(plan.items) - published, 0)
    )
    planned = (
        max(len(plan.items), published + failed)
        if item_health_rows is not None
        else max(len(plan.items), published)
    )

    return DigestDay(
        version=DigestDay.schema_version(),
        date=plan.date,
        generated_at=generated_at,
        partial=failed > 0,
        items_planned=planned,
        items_failed=failed,
        retention_window_months=retention_window_months,
        runs=runs,
        verticals=[
            desk_ref(
                vertical_id,
                display_name=names.get(vertical_id, vertical_id),
                count=sum(1 for item in combined if item.vertical == vertical_id),
                planned=this_run.get(vertical_id),
                earlier=already_said.get(vertical_id),
            )
            for vertical_id in present
        ],
        items=combined,
        leads=leading_stories(
            combined,
            date=plan.date,
            watchlist=watchlist or Watchlist(version=Watchlist.schema_version(), entities=[]),
            ui=ui or UiConfig(),
            desk_names=names,
        ),
        embeddings=merged,
    )


def run_n_for(previous: RunManifest | None, run_id: str) -> int:
    """Which run of the day this execution is, from what the day already carries.

    Two different facts used to be one string. `n` is the day's own ordinal -
    what a page footer would call the morning run - and `run_id` is the identity
    of the execution that produced it. They were the same number until an id a
    second execution could not forge was needed, and this is where they meet
    again: the ordinal is still counted off the day, and an execution that comes
    back keeps the number it already has rather than claiming the next one.

    That is the same rule `build_day` applies to `DigestRunRef`, so the day and
    the manifest cannot disagree about how many times the day was built.
    """
    if previous is None:
        return 1
    for record in previous.runs:
        if record.run_id == run_id:
            return record.n
    return previous.runs[-1].n + 1


def build_manifest(
    *,
    plan: RunPlan,
    day: DigestDay,
    previous: RunManifest | None,
    summaries: Sequence[Summary],
    models: Sequence[ModelUse],
    commit_sha: str,
    runner: str,
    started_at: str,
    completed_at: str,
    config_digests: Sequence[ConfigDigest],
    site_bytes: int,
    site_files: int,
    determinism_violations: int = 0,
    note: str | None = None,
    item_health_rows: Sequence[ItemHealthRow] | None = None,
    routes: Sequence[Route] | None = None,
    evaluation_enabled: bool | None = None,
    evaluation_sample_rate: float | None = None,
    evaluation_sampled: bool | None = None,
    scorer_version: str | None = None,
    rank_version: str | None = None,
) -> RunManifest:
    """What ran, against which model, at which commit - appended, never rewritten.

    Appended for a new execution and replaced for one that comes back, which is
    the rule `build_day` already applies to the day's own run list. A record is
    matched by `run_id`, because that is now the identity of the execution rather
    than a count of what was committed - so an assemble job re-run reads the same
    plan, computes the same id, and settles as one run instead of appending a
    phantom that planned nothing.

    The day is the surface that needs this most, because its items land on disk
    one write before this one does.
    """
    run_n = run_n_for(previous, plan.run_id)
    if item_health_rows is not None:
        succeeded = sum(1 for row in item_health_rows if row.outcome is ItemOutcome.OK)
        failed = sum(1 for row in item_health_rows if row.outcome is ItemOutcome.FAILED)
        skipped = 0
        planned = len(item_health_rows)
    else:
        succeeded = sum(1 for summary in summaries if summary.status is SummaryStatus.OK)
        skipped = sum(1 for summary in summaries if summary.status is SummaryStatus.SKIPPED)
        planned = max(len(plan.items), len(summaries))
        failed = planned - succeeded - skipped
    # A router that never ran leaves no payloads, and a payload written before
    # the clock existed carries no number. Both are "nothing was measured", which
    # is null - not a zero that would read as "it took no time".
    timed = [route.route_ms for route in (routes or []) if route.route_ms is not None]
    prefiltered = sum(1 for route in (routes or []) if not route.asked_the_model)
    record = RunRecord(
        run_id=plan.run_id,
        n=run_n,
        started_at=started_at,
        completed_at=completed_at,
        status=RunStatus.COMPLETED if not day.partial else RunStatus.PARTIAL,
        commit_sha=commit_sha,
        runner=runner,
        source_list_stale=plan.stale,
        models=list(models),
        items_planned=planned,
        items_succeeded=succeeded,
        items_failed=failed,
        items_skipped=skipped,
        items_routed=len(routes or []),
        items_prefiltered=prefiltered,
        charts_drafted=sum(1 for route in (routes or []) if route.drafted_chart),
        route_ms=sum(timed) if timed else None,
        verticals=[
            VerticalCount(
                id=vertical.id,
                planned=vertical.planned,
                published=sum(
                    1
                    for item in day.items
                    if item.vertical == vertical.id and item.introduced_by_run == run_n
                ),
                below_feed_floor=vertical.below_feed_floor,
            )
            for vertical in plan.verticals
        ],
        pipeline_fingerprints=sorted({summary.pipeline_fingerprint for summary in summaries}),
        determinism_violations=determinism_violations,
        site_bytes=site_bytes,
        site_files=site_files,
        evaluation_enabled=evaluation_enabled,
        evaluation_sample_rate=evaluation_sample_rate,
        evaluation_sampled=evaluation_sampled,
        scorer_version=scorer_version,
        rank_version=rank_version,
        config_digests=list(config_digests),
        note=note,
    )
    runs = [record if run.n == run_n else run for run in (previous.runs if previous else [])]
    if all(run.n != run_n for run in (previous.runs if previous else [])):
        runs.append(record)
    return RunManifest(version=RunManifest.schema_version(), date=plan.date, runs=runs)


def run_that_wrote(item: DigestItem) -> int:
    """Which run wrote the words this item now carries.

    The run manifest names the model per run, so this is the join anyone asking
    "which model wrote this summary" has to make. An item no run has revised was
    written by the run that introduced it. A revised one names its own run,
    because the alternative is a join that answers with the wrong run rather
    than with nothing.
    """
    return item.updated_by_run or item.introduced_by_run


def low_confidence(day: DigestDay) -> int:
    return sum(1 for item in day.items if item.band is ConfidenceBand.LOW)


def site_size(root: Path) -> tuple[int, int]:
    """Measured every run from the first one, long before any retention policy exists."""
    if not root.exists():
        return (0, 0)
    files = [path for path in root.rglob("*") if path.is_file()]
    return (sum(path.stat().st_size for path in files), len(files))
