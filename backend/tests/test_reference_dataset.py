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
import re
from collections.abc import Callable, Mapping, Sequence, Set
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import canonical_json, derive_text_digest, derive_url_key
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome
from idhazh.contracts.knobs.finetune import ReferenceDatasetConfig
from idhazh.contracts.reference_dataset import (
    ReferenceCleaningSettings,
    ReferenceCollectionMetadata,
    ReferenceDatasetLocalConfig,
    ReferenceDatasetRow,
    ReferenceExtractionRow,
    ReferenceFailureCode,
    ReferenceGroupBy,
    ReferenceImportTotals,
    ReferenceManifestRow,
    ReferencePhase,
    ReferenceSelectionSettings,
    ReferenceSplit,
)
from idhazh.fetch import FetchResult
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


def test_the_schema_is_stamped_with_a_date_and_a_newest_first_changelog() -> None:
    """The shape, not the date - a literal date makes every legitimate stamp a red build."""
    entries = ReferenceDatasetRow.__changelog__
    assert ReferenceDatasetRow.schema_version() == entries[0].version
    versions = [entry.version for entry in entries]
    assert versions == sorted(versions, reverse=True), "newest first"
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", version) for version in versions)
    assert all(entry.why for entry in entries)


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
    dataset.mkdir(exist_ok=True)
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


# --- extract-urls -----------------------------------------------------------
#
# The network boundary is driven by recorded pages under `tests/fixtures/`, so
# nothing here opens a socket (`CLAUDE.md` section 13). What is recorded is a
# real response shape, not a stub that returns whatever the assertion wants.

PAGES = REPO_ROOT / "tests" / "fixtures" / "pages"
ROBOTS = REPO_ROOT / "tests" / "fixtures" / "robots"


def served(
    pages: Mapping[str, bytes],
    *,
    robots: bytes | None = None,
    truncated: Set[str] = frozenset(),
) -> Callable[[str, RobotsOutcome], FetchResult]:
    """A reader over recorded bytes. One call, one recorded response, no socket."""
    body = robots if robots is not None else (ROBOTS / "no-rules.txt").read_bytes()

    def read(url: str, permission: RobotsOutcome) -> FetchResult:
        if url.endswith("/robots.txt"):
            return FetchResult(FetchOutcome.OK, status=200, body=body)
        if url not in pages:
            return FetchResult(FetchOutcome.PERMANENT, status=404, detail="not found")
        return FetchResult(
            FetchOutcome.OK,
            status=200,
            body=pages[url],
            body_truncated=url in truncated,
        )

    return read


def extracted(
    tmp_path: Path,
    reader: Callable[[str, RobotsOutcome], FetchResult],
    *,
    run_id: str = "2026-09-13-1",
    limit: int | None = None,
) -> tuple[Path, list[ReferenceExtractionRow]]:
    dataset, _meta = imported(tmp_path)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    code = builder.extract_supplied(
        dataset, local, run_id=run_id, limit=limit, read=reader
    )
    assert code == 0
    saved = sorted(
        (builder.run_dir(dataset, run_id) / builder.ITEMS_DIRNAME).glob("*.json")
    )
    return dataset, [
        ReferenceExtractionRow.model_validate_json(path.read_text(encoding="utf-8"))
        for path in saved
    ]


def manifest_urls(dataset: Path) -> list[str]:
    return [row.source_url for row in builder.read_manifest(dataset)]


def all_pages(dataset: Path, body: bytes) -> dict[str, bytes]:
    return dict.fromkeys(manifest_urls(dataset), body)


def test_one_request_per_identity_and_a_failure_is_a_row(tmp_path: Path) -> None:
    """Seven input lines, six identities, and the 404s are recorded rather than dropped."""
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    urls = manifest_urls(dataset)
    reader = served({urls[0]: article})
    _dataset, results = extracted(tmp_path, reader)
    assert len(results) == 6
    assert sum(1 for row in results if row.status is ArticleStatus.OK) == 1
    missing = [row for row in results if row.failure_code is not None]
    assert {row.failure_code for row in missing} == {ReferenceFailureCode.FETCH_PERMANENT}


def test_the_saved_text_is_the_whole_article_and_keeps_its_paragraphs(
    tmp_path: Path,
) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    _dataset, results = extracted(tmp_path, served(all_pages(dataset, article)))
    kept = next(row for row in results if row.status is ArticleStatus.OK)
    assert kept.text is not None
    # The sanitizer separates paragraphs with one newline, so several lines is
    # what a kept paragraph break looks like here.
    assert len([line for line in kept.text.splitlines() if line.strip()]) >= 3
    assert kept.text.endswith("\n")
    assert kept.article_words is not None and kept.article_words > 20
    assert kept.article_sha256 == derive_text_digest(kept.text)
    # The sanitizer's job, proven rather than assumed: the nav and the modal are
    # on the page and not in what was saved.
    assert "Subscribe" not in kept.text
    assert "Unsubscribe at any time" not in kept.text


def test_a_truncated_body_is_a_failure_and_never_a_short_article(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    urls = manifest_urls(dataset)
    reader = served(all_pages(dataset, article), truncated={urls[0]})
    _dataset, results = extracted(tmp_path, reader)
    cut = next(row for row in results if row.source_url == urls[0])
    assert cut.status is ArticleStatus.FETCH_FAILED
    assert cut.failure_code is ReferenceFailureCode.BODY_TRUNCATED
    assert cut.text is None


def test_a_page_with_no_prose_is_an_empty_text_failure(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    bare = b"<!DOCTYPE html><html><head><title>Nothing</title></head><body></body></html>"
    _dataset, results = extracted(tmp_path, served(all_pages(dataset, bare)))
    assert {row.failure_code for row in results} == {ReferenceFailureCode.EMPTY_TEXT}
    assert all(row.text is None for row in results)


def test_a_robots_refusal_is_recorded_and_no_article_is_requested(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    asked: list[str] = []

    inner = served(all_pages(dataset, article), robots=(ROBOTS / "blanket-disallow.txt").read_bytes())

    def counting(url: str, permission: RobotsOutcome) -> FetchResult:
        asked.append(url)
        return inner(url, permission)

    _dataset, results = extracted(tmp_path, counting)
    assert all(row.status is ArticleStatus.ROBOTS_DENIED for row in results)
    assert all(row.failure_code is ReferenceFailureCode.ROBOTS_DENIED for row in results)
    assert all(row.failure_detail for row in results), "a refusal has to say why"
    assert all(url.endswith("/robots.txt") for url in asked)


def test_a_resume_keeps_the_saved_result_and_asks_only_for_what_is_missing(
    tmp_path: Path,
) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    pages = all_pages(dataset, article)

    _dataset, first = extracted(tmp_path, served(pages), limit=2)
    assert len(first) == 2
    kept = first[0]

    asked: list[str] = []
    inner = served(pages)

    def counting(url: str, permission: RobotsOutcome) -> FetchResult:
        if not url.endswith("/robots.txt"):
            asked.append(url)
        return inner(url, permission)

    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    assert builder.extract_supplied(dataset, local, run_id="2026-09-13-1", read=counting) == 0

    again = ReferenceExtractionRow.model_validate_json(
        builder.checkpoint_path(dataset, "2026-09-13-1", kept.url_key).read_text(
            encoding="utf-8"
        )
    )
    assert again.model_dump() == kept.model_dump()
    assert kept.canonical_url not in asked
    assert len(asked) == 4


def test_a_second_pass_over_a_finished_run_makes_no_request(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    extracted(tmp_path, served(all_pages(dataset, article)))

    def refuses(url: str, permission: RobotsOutcome) -> FetchResult:
        raise AssertionError(f"a finished run asked for {url}")

    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    assert builder.extract_supplied(dataset, local, run_id="2026-09-13-1", read=refuses) == 0


def test_a_run_taken_with_different_settings_is_refused_rather_than_mixed(
    tmp_path: Path,
) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    extracted(tmp_path, served(all_pages(dataset, article)), limit=1)

    moved = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=2.0,
    )
    with pytest.raises(ValueError, match="different settings"):
        builder.extract_supplied(
            dataset, moved, run_id="2026-09-13-1", read=served(all_pages(dataset, article))
        )


def test_a_run_taken_against_a_different_manifest_is_refused(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    extracted(tmp_path, served(all_pages(dataset, article)), limit=1)

    manifest = dataset / builder.MANIFEST_FILENAME
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(rows[:-1], indent=2) + "\n", encoding="utf-8", newline="")

    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    with pytest.raises(ValueError, match="different manifest"):
        builder.extract_supplied(
            dataset, local, run_id="2026-09-13-1", read=served(all_pages(dataset, article))
        )


def test_a_checkpoint_is_named_by_recomputed_identity_and_not_by_page_text(
    tmp_path: Path,
) -> None:
    """A filename a fetched page could steer is a path a stranger controls."""
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "hostile.html").read_bytes()
    _dataset, results = extracted(tmp_path, served(all_pages(dataset, article)))
    saved = {
        path.stem
        for path in (builder.run_dir(dataset, "2026-09-13-1") / builder.ITEMS_DIRNAME).glob(
            "*.json"
        )
    }
    assert saved == {row.url_key for row in results}
    assert all(derive_url_key(row.canonical_url) == row.url_key for row in results)


def test_a_host_that_serves_only_the_supplied_name_is_asked_at_that_name(
    tmp_path: Path,
) -> None:
    """`canonicalise` strips `www.`; several newsletter hosts serve only `www`.

    Asking the apex made 188 real URLs read as "robots.txt unreachable" when
    every one of them allowed us. The canonical form is identity, not a routing
    instruction.
    """
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    asked: list[str] = []
    inner = served(all_pages(dataset, article))

    def counting(url: str, permission: RobotsOutcome) -> FetchResult:
        asked.append(url)
        return inner(url, permission)

    _dataset, results = extracted(tmp_path, counting)
    assert all(row.status is ArticleStatus.OK for row in results)
    assert [url for url in asked if url.startswith("https://www.bbc.co.uk")]
    assert not [url for url in asked if url.startswith("https://bbc.co.uk")]


# --- export-urls ------------------------------------------------------------


def exported(tmp_path: Path, reader: Callable[[str, RobotsOutcome], FetchResult]) -> Path:
    dataset, _results = extracted(tmp_path, reader)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    assert (
        builder.export_extraction(dataset, local, run_id="2026-09-13-1", root=tmp_path) == 0
    )
    return dataset


def export_of(dataset: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run = dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1"
    rows = json.loads((run / builder.ARTICLES_FILENAME).read_text(encoding="utf-8"))
    meta = json.loads((run / builder.METADATA_FILENAME).read_text(encoding="utf-8"))
    return rows, meta


def test_the_export_writes_one_row_per_input_line_not_per_identity(tmp_path: Path) -> None:
    """A reused checkpoint saves a request; it never removes an input row."""
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    rows, meta = export_of(dataset)
    assert len(rows) == 7
    assert meta["rows"] == 7
    assert meta["extraction_totals"]["unique_attempted"] == 6
    lines = [row["source_line"] for row in rows]
    assert lines == sorted(lines)


def test_an_alias_keeps_its_own_line_and_address_and_the_same_article(
    tmp_path: Path,
) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    rows, _meta = export_of(dataset)
    briefing = [row for row in rows if row["publisher"] == "chipbriefing"]
    assert len(briefing) == 2
    assert {row["source_line"] for row in briefing} == {1, 8}
    assert len({row["source_url"] for row in briefing}) == 2
    assert len({row["url_key"] for row in briefing}) == 1
    assert len({row["article_sha256"] for row in briefing}) == 1


def test_the_export_counts_come_from_reading_the_file_back(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    rows, meta = export_of(dataset)
    written = (
        dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1" / builder.ARTICLES_FILENAME
    ).read_bytes()
    assert meta["output_sha256"] == hashlib.sha256(written).hexdigest()
    assert meta["rows"] == len(rows)
    assert meta["extraction_totals"]["rows_succeeded"] + meta["extraction_totals"][
        "rows_failed"
    ] == len(rows)


def test_a_failure_is_exported_as_a_row_with_no_text(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    urls = manifest_urls(dataset)
    dataset = exported(tmp_path, served({urls[0]: article}))
    rows, meta = export_of(dataset)
    failed = [row for row in rows if row["failure_code"]]
    assert failed, "a failure has to survive the export"
    assert all(row["text"] is None for row in failed)
    assert meta["extraction_totals"]["failure_codes"]["fetch_permanent"] == len(failed)


def test_the_export_refuses_while_an_identity_has_no_result(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    extracted(tmp_path, served(all_pages(dataset, article)), limit=2)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    assert builder.export_extraction(dataset, local, run_id="2026-09-13-1", root=tmp_path) == 1
    assert not (dataset / builder.EXTRACTIONS_DIRNAME).exists()


def test_a_second_export_of_the_same_run_is_byte_identical(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    target = dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1" / builder.ARTICLES_FILENAME
    once = target.read_bytes()
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
    )
    assert builder.export_extraction(dataset, local, run_id="2026-09-13-1", root=tmp_path) == 0
    assert target.read_bytes() == once


# --- verify-urls ------------------------------------------------------------


def test_a_clean_extraction_has_no_faults(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    assert builder.extraction_faults(dataset, "2026-09-13-1", tmp_path) == []


def test_an_edited_article_stops_matching_its_digest(tmp_path: Path) -> None:
    """The one check that catches a text somebody changed in place."""
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    target = dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1" / builder.ARTICLES_FILENAME
    rows = json.loads(target.read_text(encoding="utf-8"))
    rows[0]["text"] = (rows[0]["text"] or "") + "a sentence nobody published\n"
    target.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="")
    faults = builder.extraction_faults(dataset, "2026-09-13-1", tmp_path)
    assert any("digest its text does not match" in fault for fault in faults)


def test_a_missing_input_line_is_caught(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    target = dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1" / builder.ARTICLES_FILENAME
    rows = json.loads(target.read_text(encoding="utf-8"))
    target.write_text(json.dumps(rows[:-1], indent=2) + "\n", encoding="utf-8", newline="")
    faults = builder.extraction_faults(dataset, "2026-09-13-1", tmp_path)
    assert any("input lines exactly once" in fault for fault in faults)


def test_metadata_naming_bytes_that_are_not_on_disk_is_caught(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    run = dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1"
    meta = json.loads((run / builder.METADATA_FILENAME).read_text(encoding="utf-8"))
    meta["output_sha256"] = derive_text_digest("not the file")
    (run / builder.METADATA_FILENAME).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline=""
    )
    faults = builder.extraction_faults(dataset, "2026-09-13-1", tmp_path)
    assert any("not the one on disk" in fault for fault in faults)


# --- clean-urls -------------------------------------------------------------
#
# Built in the test body, because the case that matters - a publisher that says
# the same thing on every article - is the one a bounded fixture can carry and a
# real extraction only sometimes does.


#: Six unrelated openings. The bodies have to differ in substance, not just in a
#: number: six near-identical articles are correctly read as one story, which is
#: the near-duplicate flag working rather than the fixture working.
_SUBJECTS: Final = (
    "The port authority said the dredging contract had been awarded to a local firm.",
    "Rainfall across the northern districts was the heaviest recorded since the war.",
    "Shares in the tool maker fell after it named a new chief financial officer.",
    "Two researchers published a paper arguing the census undercounts rural workers.",
    "The regulator opened an inquiry into how the utility bills its oldest customers.",
    "A committee recommended the bridge be closed to freight until spring at least.",
    "The airline restored its morning service between the two coastal capitals today.",
)


def furniture_rows(count: int, *, publisher: str = "outlet") -> list[ReferenceExtractionRow]:
    rows: list[ReferenceExtractionRow] = []
    for index in range(count):
        url = f"https://{publisher}.example.com/p/story-{index}"
        subject = _SUBJECTS[index % len(_SUBJECTS)]
        body = (
            f"{subject}\n"
            f"Officials would not say when the decision was taken or by whom, case {index}.\n"
            f"The written record for {subject.split()[1]} number {index} runs to many pages.\n"
            f"Two of the three people named in matter {index} have since left their posts.\n"
            f"A spokesman confirmed the {index} figures but declined to answer any questions.\n"
            "Disclaimer: nothing here is advice and the publisher accepts no liability.\n"
            "Subscribe now to receive our weekly letter, free, every single Tuesday.\n"
        )
        rows.append(
            ReferenceExtractionRow(
                version=ReferenceExtractionRow.schema_version(),
                source_line=index + 1,
                source_url=url,
                canonical_url=url,
                url_key=derive_url_key(url),
                source_domain="example.com",
                host=f"{publisher}.example.com",
                publisher=publisher,
                status=ArticleStatus.OK,
                text=body,
                article_words=len(body.split()),
                article_sha256=derive_text_digest(body),
                fetched_at="2026-09-13T09:00:00Z",
                extracted_at="2026-09-13T09:00:01Z",
                extractor_version="trafilatura-2.0.0-idhazh-2",
                sanitizer_version="idhazh-sanitize-3",
            )
        )
    return rows


def staged(tmp_path: Path, rows: list[ReferenceExtractionRow]) -> Path:
    dataset = tmp_path / "reference-dataset-2"
    (dataset / builder.MANIFEST_FILENAME).parent.mkdir(parents=True, exist_ok=True)
    target = dataset / builder.EXTRACTIONS_DIRNAME / "run" / builder.ARTICLES_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        canonical_json([row.model_dump(mode="json") for row in rows]).encode("utf-8")
    )
    return dataset


def cleaned(
    tmp_path: Path, rows: list[ReferenceExtractionRow], **overrides: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = staged(tmp_path, rows)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        cleaning=ReferenceCleaningSettings.model_validate({"words_min": 10, **overrides}),
    )
    assert (
        builder.clean_extraction(
            dataset, local, run_id="run", clean_id="first", root=tmp_path
        )
        == 0
    )
    out = dataset / builder.CLEANED_DIRNAME / "first"
    return (
        json.loads((out / builder.ARTICLES_FILENAME).read_text(encoding="utf-8")),
        json.loads((out / builder.METADATA_FILENAME).read_text(encoding="utf-8")),
    )


def test_a_line_every_article_carries_is_removed_from_all_of_them(tmp_path: Path) -> None:
    rows, meta = cleaned(tmp_path, furniture_rows(6))
    assert len(rows) == 6
    assert all("Disclaimer" not in row["text"] for row in rows)
    assert all("Subscribe now" not in row["text"] for row in rows)
    survived = {row["text"].splitlines()[0] for row in rows}
    assert survived == set(_SUBJECTS[:6]), "the article itself survives, whole"
    assert meta["cleaning_totals"]["lines_removed"] == 12


def test_the_removed_lines_are_written_down_where_a_person_can_read_them(
    tmp_path: Path,
) -> None:
    """A removal nobody can read is a removal nobody can argue with."""
    _rows, meta = cleaned(tmp_path, furniture_rows(6))
    removed = meta["cleaning_totals"]["removed_lines"]["outlet"]
    assert any("Disclaimer" in line for line in removed)
    assert any("Subscribe now" in line for line in removed)
    assert meta["cleaning_totals"]["removed_words_by_publisher"]["outlet"] > 0


def test_a_line_one_article_carries_is_left_alone(tmp_path: Path) -> None:
    rows = furniture_rows(6)
    once = rows[0]
    body = (once.text or "") + "A sentence that appears on exactly one of these six articles.\n"
    rows[0] = once.model_copy(
        update={
            "text": body,
            "article_words": len(body.split()),
            "article_sha256": derive_text_digest(body),
        }
    )
    written, _meta = cleaned(tmp_path, rows)
    survivor = next(row for row in written if row["url_key"] == once.url_key)
    assert "appears on exactly one" in survivor["text"]


def test_a_publisher_with_too_few_articles_is_not_touched(tmp_path: Path) -> None:
    """Two samples cannot tell furniture from content."""
    rows, meta = cleaned(tmp_path, furniture_rows(3), publisher_min_articles=4)
    assert all("Disclaimer" in row["text"] for row in rows)
    assert meta["cleaning_totals"]["lines_removed"] == 0


def test_the_safety_valve_keeps_an_article_whole_and_says_so(tmp_path: Path) -> None:
    """A rule that can empty an article says so rather than doing it quietly."""
    rows, meta = cleaned(tmp_path, furniture_rows(6), max_removed_share=0.1)
    assert all("Disclaimer" in row["text"] for row in rows)
    assert meta["cleaning_totals"]["over_cleaned"] == 6
    assert all("over_cleaned" in row["quality_flags"] for row in rows)


def test_a_dropped_article_is_absent_and_counted_by_its_reason(tmp_path: Path) -> None:
    rows = furniture_rows(6)
    url = "https://outlet.example.com/p/stub"
    rows.append(
        ReferenceExtractionRow(
            version=ReferenceExtractionRow.schema_version(),
            source_line=99,
            source_url=url,
            canonical_url=url,
            url_key=derive_url_key(url),
            source_domain="example.com",
            host="outlet.example.com",
            publisher="outlet",
            status=ArticleStatus.OK,
            text="Too short.\n",
            article_words=2,
            article_sha256=derive_text_digest("Too short.\n"),
            fetched_at="2026-09-13T09:00:00Z",
            extracted_at="2026-09-13T09:00:01Z",
            extractor_version="trafilatura-2.0.0-idhazh-2",
            sanitizer_version="idhazh-sanitize-3",
        )
    )
    written, meta = cleaned(tmp_path, rows)
    assert derive_url_key(url) not in {row["url_key"] for row in written}
    assert meta["cleaning_totals"]["articles_dropped"] == 1
    assert meta["cleaning_totals"]["dropped_by_flag"]["short"] == 1


def test_a_cleaned_row_carries_a_digest_that_matches_its_new_text(tmp_path: Path) -> None:
    written, _meta = cleaned(tmp_path, furniture_rows(6))
    for row in written:
        assert row["article_sha256"] == derive_text_digest(row["text"])
        assert row["article_words"] == len(row["text"].split())


def test_the_frozen_extraction_is_not_touched(tmp_path: Path) -> None:
    rows = furniture_rows(6)
    dataset = staged(tmp_path, rows)
    source = dataset / builder.EXTRACTIONS_DIRNAME / "run" / builder.ARTICLES_FILENAME
    before = source.read_bytes()
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        cleaning=ReferenceCleaningSettings(words_min=10),
    )
    assert (
        builder.clean_extraction(dataset, local, run_id="run", clean_id="first", root=tmp_path)
        == 0
    )
    assert source.read_bytes() == before


def test_the_cleaning_names_the_extraction_it_read(tmp_path: Path) -> None:
    rows = furniture_rows(6)
    dataset = staged(tmp_path, rows)
    _written, meta = cleaned(tmp_path, rows)
    source = dataset / builder.EXTRACTIONS_DIRNAME / "run" / builder.ARTICLES_FILENAME
    assert meta["cleaning_totals"]["extraction_sha256"] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()


def test_a_second_cleaning_pass_is_byte_identical(tmp_path: Path) -> None:
    rows = furniture_rows(6)
    dataset = staged(tmp_path, rows)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        cleaning=ReferenceCleaningSettings(words_min=10),
    )
    assert (
        builder.clean_extraction(dataset, local, run_id="run", clean_id="first", root=tmp_path)
        == 0
    )
    target = dataset / builder.CLEANED_DIRNAME / "first" / builder.ARTICLES_FILENAME
    once = target.read_bytes()
    assert (
        builder.clean_extraction(dataset, local, run_id="run", clean_id="first", root=tmp_path)
        == 0
    )
    assert target.read_bytes() == once


# --- select-urls ------------------------------------------------------------
#
# The allocation cases are built here rather than drawn from a collected set, so
# the awkward shapes - a group with nothing usable, a cap that bites before any
# group reaches its target - are present whether or not a real run produced one.


def pools(**sizes: int) -> dict[str, list[str]]:
    return {name: [f"{name}-{index}" for index in range(size)] for name, size in sizes.items()}


def test_the_allocation_fills_what_a_short_group_cannot_use() -> None:
    """Three groups holding 1, 5 and 5, target 2, cap 6: fill on selects 6."""
    taken = builder.allocate(pools(a=1, b=5, c=5), target=2, cap=6, fill=True)
    assert sum(len(keys) for keys in taken.values()) == 6
    assert len(taken["a"]) == 1
    assert max(len(taken["b"]), len(taken["c"])) > 2


def test_the_allocation_stops_at_the_target_when_filling_is_off() -> None:
    taken = builder.allocate(pools(a=1, b=5, c=5), target=2, cap=6, fill=False)
    assert sum(len(keys) for keys in taken.values()) == 5
    assert len(taken["a"]) == 1
    assert len(taken["b"]) == len(taken["c"]) == 2


def test_the_cap_wins_before_every_group_reaches_its_target() -> None:
    taken = builder.allocate(pools(a=1, b=5, c=5), target=2, cap=4, fill=True)
    assert sum(len(keys) for keys in taken.values()) == 4


def test_a_group_with_nothing_usable_contributes_nothing_and_is_still_counted() -> None:
    taken = builder.allocate(pools(a=0, b=3), target=2, cap=10, fill=False)
    assert taken["a"] == []
    assert len(taken["b"]) == 2


def test_the_allocation_never_repeats_an_article() -> None:
    taken = builder.allocate(pools(a=3, b=3), target=9, cap=99, fill=True)
    chosen = [key for keys in taken.values() for key in keys]
    assert len(chosen) == len(set(chosen)) == 6


def test_the_same_pool_and_settings_allocate_the_same_articles() -> None:
    first = builder.allocate(pools(a=1, b=5, c=5), target=2, cap=6, fill=True)
    second = builder.allocate(pools(c=5, a=1, b=5), target=2, cap=6, fill=True)
    assert first == second


def selected(tmp_path: Path, **overrides: Any) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    dataset, _meta = imported(tmp_path)
    article = (PAGES / "article.html").read_bytes()
    dataset = exported(tmp_path, served(all_pages(dataset, article)))
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
        selection=ReferenceSelectionSettings.model_validate(
            {"rows_per_domain_target": 1, "rows_max": 10, **overrides}
        ),
    )
    assert (
        builder.select_sample(
            dataset,
            local,
            run_id="2026-09-13-1",
            selection_id="first",
            root=tmp_path,
        )
        == 0
    )
    run = dataset / builder.SELECTIONS_DIRNAME / "first"
    rows = json.loads((run / builder.SELECTED_FILENAME).read_text(encoding="utf-8"))
    meta = json.loads((run / builder.METADATA_FILENAME).read_text(encoding="utf-8"))
    return dataset, meta, rows


def test_a_sample_takes_one_article_per_publisher_and_never_an_alias_twice(
    tmp_path: Path,
) -> None:
    _dataset, meta, rows = selected(tmp_path)
    assert len({row["url_key"] for row in rows}) == len(rows)
    assert meta["selection_totals"]["group_by"] == "publisher"
    assert meta["selection_totals"]["groups"] == 6
    assert all(count <= 1 for count in meta["selection_totals"]["selected_by_group"].values())


def test_the_sample_carries_the_digest_and_not_the_article(tmp_path: Path) -> None:
    _dataset, _meta, rows = selected(tmp_path)
    assert all("text" not in row for row in rows)
    assert all(len(row["article_sha256"]) == 64 for row in rows)


def test_a_sample_records_the_extraction_it_was_drawn_from(tmp_path: Path) -> None:
    dataset, meta, _rows = selected(tmp_path)
    source = (
        dataset / builder.EXTRACTIONS_DIRNAME / "2026-09-13-1" / builder.ARTICLES_FILENAME
    ).read_bytes()
    assert meta["selection_totals"]["extraction_sha256"] == hashlib.sha256(source).hexdigest()
    assert meta["input_sha256"] == hashlib.sha256(source).hexdigest()


def test_the_same_pool_and_settings_reproduce_the_same_sample(tmp_path: Path) -> None:
    dataset, _meta, rows = selected(tmp_path)
    target = dataset / builder.SELECTIONS_DIRNAME / "first" / builder.SELECTED_FILENAME
    once = target.read_bytes()
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
        selection=ReferenceSelectionSettings(rows_per_domain_target=1, rows_max=10),
    )
    assert (
        builder.select_sample(
            dataset, local, run_id="2026-09-13-1", selection_id="first", root=tmp_path
        )
        == 0
    )
    assert target.read_bytes() == once
    assert len(rows) == len(json.loads(once.decode("utf-8")))


def test_a_different_sample_gets_its_own_directory(tmp_path: Path) -> None:
    dataset, _meta, _rows = selected(tmp_path)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
        request_delay_seconds=0.0,
        selection=ReferenceSelectionSettings(rows_per_domain_target=2, rows_max=3),
    )
    assert (
        builder.select_sample(
            dataset, local, run_id="2026-09-13-1", selection_id="second", root=tmp_path
        )
        == 0
    )
    first = dataset / builder.SELECTIONS_DIRNAME / "first" / builder.SELECTED_FILENAME
    second = dataset / builder.SELECTIONS_DIRNAME / "second" / builder.SELECTED_FILENAME
    assert first.is_file() and second.is_file()
    assert len(json.loads(second.read_text(encoding="utf-8"))) == 3


def test_grouping_by_host_and_by_domain_are_both_available(tmp_path: Path) -> None:
    _dataset, meta, _rows = selected(tmp_path, group_by="source_domain")
    assert meta["selection_totals"]["group_by"] == "source_domain"
    assert meta["selection_totals"]["groups"] == 5


def test_the_selection_refuses_when_there_is_no_extraction(tmp_path: Path) -> None:
    dataset, _meta = imported(tmp_path)
    local = ReferenceDatasetLocalConfig(
        version=ReferenceDatasetLocalConfig.schema_version(),
        input_file="reference-dataset-2/urls.txt",
    )
    assert (
        builder.select_sample(
            dataset, local, run_id="missing", selection_id="first", root=tmp_path
        )
        == 1
    )


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
