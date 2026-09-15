"""The fold key, and the four questions a folded month still has to answer.

The fold deletes the full-grain shard, so a term left out of the key is a
breakdown nobody can ever ask for again. That makes the interesting cases here
the negative ones: for each of the eight key terms, two attempts that differ in
that term ALONE must stay two groups. A key missing a term merges them, the
oracle reads one number where there were two, and no later code change can undo
it.

Every attempt below is built in this module (`CLAUDE.md` section 13). Nothing
walks `state/**`: the ledger this folds has no writer yet, and a test that read
committed data would cost more every month while proving less than a built
month, which can carry the bimodal group and the nothing-was-measured group a
real archive may never produce.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from statistics import fmean
from typing import Final

import pytest
from pydantic import ValidationError

from idhazh.contracts.item_health import ElementClass
from idhazh.contracts.visual import PlanDecision, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualState
from idhazh.contracts.visual_telemetry import (
    DISTRIBUTED_COLUMNS,
    DISTRIBUTION_FIGURES,
    FAMILY_OF,
    FOLD_KEY,
    ElementBand,
    ValidatorCheck,
    VisualAggregateRow,
    VisualAttemptRow,
    VisualFamily,
    band_of,
)
from idhazh.retention import fold_visual_month

pytestmark = pytest.mark.contract

DATE: Final = "2026-09-11"
RUN: Final = "2026-09-11-17421903"


def attempt(n: int, **overrides: object) -> VisualAttemptRow:
    """One built attempt. Every key term has a default, so a case names one term."""
    fields: dict[str, object] = {
        "version": VisualAttemptRow.schema_version(),
        "date": DATE,
        "run_id": RUN,
        "item_id": f"energy-{n:04d}",
        "decision": PlanDecision.NONE,
        "none_reason": NoneReason.MODEL_DECLINED,
        "rejection_reason": None,
        "potential_primary": ElementClass.CHARTABLE,
        "family": VisualFamily.CHART,
        "elements_found": 20,
        "downgrade_depth": 0,
        "marks": None,
        "state": VisualState.ABSENT,
    }
    fields.update(overrides)
    return VisualAttemptRow.model_validate(fields)


def published(n: int, **overrides: object) -> VisualAttemptRow:
    """An attempt a reader saw. The numerator of every keep rate here."""
    fields: dict[str, object] = {
        "decision": PlanDecision.VISUAL,
        "none_reason": None,
        "marks": 6,
        "state": VisualState.RENDERED,
    }
    fields.update(overrides)
    return attempt(n, **fields)


# --- The key is complete -----------------------------------------------------


#: One override per key term, each one a value the default is not. The term
#: named by the row is the ONLY thing that differs between the two attempts.
ONE_TERM_EACH: Final[tuple[tuple[str, dict[str, object]], ...]] = (
    ("date", {"date": "2026-09-12"}),
    ("decision", {"decision": PlanDecision.VISUAL, "none_reason": None}),
    ("none_reason", {"none_reason": NoneReason.NOT_REACHABLE}),
    ("rejection_reason", {"rejection_reason": ValidatorCheck.ENOUGH_DATA}),
    ("potential_primary", {"potential_primary": ElementClass.NARRATIVE}),
    ("family", {"family": VisualFamily.INFOGRAPHIC}),
    ("element_band", {"elements_found": 2}),
    ("downgrade_depth", {"downgrade_depth": 1}),
)


def test_every_key_term_is_named_once_and_the_row_agrees() -> None:
    """The declared key and the folded row cannot drift apart.

    The module raises at import if they do, so this says out loud what that
    refusal is for, and it is also where the count is written down: eight terms,
    four of cause and four of stratum.
    """
    assert len(FOLD_KEY) == 8
    assert set(FOLD_KEY) <= set(VisualAggregateRow.model_fields)
    assert [name for name, _ in ONE_TERM_EACH] == list(FOLD_KEY), (
        "a key term with no case below is a term nothing proves earns its place"
    )


@pytest.mark.parametrize(("term", "override"), ONE_TERM_EACH, ids=[n for n, _ in ONE_TERM_EACH])
def test_two_attempts_differing_in_one_key_term_stay_two_groups(
    term: str, override: dict[str, object]
) -> None:
    """The case that proves the key is wide enough, one term at a time.

    Merged, the two attempts would fold to one row and the difference between
    them would be gone from the archive - not hidden, gone, because the fold
    deletes the rows it read.
    """
    folded = fold_visual_month([attempt(1), attempt(2, **override)])

    assert len(folded) == 2, f"the fold ignored {term}"
    values = {getattr(row, term) for row in folded}
    assert len(values) == 2, f"{term} is in the key but both groups carry one value"


def test_two_identical_attempts_fold_to_one_group() -> None:
    """The other direction. A key nothing groups on is a key that folds nothing."""
    folded = fold_visual_month([attempt(1), attempt(2)])

    assert len(folded) == 1
    assert folded[0].attempts == 2


def test_the_fold_can_only_shrink_the_store() -> None:
    """A group holds at least one attempt, so the row count never rises.

    The pathological month - every attempt in a group of its own - is the case
    worth having, because that is the month where a wide key could have cost
    more than it bought. It folds to the same number of rows, each one narrower.
    """
    rows = [attempt(n, downgrade_depth=n) for n in range(12)]
    folded = fold_visual_month(rows)

    assert len(folded) == len(rows)
    assert all(row.attempts == 1 for row in folded)
    assert len(VisualAggregateRow.csv_columns()) < len(
        VisualAttemptRow.csv_columns()
    ) + len(DISTRIBUTED_COLUMNS) * len(DISTRIBUTION_FIGURES)


# --- The oracle: four questions a folded month still answers ------------------


def a_month() -> list[VisualAttemptRow]:
    """One built month, shaped so all four questions have a non-trivial answer.

    Not a realistic month and not meant to be: every group is small enough to
    read, and the element counts in the last block are deliberately bimodal so
    the fourth question has something a mean would hide.
    """
    rows: list[VisualAttemptRow] = []
    counter = 0

    def take() -> int:
        nonlocal counter
        counter += 1
        return counter

    # The model declined: the common refusal, on narrative articles.
    rows += [
        attempt(
            take(),
            none_reason=NoneReason.MODEL_DECLINED,
            potential_primary=ElementClass.NARRATIVE,
            family=None,
            downgrade_depth=None,
            elements_found=1,
        )
        for _ in range(30)
    ]
    # The validator refused on too few marks, twice as often as on units.
    rows += [
        attempt(
            take(),
            none_reason=NoneReason.VALIDATION_FAILED,
            rejection_reason=ValidatorCheck.ENOUGH_DATA,
            potential_primary=ElementClass.UNCLASSIFIED,
            elements_found=5,
            downgrade_depth=2,
        )
        for _ in range(20)
    ]
    rows += [
        attempt(
            take(),
            none_reason=NoneReason.VALIDATION_FAILED,
            rejection_reason=ValidatorCheck.UNITS_CONVERTIBLE,
            potential_primary=ElementClass.UNCLASSIFIED,
            elements_found=5,
            downgrade_depth=1,
        )
        for _ in range(10)
    ]
    # Published at depth 0: eight of ten reached a reader.
    rows += [published(take(), downgrade_depth=0, elements_found=20) for _ in range(8)]
    rows += [
        published(take(), downgrade_depth=0, elements_found=20, state=VisualState.RENDER_FAILED)
        for _ in range(2)
    ]
    # Published at depth 1: two of eight reached a reader, and the element counts
    # split into two clumps at either end of the same band.
    for index in range(8):
        rows.append(
            published(
                take(),
                downgrade_depth=1,
                elements_found=16 if index < 4 else 200,
                state=VisualState.RENDERED if index < 2 else VisualState.RENDER_FAILED,
            )
        )
    return rows


def test_question_one_which_gate_refused_most() -> None:
    """Sum `attempts` by `none_reason` - the breakdown a fold on date alone loses."""
    by_gate = Counter[NoneReason]()
    for row in fold_visual_month(a_month()):
        if row.none_reason is not None:
            by_gate[row.none_reason] += row.attempts

    assert by_gate.most_common(1)[0] == (NoneReason.MODEL_DECLINED, 30)
    assert by_gate[NoneReason.VALIDATION_FAILED] == 30
    assert set(by_gate) == {NoneReason.MODEL_DECLINED, NoneReason.VALIDATION_FAILED}

    by_check = Counter[ValidatorCheck]()
    for row in fold_visual_month(a_month()):
        if row.rejection_reason is not None:
            by_check[row.rejection_reason] += row.attempts
    assert by_check[ValidatorCheck.ENOUGH_DATA] == 20
    assert by_check[ValidatorCheck.UNITS_CONVERTIBLE] == 10


def test_question_two_how_the_keep_rate_moved_with_downgrade_depth() -> None:
    """Two counts per depth, so the rate is division rather than an average of averages.

    The denominator is the attempts AT that depth, refused ones included, which
    is why the depth is recorded on a refusal and not only on a publication.
    """
    attempts = Counter[int]()
    kept = Counter[int]()
    for row in fold_visual_month(a_month()):
        if row.downgrade_depth is None:
            continue
        attempts[row.downgrade_depth] += row.attempts
        kept[row.downgrade_depth] += row.published

    assert kept[0] / attempts[0] == pytest.approx(8 / 10)
    assert kept[1] / attempts[1] == pytest.approx(2 / 18)
    assert kept[2] / attempts[2] == 0.0
    assert attempts[2] == 20, "a depth that published nothing still has a denominator"


def test_question_three_how_the_classes_differ() -> None:
    """The stratum survives: class, family and element band are all still askable."""
    strata: dict[tuple[ElementClass | None, VisualFamily | None, ElementBand | None], int] = {}
    for row in fold_visual_month(a_month()):
        key = (row.potential_primary, row.family, row.element_band)
        strata[key] = strata.get(key, 0) + row.attempts

    assert strata[(ElementClass.NARRATIVE, None, ElementBand.FEW)] == 30
    assert strata[(ElementClass.UNCLASSIFIED, VisualFamily.CHART, ElementBand.SOME)] == 30
    assert strata[(ElementClass.CHARTABLE, VisualFamily.CHART, ElementBand.RICH)] == 18

    chartable = [
        row for row in fold_visual_month(a_month()) if row.potential_primary is ElementClass.CHARTABLE
    ]
    assert sum(row.published for row in chartable) == 10
    assert sum(row.attempts for row in chartable) == 18


def test_question_four_how_the_distribution_is_shaped() -> None:
    """The quartiles keep a bimodal group; a mean would report an empty middle.

    Eight attempts at 16 and 200 elements. The quartiles are 16, 16 and 200, so
    a reader sees two clumps. The mean is 108, which no attempt had and which
    sits in the gap between them.
    """
    group = next(
        row
        for row in fold_visual_month(a_month())
        if row.decision is PlanDecision.VISUAL and row.downgrade_depth == 1
    )

    assert (group.elements_min, group.elements_p25) == (16, 16)
    assert (group.elements_p50, group.elements_p75, group.elements_max) == (16, 200, 200)

    hidden = fmean([16] * 4 + [200] * 4)
    assert hidden == 108.0
    assert group.elements_p50 is not None and group.elements_p75 is not None
    assert group.elements_p50 < hidden < group.elements_p75
    assert hidden not in {16, 200}, "the mean is a value no attempt ever had"


def test_the_mark_distribution_survives_for_the_ladder_that_reads_it() -> None:
    """Each rung of the downgrade ladder reads a percentile of published mark counts.

    Folded away, that population is gone and every floor below it is a floor
    computed from nothing - which the ladder reads as a refusal, so the ladder
    would silently stop working rather than fail.
    """
    folded = fold_visual_month(a_month())
    drawn = [row for row in folded if row.marks_n]

    assert drawn, "the fold lost every mark count"
    assert all(row.decision is PlanDecision.VISUAL for row in drawn)
    assert all(row.marks_p50 == 6 for row in drawn)
    assert all(row.marks_n == row.attempts for row in drawn)


# --- The shapes --------------------------------------------------------------


def test_a_group_that_measured_nothing_carries_no_spread() -> None:
    """Empty is not zero. A group nobody measured says so rather than reporting 0."""
    folded = fold_visual_month([attempt(1, elements_found=None, marks=None)])

    row = folded[0]
    assert row.element_band is None, "an unmeasured count is not the `none` band"
    assert row.elements_n == 0
    assert all(getattr(row, f"elements_{name}") is None for name in DISTRIBUTION_FIGURES[1:])
    assert row.marks_n == 0


def test_the_band_boundaries_are_the_ones_the_measurement_chose() -> None:
    """Powers of two at 4, 8 and 16, which the committed quartiles landed on."""
    assert [band_of(n) for n in (0, 1, 3)] == [
        ElementBand.NONE,
        ElementBand.FEW,
        ElementBand.FEW,
    ]
    assert [band_of(n) for n in (4, 7)] == [ElementBand.SOME, ElementBand.SOME]
    assert [band_of(n) for n in (8, 15)] == [ElementBand.MANY, ElementBand.MANY]
    assert [band_of(n) for n in (16, 247)] == [ElementBand.RICH, ElementBand.RICH]
    assert band_of(None) is None


def test_every_declarable_type_belongs_to_exactly_one_family() -> None:
    """A type in no family would be folded into a group nobody chose."""
    assert set(FAMILY_OF) == set(VisualType)
    assert set(FAMILY_OF.values()) == set(VisualFamily)


def test_an_attempt_that_proposed_nothing_drew_nothing() -> None:
    for override in ({"state": VisualState.RENDERED}, {"marks": 4}):
        with pytest.raises(ValidationError):
            attempt(1, **override)


def test_an_attempt_that_proposed_a_picture_names_no_refusing_gate() -> None:
    with pytest.raises(ValidationError):
        published(1, none_reason=NoneReason.MODEL_DECLINED)


def test_a_folded_row_refuses_a_spread_that_runs_backwards() -> None:
    good = fold_visual_month([published(1, elements_found=20)])[0].model_dump(mode="json")
    assert VisualAggregateRow.model_validate(good) is not None

    with pytest.raises(ValidationError):
        VisualAggregateRow.model_validate({**good, "elements_p25": 99})
    with pytest.raises(ValidationError):
        VisualAggregateRow.model_validate({**good, "published": good["attempts"] + 1})
    with pytest.raises(ValidationError):
        VisualAggregateRow.model_validate({**good, "elements_n": 0})


def test_both_rows_survive_a_csv_round_trip() -> None:
    """An empty cell reads back as absent, never as the empty string."""
    rows: list[VisualAttemptRow | VisualAggregateRow] = [
        attempt(1, elements_found=None, marks=None),
        published(2),
        *fold_visual_month(a_month())[:4],
    ]
    for row in rows:
        model = type(row)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=model.csv_columns(), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row.csv_row())
        read = list(csv.DictReader(io.StringIO(buffer.getvalue())))
        assert model.from_csv_row(read[0]) == row
