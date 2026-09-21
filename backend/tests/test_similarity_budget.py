"""Does the content-similarity judge refuse a night it could not finish?"""

from __future__ import annotations

import math

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council.deadline import compute_shard_deadline
from idhazh.similarity import budget

#: A config-contract rule wearing a judge's arithmetic: every case here turns on
#: what `config/idhazh.json` says, so a change to either block has to run it.
pytestmark = pytest.mark.contract


def _with(pair_budget: int, **council: int) -> AppConfig:
    """A config that draws `pair_budget` pairs, against whatever clocks are named."""
    return AppConfig.model_validate(
        {
            "council": council,
            "assemble": {"same_story": {"adaptive_dedup_threshold": {"pair_budget": pair_budget}}},
        }
    )


def _the_widest_draw_that_fits(council: CouncilConfig) -> int:
    """How many pairs a night may draw and still finish, derived rather than written.

    Driven from the council's own window function and the judge's own cost, so a
    later reading of either moves this with it instead of freezing the numbers
    these tests were written against.
    """
    window = compute_shard_deadline(council, started=0.0)
    return math.floor(window / budget.SECONDS_A_JUDGED_PAIR) * council.shards


def test_the_committed_draw_finishes_inside_the_window_the_council_leaves() -> None:
    """The shipped config has to pass its own tenant's check, or no night runs at all.

    Passing is the call returning at all: the check refuses by raising, so there
    is nothing else for it to hand back.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))

    budget.refuse_a_night_this_tenant_cannot_finish(committed)


def test_a_draw_one_pair_too_wide_is_refused_and_a_longer_night_takes_it() -> None:
    """A unit GitHub kills uploads nothing, so the day's whole draw is lost.

    The bite proof is the trade the refusal names: raise the timeout and the
    same budget starts passing. Without that second half a check that refused
    everything would look identical to one that works.
    """
    council = CouncilConfig()
    fits = _the_widest_draw_that_fits(council)

    budget.refuse_a_night_this_tenant_cannot_finish(_with(fits))

    with pytest.raises(ValueError, match=f"pair_budget {fits + 1}"):
        budget.refuse_a_night_this_tenant_cannot_finish(_with(fits + 1))

    longer = _with(fits + 1, shard_timeout_minutes=council.shard_timeout_minutes + 10)
    budget.refuse_a_night_this_tenant_cannot_finish(longer)


def test_the_window_is_the_bound_less_what_the_venue_spends_around_the_work() -> None:
    """A draw sized against the whole bound is cut off at runtime.

    The venue spends the preamble before the judging process exists and keeps
    the reserve back for the records and the upload, so the pairs that fit the
    bound are more than the pairs that fit the work. This holds the check
    against the window a unit really has: the draw below fits the bound and is
    refused, which is the case that used to be accepted and then killed.
    """
    council = CouncilConfig()
    assert council.shard_preamble_minutes + council.shard_wrap_up_minutes > 0, (
        "with nothing spent around the work there is no gap for this test to be about"
    )
    whole_bound = council.shard_timeout_minutes * 60
    fits_the_bound = math.floor(whole_bound / budget.SECONDS_A_JUDGED_PAIR) * council.shards

    assert fits_the_bound > _the_widest_draw_that_fits(council)

    with pytest.raises(ValueError, match="s a unit has to work in"):
        budget.refuse_a_night_this_tenant_cannot_finish(_with(fits_the_bound))


def test_the_refusal_names_every_knob_a_person_could_move() -> None:
    """A bare comparison leaves an operator guessing which of three knobs to move.

    The arithmetic is in the message as well, because the number to move it by
    is the one thing a person reading a failed night cannot work out.
    """
    council = CouncilConfig()
    too_wide = _the_widest_draw_that_fits(council) + 1

    with pytest.raises(ValueError) as refused:
        budget.refuse_a_night_this_tenant_cannot_finish(_with(too_wide))

    said = str(refused.value)
    for knob in ("pair_budget", "council.shards", "shard_preamble_minutes"):
        assert knob in said, f"the refusal has to name {knob}"
    assert "6 h job ceiling" in said, "raising the timeout is bounded and the message says so"
    assert str(budget.SECONDS_A_JUDGED_PAIR) in said, "the cost is what the arithmetic turns on"


def test_a_config_with_no_judge_block_has_nothing_to_check() -> None:
    """This judge is optional, so its absence is a night the council runs without it."""
    without = AppConfig.model_validate({})

    assert without.assemble.same_story.adaptive_dedup_threshold is None
    budget.refuse_a_night_this_tenant_cannot_finish(without)
