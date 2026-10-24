"""Do feed planning contracts and their strict TypeScript copies agree?"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

pytestmark = pytest.mark.contract

CONTRACT_NAMES = (
    ("feed_ingest_candidate", "FeedIngestCandidate"),
    ("feed_ingest_dispatch", "FeedIngestDispatch"),
    ("feed_ingest_rejection", "CandidateRejectionRecord"),
    ("feed_ingest_source_run", "SourceRunRecord"),
    ("feed_ingest_article_assessment", "ArticleAssessmentRecord"),
    ("feed_ingest_diversity", "DiversityMetricRow"),
    ("feed_ingest_editorial_selection", "EditorialSelectionRow"),
    ("planner_operation", "FetchedDocument"),
    ("planner_operation", "PlannerOperation"),
)


@pytest.mark.parametrize(("module", "name"), CONTRACT_NAMES)
def test_declared_contract(module: str, name: str) -> None:
    """The base must fail for absent behavior, not a missing test file."""
    import idhazh.contracts

    expected = Path.cwd() / "backend" / "idhazh" / "contracts"
    assert Path(idhazh.contracts.__file__).parent.resolve() == expected.resolve()
    try:
        loaded = importlib.import_module(f"idhazh.contracts.{module}")
    except ModuleNotFoundError:
        pytest.fail(f"Missing feed planning contract: {name}")
    contract = getattr(loaded, name)
    assert contract in idhazh.contracts.CONTRACTS
    assert contract.schema_version() == contract.model_fields["version"].default
    assert contract.json_schema()["additionalProperties"] is False


def test_typescript_provenance_is_declared() -> None:
    from idhazh.contracts.file_envelope import FileEnvelope

    assert (
        "idhazh_typescript.ledger.parquet"
        in (FileEnvelope.json_schema()["properties"]["writer"]["enum"])
    )


@pytest.fixture(scope="module")
def typescript_schemas() -> dict[str, Any]:
    bun = shutil.which("bun")
    assert bun, "Install Bun to run the shared contract binding gate"
    completed = subprocess.run(
        [bun, "run", "test/schema-binding.ts"],
        cwd=REPO_ROOT / "packages" / "common-contracts",
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def normalized_shape(node: dict[str, Any], root: dict[str, Any]) -> Any:
    """Compare actual types, required keys, defaults and vocabularies recursively."""
    if "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/"), f"Unexpected external reference: {ref}"
        target = root
        for key in ref[2:].split("/"):
            target = target[key]
        return normalized_shape(target, root)
    if "const" in node:
        return ("enum", (json.dumps(node["const"]),), node.get("default", "<required>"))
    if "enum" in node:
        return (
            "enum",
            tuple(sorted(json.dumps(value) for value in node["enum"])),
            node.get("default", "<required>"),
        )
    branches = node.get("anyOf", node.get("oneOf"))
    if branches is not None:
        return (
            "union",
            tuple(
                sorted(
                    (normalized_shape(branch, root) for branch in branches),
                    key=repr,
                )
            ),
            node.get("default", "<required>"),
        )
    kind = node.get("type")
    if isinstance(kind, list):
        return normalized_shape(
            {
                "anyOf": [{"type": value} for value in kind],
                **{k: v for k, v in node.items() if k != "type"},
            },
            root,
        )
    if kind == "object":
        assert node.get("additionalProperties") is False, "Objects must reject unknown fields"
        required = set(node.get("required", []))
        return (
            "object",
            {
                name: (name in required, normalized_shape(child, root))
                for name, child in node["properties"].items()
            },
            node.get("default", "<required>"),
        )
    if kind == "array":
        return ("array", normalized_shape(node["items"], root), node.get("default", "<required>"))
    assert kind in {"string", "integer", "number", "boolean", "null"}, node
    return (kind, node.get("default", "<required>"))


@pytest.mark.parametrize(
    ("module", "name"), (*CONTRACT_NAMES, ("feed_ingest_diagnostics", "ExtractionQuality"))
)
def test_typescript_field_types_defaults_and_vocabularies(
    module: str,
    name: str,
    typescript_schemas: dict[str, Any],
) -> None:
    contract = getattr(importlib.import_module(f"idhazh.contracts.{module}"), name)
    ours = contract.model_json_schema() if name == "ExtractionQuality" else contract.json_schema()
    theirs = typescript_schemas[name]
    assert normalized_shape(theirs, theirs) == normalized_shape(ours, ours)


def test_typescript_envelope_fields_and_footer_keys(typescript_schemas: dict[str, Any]) -> None:
    from idhazh.contracts import file_envelope
    from idhazh.contracts.feed_health import FeedHealthRow
    from idhazh.contracts.publication_inventory import PublicationEntry, PublicationInventory

    for contract in (
        file_envelope.FileEnvelope,
        file_envelope.WriterIdentity,
        file_envelope.RowIdentity,
        FeedHealthRow,
    ):
        ours = contract.model_json_schema()
        if contract is file_envelope.FileEnvelope:
            ours = file_envelope.FileEnvelope.json_schema()
        elif contract is FeedHealthRow:
            ours = FeedHealthRow.json_schema()
        theirs = typescript_schemas[contract.__name__]
        assert normalized_shape(theirs, theirs) == normalized_shape(ours, ours)
    assert typescript_schemas["__footer_keys"] == list(file_envelope._KEYS)
    assert typescript_schemas["__row_identity_column_versions"] == dict(
        file_envelope.RowIdentity.__column_versions__
    )
    projections = typescript_schemas["__publication_inputs"]
    entry = PublicationEntry.model_json_schema()
    assert normalized_shape(projections["PublicationEntry"], projections["PublicationEntry"]) == (
        normalized_shape(entry, entry)
    )
    native = PublicationInventory.json_schema()
    projected = projections["PublicationInventory"]
    assert typescript_schemas["__publication_input_versions"]["PublicationInventory"] == (
        PublicationInventory.schema_version()
    )
    assert set(projected["properties"]) == {"version", "entries"}
    for name in projected["properties"]:
        ours, theirs = native["properties"][name], projected["properties"][name]
        assert normalized_shape(
            {key: value for key, value in theirs.items() if key != "default"}, projected
        ) == normalized_shape(
            {key: value for key, value in ours.items() if key != "default"}, native
        )


def rejection_payload() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "feed-ingest-rejection" / "empty-feed.json")),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"version": 20261020},
        {"unknown": True},
        {"stage": "screen-article-candidates"},
        {"drop_reason": "FETCH_FAILED_HTTP"},
        {"drop_reason": "FETCH_TIMEOUT"},
        {"rejected_at": "2026-10-20T19:40:00+00:00"},
        {"date": "2026-10-21"},
        {"candidate_id": "a" * 64},
        {"title": "Invented article"},
        {"details": {"words_found": float("inf")}},
        {"details": {"unbounded_map": {}}},
    ],
)
def test_rejection_refuses_invalid_evidence(change: dict[str, Any]) -> None:
    from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord

    with pytest.raises(ValidationError):
        CandidateRejectionRecord.model_validate(rejection_payload() | change)


def test_malformed_candidate_keeps_only_available_identity() -> None:
    from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord

    row = CandidateRejectionRecord.model_validate(
        rejection_payload()
        | {
            "subject": "article",
            "candidate_id": "a" * 64,
            "drop_reason": "MISSING_REQUIRED_FIELDS",
            "title": "Available title",
        }
    )
    assert row.canonical_url is None and row.url_key is None
    assert row.title == "Available title"


def test_article_stub_requires_real_identity_and_threshold() -> None:
    from idhazh.contracts.feed_ingest_candidate import FeedIngestCandidate
    from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord

    candidate = FeedIngestCandidate.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-ingest-candidate" / "one-article.json")
    )
    payload = rejection_payload() | {
        "subject": "article",
        "candidate_id": candidate.candidate_id,
        "canonical_url": candidate.canonical_url,
        "url_key": candidate.url_key,
        "title": candidate.title,
        "stage": "screen-article-candidates",
        "drop_reason": "STUB_CONTENT",
        "details": {"words_found": candidate.word_count, "words_required": 180},
    }
    assert CandidateRejectionRecord.model_validate(payload).details.words_found == 6
    with pytest.raises(ValidationError, match="url_key"):
        CandidateRejectionRecord.model_validate(payload | {"url_key": "a" * 64})
    with pytest.raises(ValidationError, match="words_required"):
        CandidateRejectionRecord.model_validate(payload | {"details": {"words_found": 6}})


def test_candidate_identity_precedes_article_validation() -> None:
    from idhazh.contracts.feed_ingest_candidate import derive_candidate_id

    first = derive_candidate_id("2026-10-20-1", "fixture-feed", 0)
    assert first == derive_candidate_id("2026-10-20-1", "fixture-feed", 0)
    assert first != derive_candidate_id("2026-10-20-1", "fixture-feed", 1)
    with pytest.raises(ValidationError):
        derive_candidate_id("2026-10-20-1", "fixture-feed", -1)


def test_dispatch_keeps_selection_and_content_identity() -> None:
    from idhazh.contracts.feed_ingest_candidate import SourceReliabilityPenalty
    from idhazh.contracts.feed_ingest_dispatch import FeedIngestDispatch
    from idhazh.contracts.feed_ingest_planning_observations import PlanningObservations

    payload = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "feed-ingest-dispatch" / "one-article.json")
    )
    row = FeedIngestDispatch.model_validate(payload)
    assert row.partition.dispatch_count == 1
    assert row.selection.ratings.source_reliability is None
    for partial_feed in (False, True):
        observations = {
            "feed_headline": None,
            "best_weighted_lens": None,
            "watchlist_match": None,
            "salience": [
                {
                    "feed_id": "voter",
                    "available": not partial_feed,
                    "voted": True,
                    "unavailable_reason": "invalid-vote-address" if partial_feed else None,
                },
                {
                    "feed_id": "missing",
                    "available": False,
                    "voted": None,
                    "unavailable_reason": "feed-parse-failed",
                },
            ],
            "salience_available": False,
            "on_front_page": True,
            "salience_unavailable_reason": "salience-feed-unavailable",
        }
        partial = PlanningObservations.model_validate(observations)
        assert partial.on_front_page is True
        assert partial.salience_available is False
        current = row.model_dump(mode="json")
        current["content"]["planning_observations"] = observations
        assert FeedIngestDispatch.model_validate(current).content.planning_observations == partial
        for missing_positive in (None, False):
            with pytest.raises(ValidationError, match="preserve positive votes"):
                PlanningObservations.model_validate(
                    observations | {"on_front_page": missing_positive}
                )
        with pytest.raises(ValidationError, match="cannot prove an absent vote"):
            PlanningObservations.model_validate(
                observations
                | {
                    "salience": [
                        {
                            "feed_id": "voter",
                            "available": False,
                            "voted": False,
                            "unavailable_reason": "invalid-vote-address",
                        }
                    ]
                }
            )
    authority = (
        row.selection.policy.source_authority_weight
        * row.selection.source.weight
        * row.selection.source.applied_tier_weight
    )
    reliability = {
        "enabled": True,
        "source_authority_score": authority,
        "reliability_floor": 0.5,
        "history": {"success_fraction": 0.25, "attempted": 4, "window_days": 7},
        "production_factor": 0.5,
        "value": authority * (1 - 0.5),
    }
    current = row.model_dump(mode="json")
    current["selection"]["ratings"]["source_reliability"] = reliability
    measured = FeedIngestDispatch.model_validate(current)
    assert measured.selection.ratings.source_reliability == (
        SourceReliabilityPenalty.model_validate(reliability)
    )
    assert measured.selection.ratings.base_article_score == row.selection.ratings.base_article_score
    historical = json.loads(json.dumps(payload))
    historical["selection"]["ratings"]["source_reliability"] = reliability
    with pytest.raises(ValidationError, match="declared score contract version"):
        FeedIngestDispatch.model_validate(historical)
    for change in (
        {"production_factor": 0.25},
        {"value": 0},
        {"history": None},
        {"enabled": False},
        {"enabled": "false", "value": 0},
        {"history": {"success_fraction": 0.25, "attempted": 0, "window_days": 7}},
    ):
        with pytest.raises(ValidationError):
            SourceReliabilityPenalty.model_validate(reliability | change)
    assert SourceReliabilityPenalty.model_validate(
        reliability | {"history": None, "production_factor": None, "value": None}
    ).history is None
    assert SourceReliabilityPenalty.model_validate(
        reliability | {"enabled": False, "value": 0}
    ).value == 0
    payload["selection"]["candidate_id"] = "a" * 64
    with pytest.raises(ValidationError, match="candidate_id"):
        FeedIngestDispatch.model_validate(payload)
