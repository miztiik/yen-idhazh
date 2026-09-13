"""The reference dataset's split rule, and every way a leak could flatter a number.

Every test here is driven from `tests/fixtures/reference-dataset/` or from a set
built in the test body. **None of them opens `corpus/reference-dataset-1/`, and
none opens `corpus/corpus.jsonl`** - `CLAUDE.md` section 13 names the corpus as a
collection a test may not walk, and a check that reads committed data to ask
whether the data is well-formed is not a test whatever file it sits in. The
committed set's own answer comes from `build_reference_dataset.py verify`, which
is an operator surface pytest does not run.

The fixture is six articles over two registrable domains, four on one and two on
the other, so the same six rows drive both arms the row cares about: the domains
come out disjoint, and the split is lopsided enough to fail a floor. A
disjointness test passes on an empty set, so the floor is the half that has to
be able to fail.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.app_config import ReferenceDatasetConfig
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.reference_dataset import (
    ReferenceCollectionMetadata,
    ReferenceDatasetLocalConfig,
    ReferenceDatasetRow,
    ReferenceExtractionRow,
    ReferenceFailureCode,
    ReferenceGroupBy,
    ReferenceImportTotals,
    ReferenceManifestRow,
    ReferencePhase,
    ReferenceSplit,
)
from utilities import build_reference_dataset as builder

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "reference-dataset"


def fixture_candidates() -> list[builder.Candidate]:
    return [
        builder.Candidate.from_payload(json.loads(line))
        for line in (FIXTURES / "candidates-six.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def built_split(
    rows: Sequence[ReferenceDatasetRow],
) -> dict[ReferenceSplit, list[str]]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.source_domain] = counts.get(row.source_domain, 0) + 1
    sides = builder.assign_domains(counts)
    splits: dict[ReferenceSplit, list[str]] = {
        ReferenceSplit.DEV: [],
        ReferenceSplit.TEST: [],
    }
    for row in rows:
        splits[sides[row.source_domain]].append(row.url_key)
    for keys in splits.values():
        keys.sort()
    return splits


@pytest.fixture
def rows() -> list[ReferenceDatasetRow]:
    return builder.build_rows(fixture_candidates(), FIXTURES, fetched_on="2026-09-13")


@pytest.fixture
def splits(rows: list[ReferenceDatasetRow]) -> dict[ReferenceSplit, list[str]]:
    return built_split(rows)


def domains_of(rows: Sequence[ReferenceDatasetRow], keys: Sequence[str]) -> set[str]:
    by_key = {row.url_key: row for row in rows}
    return {by_key[key].source_domain for key in keys}


def floors(
    *, rows_per_split_min: int = 2, domains_per_split_min: int = 1
) -> ReferenceDatasetConfig:
    """Fixture-scale floors. The committed ones are 200 rows and 20 domains a side."""
    return ReferenceDatasetConfig(
        rows_per_split_min=rows_per_split_min,
        domains_per_split_min=domains_per_split_min,
        rows_per_domain_max=7,
        article_words_min=10,
    )


# --- the oracle ------------------------------------------------------------


def test_no_source_domain_lands_on_both_sides_of_the_split(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    """The one property the whole dataset exists for.

    Two articles from one outlet share boilerplate, a house style and often a
    wire original, so a split that separates rows rather than outlets puts
    near-duplicates on both sides and flatters every number taken on it.
    """
    dev = domains_of(rows, splits[ReferenceSplit.DEV])
    test = domains_of(rows, splits[ReferenceSplit.TEST])
    assert dev and test, "a disjointness check passes on an empty set"
    assert not dev & test
    assert dev | test == {row.source_domain for row in rows}


def test_the_two_sides_together_are_exactly_the_dataset(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    dev, test = set(splits[ReferenceSplit.DEV]), set(splits[ReferenceSplit.TEST])
    assert not dev & test
    assert dev | test == {row.url_key for row in rows}


def test_an_outlet_is_never_cut_in_half() -> None:
    """Whatever the counts, a domain gets one side. Ten outlets, wildly uneven."""
    counts = {f"outlet-{index}.example": (index * 7) % 23 + 1 for index in range(10)}
    assigned = builder.assign_domains(counts)
    assert set(assigned) == set(counts)
    assert set(assigned.values()) == {ReferenceSplit.DEV, ReferenceSplit.TEST}


def test_the_split_unit_is_the_registered_name_and_not_the_host() -> None:
    """What makes the oracle mean anything.

    Grouping at the host would put two mastheads of one publisher group on
    opposite sides and call the result disjoint; it would also split one
    newsletter platform into hundreds of one-article outlets.
    """
    assert (
        builder.registrable_domain("https://economictimes.indiatimes.com/a/b") == "indiatimes.com"
    )
    assert builder.registrable_domain("https://timesofindia.indiatimes.com/x") == "indiatimes.com"
    assert builder.registrable_domain("https://www.bbc.co.uk/news/x") == "bbc.co.uk"
    assert builder.registrable_domain("https://aleximas.substack.com/p/x") == "substack.com"


# --- the floors, which are the half that has to be able to fail -------------


def test_the_lopsided_fixture_fails_a_floor_while_its_domains_stay_disjoint(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    """Four rows one side, two the other. The disjointness arm cannot see this."""
    sizes = sorted(len(keys) for keys in splits.values())
    assert sizes == [2, 4]
    assert not builder.leakage_faults(rows, splits, trained_on=set(), held_out=set())
    faults = builder.floor_faults(rows, splits, floors(rows_per_split_min=3))
    assert len(faults) == 1
    assert "holds 2 rows, under the floor of 3" in faults[0]


def test_a_side_drawn_from_too_few_outlets_fails_its_own_floor(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    faults = builder.floor_faults(rows, splits, floors(domains_per_split_min=2))
    assert len(faults) == 2
    assert all("registrable domains, under the floor of 2" in fault for fault in faults)


def test_the_fixture_clears_a_floor_it_can_actually_clear(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    assert not builder.floor_faults(rows, splits, floors())


def test_an_empty_side_is_caught_by_the_floor_and_not_by_disjointness(
    rows: list[ReferenceDatasetRow],
) -> None:
    """The builder this test describes would pass 'no domain on both sides' perfectly."""
    everything: dict[ReferenceSplit, list[str]] = {
        ReferenceSplit.DEV: sorted(row.url_key for row in rows),
        ReferenceSplit.TEST: [],
    }
    assert not builder.leakage_faults(rows, everything, trained_on=set(), held_out=set())
    faults = builder.floor_faults(rows, everything, floors())
    assert any("test holds 0 rows" in fault for fault in faults)


# --- the leaks, each proved on a set that really leaks -----------------------


def leaking_set() -> tuple[list[ReferenceDatasetRow], dict[ReferenceSplit, list[str]]]:
    """A committed fixture that leaks on purpose: one key and one domain on both sides."""
    root = FIXTURES / "leaking"
    rows = builder.read_dataset(root)
    return rows, {side: builder.read_split(root, side) for side in ReferenceSplit}


def test_a_key_on_both_sides_is_named_rather_than_counted() -> None:
    rows, splits = leaking_set()
    shared = set(splits[ReferenceSplit.DEV]) & set(splits[ReferenceSplit.TEST])
    assert len(shared) == 1, "the fixture is supposed to leak exactly one key"
    faults = builder.leakage_faults(rows, splits, trained_on=set(), held_out=set())
    assert any(fault.startswith("1 url_key on both sides") for fault in faults)
    assert any(next(iter(shared)) in fault for fault in faults)


def test_a_domain_on_both_sides_is_caught_even_when_no_key_repeats() -> None:
    rows, splits = leaking_set()
    dev = [key for key in splits[ReferenceSplit.DEV] if key not in splits[ReferenceSplit.TEST]]
    cleaned = {ReferenceSplit.DEV: dev, ReferenceSplit.TEST: splits[ReferenceSplit.TEST]}
    faults = builder.leakage_faults(rows, cleaned, trained_on=set(), held_out=set())
    assert not any("url_key on both sides" in fault for fault in faults)
    assert any("domain on both sides" in fault for fault in faults)


def test_an_article_in_the_fine_tuning_window_is_caught(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    """Trained on, then measured on. The contamination decision 1 named, by the other door."""
    faults = builder.leakage_faults(rows, splits, trained_on={rows[0].url_key}, held_out=set())
    assert len(faults) == 1
    assert "corpus/corpus.jsonl" in faults[0]
    assert rows[0].url_key in faults[0]


def test_an_article_in_the_fine_tuning_holdout_is_caught(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    faults = builder.leakage_faults(rows, splits, trained_on=set(), held_out={rows[1].url_key})
    assert len(faults) == 1
    assert "corpus/holdout.txt" in faults[0]


def test_a_row_in_no_split_and_a_split_key_with_no_row_are_both_caught(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    dropped = dict(splits)
    dropped[ReferenceSplit.DEV] = splits[ReferenceSplit.DEV][1:]
    faults = builder.leakage_faults(rows, dropped, trained_on=set(), held_out=set())
    assert any("is in no split" in fault for fault in faults)

    invented = dict(splits)
    invented[ReferenceSplit.TEST] = [*splits[ReferenceSplit.TEST], "0" * 64]
    faults = builder.leakage_faults(rows, invented, trained_on=set(), held_out=set())
    assert any("has no dataset row" in fault for fault in faults)


def test_a_clean_set_produces_no_faults_at_all(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    """Without this, every test above passes on a checker that always complains."""
    assert not builder.leakage_faults(rows, splits, trained_on=set(), held_out=set())


# --- the text the labels were taken against ---------------------------------


def test_an_article_edited_in_place_stops_matching_its_row(
    tmp_path: Path, rows: list[ReferenceDatasetRow]
) -> None:
    """A label is a reading of a text. Change the text and the label is about nothing."""
    for row in rows:
        target = builder.article_path(tmp_path, row.url_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            builder.article_path(FIXTURES, row.url_key).read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="",
        )
    assert not builder.text_faults(rows, tmp_path)

    builder.article_path(tmp_path, rows[0].url_key).write_text(
        "a different article entirely\n", encoding="utf-8", newline=""
    )
    faults = builder.text_faults(rows, tmp_path)
    assert len(faults) == 1
    assert "no longer matches its digest" in faults[0]


def test_a_missing_article_file_is_caught(tmp_path: Path, rows: list[ReferenceDatasetRow]) -> None:
    faults = builder.text_faults(rows[:1], tmp_path)
    assert faults == [f"{rows[0].url_key[:12]} has no article file"]


def test_a_row_is_only_built_for_an_article_that_is_on_disk(tmp_path: Path) -> None:
    assert builder.build_rows(fixture_candidates(), tmp_path, fetched_on="2026-09-13") == []


# --- the contract -----------------------------------------------------------


def test_a_row_cannot_claim_an_identity_it_does_not_own(rows: list[ReferenceDatasetRow]) -> None:
    payload = rows[0].model_dump(mode="json")
    payload["canonical_url"] = "https://newsroom-a.example.com/somewhere-else"
    with pytest.raises(ValueError, match="identity it does not own"):
        ReferenceDatasetRow.model_validate(payload)


def test_every_label_slot_is_empty_when_the_set_is_built(rows: list[ReferenceDatasetRow]) -> None:
    """This row writes no label. A person does, in row #P3."""
    assert all(row.labels.is_empty for row in rows)
    assert all(row.second_labels is None for row in rows)


def test_there_is_no_train_split() -> None:
    """A train split in the same directory invites fine-tuning on the measurement set."""
    assert [side.value for side in ReferenceSplit] == ["dev", "test"]


def test_the_schema_is_stamped_with_a_date_and_a_first_changelog_entry() -> None:
    assert ReferenceDatasetRow.schema_version() == "2026-09-13"
    assert ReferenceDatasetRow.__changelog__[0].version == "2026-09-13"
    assert ReferenceDatasetRow.__changelog__[0].why


# --- the supplied-URL collection's shapes -----------------------------------
#
# `corpus/reference-dataset-2/` is a different collection from the frozen set
# above. These build every case in the test body rather than reading the
# collection, so they carry the awkward shapes a real run may never produce.

SAMPLE_URL = "https://chipbriefing.substack.com/p/the-lithography-squeeze"


def manifest_row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_line": 412,
        "source_url": SAMPLE_URL,
        "canonical_url": SAMPLE_URL,
        "url_key": derive_url_key(SAMPLE_URL),
        "source_domain": "substack.com",
        "host": "chipbriefing.substack.com",
        "publisher": "chipbriefing",
    }
    payload.update(overrides)
    return payload


def extraction_row(**overrides: object) -> dict[str, object]:
    text = "One paragraph.\n\nAnd a second one, so the break survives."
    payload: dict[str, object] = {
        **manifest_row(),
        "status": ArticleStatus.OK.value,
        "text": text,
        "article_words": len(text.split()),
        "article_sha256": derive_text_digest(text),
        "fetched_at": "2026-09-13T09:14:02Z",
        "extracted_at": "2026-09-13T09:14:03Z",
        "extractor_version": "trafilatura-2.0.0-idhazh-2",
        "sanitizer_version": "idhazh-sanitize-3",
    }
    payload.update(overrides)
    return payload


def import_metadata(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "phase": ReferencePhase.IMPORT.value,
        "generated_at": "2026-09-13T09:02:11Z",
        "collection_schema": "reference-dataset-manifest",
        "input_path": "corpus/reference-dataset-2/urls.txt",
        "input_sha256": derive_text_digest("input"),
        "output_path": "corpus/reference-dataset-2/manifest.json",
        "output_sha256": derive_text_digest("output"),
        "rows": 1,
        "settings": ReferenceDatasetLocalConfig(
            version=ReferenceDatasetLocalConfig.schema_version()
        ).model_dump(mode="json"),
        "import_totals": ReferenceImportTotals(
            input_lines=1,
            blank_lines=0,
            valid_urls=1,
            unique_urls=1,
            equivalent_urls=0,
            invalid_lines=0,
            unassigned_vertical=1,
        ).model_dump(mode="json"),
    }
    payload.update(overrides)
    return payload


def test_the_local_config_defaults_to_the_approved_sampling_rule() -> None:
    """20 an outlet, 1,000 at most, shortfalls filled, grouped on the publisher prefix."""
    config = ReferenceDatasetLocalConfig(version=ReferenceDatasetLocalConfig.schema_version())
    assert config.selection.rows_per_domain_target == 20
    assert config.selection.rows_max == 1000
    assert config.selection.fill_shortfall is True
    assert config.selection.group_by is ReferenceGroupBy.PUBLISHER


def test_the_local_config_takes_a_different_sample_size_without_a_code_change() -> None:
    config = ReferenceDatasetLocalConfig.model_validate(
        {"selection": {"rows_per_domain_target": 5, "rows_max": 40, "group_by": "host"}}
    )
    assert config.selection.rows_per_domain_target == 5
    assert config.selection.rows_max == 40
    assert config.selection.group_by is ReferenceGroupBy.HOST


def test_the_local_config_refuses_a_field_nobody_declared() -> None:
    with pytest.raises(ValueError, match="Extra inputs"):
        ReferenceDatasetLocalConfig.model_validate({"rows_per_domain": 20})


def test_the_local_config_refuses_a_path_that_climbs_out_of_the_repository() -> None:
    with pytest.raises(ValueError):
        ReferenceDatasetLocalConfig.model_validate({"taxonomy_file": "../../config/taxonomy.json"})


def test_a_manifest_row_needs_no_feed_and_no_vertical() -> None:
    """A supplied URL belongs to no feed, and null is 'we do not know'."""
    row = ReferenceManifestRow.model_validate(manifest_row())
    assert row.source_id is None
    assert row.vertical is None
    assert row.publisher == "chipbriefing"


def test_a_manifest_row_cannot_claim_an_identity_it_does_not_own() -> None:
    with pytest.raises(ValueError, match="identity it does not own"):
        ReferenceManifestRow.model_validate(
            manifest_row(canonical_url="https://chipbriefing.substack.com/p/something-else")
        )


def test_a_successful_extraction_keeps_its_paragraph_break_and_its_provenance() -> None:
    row = ReferenceExtractionRow.model_validate(extraction_row())
    assert row.text is not None and "\n\n" in row.text
    assert row.failure_code is None
    assert row.article_sha256 == derive_text_digest(row.text)


def test_a_failure_carries_a_reason_and_no_text() -> None:
    row = ReferenceExtractionRow.model_validate(
        {
            **manifest_row(),
            "status": ArticleStatus.ROBOTS_DENIED.value,
            "failure_code": ReferenceFailureCode.ROBOTS_DENIED.value,
            "failure_detail": "robots.txt disallows this path",
        }
    )
    assert row.text is None
    assert row.article_words is None
    assert row.extracted_at is None


def test_a_failure_that_says_nothing_about_why_is_refused() -> None:
    with pytest.raises(ValueError, match="has to say why"):
        ReferenceExtractionRow.model_validate(
            {**manifest_row(), "status": ArticleStatus.FETCH_FAILED.value}
        )


def test_a_failure_carrying_article_text_is_refused() -> None:
    """A truncated download must not arrive as a short article."""
    with pytest.raises(ValueError, match="carries no text"):
        ReferenceExtractionRow.model_validate(
            extraction_row(
                status=ArticleStatus.EXTRACT_FAILED.value,
                failure_code=ReferenceFailureCode.BODY_TRUNCATED.value,
            )
        )


def test_a_success_with_no_text_is_refused() -> None:
    with pytest.raises(ValueError, match="carries its text"):
        ReferenceExtractionRow.model_validate(
            extraction_row(
                text=None,
                article_words=None,
                article_sha256=None,
                extracted_at=None,
                extractor_version=None,
                sanitizer_version=None,
            )
        )


def test_an_empty_string_is_a_failure_rather_than_a_short_article() -> None:
    with pytest.raises(ValueError, match="empty string is a failure"):
        ReferenceExtractionRow.model_validate(
            extraction_row(text="", article_words=0, article_sha256=derive_text_digest(""))
        )


def test_metadata_carries_the_totals_of_the_phase_that_wrote_it() -> None:
    meta = ReferenceCollectionMetadata.model_validate(import_metadata())
    assert meta.import_totals is not None
    assert meta.extraction_totals is None
    assert meta.lengthened_publishers == {}


def test_metadata_without_the_totals_of_its_own_phase_is_refused() -> None:
    payload = import_metadata()
    payload.pop("import_totals")
    with pytest.raises(ValueError, match="carries no import totals"):
        ReferenceCollectionMetadata.model_validate(payload)


def test_metadata_carrying_another_phase_s_totals_is_refused() -> None:
    payload = import_metadata(
        selection_totals={
            "extraction_sha256": derive_text_digest("articles"),
            "group_by": ReferenceGroupBy.PUBLISHER.value,
            "groups": 1,
            "requested": 1,
            "selected": 1,
            "shortfall": 0,
        }
    )
    with pytest.raises(ValueError, match="totals it did not produce"):
        ReferenceCollectionMetadata.model_validate(payload)


def test_the_new_shapes_are_stamped_and_changelogged() -> None:
    for contract in (
        ReferenceDatasetLocalConfig,
        ReferenceManifestRow,
        ReferenceExtractionRow,
        ReferenceCollectionMetadata,
    ):
        assert contract.schema_version().startswith("2026-09-13")
        assert contract.__changelog__[0].why


# --- the publisher key ------------------------------------------------------
#
# Built in the test body rather than read off the collection, so the cases a
# real input may never carry - a collision, a label of punctuation - are here.

GENERIC = frozenset(
    ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version()
    ).selection.generic_host_labels
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://chipbriefing.substack.com/p/one", "chipbriefing"),
        ("https://aleximas.substack.com/p/two", "aleximas"),
        ("https://www.bbc.co.uk/news/articles/three", "bbc"),
        ("https://www.theverge.com/four", "theverge"),
        ("https://economictimes.indiatimes.com/five", "economictimes"),
        ("https://timesofindia.indiatimes.com/six", "timesofindia"),
        ("https://newsletter.semianalysis.com/p/seven", "semianalysis"),
        ("https://blog.google/eight", "blog"),
    ],
)
def test_the_publisher_key_is_the_outlet_and_not_the_registered_domain(
    url: str, expected: str
) -> None:
    """Two newsletters on one platform are two outlets; a subdomain word is not one."""
    name, _registered, _suffix, _host = builder.publisher_parts(url, generic=GENERIC)
    assert name == expected


def test_two_newsletters_on_one_platform_do_not_collapse() -> None:
    keys, lengthened = builder.assign_publishers(
        [
            "https://bengoertzel.substack.com/p/one",
            "https://chipbriefing.substack.com/p/two",
        ],
        generic=GENERIC,
    )
    assert sorted(keys.values()) == ["bengoertzel", "chipbriefing"]
    assert lengthened == {}
    assert builder.registrable_domain("https://bengoertzel.substack.com/p/one") == "substack.com"


def test_only_the_keys_that_collide_are_lengthened() -> None:
    keys, lengthened = builder.assign_publishers(
        [
            "https://news.bbc.co.uk/one",
            "https://news.ycombinator.com/two",
            "https://chipbriefing.substack.com/three",
        ],
        generic=frozenset(),
    )
    assert keys["news.bbc.co.uk"] == "news-bbc"
    assert keys["news.ycombinator.com"] == "news-ycombinator"
    assert keys["chipbriefing.substack.com"] == "chipbriefing"
    assert set(lengthened) == {"news-bbc", "news-ycombinator"}


def test_a_label_that_normalises_to_nothing_falls_back_rather_than_refusing() -> None:
    keys, _lengthened = builder.assign_publishers(["https://---.example.com/one"], generic=GENERIC)
    assert keys["---.example.com"] == "example"


def test_the_key_is_the_same_whatever_the_pool_order() -> None:
    pool = [
        "https://news.bbc.co.uk/one",
        "https://news.ycombinator.com/two",
        "https://chipbriefing.substack.com/three",
    ]
    first, _ = builder.assign_publishers(pool, generic=GENERIC)
    second, _ = builder.assign_publishers(list(reversed(pool)), generic=GENERIC)
    assert first == second


# --- import-urls ------------------------------------------------------------


def supplied(tmp_path: Path) -> tuple[Path, ReferenceDatasetLocalConfig]:
    """A collection directory holding the fixture URL list and its own config."""
    dataset = tmp_path / "reference-dataset-2"
    dataset.mkdir()
    listing = dataset / "urls.txt"
    listing.write_text(
        (FIXTURES / "url-inputs.txt").read_text(encoding="utf-8"), encoding="utf-8", newline=""
    )
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
    )
    return dataset, local


def imported(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    dataset, local = supplied(tmp_path)
    code = builder.build_manifest(
        dataset, local, sources_path=FIXTURES / "url-source-config.json", root=tmp_path
    )
    assert code == 0
    meta: dict[str, Any] = json.loads(
        (dataset / builder.MANIFEST_META_FILENAME).read_text(encoding="utf-8")
    )
    return dataset, meta


def test_every_supplied_line_appears_once_in_the_order_it_was_given(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    rows = json.loads((dataset / builder.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert [row["source_line"] for row in rows] == sorted(row["source_line"] for row in rows)
    assert len(rows) == 7


def test_equivalent_addresses_keep_both_rows_and_share_one_identity(tmp_path: Path) -> None:
    """The tracking parameter is not a second article."""
    dataset, meta = imported(tmp_path)
    rows = json.loads((dataset / builder.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    briefing = [row for row in rows if row["publisher"] == "chipbriefing"]
    assert len(briefing) == 2
    assert len({row["url_key"] for row in briefing}) == 1
    assert meta["import_totals"]["equivalent_urls"] == 1


def test_a_host_two_verticals_share_claims_neither(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    rows = json.loads((dataset / builder.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    shared = next(row for row in rows if row["host"] == "globaltimes.cn")
    assert shared["source_id"] is None
    assert shared["vertical"] is None


def test_a_declared_host_carries_its_feed_and_vertical(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    rows = json.loads((dataset / builder.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    declared = next(row for row in rows if row["host"] == "bbc.co.uk")
    assert declared["source_id"] == "bbc-world"
    assert declared["vertical"] == "world"


def test_the_manifest_stores_the_publisher_map_it_froze(tmp_path: Path) -> None:
    """Two BBC hosts read as one outlet name, so both were lengthened rather than merged."""
    _dataset, meta = imported(tmp_path)
    assert meta["publisher_hosts"]["semianalysis"] == ["newsletter.semianalysis.com"]
    assert meta["publisher_hosts"]["ycombinator"] == ["news.ycombinator.com"]
    assert set(meta["lengthened_publishers"]) == {"bbc-co-uk", "news-bbc-co-uk"}
    assert meta["lengthened_publishers"]["bbc-co-uk"] == "public_suffix"
    assert meta["lengthened_publishers"]["news-bbc-co-uk"] == "host"


def test_the_stored_totals_are_read_back_off_the_file_that_was_written(
    tmp_path: Path,
) -> None:
    """A total nobody re-read is a total that cannot disagree with its collection."""
    dataset, meta = imported(tmp_path)
    written = (dataset / builder.MANIFEST_FILENAME).read_bytes()
    assert meta["output_sha256"] == hashlib.sha256(written).hexdigest()
    assert meta["rows"] == len(json.loads(written.decode("utf-8")))


def test_a_malformed_line_blocks_the_manifest_and_is_named_by_its_line_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dataset, local = supplied(tmp_path)
    listing = tmp_path / "reference-dataset-2" / "urls.txt"
    listing.write_text(
        listing.read_text(encoding="utf-8") + "not-an-address\n", encoding="utf-8", newline=""
    )
    code = builder.build_manifest(
        dataset, local, sources_path=FIXTURES / "url-source-config.json", root=tmp_path
    )
    assert code == 1
    assert "line 9" in capsys.readouterr().out
    assert not (dataset / builder.MANIFEST_FILENAME).exists()


def test_the_import_reads_no_pipeline_config_and_writes_no_label(tmp_path: Path) -> None:
    dataset, meta = imported(tmp_path)
    rows = json.loads((dataset / builder.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert all("desk" not in row and "labels" not in row for row in rows)
    assert meta["settings"]["selection"]["group_by"] == "publisher"


# --- the builder refuses, rather than writing a set that leaks ---------------


def written_files(root: Path) -> set[str]:
    return {path.name for path in root.rglob("*") if path.is_file()}


def prepared(tmp_path: Path) -> tuple[Path, Path]:
    """A dataset directory holding the six article texts, and a work directory."""
    dataset = tmp_path / "reference-dataset-1"
    for candidate in fixture_candidates():
        target = builder.article_path(dataset, candidate.url_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            builder.article_path(FIXTURES, candidate.url_key).read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="",
        )
    work = tmp_path / "work"
    work.mkdir()
    (work / builder.CANDIDATES_FILENAME).write_text(
        (FIXTURES / "candidates-six.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="",
    )
    return dataset, work


def test_the_builder_writes_nothing_when_a_floor_would_be_missed(tmp_path: Path) -> None:
    dataset, work = prepared(tmp_path)
    empty_corpus = tmp_path / "no-corpus"
    empty_corpus.mkdir()

    code = builder.split(
        dataset, work, empty_corpus, floors(rows_per_split_min=5), fetched_on="2026-09-13"
    )
    assert code == 1
    assert builder.DATASET_FILENAME not in written_files(dataset)

    code = builder.split(dataset, work, empty_corpus, floors(), fetched_on="2026-09-13")
    assert code == 0
    assert builder.DATASET_FILENAME in written_files(dataset)
    assert len(builder.read_dataset(dataset)) == 6
    assert builder.verify(dataset, empty_corpus, floors()) == 0


def test_the_builder_refuses_a_set_that_overlaps_the_fine_tuning_window(
    tmp_path: Path,
) -> None:
    """The arm that would otherwise pass silently: every number comes out flattering.

    `overlapping-corpus/` is a real one-row window and a real one-key holdout, so
    the refusal is driven through `corpus.read_rows` rather than around it.
    """
    dataset, work = prepared(tmp_path)

    code = builder.split(
        dataset, work, FIXTURES / "overlapping-corpus", floors(), fetched_on="2026-09-13"
    )
    assert code == 1
    assert builder.DATASET_FILENAME not in written_files(dataset)


# --- what the fixture itself has to be --------------------------------------


def test_the_fixture_is_the_shape_every_test_above_assumes() -> None:
    candidates = fixture_candidates()
    assert len(candidates) == 6
    counts: Mapping[str, int] = {
        domain: sum(1 for c in candidates if c.domain == domain)
        for domain in {c.domain for c in candidates}
    }
    assert sorted(counts.values()) == [2, 4], "the lopsided case is the point of the fixture"
    for candidate in candidates:
        text = builder.article_path(FIXTURES, candidate.url_key).read_text(encoding="utf-8")
        assert hashlib.sha256(text.encode("utf-8")).hexdigest()
