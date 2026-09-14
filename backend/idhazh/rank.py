"""Decide the day, with arithmetic rather than a model.

A story the best-trusted source carried is the day's story. That is the whole
idea, and it needs no weights, no classifier and no judgement at run time -
which means the plan job finishes in seconds and produces the same answer on
every re-run.

The score is: how far the source is trusted, plus a step if more than one of
our feeds carried the same address, plus a bonus for the watchlist, for a theme
we weight, and for being new. Its terms are ordered, and the order is the
editor's: authority times the feed's weight, then decayed recency, then the
feed's reliability, then a watchlist subject. Carriage is under all four - it
breaks a tie and never decides one.

**Age is decided twice, and only the first decision drops anything.** `too_old`
refuses a story older than `max_age_hours` before it is scored at all, so a
story can be dropped for being old. What the score never does is drop one: the
recency term is a bonus over what already passed that gate, because a second
cutoff could not tell a strong old story from a weak fresh one.

Nothing bounds how many items a vertical contributes except supply, the score,
and `max_per_source`. What bounds one feed across the whole day - every desk,
every run - is `collect.max_source_share_per_day`, and it is a share rather
than a count because a count of ten is 2 percent of a big day and a quarter of
a thin one. Ties break on the canonical URL, so two runs over the same feeds
cannot disagree about the order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, NamedTuple

from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, TimeSource, VerticalPlan
from idhazh.contracts.taxonomy import SourceTier, VerticalDef
from idhazh.discover import Candidate
from idhazh.embed import cosine

#: Bumped when the shape of a published day's ranking changes. A published
#: order that moved for a reason nobody recorded is a published order nobody
#: can defend, and since 2026-09-01 the run manifest records this string. `-3`
#: added the shared-subject term: the plan-time score below is untouched, and
#: the day's item order with it, but the day now also publishes a second order
#: over the same stories - `assemble.leading_stories`, which reads `rank_score`
#: and adds to it. `-4` moved no score at all: it is the day every item started
#: carrying a base32 address instead of a decimal one, and this string is the
#: only place a later reader can see that two days were addressed differently.
#: `-5` removed a term: an aggregator's front-page vote no longer moves the
#: order. `on_front_page` is still published, so the page can still say another
#: desk led with the story - the vote stopped being worth a number, not a fact.
#: `-6` changed the shape of a term rather than removing one: carriage stopped
#: multiplying authority and became `collect.carriage_step`, a flat step that
#: fires once at two carriers. That moves the order of every carried story, so
#: two days on either side of it were ordered by different arithmetic and this
#: string is the only place a later reader can see it.
RANK_VERSION: Final = "idhazh-rank-6"

#: Crockford base32, lowercased. `i`, `l`, `o` and `u` are out, so no id can be
#: misread aloud and none can spell a word. The 32 symbols left are a subset of
#: the slug alphabet, so an item id is still a slug.
CROCKFORD_ALPHABET: Final = "0123456789abcdefghjkmnpqrstvwxyz"

#: Bytes of the address hash an item id is built from. Ten bytes is 80 bits,
#: which is exactly 16 base32 symbols with nothing left over and nothing padded.
ITEM_ID_BYTES: Final = 10

#: Symbols in the trailing field of an item id. Derived from `ITEM_ID_BYTES`
#: rather than chosen, so the two cannot fall out of step.
ITEM_ID_SYMBOLS: Final = ITEM_ID_BYTES * 8 // 5

_STAMP: Final = "%Y-%m-%dT%H:%M:%SZ"


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)


def _hours(later: str, earlier: str) -> float:
    return (_at(later) - _at(earlier)).total_seconds() / 3600.0


# --- identity ----------------------------------------------------------------


def item_id(vertical: str, url_key: str) -> str:
    """`<vertical>-<sixteen base32 symbols>`, from the address and nothing else.

    The id used to be the rank position, so run 2 of a day renumbered every
    story: the same article came back under a different id, the digest
    deduplicated on that id, and anything that moved one place published twice.
    Deriving it from the address means a later run of the same day recognises
    the work the earlier one already did.

    It was ten decimal digits until 2026-09-12, which is 33 bits and collided
    often enough that the collision needed resolving - and the only way to
    resolve one is to look at the other addresses in the pool, which made a
    collided id depend on the pool rather than on the address. Eighty bits do
    not collide, so there is nothing to resolve and nothing to look at. Old ids
    are never rewritten: a published day is frozen, and `ITEM_ID_PATTERN`
    accepts both shapes for as long as one of those days survives.
    """
    number = int.from_bytes(bytes.fromhex(url_key)[:ITEM_ID_BYTES], "big")
    symbols = "".join(
        CROCKFORD_ALPHABET[(number >> shift) & 0x1F]
        for shift in range(5 * (ITEM_ID_SYMBOLS - 1), -1, -5)
    )
    return f"{vertical}-{symbols}"


# --- when a story appeared ---------------------------------------------------


class Appearance(NamedTuple):
    """When a story appeared, and which clock said so."""

    at: str | None
    source: TimeSource


def appeared_at(
    published_at: str | None,
    *,
    first_seen_at: str | None,
    now: str,
    max_future_hours: float,
) -> Appearance:
    """When to treat a story as having appeared, and whose clock that is.

    The feed's own date wins, unless it claims a future too far ahead to be
    true: a feed that stamps tomorrow would otherwise hold the top slot every
    single day. First sight is the fallback, and for an article carrying no
    date at all it is the only age anybody has.

    The label leaves with the value rather than being worked out again further
    down, because the fallback is silent: once the two clocks are in one field
    nothing can tell them apart, and a page that prints the time cannot say
    whose it is.
    """
    if published_at is not None and _hours(published_at, now) <= max_future_hours:
        return Appearance(published_at, TimeSource.FEED)
    if first_seen_at is not None:
        return Appearance(first_seen_at, TimeSource.FIRST_SEEN)
    return Appearance(None, TimeSource.UNKNOWN)


def too_old(at: str | None, *, now: str, config: CollectConfig) -> bool:
    """Past the age at which a story stops being news.

    A story we could not date at all is never too old: first sight is the only
    age it has, so it gets the run that found it and ages out from there.
    """
    if at is None:
        return False
    return _hours(now, at) > config.max_age_hours


def recency_bonus(at: str | None, *, now: str, config: CollectConfig) -> float:
    """A bonus that halves every `recency_half_life_hours`. Orders, never admits.

    `too_old` decides what may be added; this decides the order of what passed.
    A day-old item at the edge of the window still scores below an hour-old one.
    """
    if at is None:
        return 0.0
    hours = max(0.0, _hours(now, at))
    decay: float = 0.5 ** (hours / config.recency_half_life_hours)
    return config.recency_weight * decay


# --- scoring -----------------------------------------------------------------


def tier_weight(tier: SourceTier, config: CollectConfig) -> float:
    weights = config.tier_weights
    return {
        SourceTier.INSTITUTION: weights.institution,
        SourceTier.TRADE_PRESS: weights.trade_press,
        SourceTier.COMMUNITY: weights.community,
    }[tier]


def authority(
    candidate: Candidate,
    config: CollectConfig,
    reliability: Mapping[str, float] | None = None,
) -> float:
    """The source's tier score, scaled by that feed's weight and its reliability.

    Weight is soft retirement: drop a feed to 0.5, watch what it costs, then
    decide. Multiplying rather than adding keeps a weighted-down institution
    below a full-weight one of the same tier, which is the point.

    Reliability is the same scaling, derived from the feed's recent record
    rather than set by hand: a feed that has published badly over the trailing
    window - failed reads, or reads that parsed to nothing - carries a factor
    below 1.0 and scores below a dependable feed of the same tier. The factor
    only ever reduces, because it is clamped at 1.0, and a feed we have no
    recent evidence on carries 1.0, so an untested feed is never punished. The
    map is built once per run by `ledger.reliability`; a missing feed reads 1.0.
    """
    factor = 1.0 if reliability is None else reliability.get(candidate.source_id, 1.0)
    return tier_weight(candidate.tier, config) * candidate.weight * factor


def merge(candidates: Iterable[Candidate]) -> dict[str, list[Candidate]]:
    """Group by canonical URL. The group size is the cross-source repetition."""
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.url_key, []).append(candidate)
    return grouped


def score(
    carried: Sequence[Candidate],
    *,
    config: CollectConfig,
    watchlist_hit: bool,
    lens_bonus: float = 0.0,
    appeared: str | None,
    now: str,
    reliability: Mapping[str, float] | None = None,
) -> float:
    """Authority, plus the bonuses. Every term is one a person named.

    Authority is the best-trusted source that carried the story, not the
    average: one institution saying it makes it true regardless of how many
    aggregators repeated it.

    A lens bonus is the weight of one lens, never the sum of several. Two
    themes in one headline is not twice the story, and summing would let a
    keyword list outweigh the fact that another feed carried it too.

    **Carriage was a multiplier here until 2026-09-13 and is a flat step now.**
    `1 + repetition_weight * (carriers - 1)` at a weight of 1.0 DOUBLED the
    authority term at two carriers and tripled it at three, which is a bigger
    move than any bonus on this page and uncapped besides - a story on six
    feeds took the day. Worse, a multiplier pays most to whatever already
    scored highest, so the same signal bought 1.0 for an institution and 0.6
    for the trade press: the opposite of what a tie-break does. `carriage_step`
    fires once at two carriers and never grows, because three carriers is not
    three times the story. What the count measures is syndication rather than
    agreement - `carried_by` counts feeds carrying ONE address, so two outlets
    writing their own piece produce two addresses and both read 1 - and
    `docs/concepts/digest.md` already refuses to print that claim in words.

    An aggregator's front-page vote was a term here until 2026-09-13 and is
    not one now. It fired on 8 of 5,682 published stories - 0.1 percent - and
    was worth 0.4, more than the smallest step between two tiers. A term nobody
    can attribute a move to is not a ranking term. Removing it takes no story
    out of the first twenty on any of the 13 committed days that carry a score,
    and it does change which of those twenty leads on 2 of them - a term that is
    silent 99.9 percent of the time and then decides the lead is a lottery. The
    vote is still published on the item; it just no longer buys a place.
    """
    best = max(authority(candidate, config, reliability) for candidate in carried)
    total = best
    if len(carried) > 1:
        total += config.carriage_step
    if watchlist_hit:
        total += config.watchlist_bonus
    total += lens_bonus
    total += recency_bonus(appeared, now=now, config=config)
    return round(total, 6)


@dataclass(frozen=True, slots=True)
class Ranked:
    """One story after scoring, before anything decides whether to take it.

    `score_counterfactual` is what the same story would have scored if one lens
    weight had been a different number, and it is `None` on a run that asked no
    such question. It comes from a second call to `score` over the same
    candidates rather than from arithmetic on `score`, because a lens term that
    is added flatly today is an implementation detail and not a promise - the
    day it stops being flat, a subtraction would keep returning a number and
    the number would be wrong.
    """

    score: float
    candidate: Candidate
    appeared_at: str | None
    time_source: TimeSource
    carried_by: int
    watchlist_hit: bool
    on_front_page: bool
    lens_bonus: float = 0.0
    score_counterfactual: float | None = None


class DeskPlan(NamedTuple):
    """What one desk scored, and what it took out of that.

    Three facts about one pass. `pool` is every candidate the desk scored -
    taken and refused alike, in the order the take read them - and it is the
    one of the three that exists nowhere else. `items` is the subset that
    survived `max_per_source` and the day ceiling, and the grouping, the
    already-published drop and the too-old drop that decide who is in the pool
    at all all happen inside `plan_vertical`. A second function recomputing a
    refused candidate would be a second copy of the rules that decide the day,
    which is the drift a single scoring path exists to prevent.

    Returned rather than appended to a list the caller passes in:
    `stages.plan._plan_desks` runs twice on a day whose source ceiling binds,
    and only the second pass is the true one. A return value is replaced by the
    rebinding that is already there; an accumulator stacks both passes.
    """

    summary: VerticalPlan
    items: list[PlannedItem]
    pool: list[Ranked]


def _ordered(scored: list[Ranked]) -> list[Ranked]:
    """Score first, then when it appeared, then the address.

    The tie-break matters more than it looks. On a day when no story is carried
    twice the scores sit close together, and an alphabetical tie-break silently
    hands the day to whichever host sorts first. Sorts are stable, so these
    compose least-significant first.
    """
    ordered = sorted(scored, key=lambda item: item.candidate.canonical_url)
    ordered.sort(key=lambda item: item.appeared_at or "", reverse=True)
    ordered.sort(key=lambda item: item.score, reverse=True)
    return ordered


@dataclass(frozen=True, slots=True)
class DayCeiling:
    """How much of one day one feed may hold, and how much it holds already.

    `max_per_source` bounds a feed inside one desk in one run, and a feed sits
    on exactly one desk, so a feed's ceiling for a whole day is that count
    times the runs the day had. That is a fixed number, and a fixed number is a
    moving share: ten items is 2.3 percent of a 431-item day and a quarter of a
    four-item one. This is the share.

    `carried` is what today's earlier runs already put in front of a reader,
    per feed, and the run adds to it as each desk is planned - so the ceiling
    counts across desks and across runs, which is the whole point of it.
    """

    per_source: int
    carried: dict[str, int]

    def room_for(self, source_id: str) -> int:
        """How many more items this feed may still take today. Never negative."""
        return max(0, self.per_source - self.carried.get(source_id, 0))

    def record(self, source_id: str) -> None:
        """Count one more item for this feed, so the next desk plans against it."""
        self.carried[source_id] = self.carried.get(source_id, 0) + 1


def day_source_ceiling(share: float, day_items: int, *, max_per_source: int) -> int:
    """Turn the share into the count a run can enforce.

    Never below `max_per_source`. A day ceiling under that would tighten what
    one desk may take in one run, which is a different decision about a desk
    rather than about a day, and it was refused: it starves a desk where one
    publication is genuinely the best source and still does not bound the day.
    """
    return max(max_per_source, int(share * day_items))


def _take(
    ordered: list[Ranked],
    *,
    max_per_source: int,
    day_ceiling: DayCeiling | None = None,
) -> list[Ranked]:
    """Everything the feeds offered, except that no one feed becomes the vertical.

    Two limits, and they answer different questions. `max_per_source` asks how
    much of this desk one feed may be in this run. `day_ceiling` asks how much
    of today one feed may be, counting every desk and every run.

    A day ceiling displaces a story; it never shortens the day. Every slot it
    takes back is offered to the best candidate `max_per_source` alone held
    down - the next candidate on this desk - as long as the day still has room
    for that feed. Where the desk has nothing to put in its place, the story
    comes back: a shorter day is the one thing this is not allowed to buy, and
    a reader cannot see what was left out.

    A story the day ceiling refuses still spends its feed's `max_per_source`
    quota, and that is what makes the two rules compose. Without it a feed with
    no room left would never reach the per-desk limit, so every one of its
    candidates would queue for the slot instead of two of them - and a desk
    where most feeds are out of room would hand one of them the whole day. That
    is the failure this exact line prevents, measured on a real day's pool.
    """
    chosen: set[str] = set()
    per_source: dict[str, int] = {}
    held: list[Ranked] = []
    refused: list[Ranked] = []
    for item in ordered:
        source_id = item.candidate.source_id
        used = per_source.get(source_id, 0)
        if used >= max_per_source:
            held.append(item)
            continue
        per_source[source_id] = used + 1
        if day_ceiling is not None and used >= day_ceiling.room_for(source_id):
            refused.append(item)
            continue
        chosen.add(item.candidate.url_key)

    owed = len(refused)
    for item in held:
        if not owed:
            break
        source_id = item.candidate.source_id
        used = per_source.get(source_id, 0)
        if day_ceiling is not None and used >= day_ceiling.room_for(source_id):
            continue
        per_source[source_id] = used + 1
        chosen.add(item.candidate.url_key)
        owed -= 1

    for item in refused[:owed]:
        chosen.add(item.candidate.url_key)

    return [item for item in ordered if item.candidate.url_key in chosen]


def desks_below_floor(verticals: Iterable[VerticalPlan]) -> frozenset[str]:
    """The ids this run collected but will not render, off its own plan.

    Read from the plan rather than from the taxonomy so it says what THIS run
    found. A vertical is under its floor because of how many of its addresses
    were lawfully askable today, and that is a fact about a run.
    """
    return frozenset(plan.id for plan in verticals if plan.below_feed_floor)


def desk_of(vertical: str, desk: str | None, *, below_floor: Container[str]) -> str | None:
    """Where a story publishes, or None where nothing has said.

    Null is not a quiet way of writing the vertical. Nothing reads an article
    yet, so almost every item takes this branch, and writing the feed's word
    into `desk` would make each of them claim a reading of itself that never
    happened. A page falls back to the vertical; the payload does not.

    Where something HAS said, the answer is a decided fact and the field carries
    it - including when the answer is the feed's own word after the floor
    refused the label. The feed floor is a statement about supply, and supply is
    collected per feed. Without that fallback an above-floor vertical's stories
    would land in a desk that renders while the same day's payload flags it as
    having planned nothing - the page and the operator surface saying opposite
    things about one name.
    """
    if desk is None:
        return None
    return vertical if desk in below_floor else desk


def plan_vertical(
    vertical: VerticalDef,
    candidates: Sequence[Candidate],
    *,
    config: CollectConfig,
    eligible_feeds: int,
    now: str,
    first_seen: Mapping[str, str] | None = None,
    already_published: frozenset[str] = frozenset(),
    settled_today: frozenset[str] = frozenset(),
    watchlist_keys: frozenset[str] = frozenset(),
    front_page_keys: frozenset[str] = frozenset(),
    lens_bonuses: Mapping[str, float] | None = None,
    counterfactual_lens_bonuses: Mapping[str, float] | None = None,
    day_ceiling: DayCeiling | None = None,
    reliability: Mapping[str, float] | None = None,
) -> DeskPlan:
    """Rank one vertical's candidates and take what its feeds actually offered.

    Supply, the score and `max_per_source` set the size. A vertical below its
    feed floor is still counted - it is being built in the open - but it plans
    nothing, so an under-sourced desk never reaches a reader.

    `eligible_feeds` is how many of the desk's addresses this run may lawfully
    ask, counted by `source_health.eligible`. A resting or failing endpoint is
    in it and a retired or robots-refused one is not: the floor is about how
    many independent sources the desk has, not about how many answered today.

    An address that reached a committed digest is dropped before anything is
    counted. A freshness rule cannot do that job on its own: an article
    published at 23:00 is seven hours old at 06:00 the next morning.

    An address that already failed today for a reason today cannot change is
    dropped the same way. `already_published` cannot cover it, because a failure
    is never published - so run 2 used to re-plan run 1's paywalls and get the
    same paywalls. The two sets are kept apart rather than merged: they are
    different facts, and `considered` has to be able to say which one cost a
    slot.

    A story past `max_age_hours` is dropped after it is counted, not before, so
    `considered` still says what the feeds offered and `too_old` says how much
    of it was a back catalogue.

    `lens_bonuses` is a theme's weight per address, matched on the headline
    before this is called - the body has not been fetched yet. One story takes
    the largest weight it earned and never the sum: two themes in one headline
    is not twice the story.

    `published_at` on the planned item is the time we believe, not the time the
    feed claimed. A date rejected as impossible must not reach a reader either,
    and `time_source` says which of the two clocks answered.

    `day_ceiling` is the one input here that counts past this desk and past
    this run. Without it a feed's ceiling for a whole day is `max_per_source`
    times the runs the day had, which is a count and not a share - and the
    share is what a reader sees. A run that does not pass one plans exactly
    what it planned before.

    The scored pool comes back beside the summary and the items, because a
    candidate this desk refused is recorded nowhere else and the only honest
    way to know what the score refused is to keep the scores it refused on.
    `DeskPlan` says what the three are.

    `counterfactual_lens_bonuses` is the same mapping under a different set of
    lens weights, and it decides nothing. Every story is scored a second time
    with it and the second answer is carried on `Ranked.score_counterfactual`
    for a ledger to record; the take, the order and the plan are the first
    answer's alone. Passing it is what makes a run able to say what a weight
    change would have cost, and the only way to know that from committed data
    is to have asked at the time - after the fact, the candidates a run
    refused are gone.
    """
    sightings = first_seen or {}
    themes = lens_bonuses or {}
    probes = counterfactual_lens_bonuses
    dropped = already_published | settled_today
    grouped = {
        url_key: carried
        for url_key, carried in merge(candidates).items()
        if url_key not in dropped
    }
    below_floor = eligible_feeds < vertical.min_feeds
    summary = VerticalPlan(
        id=vertical.id,
        considered=len(grouped),
        planned=0,
        eligible_feeds=eligible_feeds,
        feed_floor=vertical.min_feeds,
        below_feed_floor=below_floor,
    )
    if below_floor:
        return DeskPlan(summary, [], [])

    scored: list[Ranked] = []
    stale = 0
    for url_key, carried in grouped.items():
        best = min(
            carried,
            key=lambda item: (-authority(item, config, reliability), item.source_id),
        )
        watchlist_hit = url_key in watchlist_keys
        on_front_page = best.canonical_url in front_page_keys
        appeared = appeared_at(
            best.published_at,
            first_seen_at=sightings.get(url_key),
            now=now,
            max_future_hours=config.max_future_hours,
        )
        if too_old(appeared.at, now=now, config=config):
            stale += 1
            continue
        theme = themes.get(url_key, 0.0)
        scored.append(
            Ranked(
                score=score(
                    carried,
                    config=config,
                    watchlist_hit=watchlist_hit,
                    lens_bonus=theme,
                    appeared=appeared.at,
                    now=now,
                    reliability=reliability,
                ),
                candidate=best,
                appeared_at=appeared.at,
                time_source=appeared.source,
                carried_by=len(carried),
                watchlist_hit=watchlist_hit,
                on_front_page=on_front_page,
                lens_bonus=theme,
                score_counterfactual=(
                    None
                    if probes is None
                    else score(
                        carried,
                        config=config,
                        watchlist_hit=watchlist_hit,
                        lens_bonus=probes.get(url_key, 0.0),
                        appeared=appeared.at,
                        now=now,
                        reliability=reliability,
                    )
                ),
            )
        )

    ordered = _ordered(scored)
    taken = _take(ordered, max_per_source=config.max_per_source, day_ceiling=day_ceiling)
    items = [
        PlannedItem(
            item_id=item_id(vertical.id, item.candidate.url_key),
            url_key=item.candidate.url_key,
            source_url=item.candidate.source_url,
            canonical_url=item.candidate.canonical_url,
            source_id=item.candidate.source_id,
            tier=item.candidate.tier,
            source_form=item.candidate.source_form,
            vertical=vertical.id,
            title=item.candidate.title,
            published_at=item.appeared_at,
            time_source=item.time_source,
            carried_by=item.carried_by,
            watchlist_hit=item.watchlist_hit,
            on_front_page=item.on_front_page,
            rank_score=item.score,
        )
        for item in taken
    ]
    return DeskPlan(
        summary.model_copy(update={"planned": len(items), "too_old": stale}),
        items,
        ordered,
    )


# --- day-wide duplicates: the same story at two addresses --------------------


class DuplicateFinding(NamedTuple):
    """One story the plan would fold into another it already kept.

    `item` is the lower-ranked address that repeats `duplicate_of`. Record-only,
    the pair is logged and both survive; enforcing, `item` is the one that goes.
    """

    item: PlannedItem
    duplicate_of: PlannedItem
    similarity: float


def dedup_text(title: str | None, lead: str | None) -> str | None:
    """The text that stands for a story when the plan looks for a repeat of it.

    The headline and the feed's lead, which is what the assemble-stage duplicate
    pass compares as well: a bare headline is too short for two outlets' wording
    of one story to land close. An item with no title earns no text and is never
    a duplicate, because there is nothing to compare.
    """
    if not title:
        return None
    return f"{title} {lead}".strip() if lead else title


def duplicates_within_plan(
    items: Sequence[PlannedItem],
    vectors: Mapping[str, Sequence[float]],
    *,
    similarity_min: float,
) -> list[DuplicateFinding]:
    """What a semantic pass would collapse, keeping the higher-ranked of each pair.

    The day's stories are walked in descending rank, so the first telling of a
    story is its strongest and is kept; a later, weaker telling of the same story
    from a DIFFERENT source is what is recorded. Same-source is never a duplicate
    here - a feed carrying two near-identical posts of its own is a different
    problem and `max_per_source` already bounds it.

    A desk's only story is never recorded, whatever it resembles. A single-carrier
    story scores lowest by construction, so a pass that cut the weakest would cut
    the exclusive story first (decision, row 52); the guard is the desk's item
    count, not the score.

    The walk is honest about enforcement: a story recorded as a would-cut is not
    itself offered as a match for a later story, because were the pass enforcing
    it would already be gone. So the count is what enforcing would remove, not an
    over-count matched against items that would not survive.

    Cost is bounded by the day's plan, never by the archive (Guardrail #12): the
    safety ceiling caps `items`, and the vectors are handed in already computed.
    """
    desk_size = Counter(item.vertical for item in items)
    kept: list[PlannedItem] = []
    findings: list[DuplicateFinding] = []
    for item in sorted(items, key=lambda planned: (-planned.rank_score, planned.item_id)):
        vector = vectors.get(item.item_id)
        if vector is not None and desk_size[item.vertical] > 1:
            best: DuplicateFinding | None = None
            left = list(vector)
            for other in kept:
                if other.source_id == item.source_id:
                    continue
                right = vectors.get(other.item_id)
                if right is None:
                    continue
                similarity = cosine(left, list(right))
                if similarity >= similarity_min and (best is None or similarity > best.similarity):
                    best = DuplicateFinding(item=item, duplicate_of=other, similarity=similarity)
            if best is not None:
                findings.append(best)
                continue
        kept.append(item)
    return findings
