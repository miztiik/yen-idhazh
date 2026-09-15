"""Can a person read the writing a qualification run judged?"""

from __future__ import annotations

import pytest
import test_qualify as built
from pydantic import ValidationError

from idhazh.contracts.qualification import QualificationSamples, SummarySample

pytestmark = pytest.mark.contract


def sample(item: str, *, hhem: float, **overrides: object) -> SummarySample:
    fields: dict[str, object] = {
        "item_id": item,
        "title": "A headline the model wrote",
        "summary": "Two sentences of our own text. They are what the score judged.",
        "source_url": "https://example.org/a-story",
        "band_index": 1,
        "truncated": False,
        "hhem": hhem,
        "compression": 0.31,
    }
    fields.update(overrides)
    return SummarySample.model_validate(fields)


def a_file(*scores: float) -> QualificationSamples:
    return QualificationSamples(
        version=QualificationSamples.schema_version(),
        date="2026-09-15",
        shard=0,
        candidate=built.a_passing_shard().candidate,
        samples=[sample(f"ai-{index:02d}", hhem=score) for index, score in enumerate(scores)],
    )


def test_the_worst_summary_is_the_first_one_a_reviewer_meets() -> None:
    """Worst first is the whole reading order, so it is a rule and not a habit.

    A reviewer has minutes, not hours. The items worth their attention are the
    ones the scorer liked least, and a file that stored them in item order would
    make the producer's convenience the reviewer's problem.
    """
    with pytest.raises(ValidationError, match="worst-first"):
        a_file(0.9, 0.2, 0.5)

    assert [s.hhem for s in a_file(0.2, 0.5, 0.9).samples] == [0.2, 0.5, 0.9]


def test_an_item_carries_what_it_takes_to_judge_the_score_without_a_second_file() -> None:
    """A score is believable or not depending on what the model was shown.

    0.61 on a truncated long read and 0.61 on a short brief are different
    findings, so the length band and the truncation flag travel with the words
    rather than sitting in the shard a reviewer would have to join against.
    """
    one = a_file(0.61).samples[0]

    assert one.summary, "the writing under judgement"
    assert one.source_url, "the only way to check a claim"
    assert one.band_index == 1 and one.truncated is False
    assert one.hhem == 0.61 and one.compression >= 0.0


def test_a_dropped_title_is_recorded_as_absent_rather_than_as_empty_text() -> None:
    """`title_fell_back` on the score says it happened. This says what a reader sees."""
    assert sample("ai-01", hhem=0.5, title=None).title is None

    with pytest.raises(ValidationError):
        sample("ai-01", hhem=0.5, title="")


def test_the_verdict_cannot_read_the_writing_it_judged() -> None:
    """The Oracle. A gate that read this would grade text it also scored.

    `QualificationReport` is the document the gates are computed from, and it
    has no field of this shape and no field that could hold one. The samples
    ride in their own file and their own artifact, so making a gate read them
    would take a contract change somebody has to argue for.
    """
    from idhazh.contracts.qualification import QualificationReport

    fields = QualificationReport.model_fields
    assert "samples" not in fields
    for name, field in fields.items():
        assert "SummarySample" not in str(field.annotation), (
            f"the report reaches the writing through {name}"
        )
