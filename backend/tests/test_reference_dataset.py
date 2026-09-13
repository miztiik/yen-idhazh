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

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.app_config import ReferenceDatasetConfig
from idhazh.contracts.reference_dataset import ReferenceDatasetRow, ReferenceSplit
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


def domains_of(
    rows: Sequence[ReferenceDatasetRow], keys: Sequence[str]
) -> set[str]:
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
    assert builder.registrable_domain("https://economictimes.indiatimes.com/a/b") == "indiatimes.com"
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
    rows: list[ReferenceDatasetRow]
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
    faults = builder.leakage_faults(
        rows, splits, trained_on={rows[0].url_key}, held_out=set()
    )
    assert len(faults) == 1
    assert "corpus/corpus.jsonl" in faults[0]
    assert rows[0].url_key in faults[0]


def test_an_article_in_the_fine_tuning_holdout_is_caught(
    rows: list[ReferenceDatasetRow], splits: dict[ReferenceSplit, list[str]]
) -> None:
    faults = builder.leakage_faults(
        rows, splits, trained_on=set(), held_out={rows[1].url_key}
    )
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


def test_a_missing_article_file_is_caught(
    tmp_path: Path, rows: list[ReferenceDatasetRow]
) -> None:
    faults = builder.text_faults(rows[:1], tmp_path)
    assert faults == [f"{rows[0].url_key[:12]} has no article file"]


def test_a_row_is_only_built_for_an_article_that_is_on_disk(tmp_path: Path) -> None:
    assert builder.build_rows(fixture_candidates(), tmp_path, fetched_on="2026-09-13") == []


# --- the contract -----------------------------------------------------------


def test_a_row_cannot_claim_an_identity_it_does_not_own(
    rows: list[ReferenceDatasetRow]
) -> None:
    payload = rows[0].model_dump(mode="json")
    payload["canonical_url"] = "https://newsroom-a.example.com/somewhere-else"
    with pytest.raises(ValueError, match="identity it does not own"):
        ReferenceDatasetRow.model_validate(payload)


def test_every_label_slot_is_empty_when_the_set_is_built(
    rows: list[ReferenceDatasetRow]
) -> None:
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
