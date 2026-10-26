"""Do current planner payloads and their strict TypeScript copies agree?"""

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

from ._fixtures import planner_payload

pytestmark = pytest.mark.contract

CONTRACT_NAMES = (
    ("feed_ingest_candidate", "FeedIngestCandidate"),
    ("planner_operation", "FetchedDocument"),
    ("planner_operation", "PlannerOperation"),
    ("planner_stage", "ParsedFeedBatch"),
    ("planner_stage", "SelectedFeedBatch"),
    ("planner_stage", "PartitionedFeedBatch"),
    ("feed_ingest_discovered_article", "DiscoveredArticleRow"),
    ("feed_ingest_selected_article", "SelectedArticleRow"),
    ("feed_ingest_selected_article", "SelectedArticlesArtifact"),
    ("feed_health_state", "FeedHealthStateRow"),
    ("feed_ingest_plan_run", "PlanRunRow"),
    ("file_envelope", "PlannerFileEnvelope"),
)
MODEL_NAMES = (
    ("feed_ingest_candidate", "SourceSnapshot"),
    ("planner_stage", "PlannerStageContext"),
    ("planner_stage", "PlannerStageRequest"),
    ("planner_stage", "RecordedIdentity"),
    ("planner_stage", "PrimaryEvidence"),
    ("planner_stage", "PlannerArticleEvidence"),
    ("planner_stage", "PlannerFeedEntry"),
    ("planner_stage", "PlannerFeedOffer"),
    ("planner_stage", "PreflightFreshness"),
    ("planner_stage", "PlannerHarvestObservation"),
    ("planner_stage", "PlannerSeenAvailable"),
    ("planner_stage", "PlannerSeenUnavailable"),
    ("planner_stage", "PlannerRejectionCount"),
    ("planner_stage", "PlannerHealthDay"),
    ("planner_stage", "PlannerRequestReport"),
    ("planner_stage", "SelectedArticleContent"),
    ("planner_stage", "StageReferenceRequest"),
    ("planner_stage", "PartitionArticlesRequest"),
    ("feed_ingest_selected_article", "SelectedArticleMetadata"),
    ("feed_ingest_selected_article", "SelectedArtifactArticle"),
    ("feed_ingest_selected_article", "SelectedArticleRatings"),
    ("feed_ingest_selected_article", "SelectedArticleAdjustment"),
    ("feed_health_state", "FeedHealthReliability"),
    ("feed_health_state", "FeedHealthRejectionCount"),
    ("feed_ingest_plan_run", "PlanApiTiming"),
)


@pytest.mark.parametrize(("module", "name"), CONTRACT_NAMES)
def test_declared_contract(module: str, name: str) -> None:
    """The current row format is closed; retired payloads never acquire a migration."""
    import idhazh.contracts
    from idhazh.contracts.feed_ingest_discovered_article import PlannerRow

    expected = Path.cwd() / "backend" / "idhazh" / "contracts"
    assert Path(idhazh.contracts.__file__).parent.resolve() == expected.resolve()
    contract = getattr(importlib.import_module(f"idhazh.contracts.{module}"), name)
    assert contract.json_schema()["additionalProperties"] is False
    if name == "FetchedDocument":
        payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "fetched-document" / "refused.json"))
        old = contract.model_validate(payload)
        assert old.parent_fetch_request_id is None and old.parent_batch_id is None
        assert old.entry_ordinal is None and old.version == payload["version"]
        linked = contract.model_validate(payload | {
            "version": "2026-10-26",
            "parent_fetch_request_id": "00000000-0000-4000-8000-000000000010",
            "parent_batch_id": "00000000-0000-4000-8000-000000000011",
            "entry_ordinal": 1,
        })
        assert str(linked.parent_batch_id) == "00000000-0000-4000-8000-000000000011"
        with pytest.raises(ValidationError):
            contract.model_validate(payload | {"version": "2026-10-25"})
    if name == "PlannerOperation":
        payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "planner-operation" / "started.json"))
        current = contract.model_validate(payload | {
            "version": "2026-10-26", "created_at": "2026-10-20T12:00:00.123Z",
        })
        assert current.created_at == "2026-10-20T12:00:00.123Z"
        assert contract.model_validate(payload | {
            "version": "2026-10-23T18:50", "created_at": current.created_at,
        }).created_at == current.created_at
        with pytest.raises(ValidationError, match="whole-second"):
            contract.model_validate(payload | {
                "version": "2026-10-23T09:22", "created_at": current.created_at,
            })
    if module == "planner_stage" or name == "FeedIngestCandidate":
        assert contract.schema_version() == "2026-10-25"
    else:
        assert contract in (*idhazh.contracts.CONTRACTS, *idhazh.contracts.PLANNER_CONTRACTS)
    if name not in {"FetchedDocument", "PlannerOperation"}:
        payload = planner_payload(name)
        row = contract.model_validate(payload)
        assert contract.model_validate_json(row.to_json()) == row
        with pytest.raises(ValidationError):
            contract.model_validate(payload | {"unexpected": {"hidden": "payload"}})
        if issubclass(contract, PlannerRow) and name != "SelectedArticlesArtifact":
            assert "version" not in contract.model_fields
            for forbidden in (
                "version", "schema_version", "ledger", "covers", "unit_id", "git_sha",
                "identity", "job", "pipeline_name", "task_name", "shard", "producer",
                "article_text", "evaluated_at", "vertical", "labels", "policy",
            ):
                if name == "PlanRunRow" and forbidden == "evaluated_at":
                    continue
                assert forbidden not in contract.model_fields
                with pytest.raises(ValidationError):
                    contract.model_validate(payload | {forbidden: "not-a-declared-cell"})
        if module == "planner_stage" or name == "FeedIngestCandidate":
            with pytest.raises(ValidationError):
                contract.model_validate(payload | {"version": "2026-10-24"})
        if name == "ParsedFeedBatch":
            assert row.offers == [] and row.feed_fetch_request_id is None and row.input_complete
            source = planner_payload("FeedIngestCandidate")["source"]
            offered = contract.model_validate(payload | {
                "input_complete": False, "offers": [{
                    "offer_id": "f" * 64, "source": source,
                    "entry": {
                        "entry_ordinal": 1, "title": None, "link": "https://example.org/offered",
                        "categories": [], "author": None, "published_at": None,
                    },
                    "state": "pending", "fetch_request_id": None,
                }],
            })
            assert len(offered.offers) == 1 and not offered.input_complete
        if name == "FeedHealthStateRow":
            work_only = payload | {
                "date": "2026-10-21", "checked_at": None, "items": None, "outcome": None,
                "reliability": None, "feed_reads": 0, "productive_reads": 0,
                "feed_requests": 0, "article_requests": 2,
            }
            assert contract.model_validate(work_only).counts_complete
            partial = work_only | {"counts_complete": False, "article_requests": None}
            assert contract.model_validate(partial).article_requests is None
            with pytest.raises(ValidationError):
                contract.model_validate(work_only | {"article_requests": None})
            with pytest.raises(ValidationError):
                contract.model_validate(payload | {"feed_requests": 0.5})
        if name == "DiscoveredArticleRow":
            with pytest.raises(ValidationError):
                contract.model_validate(payload | {"date": "2026-10-21"})
        if name == "PlanRunRow":
            assert row.selected_count == 0 and row.selected_articles_artifact is None
            failed_before_selection = contract.model_validate(payload | {
                "status": "failed", "failure_code": "fetch-failed", "dispatch_count": 0,
                "selection_started_at_utc": None,
            })
            assert failed_before_selection.selection_started_at_utc is None
            resumed = contract.model_validate(payload | {"duration_ms": None})
            assert resumed.duration_ms is None
            with pytest.raises(ValidationError, match="duration_ms"):
                contract.model_validate({key: value for key, value in payload.items() if key != "duration_ms"})
            with pytest.raises(ValidationError):
                contract.model_validate(payload | {"duration_ms": 0.5})
            for reference in (
                "https://example.org/signed?token=secret", "/tmp/a.json",
                "C:\\tmp\\a.json", "../a.json", "a/../a.json", "./a.json",
                "a//b.json", "a\nb.json",
            ):
                with pytest.raises(ValidationError):
                    contract.model_validate(payload | {"selected_articles_artifact": reference})
            assert contract.model_validate(payload | {
                "selected_articles_artifact": "backend/var/run/selected-articles.json",
            }).selected_articles_artifact == "backend/var/run/selected-articles.json"
        if name == "PlannerFileEnvelope":
            for forbidden in ("identity", "unit_id", "run_id", "job", "shard", "producer", "git_sha"):
                with pytest.raises(ValidationError):
                    contract.model_validate(payload | {forbidden: "retired-audit-metadata"})
            assert contract.from_metadata(row.as_metadata()) == row
            with pytest.raises(ValueError, match="undeclared keys"):
                contract.from_metadata(row.as_metadata() | {b"unit_id": b"retired"})


def test_typescript_provenance_is_declared() -> None:
    from idhazh.contracts.file_envelope import FileEnvelope, PlannerFileEnvelope

    for model in (FileEnvelope, PlannerFileEnvelope):
        assert "idhazh_typescript.ledger.parquet" in model.json_schema()["properties"]["writer"]["enum"]


@pytest.fixture(scope="module")
def typescript_schemas() -> dict[str, Any]:
    bun = shutil.which("bun")
    assert bun, "Install Bun to run the shared contract binding gate"
    completed = subprocess.run(
        [bun, "run", "test/schema-binding.ts"], cwd=REPO_ROOT / "packages" / "common-contracts",
        text=True, capture_output=True, check=True,
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
        return ("enum", tuple(sorted(json.dumps(value) for value in node["enum"])), node.get("default", "<required>"))
    branches = node.get("anyOf", node.get("oneOf"))
    if branches is not None:
        return (
            "union", tuple(sorted((normalized_shape(branch, root) for branch in branches), key=repr)),
            node.get("default", "<required>"),
        )
    kind = node.get("type")
    if isinstance(kind, list):
        return normalized_shape({
            "anyOf": [{"type": value} for value in kind],
            **{key: value for key, value in node.items() if key != "type"},
        }, root)
    if kind == "object":
        if "patternProperties" in node:
            patterns = node["patternProperties"]
            if len(patterns) == 1:
                pattern, value = next(iter(patterns.items()))
                return ("record", pattern, normalized_shape(value, root), node.get("default", "<required>"))
            return (
                "record", tuple(sorted((pattern, normalized_shape(value, root)) for pattern, value in patterns.items())),
                node.get("additionalProperties", False), node.get("default", "<required>"),
            )
        if "properties" not in node and isinstance(node.get("additionalProperties"), dict):
            return (
                "record", node.get("propertyNames", {}).get("pattern"),
                normalized_shape(node["additionalProperties"], root), node.get("default", "<required>"),
            )
        assert node.get("additionalProperties") is False, "Objects must reject unknown fields"
        required = set(node.get("required", []))
        return (
            "object", {name: (name in required, normalized_shape(child, root)) for name, child in node["properties"].items()},
            node.get("default", "<required>"),
        )
    if kind == "array":
        return ("array", normalized_shape(node["items"], root), node.get("default", "<required>"))
    assert kind in {"string", "integer", "number", "boolean", "null"}, node
    return (kind, node.get("default", "<required>"))


@pytest.mark.parametrize(
    ("module", "name"),
    (*CONTRACT_NAMES, ("feed_ingest_diagnostics", "ExtractionQuality"), *MODEL_NAMES, ("planner_stage", "PlannerSeenEvidence")),
)
def test_typescript_field_types_defaults_and_vocabularies(
    module: str, name: str, typescript_schemas: dict[str, Any],
) -> None:
    loaded = importlib.import_module(f"idhazh.contracts.{module}")
    if name == "PlannerSeenEvidence":
        from pydantic import TypeAdapter

        ours = TypeAdapter(loaded.PlannerSeenEvidence).json_schema()
        theirs = typescript_schemas["__planner_stage_schemas"][name]
    elif name == "ExtractionQuality" or (module, name) in MODEL_NAMES:
        ours = getattr(loaded, name).model_json_schema()
        theirs = typescript_schemas[name]
    else:
        ours = getattr(loaded, name).json_schema()
        theirs = typescript_schemas[name]
    assert normalized_shape(theirs, theirs) == normalized_shape(ours, ours)


def test_typescript_envelope_fields_and_footer_keys(typescript_schemas: dict[str, Any]) -> None:
    from idhazh.contracts import file_envelope
    from idhazh.contracts.base import Contract
    from idhazh.contracts.feed_health import FeedHealthRow
    from idhazh.contracts.publication_inventory import PublicationEntry, PublicationInventory

    # Other-family historical identity and publication bindings stay unchanged.
    with pytest.raises(ValidationError, match="curated publisher identity requires its declared contract version"):
        FeedHealthRow.model_validate({"version": "2026-10-23T18:50", "publisher_id": "recorded-publication"})
    for contract in (
        file_envelope.FileEnvelope, file_envelope.PlannerFileEnvelope,
        file_envelope.WriterIdentity, file_envelope.RowIdentity, FeedHealthRow,
    ):
        ours = contract.json_schema() if issubclass(contract, Contract) else contract.model_json_schema()
        theirs = typescript_schemas[contract.__name__]
        assert normalized_shape(theirs, theirs) == normalized_shape(ours, ours)
    assert typescript_schemas["__footer_keys"] == list(file_envelope._KEYS)
    assert typescript_schemas["__planner_footer_keys"] == list(file_envelope.PLANNER_FOOTER_KEYS)
    assert set(typescript_schemas["__planner_optional_footer_keys"]) == file_envelope.PLANNER_OPTIONAL_FOOTER_KEYS
    versions = typescript_schemas["__envelope_versions"]
    assert len(versions) == len(set(versions))
    assert set(versions) == set(file_envelope._ENVELOPE_VERSIONS)
    assert typescript_schemas["__file_envelope_version"] == file_envelope.FileEnvelope.schema_version()
    assert typescript_schemas["__row_identity_column_versions"] == dict(file_envelope.RowIdentity.__column_versions__)
    projections = typescript_schemas["__publication_inputs"]
    entry = PublicationEntry.model_json_schema()
    assert normalized_shape(projections["PublicationEntry"], projections["PublicationEntry"]) == normalized_shape(entry, entry)
    native = PublicationInventory.json_schema()
    projected = projections["PublicationInventory"]
    assert typescript_schemas["__publication_input_versions"]["PublicationInventory"] == PublicationInventory.schema_version()
    assert set(projected["properties"]) == {"version", "entries"}
    for name in projected["properties"]:
        ours, theirs = native["properties"][name], projected["properties"][name]
        assert normalized_shape({key: value for key, value in theirs.items() if key != "default"}, projected) == normalized_shape(
            {key: value for key, value in ours.items() if key != "default"}, native,
        )


def rejection_payload() -> dict[str, Any]:
    return {
        "reason_code": "STUB_CONTENT", "count": 1, "subject": "article",
        "stage": "screen-article-candidates", "attribution": None,
    }


@pytest.mark.parametrize("change", [
    {"version": 20261020}, {"unknown": True}, {"stage": ""},
    {"reason_code": ""}, {"count": -1}, {"count": 0.5}, {"count": None},
    {"subject": "request"}, {"attribution": "invented"},
    {"candidate_id": "a" * 64}, {"article_text": "must not persist"},
    {"details": {"words_found": float("inf")}}, {"details": {"unbounded_map": {}}},
])
def test_rejection_refuses_invalid_evidence(change: dict[str, Any]) -> None:
    from idhazh.contracts.feed_health_state import FeedHealthRejectionCount

    with pytest.raises(ValidationError):
        FeedHealthRejectionCount.model_validate(rejection_payload() | change)


def test_malformed_candidate_keeps_only_available_identity() -> None:
    from idhazh.contracts.feed_health_state import FeedHealthRejectionCount

    row = FeedHealthRejectionCount.model_validate(rejection_payload())
    assert set(row.model_dump()) == {"reason_code", "count", "subject", "stage", "attribution"}
    assert row.attribution is None


def test_article_stub_requires_real_identity_and_threshold() -> None:
    from idhazh.contracts.feed_ingest_candidate import FeedIngestCandidate

    candidate = FeedIngestCandidate.model_validate(planner_payload("FeedIngestCandidate"))
    payload = candidate.model_dump(mode="json")
    assert candidate.word_count == 6
    with pytest.raises(ValidationError, match="url_key"):
        FeedIngestCandidate.model_validate(payload | {"url_key": "a" * 64})
    with pytest.raises(ValidationError, match="word_count"):
        FeedIngestCandidate.model_validate(payload | {"word_count": -1})
    with pytest.raises(ValidationError):
        FeedIngestCandidate.model_validate(payload | {"policy": {"min_words_article": 180}})
    with pytest.raises(ValidationError):
        FeedIngestCandidate.model_validate(payload | {"vertical": "world"})
    with pytest.raises(ValidationError):
        FeedIngestCandidate.model_validate(payload | {"source": payload["source"] | {"vertical": "world"}})


def test_candidate_identity_precedes_article_validation() -> None:
    from idhazh.contracts.feed_ingest_candidate import derive_candidate_id

    first = derive_candidate_id("2026-10-20-1", "fixture-feed", 0)
    assert first == derive_candidate_id("2026-10-20-1", "fixture-feed", 0)
    assert first != derive_candidate_id("2026-10-20-1", "fixture-feed", 1)
    with pytest.raises(ValidationError):
        derive_candidate_id("2026-10-20-1", "fixture-feed", -1)


def test_dispatch_keeps_selection_and_content_identity() -> None:
    from idhazh.contracts.feed_ingest_selected_article import (
        SelectedArticleRow,
        SelectedArticlesArtifact,
        selected_article_metadata,
    )

    artifact = SelectedArticlesArtifact.model_validate(planner_payload("SelectedArticlesArtifact"))
    original = artifact.to_json()
    metadata = selected_article_metadata(artifact.articles[0])
    assert "article_text" not in type(metadata).model_fields
    row = SelectedArticleRow.model_validate(metadata.model_dump(mode="json") | {
        "run_id": artifact.run_id, "attempt": artifact.attempt, "date": artifact.date,
    })
    assert row.url_key == artifact.articles[0].url_key
    assert [term.value for term in row.ratings.adjustments] == [None, 0.0, -0.25]
    future = SelectedArticleRow.model_validate(row.model_dump(mode="json") | {
        "timing_at": "2026-10-20T11:00:00Z", "timing_basis": "published_at", "age_hours": -1.0,
    })
    assert future.age_hours == -1.0
    with pytest.raises(ValidationError):
        SelectedArticleRow.model_validate(row.model_dump(mode="json") | {"timing_basis": "fetched_at"})
    metadata.categories.append("not-shared")
    metadata.ratings.adjustments[0].value = 0.5
    assert artifact.to_json() == original
    with pytest.raises(ValidationError):
        SelectedArticleRow.model_validate(row.model_dump(mode="json") | {"article_text": "must not persist"})
