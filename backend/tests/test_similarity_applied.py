"""Which merge line does a build use, and what happens when there is not one?

Every fitted row here is built in the test that uses it. The two integration
tests read the canary day, which is fixed in size and can carry a case the
archive has never produced (CLAUDE.md section 13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from test_same_story import block, item, unit
from test_similarity_fit import a_written_row

from idhazh import assemble, config, ledger
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.knobs.placement import SameStoryConfig, SimilarityThresholdConfig
from idhazh.contracts.run_manifest import RunManifest
from idhazh.similarity import applied
from utilities import build_canary_day

DATE: Final = "2026-09-18"

#: The feature switched on. Everything else is the committed default, so a test
#: that names a knob is naming the one thing it is about.
ON: Final = SimilarityThresholdConfig(enabled=True)


def a_fitted_row(
    *, date: str, applied_line: float, previous: float = 0.94
) -> FittedSimilarityThreshold:
    """One row a fit wrote, with a line on it and nothing holding it."""
    return a_written_row(
        date=date, proposed=applied_line, previous=previous, applied=applied_line
    )


def a_held_row(*, date: str, previous: float = 0.94) -> FittedSimilarityThreshold:
    """One row a gate held. It carries yesterday's line, which is not a choice."""
    return a_written_row(date=date, previous=previous)


def a_tree(tmp_path: Path, rows: list[FittedSimilarityThreshold]) -> Path:
    """The rows on disk, through the real appender, one day file each."""
    state = tmp_path / "state"
    for row in rows:
        ledger.append_fitted_thresholds(state, row.date, [row])
    return state


def test_the_flag_off_returns_the_same_object(tmp_path: Path) -> None:
    """A real fitted row on disk, and the block comes back unchanged.

    The same OBJECT, not an equal copy: with the flag off this row is off the
    path entirely, and a `model_copy` that produced an identical value would
    still mean the read ran.
    """
    state = a_tree(tmp_path, [a_fitted_row(date=DATE, applied_line=0.91)])
    committed = SameStoryConfig()

    assert (
        applied.effective_same_story(committed, state_dir=state, date=DATE) is committed
    )
    assert applied.applied_line(state, date=DATE, knobs=SimilarityThresholdConfig()) is None


def test_a_tree_with_no_fitted_rows_returns_the_config_value(tmp_path: Path) -> None:
    """A fresh clone has no record, and it publishes on the committed floor."""
    committed = SameStoryConfig()

    effective = applied.effective_same_story(
        committed, state_dir=tmp_path / "state", date=DATE, knobs=ON
    )

    assert effective is committed


def test_a_held_row_is_not_applied(tmp_path: Path) -> None:
    """A held row carries yesterday's line so the column is never empty.

    Reading it would make a line the evidence refused to move look like a line
    the evidence chose.
    """
    state = a_tree(tmp_path, [a_held_row(date=DATE)])

    assert applied.applied_line(state, date=DATE, knobs=ON) is None


def test_the_newest_applied_row_inside_the_window_wins(tmp_path: Path) -> None:
    """Three days, three lines, and the build uses the one written last."""
    state = a_tree(
        tmp_path,
        [
            a_fitted_row(date="2026-09-16", applied_line=0.930),
            a_fitted_row(date="2026-09-17", applied_line=0.935),
            a_fitted_row(date=DATE, applied_line=0.941),
        ],
    )

    assert applied.applied_line(state, date=DATE, knobs=ON) == pytest.approx(0.941)


def test_a_held_day_falls_back_to_the_newest_row_that_was_not_held(tmp_path: Path) -> None:
    """A gate today does not send the build back to the committed floor.

    The line it was already publishing at is the line it keeps, which is what
    makes a held day invisible to a reader rather than a visible regrouping.
    """
    state = a_tree(
        tmp_path,
        [a_fitted_row(date="2026-09-17", applied_line=0.935), a_held_row(date=DATE)],
    )

    assert applied.applied_line(state, date=DATE, knobs=ON) == pytest.approx(0.935)


def test_a_row_older_than_the_lookback_is_not_read(tmp_path: Path) -> None:
    """A gap longer than the lookback means the judge has been down that long.

    The committed config value is the honest answer then, and the lookback is
    what says how long "that long" is.
    """
    stale = "2026-09-09"
    state = a_tree(tmp_path, [a_fitted_row(date=stale, applied_line=0.91)])

    assert applied.applied_line(state, date=DATE, knobs=ON) is None
    assert applied.applied_line(
        state, date=DATE, knobs=SimilarityThresholdConfig(enabled=True, applied_lookback_days=30)
    ) == pytest.approx(0.91)


def test_the_fitted_line_reaches_the_block_the_grouping_pass_reads(tmp_path: Path) -> None:
    """One `model_copy`, and every other weight on the block survives it.

    `collapse_same_story` reads `floor_min`, `cosine_weight` and
    `key_point_weight` off the value it is handed. Replacing the floor may not
    disturb the other two, or the fitted line would arrive with the scoring
    changed underneath it.
    """
    state = a_tree(tmp_path, [a_fitted_row(date=DATE, applied_line=0.912)])
    committed = SameStoryConfig()

    effective = applied.effective_same_story(committed, state_dir=state, date=DATE, knobs=ON)

    assert effective.floor_min == pytest.approx(0.912)
    assert effective.cosine_weight == committed.cosine_weight
    assert effective.key_point_weight == committed.key_point_weight
    assert effective.adaptive_dedup_threshold == committed.adaptive_dedup_threshold


def test_the_knobs_come_from_the_block_when_the_caller_names_none(tmp_path: Path) -> None:
    """Production never passes `knobs`, so the nested block is the one source.

    The parameter exists so a test can drive this with a built block; a caller
    that omits it has to reach the same knobs the config file declares.
    """
    state = a_tree(tmp_path, [a_fitted_row(date=DATE, applied_line=0.912)])
    switched_on = SameStoryConfig(adaptive_dedup_threshold=ON)

    effective = applied.effective_same_story(switched_on, state_dir=state, date=DATE)

    assert effective.floor_min == pytest.approx(0.912)


def test_the_committed_config_ships_with_the_line_switched_off() -> None:
    """A fresh clone publishes exactly what it published before this feature existed.

    The flag is what makes row 9 revertible by a one-character config edit rather
    than by a revert commit, so it is read off the committed file and never off
    the model default.
    """
    settings = config.load(config.REPO_ROOT / "config")

    assert not settings.app.assemble.same_story.adaptive_dedup_threshold.enabled


def test_a_guard_clamp_still_counts_as_a_line_the_fit_applied(tmp_path: Path) -> None:
    """The guard holds the line where it was; it does not refuse to answer.

    `held_reason` is what says a fit did not run. A guarded row ran the fit and
    chose to move nothing, so the line on it is a choice and is applied.
    """
    guarded = a_written_row(date=DATE, proposed=0.99, previous=0.94, applied=0.94).model_copy(
        update={"clamp_kind": ClampKind.GUARD, "held_reason": HeldReason.NONE}
    )
    state = a_tree(tmp_path, [guarded])

    assert applied.applied_line(state, date=DATE, knobs=ON) == pytest.approx(0.94)


# --- the day the reader gets ---------------------------------------------------


def a_canary_day(target: Path) -> DigestDay:
    """The canary day, built into a directory the test owns.

    The day the browser suite draws rather than a second fixture that drifts from
    it. Fixed in size whatever the archive grows to (CLAUDE.md section 13).
    """
    settings = config.load(config.REPO_ROOT / "config")
    return build_canary_day.build(target, settings.app.evaluation, settings.app.visuals)


def _groups(day: DigestDay, same_story: SameStoryConfig) -> int:
    grouped = assemble.collapse_same_story(day.items, day.embeddings, same_story=same_story)
    return sum(1 for one in grouped if one.same_story_as is not None)


def test_the_applied_line_reaches_the_group_the_pass_forms(tmp_path: Path) -> None:
    """One pair at a known angle, two fitted lines, and the pair merges under one.

    The end of the chain: a row on disk, through `effective_same_story`, into the
    pass that decides what a reader sees folded behind what. A test that stopped
    at the returned block would prove the copy happened and nothing about whether
    the number arrives where it is read.

    Two vectors 12 degrees apart score about 0.978, so a line below that folds
    them and a line above leaves them as two stories. Built rather than drawn off
    the canary, because the angle is the whole experiment and the canary's own
    pairs are wherever its text put them.
    """
    both = ["world-01", "world-02"]
    items = [item(one, source=one) for one in both]
    vectors = block({both[0]: unit(0.0), both[1]: unit(12.0)})

    def merges(line: float) -> int:
        state = a_tree(tmp_path / f"at-{line}", [a_fitted_row(date=DATE, applied_line=line)])
        effective = applied.effective_same_story(
            SameStoryConfig(), state_dir=state, date=DATE, knobs=ON
        )
        assert effective.floor_min == pytest.approx(line)
        grouped = assemble.collapse_same_story(items, vectors, same_story=effective)
        return sum(1 for one in grouped if one.same_story_as is not None)

    assert merges(0.95) == 1, "a line below the pair's score folds it"
    assert merges(0.99) == 0, "a line above it leaves two stories"


def test_the_day_still_builds_when_the_fitted_tree_is_absent(tmp_path: Path) -> None:
    """No record, no judge, no run of this feature at all - and the day is unchanged.

    This is the property that makes row 9 safe to land: a fresh clone and every
    day published before the fit existed group at exactly the committed floor.
    """
    day = a_canary_day(tmp_path / "canary")
    committed = SameStoryConfig()

    effective = applied.effective_same_story(
        committed, state_dir=tmp_path / "nothing-here", date=build_canary_day.DATE, knobs=ON
    )

    assert effective is committed
    assert _groups(day, effective) == _groups(day, committed)


def test_the_manifest_records_the_line_the_day_was_grouped_at() -> None:
    """A committed run.json predates the column and reads back as unrecorded.

    Driven by removing nothing from a fixture: the committed shape simply has no
    such key, which is what every run.json in the published tree looks like. A
    test that counted how many committed manifests still lack the key would go
    red on the day the last one aged out (CLAUDE.md section 13).
    """
    older = RunManifest.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    )

    assert older.runs[-1].same_story_floor_applied is None

    grouped_at = older.model_copy(
        update={
            "runs": [
                *older.runs[:-1],
                older.runs[-1].model_copy(update={"same_story_floor_applied": 0.9375}),
            ]
        }
    )
    again = RunManifest.from_json(grouped_at.to_json())

    assert again.runs[-1].same_story_floor_applied == pytest.approx(0.9375)
