"""What a story's age is worth at the hour the page is drawn.

Unit tier (CLAUDE.md section 13). The curve is arithmetic over two stamps and
three knobs, so every case here is built rather than read off a published day.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from idhazh.contracts.knobs.placement import PlacementConfig
from idhazh.placement import freshness_multiplier

NOW = "2026-09-16T12:00:00Z"
_STAMP = "%Y-%m-%dT%H:%M:%SZ"


def at(hours_ago: float) -> str:
    """A stamp that many hours before `NOW`, to the second."""
    when = datetime.strptime(NOW, _STAMP).replace(tzinfo=UTC) - timedelta(hours=hours_ago)
    return when.strftime(_STAMP)


def test_a_story_inside_the_shoulder_is_worth_all_of_itself() -> None:
    """The shoulder is flat, so nothing in it is marked down at all.

    A story nothing has had time to answer yet should not lose score for being
    new, which is the whole reason the curve has an offset rather than starting
    to fall at minute one.
    """
    knobs = PlacementConfig()
    for hours in (0.0, 1.0, knobs.freshness_offset_hours):
        assert freshness_multiplier(at(hours), now=NOW, config=knobs) == 1.0


def test_a_story_a_scale_past_the_shoulder_is_worth_exactly_the_decay() -> None:
    """The derived width is what this checks, and it is the only way to check it.

    Sigma is never typed. It is worked out from the two numbers a person sets -
    at `freshness_scale_hours` past the shoulder a story is worth
    `freshness_decay_at_scale` - so the test that the derivation is right is
    that the curve passes through that point.
    """
    knobs = PlacementConfig()
    hours = knobs.freshness_offset_hours + knobs.freshness_scale_hours
    assert freshness_multiplier(at(hours), now=NOW, config=knobs) == pytest.approx(
        knobs.freshness_decay_at_scale
    )


@pytest.mark.parametrize(
    ("offset", "scale", "decay"),
    [(0.0, 6.0, 0.5), (12.0, 48.0, 0.1), (3.5, 9.25, 0.75)],
)
def test_the_curve_passes_through_the_point_whatever_the_knobs_say(
    offset: float, scale: float, decay: float
) -> None:
    """Three settings nobody ships, because a derivation right at one point only is not one."""
    knobs = PlacementConfig(
        freshness_offset_hours=offset,
        freshness_scale_hours=scale,
        freshness_decay_at_scale=decay,
    )
    assert freshness_multiplier(at(offset), now=NOW, config=knobs) == 1.0
    assert freshness_multiplier(at(offset + scale), now=NOW, config=knobs) == pytest.approx(decay)


def test_the_curve_only_ever_falls_and_never_reaches_zero() -> None:
    """It is a mark-down and never a cut-off. Nothing here drops a story."""
    knobs = PlacementConfig()
    readings = [
        freshness_multiplier(at(hours), now=NOW, config=knobs) for hours in range(0, 240, 6)
    ]
    assert readings[0] == 1.0
    assert all(later <= earlier for earlier, later in pairwise(readings))
    assert all(value > 0.0 for value in readings)


def test_a_decay_of_one_switches_the_whole_curve_off() -> None:
    """The revert path, and it is one edit to one line.

    A decay of exactly 1.0 has no sigma to derive - the arithmetic divides by
    the logarithm of 1, which is zero - so this is the off switch as well as the
    edge case, and both have to be the same answer.
    """
    off = PlacementConfig(freshness_decay_at_scale=1.0)
    for hours in (0.0, 6.0, 48.0, 720.0):
        assert freshness_multiplier(at(hours), now=NOW, config=off) == 1.0


def test_a_story_we_could_not_date_is_never_marked_down() -> None:
    """Marking one down would claim an age the payload never stated."""
    assert freshness_multiplier(None, now=NOW, config=PlacementConfig()) == 1.0


def test_a_story_the_feed_dated_in_the_future_is_worth_all_of_itself() -> None:
    """A clock ahead of ours is a feed's mistake, not a reason to reward it.

    The age is clamped at zero, so the best a future stamp can buy is the same
    1.0 a story published this minute gets.
    """
    knobs = PlacementConfig()
    assert freshness_multiplier(at(-6.0), now=NOW, config=knobs) == 1.0


def test_the_shape_is_a_bell_and_not_a_half_life() -> None:
    """What the curve buys over the exponential the plan-time bonus already uses.

    An exponential cuts hardest in its first hours, which is the opposite of
    what a digest wants. This one is flat through the shoulder and then falls,
    so at half the scale it has given up far less than half the distance to the
    decay point.
    """
    knobs = PlacementConfig()
    half_way = freshness_multiplier(
        at(knobs.freshness_offset_hours + knobs.freshness_scale_hours / 2),
        now=NOW,
        config=knobs,
    )
    exponential = math.sqrt(knobs.freshness_decay_at_scale)
    assert half_way > exponential
