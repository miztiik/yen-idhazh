"""The night's draw: which pairs get judged, in what order, and on which shard.

Nothing under test here calls a model or opens a socket, because the step does
neither - it says which pairs are worth a model's time and writes them out with
every verdict column empty.

Unit tier for the rules - across mastheads, one pair of addresses once, what each
slice gives, how the shards are dealt and the file is ordered - and integration tier
for the stage writing a file the contract can read back. Real quantised vectors
through the encoder's own wire format and generated native manifests throughout.
No mocks, no network.

**No test here walks committed data** (CLAUDE.md section 13). The day the
integration tests read is built into the test's own tree, which is fixed in size
and can carry the cases the archive is thin on: two mastheads running the same
headline, which scores 1.0 by a different rule than every other pair, and an
address that published on two days.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import assemble, atomic_write, config, ledger
from idhazh.assemble import ScoredPair, cross_source_pairs
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.base import ServerJob, Sha256, derive_url_key
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestEmbeddings,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
)
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.placement import SameStoryConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import PairBucket, StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, to_base64
from idhazh.similarity.selection import (
    Draw,
    assign_shards,
    draw_order_of,
    one_pair_a_key,
    pair_key,
    select,
)
from idhazh.similarity.stamps import ScorerStamp, scorer_inputs
from idhazh.similarity.thresholds_in_force import (
    ThresholdsInForce,
    lookback_days,
    thresholds_in_force,
)
from idhazh.stages import common
from idhazh.stages.pick_item_pairs import stage_pick_item_pairs

#: The generated published day; drawn rows still name the council's own run.
DATE: Final = "2026-08-21"

#: What the council calls itself on the night it judges `DATE`. The day after the
#: judged date, because the prefix is the day the council RUNS, and a platform
#: run id after it.
COUNCIL_RUN: Final = "2026-08-22-35534060762"

#: The committed draw settings and starts, which the hand-worked numbers below follow.
JUDGE: Final = judge_settings.load(CONFIG_DIR)
DRAW: Final = JUDGE.draw

#: Digits spelled as letters, so a built item's headline carries no figure - a
#: pair of headlines around two different numbers is vetoed before it is scored,
#: and every pair in this file has to reach the scorer.
_NO_FIGURES: Final = str.maketrans("0123456789", "abcdefghij")


def unit(degrees: float) -> str:
    """A real quantised vector at a chosen angle, through the wire format.

    Two components carry the whole vector, so the angle between two of these is
    the angle between their arguments and a test names the similarity it wants
    instead of discovering it.
    """
    radians = math.radians(degrees)
    return to_base64([math.cos(radians), math.sin(radians)] + [0.0] * (DIMENSIONS - 2))


def block(vectors: dict[str, str]) -> DigestEmbeddings:
    return DigestEmbeddings(
        model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE, vectors=vectors
    )


def item(item_id: str, *, outlet: str, title: str | None = None) -> DigestItem:
    """One published story, with the four cells the draw reads filled in."""
    return DigestItem(
        item_id=item_id,
        vertical=item_id.rsplit("-", 1)[0],
        title=title if title is not None else f"Story {item_id.translate(_NO_FIGURES)}",
        source_url=f"https://{outlet.lower().replace(' ', '-')}.test/{item_id}",
        source_id=outlet.lower().replace(" ", "-"),
        source_name=outlet,
        summary="A summary long enough to be a summary.",
        band=ConfidenceBand.HIGH,
        rank_score=1.0,
        introduced_by_run=1,
    )


def scored(left: str, right: str, *, score: float) -> ScoredPair:
    """A pair at a chosen score, so a test names the number it is about.

    The terms are not the score's arithmetic here and do not need to be: the
    slice, the budget and the order read the score alone, and the rule that ties
    the terms to the score is the contract's, exercised by the integration tests
    below.
    """
    return ScoredPair(left=left, right=right, cosine=score, headline=False, score=score)


def stamp(*, cosine_weight: float = 1.0) -> ScorerStamp:
    return ScorerStamp(scorer_model=EMBEDDER_ID, cosine_weight=cosine_weight)


#: Every slice of the committed starts, and how many pairs each holds in the night below:
#: the end under 0.70, six thin slices, three coarse ones, six thin ones, the end over 0.93.
SLICE_EDGES: Final = [
    (-1.0, 0.70), *[(0.70 + n / 100, 0.71 + n / 100) for n in range(6)],
    (0.76, 0.80), (0.80, 0.84), (0.84, 0.87),
    *[(0.87 + n / 100, 0.88 + n / 100) for n in range(6)], (0.93, 1.0),
]
HELD: Final = [5000, *[30] * 6, *[60] * 3, *[20] * 6, 9]


def a_night_of_pairs(
    held: list[int] = HELD, *, prefix: str = "a"
) -> list[ScoredPair]:
    """Pairs spread through every slice, each at a score strictly inside its own slice."""
    pairs: list[ScoredPair] = []
    for index, ((low, high), count) in enumerate(zip(SLICE_EDGES, held, strict=True)):
        for number in range(count):
            score = low + (high - low) * (number + 1) / (count + 1)
            pairs.append(
                scored(f"{prefix}-{index:02d}-{number:05d}", f"z-{index:02d}-{number:05d}", score=score)
            )
    return pairs


def taken_by_slice(drawn: Draw) -> dict[tuple[float, float], int]:
    counts = Counter((one.slice.low, one.slice.high) for one in drawn.taken)
    return {edges: counts.get(edges, 0) for edges in sorted(set(counts))}


# --- across mastheads --------------------------------------------------------


def test_a_pair_from_one_outlet_is_never_drawn() -> None:
    """One newsroom's second piece is a different problem with a different control.

    It is also where the encoder is least trustworthy: two pieces off one desk
    share their boilerplate, so a high cosine between them says nothing about
    whether they are one story. A draw that judged them would spend the budget
    on pairs the grouping pass refuses before it looks at a score.
    """
    items = [
        item("world-01", outlet="The Wire"),
        item("world-02", outlet="The Wire"),
        item("world-03", outlet="The Paper"),
    ]
    vectors = block({"world-01": unit(0.0), "world-02": unit(0.4), "world-03": unit(0.8)})

    drawn = list(cross_source_pairs(items, vectors, same_story=SameStoryConfig()))

    assert [(pair.left, pair.right) for pair in drawn] == [
        ("world-01", "world-03"),
        ("world-02", "world-03"),
    ], "the two stories one masthead carried are not a pair"


# --- one pair of addresses, once ------------------------------------------------


def test_a_pair_of_addresses_is_kept_once_and_as_the_night_s_own_copy() -> None:
    """A story republished on a later day keeps its address and takes a new item id.

    So one pair of addresses arrives as two pairs of items, and a model call spent on the
    second is a call spent twice. The copy kept is the one made of the night's own items,
    because the judge reads the night's own copy of an address, and then the score the
    slice is cut by is the score of the text judged.
    """
    address_of = {"old": "x", "new": "x", "other": "y", "also": "z"}
    earlier_copy = scored("old", "other", score=0.77)
    own_copy = scored("new", "other", score=0.95)
    unrelated = scored("also", "other", score=0.5)

    kept = one_pair_a_key(
        [earlier_copy, own_copy, unrelated],
        address_of=address_of,
        own={"new", "other", "also"},
    )

    assert kept == [own_copy, unrelated]
    assert one_pair_a_key(
        [own_copy, earlier_copy], address_of=address_of, own={"new", "other"}
    ) == [own_copy], "the order the copies arrive in does not decide it"
    assert one_pair_a_key(
        [earlier_copy, scored("old", "other", score=0.78)],
        address_of=address_of,
        own={"other"},
    ) == [earlier_copy], "two copies equally the night's own keep the first"


# --- what each slice gives -----------------------------------------------------


def test_each_slice_gives_the_number_the_allocation_names_and_the_row_says_what_it_held() -> None:
    """A hand-worked night: every slice holds more than its share except the similar end.

    Under the committed starts 150 pairs go 4 to the dissimilar end, 62, 31 and 47 to the
    thin lower, coarse and thin upper slices, and the similar end holds 9 and gives its
    maximum of 6. Each pair says how many its slice held and how many the draw took.
    """
    drawn = select(
        a_night_of_pairs(), lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp()
    )

    assert [taken_by_slice(drawn)[edges] for edges in SLICE_EDGES] == [
        4, 11, 11, 10, 10, 10, 10, 11, 10, 10, 8, 8, 8, 8, 8, 7, 6,
    ]
    assert len(drawn.taken) == DRAW.pair_budget
    assert drawn.pairs_available == sum(HELD)
    assert {
        ((one.slice.low, one.slice.high), one.slice_pairs_available, one.slice_pairs_judged)
        for one in drawn.taken
    } == {
        (edges, held, given)
        for edges, held, given in zip(
            SLICE_EDGES, HELD, [4, 11, 11, 10, 10, 10, 10, 11, 10, 10, 8, 8, 8, 8, 8, 7, 6],
            strict=True,
        )
    }


def test_a_pair_scoring_below_zero_is_drawn() -> None:
    """The draw reaches down to -1, where the lightly sampled end is the check on the judge."""
    below = [scored(f"a-{n}", f"z-{n}", score=-0.9 + n / 10) for n in range(3)]

    drawn = select(below, lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp())

    assert len(drawn.taken) == len(below)
    assert {one.slice.bucket for one in drawn.taken} == {PairBucket.FULLY_DISSIMILAR}
    assert min(one.pair.score for one in drawn.taken) < 0


def test_the_same_night_drawn_twice_gives_the_same_pairs_in_any_input_order() -> None:
    """The order is the hash of the pair's own contents and there is no seed."""
    pairs = a_night_of_pairs()

    once = select(pairs, lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp())
    again = select(
        list(reversed(pairs)), lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp()
    )

    assert [one.pair for one in once.taken] == [one.pair for one in again.taken]


def test_a_changed_date_or_scorer_stamp_draws_different_pairs() -> None:
    """A re-scored day is re-drawn rather than handed yesterday's sequence."""
    pairs = a_night_of_pairs()

    def drawn(**changes: object) -> list[ScoredPair]:
        arguments: dict[str, object] = {"date": DATE, "stamp": stamp()} | changes
        return [
            one.pair
            for one in select(
                pairs, lower=0.70, upper=0.93, draw=DRAW, **arguments  # type: ignore[arg-type]
            ).taken
        ]

    assert drawn() != drawn(stamp=stamp(cosine_weight=0.9))
    assert drawn() != drawn(date="2026-08-22")


def test_the_order_ignores_which_side_of_a_pair_was_named_first() -> None:
    """One pair has one sort key, whichever way round a caller built it."""
    order = draw_order_of(date=DATE, stamp=stamp())

    assert order(scored("world-01", "world-02", score=0.90)) == order(
        scored("world-02", "world-01", score=0.90)
    )


def test_a_pair_key_is_the_full_digest_of_both_addresses_sorted() -> None:
    """The contract recomputes this on read, so a short or separated key is refused.

    It is refused at write time, which is after the model calls on that pair
    have been paid for - so the day's whole draw is lost to a key that was one
    expression away from the one the contract holds.
    """
    left, right = derive_url_key("https://wire.test/one"), derive_url_key("https://paper.test/two")
    column = TypeAdapter(Sha256)

    key = pair_key(left, right)

    assert key == pair_key(right, left), "a pair scored either way round is one key"
    assert column.validate_python(key) == key
    with pytest.raises(ValidationError):
        column.validate_python(key[:16])


# --- the shards and the file -----------------------------------------------------


def test_the_shards_are_even_to_within_one_and_every_slice_is_dealt_round_them() -> None:
    """The deal runs over every slice in turn, so a lost runner takes a share of each slice.

    A slice of two pairs or more reaches two shards, so one lost runner can never take a
    whole slice of them, and the counts a shard holds differ by no more than one.
    """
    drawn = select(
        a_night_of_pairs(), lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp()
    )

    dealt = assign_shards(drawn.taken, shards=4)

    sizes = Counter(shard for shard, _ in dealt)
    assert sorted(sizes) == [0, 1, 2, 3]
    assert max(sizes.values()) - min(sizes.values()) <= 1
    shards_of_a_slice: dict[tuple[float, float], set[int]] = {}
    for shard, one in dealt:
        shards_of_a_slice.setdefault((one.slice.low, one.slice.high), set()).add(shard)
    assert all(
        len(shards) >= 2
        for edges, shards in shards_of_a_slice.items()
        if taken_by_slice(drawn)[edges] >= 2
    )


def test_the_file_lists_every_slice_in_proportion_so_a_cut_off_tail_takes_a_share_of_each() -> None:
    """A runner that stops on its clock loses the end of its file.

    The first pair of every slice comes first and the last pair of each comes last, so the
    end of a file is a similar share of every slice. A file ordered by the hash alone would
    put the small slices last, because a big pool gives the pairs with the smallest hashes.
    """
    drawn = select(
        a_night_of_pairs(), lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp()
    )

    places = [one.slice_rank / one.slice_pairs_judged for one in drawn.taken]
    tail = drawn.taken[-30:]

    assert places == sorted(places)
    assert len({(one.slice.low, one.slice.high) for one in tail}) >= 10, (
        "the last 30 of 150 pairs come from most of the 17 slices, not from a few"
    )


@pytest.mark.parametrize("count", [200, 199])
def test_the_shards_stay_even_whatever_the_count(count: int) -> None:
    """Index modulo the shard count, so a draw the budget cut short still spreads."""
    pairs = [scored(f"left-{n:03d}", f"right-{n:03d}", score=0.90) for n in range(count)]
    drawn = select(pairs, lower=0.70, upper=0.93, draw=DRAW, date=DATE, stamp=stamp())

    counts = Counter(shard for shard, _ in assign_shards(drawn.taken, shards=4))

    assert sorted(counts) == [0, 1, 2, 3], "every shard gets work"
    assert max(counts.values()) - min(counts.values()) <= 1


# --- the thresholds the night follows ----------------------------------------------


def a_history_row(date: str, *, lower: float, upper: float) -> StorySimilarityThresholdHistoryRow:
    """A night that held both thresholds where it says, built from the contract's own fixture."""
    raw = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR
            / "story-similarity-threshold-history-row"
            / "a-night-that-held-both-thresholds.json"
        )
    )
    return StorySimilarityThresholdHistoryRow.model_validate(
        raw
        | {
            "date": date,
            "run_id": f"{date}-9",
            "lower_threshold_before": lower,
            "lower_threshold_after": lower,
            "lower_estimate": lower + raw["lower_gap"],
            "upper_threshold_before": upper,
            "upper_threshold_after": upper,
            "upper_estimate": upper + raw["upper_gap"],
        }
    )


def test_the_newest_row_before_the_night_inside_the_lookback_sets_the_thresholds() -> None:
    history = [
        a_history_row("2026-08-10", lower=0.60, upper=0.90),
        a_history_row("2026-08-19", lower=0.65, upper=0.95),
        a_history_row("2026-08-19", lower=0.66, upper=0.96),
        a_history_row("2026-08-21", lower=0.50, upper=0.99),
        a_history_row("2026-08-22", lower=0.40, upper=0.98),
    ]

    followed = thresholds_in_force(
        history, night=DATE, within_days=14, lower_start=0.70, upper_start=0.93
    )

    assert followed == ThresholdsInForce(lower=0.66, upper=0.96, set_on="2026-08-19"), (
        "the last row of the newest day wins, and the night's own row and a later one never do"
    )
    assert followed.row is history[2], "the row that set them is handed back, not looked up again"


def test_with_no_row_inside_the_lookback_the_configured_starts_set_the_thresholds() -> None:
    old = [a_history_row("2026-08-01", lower=0.60, upper=0.90)]

    assert thresholds_in_force(
        old, night=DATE, within_days=14, lower_start=0.70, upper_start=0.93
    ) == ThresholdsInForce(lower=0.70, upper=0.93, set_on=None)
    starts = thresholds_in_force(
        [], night=DATE, within_days=14, lower_start=0.70, upper_start=0.93
    )
    assert (starts.set_on, starts.row) == (None, None)


def test_the_days_to_read_are_the_days_the_rule_keeps() -> None:
    """The read names the lookback days, and the rule keeps a row dated inside the same window."""
    days = lookback_days(DATE, within_days=14)

    assert (days[0], days[-1], len(days)) == ("2026-08-07", "2026-08-20", 14)
    for day in (days[0], days[-1]):
        assert thresholds_in_force(
            [a_history_row(day, lower=0.65, upper=0.95)],
            night=DATE,
            within_days=14,
            lower_start=0.70,
            upper_start=0.93,
        ).set_on == day
    assert thresholds_in_force(
        [a_history_row("2026-08-06", lower=0.65, upper=0.95)],
        night=DATE,
        within_days=14,
        lower_start=0.70,
        upper_start=0.93,
    ).set_on is None


# --- the stage ---------------------------------------------------------------


def publish(root: Path, date: str, items: list[DigestItem], angles: list[float]) -> None:
    """One day on disk with vectors at the named angles."""
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{date}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(Counter(one.vertical for one in items).items())
        ],
        items=items,
        embeddings=block({one.item_id: unit(angle) for one, angle in zip(items, angles, strict=True)}),
    )
    atomic_write.write_atomic(assemble.day_dir(root, date) / "digest.json", day.to_json())


def a_published_day(root: Path) -> None:
    """One day: six stories, five mastheads, one shared headline, scores from -0.17 to 1.0.

    Built rather than read off the archive, because the case that matters most
    here is two outlets running the same headline - which scores 1.0 by a rule
    the weighted sum never reaches, and which the contract refuses a row for
    unless the `headline` column agrees with the score. Few pairs sit above 0.93 so
    the draw takes the shared headline's pair whatever the hash order is.
    """
    publish(
        root,
        DATE,
        [
            item("world-01", outlet="The Wire", title="Floods reach the delta"),
            item("world-02", outlet="The Paper", title="Floods reach the delta"),
            item("world-03", outlet="The Herald"),
            item("world-04", outlet="The Gazette"),
            item("business-01", outlet="The Ledger"),
            item("business-02", outlet="The Wire"),
        ],
        [0.0, 0.6, 25.0, 45.0, 100.0, 70.0],
    )


def drawn_rows(path: Path) -> list[StorySimilarityPairVerdict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [StorySimilarityPairVerdict.from_csv_row(row) for row in csv.DictReader(handle)]


def draw_the_night(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: config.Settings | None = None,
    state: Path | None = None,
    out: str = "draw",
) -> tuple[Draw, list[StorySimilarityPairVerdict]]:
    """Run the stage over the day under `tmp_path` and read the file back through the contract."""
    digest_root = tmp_path / "digest"
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    path = tmp_path / out / "draw.csv"
    drawn = stage_pick_item_pairs(
        DATE,
        run_id=COUNCIL_RUN,
        settings=settings or config.load(CONFIG_DIR),
        digest_root=digest_root,
        draw_path=path,
        state_dir=state or tmp_path / "state",
    )
    return drawn, drawn_rows(path)


@pytest.mark.parametrize("earlier_count", [0, 1, 2], ids=["same-day", "cross-day", "earlier-day"])
def test_the_picker_excludes_self_pairs_before_the_pool_is_counted_and_the_shards_dealt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, earlier_count: int
) -> None:
    """Removing the shared URL guard must fail before an invalid draw is written.

    Three placements of one headline, two of them the same canonical article URL, laid out
    on one day, across two days and with the two on the earlier day. The pair those two
    make is not a pair. The other two comparisons name one pair of addresses, so the pool
    holds it once, and with the guard gone the self-pair would be drawn and the contract
    would refuse its row.
    """
    first = item("world-01", outlet="The Wire", title="Floods reach the delta")
    duplicate = item("business-02", outlet="The Paper", title=first.title).model_copy(
        update={"source_url": first.source_url, "desk": "business"}
    )
    distinct = item("science-03", outlet="The Herald", title=first.title)
    placements = [
        one.model_copy(update={"published_at": "2026-08-20T23:00:00Z"})
        for one in (first, duplicate, distinct)
    ]
    publish(tmp_path / "digest", DATE, placements[earlier_count:], [0.0] * (3 - earlier_count))
    if earlier_count:
        publish(tmp_path / "digest", "2026-08-20", placements[:earlier_count], [0.0] * earlier_count)

    drawn, rows = draw_the_night(tmp_path, monkeypatch)

    assert drawn.pairs_available == len(drawn.taken) == len(rows) == 1
    keys = sorted((derive_url_key(first.source_url), derive_url_key(distinct.source_url)))
    assert [[row.left_url_key, row.right_url_key] for row in rows] == [keys], (
        "the two placements of one article are one address, so they draw one pair of addresses"
    )


def test_a_pair_of_addresses_that_two_days_published_is_drawn_once_as_the_nights_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The night's story and an earlier day's republished copy of one address, each paired
    with the same third story, are two pairs of items and one pair of addresses.

    The copy that is kept is the night's own, so the stored score is the night's copy's:
    10 degrees from the third story scores 0.985, where the earlier copy at 40 degrees
    would have scored 0.766.
    """
    republished = item("world-01", outlet="The Wire")
    earlier_copy = republished.model_copy(update={"item_id": "world-90"})
    other = item("world-02", outlet="The Paper")
    timed = [
        republished.model_copy(update={"published_at": "2026-08-21T01:00:00Z"}),
        other.model_copy(update={"published_at": "2026-08-21T02:00:00Z"}),
    ]
    publish(tmp_path / "digest", DATE, timed, [10.0, 0.0])
    publish(
        tmp_path / "digest",
        "2026-08-20",
        [earlier_copy.model_copy(update={"published_at": "2026-08-20T23:00:00Z"})],
        [40.0],
    )

    drawn, rows = draw_the_night(tmp_path, monkeypatch)

    assert len(rows) == len(drawn.taken) == 1, "one pair of addresses, drawn once"
    assert rows[0].similarity_score == pytest.approx(math.cos(math.radians(10.0)), abs=1e-3)


def test_the_draw_round_trips_through_the_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every row the stage writes is one the contract will read back and accept.

    The contract recomputes the pair key from the row's own two addresses and the score
    from its own terms and weights, and it does both at WRITE time - so a stage that got
    either wrong would throw away a night of model calls that had already been paid for.
    Reading the file back through `from_csv_row` is what proves the columns survive the
    round trip as well as the constructor.

    It also fixes the shapes a reader downstream depends on: nothing is judged yet, the
    two columns the collecting job fills are empty, and the shared headline arrives with
    `headline` true, a score of 1.0 and the similar end's slice.
    """
    a_published_day(tmp_path / "digest")

    drawn, rows = draw_the_night(tmp_path, monkeypatch)

    assert rows, "the day holds pairs, so the draw is not empty"
    assert len(rows) == len(drawn.taken) <= drawn.pairs_available
    assert all(row.date == DATE and row.run_id == COUNCIL_RUN for row in rows), (
        "a row names the run that scored it, which is the council night"
    )
    assert all(row.left_url_key < row.right_url_key for row in rows)
    assert not any(
        row.verdict or row.verdict_swapped or row.readings_agree or row.judge_model
        or row.slice_pairs_usable is not None or row.sampling_chance is not None
        for row in rows
    ), "this step judges nothing, and the collecting job fills the chance"
    assert {row.config_versions for row in rows} == {judge_settings.config_versions(CONFIG_DIR)}
    assert {(row.lower_threshold_in_force, row.upper_threshold_in_force) for row in rows} == {
        (JUDGE.thresholds.lower_start, JUDGE.thresholds.upper_start)
    }
    headline = [row for row in rows if row.headline]
    assert len(headline) == 1, "one pair of mastheads ran the same headline"
    assert (headline[0].similarity_score, headline[0].bucket) == (1.0, PairBucket.FULLY_SIMILAR)
    shards = config.load(CONFIG_DIR).council.shards
    assert all(0 <= row.work_part_index < shards for row in rows)


def test_a_pair_scoring_below_zero_is_filed_in_the_dissimilar_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two stories pointing opposite ways score -1, which the old floor of zero could not hold."""
    publish(
        tmp_path / "digest",
        DATE,
        [item("world-01", outlet="The Wire"), item("world-02", outlet="The Paper")],
        [0.0, 180.0],
    )

    _, rows = draw_the_night(tmp_path, monkeypatch)

    assert [(row.similarity_score, row.bucket, row.slice_low) for row in rows] == [
        (-1.0, PairBucket.FULLY_DISSIMILAR, -1.0)
    ]


def a_filed_history(state: Path, row: StorySimilarityThresholdHistoryRow) -> None:
    """One night's thresholds filed through the door, the way the save job files them."""
    ledger.persist(
        state,
        [row],
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.SAVE_COUNCIL_RESULTS,
            shard=0,
            producer="stages.review_thresholds",
            git_sha=SEED_COMMIT,
        ),
    )


def test_the_draw_follows_the_thresholds_the_newest_filed_row_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a row dated before the night, its `threshold_after` columns decide the slices."""
    a_published_day(tmp_path / "digest")
    state = tmp_path / "state"
    a_filed_history(state, a_history_row("2026-08-20", lower=0.65, upper=0.95))

    _, rows = draw_the_night(tmp_path, monkeypatch, state=state)

    assert {(row.lower_threshold_in_force, row.upper_threshold_in_force) for row in rows} == {
        (0.65, 0.95)
    }
    assert all(row.slice_low >= 0.95 - 1e-9 for row in rows if row.bucket is PairBucket.FULLY_SIMILAR)


def test_a_written_judge_file_moves_the_thresholds_the_draw_starts_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The starts are config, so a changed start changes the slice a pair is filed under.

    A pair 12 degrees apart scores 0.978: the similar end under the committed 0.93, and a
    thin slice under an upper start of 0.99.
    """
    publish(
        tmp_path / "digest",
        DATE,
        [item("world-01", outlet="The Wire"), item("world-02", outlet="The Paper")],
        [0.0, 12.0],
    )
    raw = json.loads(read_text(CONFIG_DIR / "judges" / "content-similarity-judge.json"))
    raw["thresholds"]["upper_start"] = 0.99
    target = tmp_path / "config" / "judges" / "content-similarity-judge.json"
    atomic_write.write_atomic(target, json.dumps(raw))
    settings = replace(config.load(CONFIG_DIR), config_dir=target.parent.parent)

    _, committed_rows = draw_the_night(tmp_path, monkeypatch, out="committed")
    _, moved_rows = draw_the_night(tmp_path, monkeypatch, settings=settings, out="moved")

    assert [row.bucket for row in committed_rows] == [PairBucket.FULLY_SIMILAR]
    assert [row.bucket for row in moved_rows] == [PairBucket.UPPER_THIN]
    assert moved_rows[0].upper_threshold_in_force == 0.99


def test_a_day_that_is_not_on_disk_writes_an_empty_draw(tmp_path: Path) -> None:
    """A missing day is nothing to judge rather than a run to fail.

    The header still goes down, so the shard that opens the file reads an empty
    draw instead of dying on a file that is not there - which on a four-shard
    matrix is four failed jobs for one day nobody published.
    """
    out_dir = tmp_path / "judge"

    drawn = stage_pick_item_pairs(
        DATE,
        run_id=COUNCIL_RUN,
        settings=config.load(CONFIG_DIR),
        digest_root=tmp_path / "nothing-here",
        draw_path=out_dir / "draw.csv",
        state_dir=tmp_path / "state",
    )

    written = (out_dir / "draw.csv").read_text(encoding="utf-8")
    assert drawn == Draw(taken=[], pairs_available=0)
    assert written.splitlines() == [",".join(StorySimilarityPairVerdict.csv_columns())]


def test_the_stamp_is_the_committed_config_and_the_encoder_that_ran() -> None:
    """A row records the ruler it was scored under, read off the shipped config.

    A stamp taken from anywhere else would describe a scorer nobody ran, and
    the evidence would then be read under weights that never produced it.
    """
    settings = config.load(CONFIG_DIR)

    taken = scorer_inputs(settings)

    assert taken.scorer_model == EMBEDDER_ID
    assert taken.cosine_weight == settings.app.assemble.same_story.cosine_weight
