"""The day's draw: which borderline pairs get judged, in what order, on which leg.

Nothing under test here calls a model or opens a socket, because the step does
neither - it says which pairs are worth a model's time and writes them out with
every verdict column empty.

Unit tier for the four rules - across mastheads, the band's edges, what the
budget may cut, and how the legs are dealt - and integration tier for the stage
writing a file the contract can read back. Real quantised vectors through the
encoder's own wire format and the committed run-manifest fixture throughout. No
mocks, no network.

**No test here walks committed data** (CLAUDE.md section 13). The day the
integration test reads is built into the test's own tree, which is fixed in size
and can carry the case the archive is thin on: two mastheads running the same
headline, which scores 1.0 by a different rule than every other pair.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from pydantic import TypeAdapter, ValidationError

from idhazh import assemble, config
from idhazh.assemble import ScoredPair, cross_source_pairs
from idhazh.contracts.base import Sha256, derive_url_key
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestEmbeddings,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
)
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.knobs.placement import SameStoryConfig
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, to_base64
from idhazh.similarity.draw import (
    Draw,
    assign_shards,
    draw_order,
    in_band,
    pair_key,
    select,
)
from idhazh.similarity.stamps import ScorerStamp, scorer_inputs
from idhazh.stages import common
from idhazh.stages.judge_draw import DRAW_FILENAME, stage_judge_draw

#: The date the committed run-manifest fixture is addressed by. Used rather than
#: re-spelled, so the run id a drawn row carries is one a real manifest holds.
MANIFEST_FIXTURE: Final = CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"
DATE: Final = "2026-08-21"

#: A line and a band chosen for the tests below rather than read off config: a
#: unit test about what a budget may cut is not a test about today's floor, and
#: naming the number is what makes the assertion readable.
LINE: Final = 0.94

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
        key_points=["One point."],
        band=ConfidenceBand.HIGH,
        rank_score=1.0,
        introduced_by_run=1,
    )


def scored(left: str, right: str, *, score: float) -> ScoredPair:
    """A pair at a chosen score, so a test names the number it is about.

    The terms are not the score's arithmetic here and do not need to be: the
    band, the budget and the order read the composite alone, and the rule that
    ties the terms to the composite is the contract's, exercised by the
    integration test below.
    """
    return ScoredPair(
        left=left, right=right, cosine=score, key_points=score, headline=False, score=score
    )


def stamp(*, cosine_weight: float = 1.0, key_point_weight: float = 0.0) -> ScorerStamp:
    return ScorerStamp(
        scorer_model=EMBEDDER_ID, cosine_weight=cosine_weight, key_point_weight=key_point_weight
    )


def a_band_of_fifty_five() -> list[ScoredPair]:
    """Five pairs the day merged and fifty it did not, which is the shape of a real day."""
    above = [scored(f"above-{n:02d}", f"other-{n:02d}", score=0.95) for n in range(5)]
    below = [scored(f"below-{n:02d}", f"other-{n:02d}", score=0.90) for n in range(50)]
    return [*above, *below]


def named(drawn: Draw) -> list[tuple[str, str]]:
    return [(pair.left, pair.right) for pair in drawn.taken]


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


# --- the band ----------------------------------------------------------------


def test_the_band_keeps_the_edges_it_declares() -> None:
    """Both edges are inside, because a pair on an edge belongs in the slot it opens.

    The record slices the band into slots and counts what lands in each. An edge
    the band excluded would leave its slot able to hold nothing, and the fit
    would then place the line on a slot no pair can reach.
    """
    pairs = [
        scored("a-one", "b-one", score=0.8799),
        scored("a-two", "b-two", score=0.88),
        scored("a-three", "b-three", score=0.95),
        scored("a-four", "b-four", score=0.9501),
    ]

    kept = in_band(pairs, band_low=0.88, band_high=0.95)

    assert [pair.left for pair in kept] == ["a-two", "a-three"]


# --- the budget --------------------------------------------------------------


def test_every_pair_above_the_line_survives_a_budget_of_one() -> None:
    """A merge the day already made is the whole of what precision is read off.

    Sampling one away would leave the run unable to say how many of its own
    merges were wrong, which is the one number this feature exists to produce.
    So the budget is overspent rather than enforced, and this is the assertion
    that says which way round it goes.
    """
    drawn = select(a_band_of_fifty_five(), line=LINE, budget=1, date=DATE, stamp=stamp())

    assert sorted(named(drawn)) == [(f"above-{n:02d}", f"other-{n:02d}") for n in range(5)]


def test_the_budget_records_what_it_cut_from() -> None:
    """A day that hit the cap reads as partial rather than as a quiet truncation.

    Without the count, a day drawing 200 out of 200 and a day drawing 200 out of
    2,000 write the same file, and the second is a sample of the band while the
    first is the band.
    """
    drawn = select(a_band_of_fifty_five(), line=LINE, budget=10, date=DATE, stamp=stamp())

    assert drawn.pairs_in_band == 55, "the count is what the band held before the cut"
    assert len(drawn.taken) == 10


# --- the order ---------------------------------------------------------------


def test_the_order_is_the_hash_and_not_the_input_order() -> None:
    """Two runs over one day draw the same pairs, whatever order the day arrived in.

    The pairs below the line are interchangeable evidence, so the thing that
    chooses between them has to be a property of the pairs themselves. Input
    order is a property of how the day was assembled, and it moves.
    """
    pairs = a_band_of_fifty_five()

    forwards = select(pairs, line=LINE, budget=10, date=DATE, stamp=stamp())
    backwards = select(list(reversed(pairs)), line=LINE, budget=10, date=DATE, stamp=stamp())

    assert named(forwards) == named(backwards)


def test_a_changed_scorer_stamp_changes_the_order() -> None:
    """A re-weighted day is re-drawn rather than handed yesterday's sequence.

    The scores moved, so which pairs are borderline moved with them. An order
    that ignored the ruler would keep drawing the pairs that were interesting
    under the old weights.
    """
    pairs = a_band_of_fifty_five()

    under_cosine = select(pairs, line=LINE, budget=10, date=DATE, stamp=stamp())
    under_both = select(
        pairs,
        line=LINE,
        budget=10,
        date=DATE,
        stamp=stamp(cosine_weight=0.9, key_point_weight=0.1),
    )

    assert named(under_cosine) != named(under_both)


def test_the_order_ignores_which_side_of_a_pair_was_named_first() -> None:
    """One pair has one sort key, whichever way round a caller built it.

    The two items are symmetric, so a key that read them in argument order would
    put one pair in two places in the sequence and the budget would then cut a
    pair it had already taken.
    """
    left_first = scored("world-01", "world-02", score=0.90)
    right_first = scored("world-02", "world-01", score=0.90)

    assert draw_order(left_first, date=DATE, stamp=stamp()) == draw_order(
        right_first, date=DATE, stamp=stamp()
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


# --- the legs ----------------------------------------------------------------


@pytest.mark.parametrize("count", [200, 199])
def test_the_shards_are_even_to_within_one(count: int) -> None:
    """Index modulo the leg count, so a draw the budget cut short still spreads.

    A contiguous block would fill the first leg and starve the last on any day
    the cap bit, and the leg that finished first would be the one with nothing
    to do.
    """
    pairs = [scored(f"left-{n:03d}", f"right-{n:03d}", score=0.90) for n in range(count)]

    counts = Counter(shard for shard, _ in assign_shards(pairs, shards=4))

    assert sorted(counts) == [0, 1, 2, 3], "every leg gets work"
    assert max(counts.values()) - min(counts.values()) <= 1


# --- the stage ---------------------------------------------------------------


def a_published_day(root: Path) -> None:
    """One day on disk with its manifest: six stories, five mastheads, one shared headline.

    Built rather than read off the archive, because the case that matters most
    here is two outlets running the same headline - which scores 1.0 by a rule
    the weighted sum never reaches, and which the contract refuses a row for
    unless the `headline` column agrees with the score.
    """
    items = [
        item("world-01", outlet="The Wire", title="Floods reach the delta"),
        item("world-02", outlet="The Paper", title="Floods reach the delta"),
        item("world-03", outlet="The Herald"),
        item("world-04", outlet="The Gazette"),
        item("business-01", outlet="The Ledger"),
        item("business-02", outlet="The Wire"),
    ]
    angles = [0.0, 0.6, 1.2, 4.0, 12.0, 30.0]
    vectors = block({one.item_id: unit(angle) for one, angle in zip(items, angles, strict=True)})
    manifest = RunManifest.from_json(read_text(MANIFEST_FIXTURE))
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[
            DigestRunRef(
                n=run.n,
                at=run.started_at,
                items_added=sum(1 for one in items if one.introduced_by_run == run.n),
            )
            for run in manifest.runs
        ],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(Counter(one.vertical for one in items).items())
        ],
        items=items,
        embeddings=vectors,
    )
    target = assemble.day_dir(root, DATE)
    assemble.write_atomic(target / "digest.json", day.to_json())
    assemble.write_atomic(target / "run.json", manifest.to_json())


def test_the_draw_round_trips_through_the_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every row the stage writes is one the contract will read back and accept.

    The contract recomputes the pair key from the row's own two addresses and
    recomputes the composite from the row's own terms and weights, and it does
    both at WRITE time - so a stage that got either wrong would throw away a
    day of model calls that had already been paid for. Reading the file back
    through `from_csv_row` is what proves the columns survive the round trip as
    well as the constructor.

    It also fixes the two shapes a reader downstream depends on: nothing is
    judged yet, and the shared headline arrives with `headline` true and a
    composite of 1.0 rather than the weighted sum.
    """
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    out_dir = tmp_path / "judge"

    drawn = stage_judge_draw(
        DATE, settings=config.load(CONFIG_DIR), digest_root=digest_root, out_dir=out_dir
    )

    written = (out_dir / DATE / DRAW_FILENAME).read_text(encoding="utf-8")
    rows = [
        StorySimilarityPair.from_csv_row(row) for row in csv.DictReader(written.splitlines())
    ]
    assert rows, "the day holds pairs inside the band, so the draw is not empty"
    assert len(rows) == len(drawn.taken) <= drawn.pairs_in_band
    assert all(row.date == DATE and row.run_id == "2026-08-21-2" for row in rows), (
        "a row names the run whose day it read"
    )
    assert all(row.left_url_key < row.right_url_key for row in rows)
    assert not any(
        row.verdict or row.verdict_swapped or row.usable or row.judge_model for row in rows
    ), "this step judges nothing"

    headline = [row for row in rows if row.headline]
    assert len(headline) == 1, "one pair of mastheads ran the same headline"
    assert headline[0].composite_score == 1.0


def test_the_draw_samples_the_config_band_and_never_the_line_a_fit_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The population the record is folded from is the config band, whatever the line.

    Verified in the stage as it stands: `in_band` is handed `tuning.band_low` and
    `tuning.band_high` off the config file, and no fitted value reaches it. This
    is the regression guard against the tidy-up that creates the feedback loop -
    wiring `applied.effective_same_story` into the draw the way `assemble` reads
    it. A band that opened at the applied line would narrow every time the line
    rose, and the next fit would then be reading a record it had shaped itself.

    Driven by moving the committed floor the whole width of the band, which is
    the furthest a fit could ever carry it.
    """
    digest_root = tmp_path / "digest"
    a_published_day(digest_root)
    monkeypatch.setattr(common, "PUBLIC_ROOT", digest_root)
    settings = config.load(CONFIG_DIR)
    same_story = settings.app.assemble.same_story
    tuning = same_story.judging_knobs()

    def drawn_with(floor: float, out: str) -> Draw:
        assemble_block = settings.app.assemble.model_copy(
            update={"same_story": same_story.model_copy(update={"floor_min": floor})}
        )
        driven = replace(settings, app=settings.app.model_copy(update={"assemble": assemble_block}))
        return stage_judge_draw(
            DATE, settings=driven, digest_root=digest_root, out_dir=tmp_path / out
        )

    at_the_bottom = drawn_with(tuning.band_low, "bottom")
    at_the_top = drawn_with(tuning.band_high, "top")

    assert at_the_bottom.pairs_in_band > 0, "the day holds pairs inside the band"
    assert at_the_top.pairs_in_band == at_the_bottom.pairs_in_band, (
        "the band is the config's and the line does not narrow it"
    )
    assert sorted(named(at_the_top)) == sorted(named(at_the_bottom))


def test_a_day_that_is_not_on_disk_writes_an_empty_draw(tmp_path: Path) -> None:
    """A missing day is nothing to judge rather than a run to fail.

    The header still goes down, so the leg that opens the file reads an empty
    draw instead of dying on a file that is not there - which on a four-leg
    matrix is four failed jobs for one day nobody published.
    """
    out_dir = tmp_path / "judge"

    drawn = stage_judge_draw(
        DATE,
        settings=config.load(CONFIG_DIR),
        digest_root=tmp_path / "nothing-here",
        out_dir=out_dir,
    )

    written = (out_dir / DATE / DRAW_FILENAME).read_text(encoding="utf-8")
    assert drawn == Draw(taken=[], pairs_in_band=0)
    assert written.splitlines() == [",".join(StorySimilarityPair.csv_columns())]


def test_the_stamp_is_the_committed_config_and_the_encoder_that_ran() -> None:
    """A row records the ruler it was scored under, read off the shipped config.

    A stamp taken from anywhere else would describe a scorer nobody ran, and
    the record would then reinterpret a year of counts under weights that never
    produced them.
    """
    settings = config.load(CONFIG_DIR)

    taken = scorer_inputs(settings)

    assert taken.scorer_model == EMBEDDER_ID
    assert taken.cosine_weight == settings.app.assemble.same_story.cosine_weight
    assert taken.key_point_weight == settings.app.assemble.same_story.key_point_weight
