"""Do feed planning contracts and their strict TypeScript copies agree?"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

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
    from idhazh.contracts.feed_ingest_dispatch import FeedIngestDispatch

    payload = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "feed-ingest-dispatch" / "one-article.json")
    )
    row = FeedIngestDispatch.model_validate(payload)
    assert row.partition.dispatch_count == 1
    payload["selection"]["candidate_id"] = "a" * 64
    with pytest.raises(ValidationError, match="candidate_id"):
        FeedIngestDispatch.model_validate(payload)
