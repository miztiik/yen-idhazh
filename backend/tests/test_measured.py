"""The measured records carry their own provenance, so a value cannot outlive it."""

from __future__ import annotations

from datetime import date

import pytest

from idhazh.measured import EVERY_MEASURED, Measured

pytestmark = pytest.mark.contract


def test_every_measured_number_says_what_it_is_of_and_what_to_do() -> None:
    """A value with no method is an estimate, and Guardrail #10 refuses one a design leans on."""
    for record in EVERY_MEASURED:
        assert record.measures.strip(), f"{record} does not say what it measures"
        assert record.method.strip(), f"{record.measures} does not say how it was taken"
        assert record.when_it_fires.strip(), (
            f"{record.measures} does not say what to do when it fires - a guardrail that "
            "only ever stops work gets raised by whoever finds it inconvenient"
        )


def test_every_number_says_why_it_is_a_number_at_all() -> None:
    """The field that keeps this module from becoming a comfortable home for the
    thing it exists to prevent.

    A threshold is a proxy for a property nobody stated, and it fails in two
    directions that are both green. `page_weight.ceilings_bytes` did both before
    2026-09-10: four of its numbers fired on ordinary publishing and were raised
    each time, while `/console/` sat at 7.2 times the page it bounded for four
    days with the build green. A record that cannot say why a property check
    would not do instead should be a property check.
    """
    for record in EVERY_MEASURED:
        assert record.why_a_number.strip(), (
            f"{record.measures} does not say why it is a number rather than a property "
            "asserted directly - which is the question that deletes most thresholds"
        )


def test_a_measurement_is_dated_and_not_from_the_future() -> None:
    for record in EVERY_MEASURED:
        assert isinstance(record.taken_on, date)
        assert record.taken_on.year >= 2026, f"{record.measures} predates the project"


def test_a_judgement_says_so_rather_than_wearing_a_measurement_s_clothes() -> None:
    """The two are read differently: only one of them is evidence."""
    kinds = {record.kind for record in EVERY_MEASURED}
    assert kinds <= {"measurement", "judgement"}
    assert "judgement" in kinds, (
        "every record claims to be a measurement, which is how an unmeasured number "
        "comes to justify a design"
    )


def test_a_record_refuses_to_exist_without_its_provenance() -> None:
    for missing in ("measures", "method", "when_it_fires", "why_a_number"):
        fields = {
            "value": 1,
            "measures": "a thing",
            "taken_on": date(2026, 9, 10),
            "method": "counted it",
            "when_it_fires": "count it again",
            "why_a_number": "nothing else answers it",
        }
        fields[missing] = "   "
        with pytest.raises(ValueError, match=missing):
            Measured(**fields)  # type: ignore[arg-type]


def test_no_two_records_measure_the_same_thing() -> None:
    """Two records of one quantity is the drift this module exists to remove."""
    subjects = [record.measures for record in EVERY_MEASURED]
    assert len(subjects) == len(set(subjects))
