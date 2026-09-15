"""What must an article, a summary and an eval row carry, and what may they never carry?"""

from __future__ import annotations

import json

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text

from idhazh.contracts import derive_url_key
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import FailureCode, ItemHealthRow
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.visual_decision import VisualDecision

from ._fixtures import (
    mutate,
)

pytestmark = pytest.mark.contract


def test_url_key_is_rebuilt_not_trusted() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "article" / "ok.json",
        canonical_url="https://blog.example-lab.org/2026/08/other",
    )
    with pytest.raises(ValueError, match="url_key"):
        Article.model_validate(payload)
    payload["url_key"] = derive_url_key(payload["canonical_url"])
    assert Article.model_validate(payload).url_key == derive_url_key(payload["canonical_url"])


def test_an_ok_article_must_carry_text() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "ok.json", text=None)
    with pytest.raises(ValueError, match="title and text"):
        Article.model_validate(payload)


def test_a_failed_article_must_record_why() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "fetch-failed.json", failure_detail=None)
    with pytest.raises(ValueError, match="must record why"):
        Article.model_validate(payload)


def test_truncation_is_flagged_and_located_together() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "truncated.json", truncated_at_tokens=None)
    with pytest.raises(ValueError, match="truncated"):
        Article.model_validate(payload)


def test_an_item_decided_to_nothing_carries_no_spec() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json", spec="anything")
    with pytest.raises(ValueError, match="no spec"):
        VisualDecision.model_validate(payload)


def test_a_day_still_carrying_the_retired_drawing_path_reads() -> None:
    """The read-side migration `path` owes, proved by putting the key back.

    Every one of the 24 committed days names a `.svg` on every rendered visual,
    and none of them is ever rewritten. `Model` forbids a key it does not
    declare, so without the named pop those days stop parsing the day this
    lands - `validate-days` red, the build red, the release blocked. Driven by
    adding the key to a fixture rather than by counting how many committed days
    still carry it, because a count of a growing collection is a check timed to
    go red on a date nobody chose (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    carried = 0
    for item in payload["items"]:
        if item["visual"] is not None:
            item["visual"]["path"] = "digest/2026/08/21/ai-01.svg"
            carried += 1
    assert carried, "the fixture stopped carrying a visual, so this proves nothing"

    day = DigestDay.model_validate(payload)

    assert [item.visual.data_path for item in day.items if item.visual] == [
        "digest/2026/08/21/ai-01.json"
    ] * carried
    assert "path" not in day.items[0].visual.model_dump() if day.items[0].visual else True


def test_a_visual_carrying_a_data_path_must_have_rendered() -> None:
    """One-way, and this is the direction that can hold.

    The other direction cannot: 495 visuals across the 24 frozen days are
    `rendered` and carry no data file, permanently, because back-filling one
    would mean re-fetching 495 source pages that have since moved. So what is
    asserted is that a path never appears without the state that produced it.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in payload["items"]:
        if item["visual"] is not None:
            item["visual"]["state"] = "absent"

    with pytest.raises(ValueError, match="data path"):
        DigestDay.model_validate(payload)


def test_hhem_delta_is_rebuilt_not_trusted() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json", hhem_delta=0.9)
    with pytest.raises(ValueError, match="hhem_delta"):
        EvalRow.model_validate(payload)


#: The four columns the owner refused to delete on 2026-08-30, and the two things
#: each description has to carry. Every one of them is a cell a reader cannot
#: interpret from its value: a constant that looks like a count, a derived cell
#: that looks like a measurement, a flag that changed meaning on a fixed date, and
#: a timing that is not on the path it sits beside. Each entry is
#: (model, field, unit phrases, reader phrases) and one phrase from each group has
#: to appear, so a later edit cannot quietly strip the unit or the reader back out.
KEPT_COLUMNS: tuple[tuple[type[Contract], str, tuple[str, ...], tuple[str, ...]], ...] = (
    (Summary, "attempt", ("A count, not a duration",), ("Nothing reads it",)),
    (EvalRow, "score_ms", ("Milliseconds",), ("observability.sample_rate",)),
    (EvalRow, "hhem_delta", ("0-to-1 faithfulness scale",), ("no band reads it",)),
    (EvalRow, "truncation_flagged", ("True when",), ("model-work.ts",)),
)

@pytest.mark.parametrize(("model", "field", "units", "readers"), KEPT_COLUMNS)
def test_a_kept_column_says_what_it_holds_and_who_reads_it(
    model: type[Contract], field: str, units: tuple[str, ...], readers: tuple[str, ...]
) -> None:
    """A column kept for history still has to explain itself.

    The owner asked what two of these four meant, which is what a description
    that is not doing its job looks like. A test that only checks the field
    exists would have passed on every one of them.
    """
    described = model.model_fields[field].description or ""
    assert described.strip(), f"{model.__name__}.{field} carries no description"
    assert any(unit in described for unit in units), (
        f"{model.__name__}.{field} does not say what its value is measured in"
    )
    assert any(reader in described for reader in readers), (
        f"{model.__name__}.{field} does not say who reads it"
    )


def test_every_kept_column_reaches_its_generated_schema() -> None:
    """A description a reader never sees is a comment. These are read by people."""
    for model, field, units, readers in KEPT_COLUMNS:
        schema = json.loads(read_text(SCHEMAS_DIR / f"{model.__schema_stem__}.schema.json"))
        described = schema["properties"][field]["description"]
        assert any(unit in described for unit in units)
        assert any(reader in described for reader in readers)


def test_the_model_cannot_have_read_more_words_than_the_article_holds() -> None:
    """The impossible direction, refused.

    610 of 2,346 committed rows carried a seen count LARGER than the full
    count, because the two cells were filled by two different counters over the
    same truncated string. Nothing compared them, so nothing could see it.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1874,
    )
    with pytest.raises(ValueError, match="not more"):
        EvalRow.model_validate(payload)


def test_an_article_shorter_than_the_cap_reads_the_same_length_twice() -> None:
    """Equal is the normal case, not an error: nothing was cut."""
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1875,
    )
    assert EvalRow.model_validate(payload).source_word_count == 1875


def test_an_eval_row_may_not_know_how_long_its_article_was() -> None:
    """Null and not zero (section 11).

    A row written before 2026-08-27 whose article was truncated has no full
    length anywhere: extract discarded the pre-cap body. Zero would claim the
    article was empty.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=None,
    )
    row = EvalRow.model_validate(payload)
    assert row.source_word_count is None
    assert row.source_seen_word_count == 1875, "the seen count is still a measurement"


def test_an_ok_item_health_row_carries_only_recorded_extract_signals() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.UNKNOWN,
        detail="unclassified failure",
    )
    with pytest.raises(ValueError, match="recorded extract signal"):
        ItemHealthRow.model_validate(payload)

    signalled = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.NOT_PROSE,
    )
    assert ItemHealthRow.model_validate(signalled).code is FailureCode.NOT_PROSE


def test_item_health_failure_code_must_belong_to_stage() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.HTTP_CLIENT_ERROR,
    )
    with pytest.raises(ValueError, match="does not belong"):
        ItemHealthRow.model_validate(payload)


def test_item_health_http_status_belongs_only_to_fetch() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json", http_status=200)
    with pytest.raises(ValueError, match="http_status"):
        ItemHealthRow.model_validate(payload)


def test_a_failed_item_health_row_may_say_why_and_an_ok_one_may_not() -> None:
    """`unknown` still demands a detail; every other failure may now carry one.

    The rule used to be that detail belonged to `unknown` alone, so a known
    failure recorded its code and threw the exception message away - and a
    person debugging it had to reproduce the failure to read the sentence the
    process already had in hand. An ok row still carries none: a row that
    succeeded has nothing to explain.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.UNKNOWN,
        detail="source shape did not match a known bucket",
    )
    assert ItemHealthRow.model_validate(payload).code is FailureCode.UNKNOWN

    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.UNKNOWN,
        detail=None,
    )
    with pytest.raises(ValueError, match="must carry detail"):
        ItemHealthRow.model_validate(payload)

    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "summarize-model-unreachable.json",
        detail="HTTPConnectionPool(host='127.0.0.1', port=8080): read timed out",
    )
    assert ItemHealthRow.model_validate(payload).detail is not None

    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        detail="nothing went wrong",
    )
    with pytest.raises(ValueError, match="carries no detail"):
        ItemHealthRow.model_validate(payload)


def test_a_retired_entry_must_carry_its_date() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["verticals"][2]["retired_on"] = None
    with pytest.raises(ValueError, match="retired_on"):
        Taxonomy.model_validate(payload)
