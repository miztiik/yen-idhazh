"""The measured records carry their own provenance, so a value cannot outlive it."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import config
from idhazh.measured import (
    EVERY_MEASURED,
    SIZED_BY_A_READING_HERE,
    Measured,
    TokenizerMeasured,
    readings_awaiting_a_retake,
    refuse_a_reading_taken_against_other_weights,
)

pytestmark = pytest.mark.contract


def configured_weights() -> str:
    """The sha256 of the weights `config/` currently names for summarizing."""
    declared = config.load(CONFIG_DIR).models.summarize.sha256
    assert declared is not None, "the configured summarizer names no weights digest"
    return declared


def a_tokenizer_reading(subject: str) -> TokenizerMeasured:
    """A built reading, so the gate is never driven off the committed records."""
    return TokenizerMeasured(
        value=1234,
        measures="a built reading that exists only inside this test",
        taken_on=date(2026, 9, 13),
        subject=subject,
        method="tokenized a built string",
        when_it_fires="tokenize it again",
        why_a_number="nothing else answers it",
    )


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


def test_every_tokenizer_reading_names_the_weights_the_config_still_names() -> None:
    """The whole row in one line: a token count belongs to the vocabulary that counted it.

    There is no case here for a tokenizer reading that omits its subject, and no
    case for a timing record that carries one. `TokenizerMeasured.subject` has no
    default and `Measured` has no such field, so `mypy backend` refuses both and
    a runtime test would only repeat it (Fowler, 2026-09-13).
    """
    pinned = [record for record in EVERY_MEASURED if isinstance(record, TokenizerMeasured)]
    assert len(pinned) == 6, (
        "six of the eight records are token counts. If a record moved between the two "
        "classes, say which and why here; if a reading was added, raise this count"
    )

    refuse_a_reading_taken_against_other_weights(
        configured_sha256=configured_weights(), records=EVERY_MEASURED
    )


def test_a_reading_taken_against_other_weights_is_refused_and_names_both_digests() -> None:
    """The case that proves the gate can fail for the reason it exists.

    Driven from a built record rather than from the committed ones, so it stays
    true on the day somebody retakes a reading (`CLAUDE.md` section 13).
    """
    configured = configured_weights()
    stale = "f" * 64
    assert stale != configured

    with pytest.raises(ValueError) as refusal:
        refuse_a_reading_taken_against_other_weights(
            configured_sha256=configured, records=[a_tokenizer_reading(stale)]
        )

    said = str(refusal.value)
    assert configured in said, "the refusal does not say which weights are configured"
    assert stale in said, "the refusal does not say which weights the reading was taken against"


def test_the_refusal_hands_over_the_three_sites_the_gate_cannot_reach() -> None:
    """A model swap makes all three stale at the same instant, so they ride on the refusal.

    The person swapping a model is reading `config/idhazh.json` and a failing
    gate, not `measured.py`, and the refusal is the one moment they are provably
    looking (Fowler, 2026-09-13).
    """
    with pytest.raises(ValueError) as refusal:
        refuse_a_reading_taken_against_other_weights(
            configured_sha256="a" * 64, records=[a_tokenizer_reading("b" * 64)]
        )

    said = str(refusal.value)
    for site in SIZED_BY_A_READING_HERE:
        assert site.module in said
        assert site.constant in said
        assert site.reading_name in said


def test_the_refusal_lists_only_the_sites_that_are_actually_stale() -> None:
    """The other half of the same rule, and the half row #13b turns green one at a time.

    Driven off a digest a committed reading already names, so it keeps working
    when a retake lands. A refusal that listed all three whatever their subjects
    said would be a refusal that stopped meaning anything after the first retake.
    """
    current = SIZED_BY_A_READING_HERE[0].reading.subject
    still_stale = readings_awaiting_a_retake(configured_sha256=current)
    assert len(still_stale) < len(SIZED_BY_A_READING_HERE) or not still_stale

    with pytest.raises(ValueError) as refusal:
        refuse_a_reading_taken_against_other_weights(
            configured_sha256=current, records=[a_tokenizer_reading("b" * 64)]
        )

    said = str(refusal.value)
    assert f"{len(still_stale)} of {len(SIZED_BY_A_READING_HERE)} constants" in said


def test_each_site_the_gate_names_still_exists_and_still_declares_its_constant() -> None:
    """A list of what to retake is worth nothing once a rename has made it a lie."""
    for site in SIZED_BY_A_READING_HERE:
        module = REPO_ROOT / site.module
        assert module.is_file(), f"{site.module} has moved and the list now points at nothing"
        assert site.constant in read_text(module), (
            f"{site.module} no longer declares {site.constant}"
        )


def test_a_constant_sized_by_a_reading_is_not_also_a_record_in_the_walked_set() -> None:
    """Two homes for one number is the drift this module exists to remove.

    These three are deliberately out of `EVERY_MEASURED`: every one of them names
    the retired 8B, so a gate that walked them would be red on every commit until
    row #13b retakes them, and a gate that is red on a state nobody has fixed is a
    gate people learn to scroll past (`CLAUDE.md` section 13).
    """
    walked = {record.measures for record in EVERY_MEASURED}
    for site in SIZED_BY_A_READING_HERE:
        assert site.reading.measures not in walked, (
            f"{site.reading_name} is in both EVERY_MEASURED and SIZED_BY_A_READING_HERE, so "
            "the gate would refuse every commit until it is retaken"
        )


def test_a_timing_record_is_not_filtered_into_the_gate() -> None:
    """Only a token count is pinned - a second and a resident set belong to the box.

    Carmack, 2026-09-13. A plain `Measured` travels through the gate untouched
    whatever the configured digest is, which is what lets the site growth rate
    and the warning-days judgement sit in the same tuple.
    """
    timing = Measured(
        value=1,
        measures="a built timing that exists only inside this test",
        taken_on=date(2026, 9, 13),
        method="read a clock",
        when_it_fires="read it again",
        why_a_number="nothing else answers it",
    )
    refuse_a_reading_taken_against_other_weights(configured_sha256="c" * 64, records=[timing])
