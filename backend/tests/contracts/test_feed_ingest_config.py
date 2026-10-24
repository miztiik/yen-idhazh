"""Do Python and TypeScript accept the same authored planning policies?"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from conftest import REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.knobs import feed_ingest

pytestmark = pytest.mark.contract

MODEL_NAMES = (
    "FeedScreeningPolicy", "FeedPenaltyWeights", "FeedCurationPolicy",
    "FeedScreeningPatch", "FeedPenaltyWeightsPatch", "FeedCurationPatch",
    "VerticalPolicyOverride", "PlanningRunOverrides", "EffectiveFeedPolicy",
    "FeedHarvestConfig", "FeedTriageConfig", "FeedSoftCaps", "FeedCurateConfig",
    "FeedPartitionConfig", "FeedSealConfig", "FeedWorkflowReportingConfig",
    "FeedMetricsConfig", "FeedIngestConfig", "PlanningTaxonomy",
)


@pytest.fixture(scope="module")
def typescript_schemas() -> dict[str, Any]:
    bun = shutil.which("bun")
    assert bun, "Install Bun and restore packages/common-contracts dependencies for config binding"
    completed = subprocess.run(
        [bun, "run", "test/config.test.ts", "--emit-schemas"],
        cwd=REPO_ROOT / "packages" / "common-contracts",
        capture_output=True, text=True, check=True,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def input_shape(node: dict[str, Any], root: dict[str, Any]) -> Any:
    """Compare every field, bound and vocabulary, resolving only local schema references."""
    if "$ref" in node:
        target = root
        assert node["$ref"].startswith("#/"), node["$ref"]
        for name in node["$ref"][2:].split("/"):
            target = target[name]
        return input_shape(target, root)
    ignored = {"title", "description", "$schema", "$defs"}
    result = {key: value for key, value in node.items() if key not in ignored}
    if "const" in result:
        result["enum"] = [result.pop("const")]
    if "enum" in result:
        result["enum"] = sorted(result["enum"])
    if "required" in result:
        result["required"] = sorted(result["required"])
    for name in ("anyOf", "oneOf"):
        if name in result:
            result[name] = sorted((input_shape(branch, root) for branch in result[name]), key=repr)
    if "properties" in result:
        result["properties"] = {
            key: input_shape(value, root) for key, value in result["properties"].items()
        }
    if "patternProperties" in result:
        # Pydantic emits string-key validation as patternProperties; Zod uses propertyNames.
        (pattern, value), = result.pop("patternProperties").items()
        result["propertyNames"] = {"type": "string", "pattern": pattern}
        result["additionalProperties"] = input_shape(value, root)
    for name in ("items", "propertyNames", "additionalProperties"):
        if isinstance(result.get(name), dict):
            result[name] = input_shape(result[name], root)
    if result.get("additionalProperties") is True:
        result.pop("additionalProperties")
    return result


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_config_reader_binding(name: str, typescript_schemas: dict[str, Any]) -> None:
    model = getattr(feed_ingest, name)
    assert Path(feed_ingest.__file__).resolve() == (
        REPO_ROOT / "backend" / "idhazh" / "contracts" / "knobs" / "feed_ingest.py"
    ).resolve()
    ours = model.model_json_schema(mode="validation")
    theirs = typescript_schemas[name]
    assert input_shape(ours, ours) == input_shape(theirs, theirs)


def config_payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(read_text(REPO_ROOT / "config" / "feed-ingest-plan.json")))


def test_python_authored_config_and_config_only_vertical_extension() -> None:
    payload = config_payload()
    payload["triage"].update({
        "min_words_article": 181,
        "min_words_abstract": 61,
        "max_age_hours": 25,
        "recency_half_life_hours": 19,
    })
    payload["curate"]["article_limit"] = 101
    taxonomy_payload = json.loads(read_text(REPO_ROOT / "config" / "taxonomy.json"))
    taxonomy = feed_ingest.PlanningTaxonomy.model_validate(taxonomy_payload)
    config = feed_ingest.FeedIngestConfig.model_validate(payload)
    config.validate_verticals(taxonomy)
    assert config.triage.min_words_article == payload["triage"]["min_words_article"]
    assert config.triage.min_words_abstract == payload["triage"]["min_words_abstract"]
    assert config.triage.max_age_hours == payload["triage"]["max_age_hours"]
    assert config.triage.recency_half_life_hours == payload["triage"]["recency_half_life_hours"]
    assert config.workflow_reporting.enabled
    assert config.curate.article_limit == payload["curate"]["article_limit"]
    assert config.curate.source_reliability_penalty_enabled
    previous = dict(payload["curate"])
    previous.pop("source_reliability_penalty_enabled")
    assert feed_ingest.FeedCurateConfig.model_validate(previous).source_reliability_penalty_enabled
    assert not feed_ingest.FeedCurateConfig.model_validate(
        payload["curate"] | {"source_reliability_penalty_enabled": False}
    ).source_reliability_penalty_enabled

    taxonomy_payload["verticals"].append(dict(taxonomy_payload["verticals"][0], id="oceans"))
    payload["vertical_overrides"] = {
        "oceans": {"triage": {"max_age_hours": 12}, "curate": {"mmr_weights": {"lambda_lens": 0}}},
    }
    extended = feed_ingest.FeedIngestConfig.model_validate(payload)
    extended.validate_verticals(feed_ingest.PlanningTaxonomy.model_validate(taxonomy_payload))
    assert extended.vertical_overrides["oceans"].model_dump(exclude_unset=True) == {
        "triage": {"max_age_hours": 12}, "curate": {"mmr_weights": {"lambda_lens": 0}},
    }
    with pytest.raises(ValueError, match=r"vertical_overrides\.oceans"):
        extended.validate_verticals(taxonomy)


@pytest.mark.parametrize("patch", [
    {"triage": {"min_words_article": 0}},
    {"triage": {"min_words_article": "180"}},
    {"triage": {"min_words_abstract": 1.5}},
    {"triage": {"max_age_hours": None}},
    {"triage": {"max_age_hours": float("inf")}},
    {"triage": {"recency_weight": -1}},
    {"curate": {"source_authority_weight": True}},
    {"curate": {"mmr_weights": {"lambda_lens": float("nan")}}},
    {"curate": {"mmr_weights": {"lambda_lens": None}}},
    {"curate": {"base_source_allowance": -1}},
    {"curate": {"soft_caps": {"max_source_share": 0.2}}},
    {"curate": {"source_reliability_penalty_enabled": False}},
    {"triage": {"blocked_http_statuses": []}},
    {"harvest": {"concurrency": 1}},
    {"desk_overrides": {}},
])
def test_python_refuses_invalid_or_global_only_patch(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        feed_ingest.VerticalPolicyOverride.model_validate(patch)


@pytest.mark.parametrize("value", [0, -1, "12", None, True, float("nan"), float("inf")])
def test_python_refuses_invalid_run_override(value: Any) -> None:
    with pytest.raises(ValidationError, match="freshness_hours"):
        feed_ingest.PlanningRunOverrides.model_validate({"freshness_hours": value})


def test_python_refuses_invalid_global_settings_and_duplicate_references() -> None:
    payload = config_payload()
    patches: tuple[dict[str, Any], ...] = (
        {"partition": dict(payload["partition"], default_shards=9)},
        {"partition": dict(payload["partition"], min_shards=9)},
        {"curate": dict(payload["curate"], article_limit=0)},
        {"curate": dict(payload["curate"], article_limit=1.5)},
        {"curate": dict(payload["curate"], source_reliability_penalty_enabled="true")},
        {"curate": dict(payload["curate"], source_reliability_penalty_enabled=None)},
        {"harvest": dict(payload["harvest"], concurrency="24")},
        {"desk_overrides": {}},
    )
    for patch in patches:
        with pytest.raises(ValidationError):
            feed_ingest.FeedIngestConfig.model_validate(payload | patch)
    with pytest.raises(ValidationError, match="duplicate ids"):
        feed_ingest.PlanningTaxonomy.model_validate({"verticals": [{"id": "ai"}, {"id": "ai"}]})
