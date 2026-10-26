"""Builders and committed-file readers more than one contract module needs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Final

from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts import CONTRACTS, canonical_json
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.base import Contract, derive_url_key
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}

CONFIG_FILES: dict[str, type[Contract]] = {
    "appearance.json": AppearanceConfig,
    "idhazh.json": AppConfig,
    "pipeline-tests.json": PipelineTestsConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}

FIXTURE_FILES: Final = (
    "fetched-document/refused.json",
    "planner-operation/started.json",
    "run-shards/unknown.json",
    "app-config/every-knob-differs-from-the-committed-config.json",
    "appearance-config/knobs-set-away-from-the-defaults.json",
    "article/brief.json",
    "article/fetch-failed.json",
    "article/ok.json",
    "article/truncated.json",
    "collection-prune-row/a-compaction-that-recovered-three-periods.json",
    "collection-prune-row/a-dry-walk-that-counted-past-its-ceiling.json",
    "collection-prune-row/a-live-fold-beside-a-dry-window.json",
    "collection-prune-row/a-live-walk-past-a-member-github-kept.json",
    "collection-prune-row/a-pass-github-did-not-answer.json",
    "collection-prune-row/ceiling-reached.json",
    "collection-prune-row/exhausted-dry-run.json",
    "compact-index/a-daily-index.json",
    "compact-index/a-lost-day.json",
    "compact-index/a-month-with-lost-days.json",
    "compact-index/a-monthly-index.json",
    "compact-index/a-yearly-index.json",
    "compact-index/an-empty-day.json",
    "console-band/newest-day.json",
    "content-similarity-judge-merge-line-holdout-score/a-holdout-retention-has-eaten-into.json",
    "content-similarity-judge-merge-line-holdout-score/a-line-scored-against-the-holdout.json",
    "content-similarity-judge-metrics/a-shard-that-read-its-pairs.json",
    "content-similarity-judge-metrics/a-shard-that-was-dealt-nothing.json",
    "corpus-meta/window.json",
    "corpus-row/harvested.json",
    "council-run-record/a-migrated-count-that-had-nothing-to-do.json",
    "council-run-record/a-part-that-ran-the-model.json",
    "council-run-record/a-part-that-raised.json",
    "council-run-record/a-selection-that-ran-no-model.json",
    "counterfactual-score-row/a-refused-candidate-a-heavier-lens-would-lift.json",
    "counterfactual-score-row/no-lens-matched-so-both-scores-agree.json",
    "day-metrics/full.json",
    "day-metrics/with-label-similarity.json",
    "digest-day/two-runs.json",
    "digest-run-fragment/one-block.json",
    "digest-view/one-day.json",
    "element-table/labelled.json",
    "element-table/regex-only.json",
    "eval-row/determinism-violation.json",
    "eval-row/high.json",
    "eval-row/low-invented-number.json",
    "eval-row/premise-recorded.json",
    "eval-row/truncation-artifact.json",
    "evidence-item/premise-recorded.json",
    "feed-health-row/answered.json",
    "feed-health-row/unreachable.json",
    "feed-retirement-row/answered-and-never-read.json",
    "feed-retirement-row/gone.json",
    "file-envelope/a-monthly-compact-file.json",
    "file-envelope/a-raw-file.json",
    "fitted-similarity-threshold/the-clamp-held-a-fall-back-to-the-step.json",
    "fitted-similarity-threshold/the-record-is-too-small-to-fit-on.json",
    "host-fingerprint-row/a-machine-that-reported-nothing.json",
    "host-fingerprint-row/every-reading-taken.json",
    "host-fingerprint-row/the-clock-a-job-kept.json",
    "icon-manifest/the-committed-set.json",
    "item-health-row/extract-too-short.json",
    "item-health-row/published-with-elements.json",
    "item-health-row/published.json",
    "item-health-row/summarize-model-unreachable.json",
    "item-health-summary-row/nothing-was-timed.json",
    "item-health-summary-row/published-day.json",
    "label-row/supported.json",
    "label-row/unsupported.json",
    "machine-panels/nothing-recorded-this-run.json",
    "machine-panels/three-machines-one-run.json",
    "pipeline-tests-config/the-smallest-list-that-draws.json",
    "publication-inventory/published.json",
    "publication-receipt/completed-writes.json",
    "published-row/one-item.json",
    "raw-day-index/a-json-format-day.json",
    "raw-day-index/a-populated-day.json",
    "raw-day-index/an-empty-day.json",
    "reference-dataset-config/defaults.json",
    "reference-dataset-extractions/extracted.json",
    "reference-dataset-extractions/robots-denied.json",
    "reference-dataset-manifest/newsletter-on-a-shared-platform.json",
    "reference-dataset-metadata/extraction.json",
    "reference-dataset-metadata/import.json",
    "reference-dataset-metadata/selection.json",
    "reference-dataset-row/labelled-by-two-people.json",
    "reference-dataset-row/unlabelled.json",
    "reference-dataset-selection/chosen.json",
    "review-queue/one-of-each-population.json",
    "run-manifest/runs-with-a-gap.json",
    "run-manifest/two-runs.json",
    "run-plan/one-day.json",
    "search-index/one-month.json",
    "seen-row/first-sight.json",
    "similarity-holdout-pair/two-stories-a-person-marked-apart.json",
    "source-health-view/four-facts.json",
    "sources/two-verticals.json",
    "story-candidate-vector-state/generated-new-candidate-only.json",
    "story-candidate-vector-unit/generated-float32-unit.json",
    "story-pinned-encoder-candidate/generated-unknown-legacy-control.json",
    "story-similarity-distribution/a-narrow-band-with-one-day-counted.json",
    "story-similarity-pair/a-headline-match-scores-one.json",
    "story-similarity-pair/judged-the-same-in-both-orders.json",
    "story-similarity-pair/scored-but-not-yet-judged.json",
    "summary/failed.json",
    "summary/ok.json",
    "summary/titled.json",
    "taxonomy/with-tombstones.json",
    "visual-aggregate-row/a-gate-that-refused.json",
    "visual-aggregate-row/a-group-nothing-measured.json",
    "visual-aggregate-row/published-charts.json",
    "visual-attempt-row/nothing-was-measured.json",
    "visual-attempt-row/published-chart.json",
    "visual-attempt-row/refused-by-the-validator.json",
    "visual-data/bars-from-the-committed-plan.json",
    "visual-data/histogram-from-wind.json",
    "visual-data/stacked-bar-from-whole.json",
    "visual-decision/chart-render-failed.json",
    "visual-decision/chart-rendered.json",
    "visual-decision/none-the-gate-refused.json",
    "visual-decision/none.json",
    "visual-plan/bar-chart.json",
    "visual-plan/declined.json",
    "visual-prune-row/fuse-tripped.json",
    "visual-prune-row/policy-off.json",
    "watchlist/seeded.json",
)

#: The three blocks `AppearanceConfig` re-exposes, as (the key
#: `config/idhazh.json` still carries, the key `config/appearance.json` carries).
MOVED_BLOCKS = (("ui", "digest"), ("console", "console"), ("assist", "assist"))

#: Keys `config/idhazh.json` owns although they sit on a moved model, with the
#: reason each one is not the appearance file's to declare. Both are on
#: `AssistConfig` and neither is drawn, so the frontend's own `AssistConfig`
#: interface declares neither. `max_tokens` and `min_readable_letter_share` are
#: the encoder's, read by `backend/idhazh/embed.py`; the appearance file carried
#: a copy of each with the same value until the keep-list stopped the page
#: receiving either, and a copy nothing reads was deleted (2026-09-05).
PIPELINE_OWNED = {
    "max_tokens",
    "min_readable_letter_share",
    # Build-owned rather than pipeline-owned, and on this list for the same
    # reason: the published surface does not draw any of them, so
    # `config/appearance.json` has nothing to say about them. `vite.config.ts`
    # and `svelte.config.js` read them from `config/idhazh.json` at build time
    # and put what a tab needs into the bundle, so they never reach an
    # appearance file or a prerendered document at all.
    "model_base_url",
    "model_cdn_origins",
    "model_digests",
    "model_fetch_deadline_ms",
    "model_revision",
}

#: Dotted paths a config file's model declares but the file must NOT name,
#: because another file owns them. Naming a knob in two files is how one of them
#: goes silent: the frontend merges the appearance block over the legacy one, so
#: the loser is edited and nothing happens (`test_appearance_config.py`).
#:
#: `config/idhazh.json` keeps the three moved blocks only as the read-side
#: migration's middle layer - a file written before 2026-08-29 still resolves to
#: what it used to - so it names what it already named and gains nothing.
CONFIG_NOT_OWNED: dict[str, frozenset[str]] = {
    "idhazh.json": frozenset(legacy for legacy, _ in MOVED_BLOCKS),
    "appearance.json": frozenset(f"assist.{key}" for key in PIPELINE_OWNED),
}


#: The two pages that spell the item-health failure vocabulary out by hand.
DOC_ITEM_HEALTH = REPO_ROOT / "docs" / "architecture" / "sources" / "item-health.md"

DOC_ONE_URL = REPO_ROOT / "docs" / "how-to" / "troubleshoot-one-url.md"


def backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", text))


def paragraph_after(text: str, lead: str) -> str:
    _, found, rest = text.partition(lead)
    assert found, f"the page no longer says {lead!r}"
    return rest.split("\n\n", 2)[1]

# The one `app-config` fixture. Its name is its invariant: every knob in it holds
# a value the committed `config/idhazh.json` does not, so a reader that ignored
# the file and fell back to a default would fail rather than pass.
#
# One knob cannot keep it: `assemble.same_story.cosine_weight` has exactly one
# legal value since the cosine became the whole score, so this file carries the
# committed 1.0 and the validator is what proves a reader cannot ignore it.
APP_CONFIG_EVERY_KNOB_DIFFERS: Final = (
    CONTRACT_FIXTURES_DIR / "app-config" / "every-knob-differs-from-the-committed-config.json"
)

def committed_models_raw() -> dict[str, Any]:
    """The active model's file as bytes on disk, found by following the pointer.

    Never by naming the file. `config/idhazh.json` says which model is active
    and a test that spelled the filename instead would keep passing on the day
    somebody pointed the pointer somewhere else.
    """
    app = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    payload: dict[str, Any] = json.loads(read_text(CONFIG_DIR / app.models_file))
    return payload


def committed_models() -> ModelsConfig:
    """The same file, validated - what `config.load` puts on `Settings.models`."""
    return ModelsConfig.model_validate(committed_models_raw())


def fixture_paths() -> list[Path]:
    """Return named inputs without discovering files as the tree grows."""
    return [CONTRACT_FIXTURES_DIR / name for name in FIXTURE_FILES]


def fixture_id(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


def load(path: Path) -> Contract:
    return BY_STEM[path.parent.name].from_json(read_text(path))


def planner_payload(
    name: str, *, day: str = "2026-10-20", run: int = 1, attempt: int = 1, second: bool = False,
) -> dict[str, Any]:
    """Bounded current planner data; none of these facts comes from retired ledger files."""
    at = f"{day}T10:00:00.123Z"
    clock = f"{day}T10:00:00Z"
    run_id = f"{day}-{run}"
    url = f"https://example.org/article/{int(second)}"
    selected = {
        "run_id": run_id, "attempt": attempt, "date": day,
        "url_key": derive_url_key(url), "feed_id": "second-feed" if second else "fixture-feed",
        "publisher_id": None, "canonical_url": url, "title": "Caf\u00e9 \u6771\u4eac",
        "categories": ["world", "science"], "author": None, "published_at": at,
        "published_at_source": "selection",
        "tier": 1, "weight": 1.0, "applied_tier_weight": 0.5,
        "editorial_rank": int(second) + 1, "estimated_work": 180,
        "worker_assignment": 0, "ratings": {
            "base_article_score": 1.5, "marginal_score": 1.25,
            "adjustments": [
                {"term": "feed-reliability", "value": None},
                {"term": "publisher-exposure", "value": 0.0},
                {"term": "domain", "value": -0.25},
            ],
            "recency_score": 1.0, "feed_authority_score": 0.5,
        },
        "feed_allowance": 3, "exploration_slot": False, "cap_relaxations": [],
        "timing_at": at, "timing_basis": "first_seen", "age_hours": 0.0,
        "allowance_reasons": [],
    }
    if name in {"discovered-articles", "DiscoveredArticleRow"}:
        return {"url_key": derive_url_key(url), "first_seen_at": at, "date": day}
    if name in {"selected-articles", "SelectedArticleRow"}:
        return selected
    if name == "FeedIngestCandidate":
        from idhazh.contracts.feed_ingest_candidate import derive_candidate_id

        feed_id = str(selected["feed_id"])
        return {
            "version": "2026-10-25", "date": day, "correlation_id": "fixture-correlation",
            "run_id": run_id, "candidate_id": derive_candidate_id(run_id, feed_id, int(second)),
            "entry_ordinal": int(second), "source_id": feed_id,
            "source": {
                "source_id": feed_id, "publisher_id": None,
                "feed_url": "https://example.org/feed", "title": "Fixture feed",
                "kind": "reporting", "tier": 1,
                "form": "article", "status": "active", "weight": 1.0, "applied_tier_weight": 0.5,
            },
            "canonical_url": url, "url_key": derive_url_key(url), "title": selected["title"],
            "categories": [], "article_text": "An article with six recorded words.",
            "word_count": 6, "author": None, "published_at": None, "fetched_at": clock,
        }
    if name in {"feed-health-state", "FeedHealthStateRow"}:
        return {
            "feed_id": selected["feed_id"], "endpoint_key": derive_url_key("https://example.org/feed"),
            "checked_at": at, "permission": "allowed", "availability": "eligible",
            "strikes": 0, "rested_runs": 0, "last_failure_code": None, "status": 200,
            "reliability": {
                "productive": 0, "attempted": 0, "success_fraction": None,
                "from_day": None, "through_day": None, "production_factor": None, "complete": False,
            },
            "date": day, "feed_reads": 1, "productive_reads": 1, "failed_reads": 0,
            "article_candidates": 1, "articles_selected": 1, "feed_requests": 2,
            "article_requests": 1, "robots_requests": 0, "counts_complete": True,
            "rejection_counts": [], "run_id": run_id, "attempt": attempt, "items": 1, "outcome": "ok",
        }
    if name in {"plan-runs", "PlanRunRow"}:
        return {
            "run_id": run_id, "started_at": at, "duration_ms": 25, "status": "completed",
            "failure_code": None, "selected_count": 0, "strategy": "none", "dispatch_count": 0,
            "selected_articles_artifact": None, "api_timings": [{
                "operation": "feed-health-before-fetch", "duration_ms": 0, "status": "completed",
            }],
            "date": day, "attempt": attempt, "lifecycle_window_days": 31,
            "reliability_floor": 0.5, "reliability_penalty_enabled": True, "evaluated_at": at,
            "request_report_closed_days": 7, "reliability_window_days": 30,
            "selection_started_at_utc": at,
        }
    if name == "SelectedArticlesArtifact":
        metadata = {key: value for key, value in selected.items() if key not in {"run_id", "attempt", "date"}}
        return {
            "schema_version": "2026-10-26", "run_id": run_id, "attempt": attempt, "date": day,
            "evaluated_at": at, "articles": [metadata | {"article_text": "Sanitized artifact-only text."}],
        }
    if name == "PlannerFileEnvelope":
        return {
            "version": "2026-10-25", "row_schema_version": "2026-10-25",
            "tier": "raw", "ledger": "selected-articles", "covers": day, "period": None,
            "file_id": "00000000-0000-8000-8000-000000000001", "content_sha256": "a" * 64,
            "writer": "idhazh.ledger.parquet", "writer_version": "fixture-engine",
            "compression": "snappy", "updated_at": None,
        }
    context = {
        "now": clock, "captured_at": at, "date": day, "run_id": run_id,
        "correlation_id": "00000000-0000-4000-8000-000000000001",
        "writer": {
            "run_id": run_id, "attempt": attempt, "job": None,
            "pipeline_name": "feed-ingest-plan", "task_name": "plan", "shard": 0,
            "producer": "tests.planner", "git_sha": "a" * 40,
        },
    }
    batch = {
        "version": "2026-10-25", "batch_id": "00000000-0000-4000-8000-000000000002",
        "config_sha256": "a" * 64, "context": context,
    }
    if name == "ParsedFeedBatch":
        return batch | {
            "request": {}, "candidates": [], "observations": {},
            "seen": {"availability": "available", "rows": []}, "evidence": {},
            "history_rows": [], "history_days": [], "work_rows": [], "exclusions": [],
        }
    batch |= {
        "version": "2026-10-26",
        "parsed_batch_id": "00000000-0000-4000-8000-000000000003",
        "selection_started_at_utc": clock, "evaluated_at": clock,
        "articles": [], "health_rows": [], "exclusions": [],
        "request_report": {"from_day": day, "through_day": day, "complete": False, "feeds": []},
    }
    if name == "SelectedFeedBatch":
        return batch
    if name == "PartitionedFeedBatch":
        return batch | {
            "selection_batch_id": "00000000-0000-4000-8000-000000000004",
            "strategy": "none", "dispatch_count": 1, "work": [0.0],
        }
    raise ValueError(f"No generated current planner payload for {name}")


def copy_config(root: Path, *, models: dict[str, Any] | None = None) -> str:
    """The config loader's named inputs, with the active model file replaced.

    Copy only the files `config.load` consumes, not unrelated declarations.

    Returns the pointer the copy carries, which is the path a refusal has to
    name and the value a swap has to move.
    """
    target = root / "config"
    pointer = str(AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models_file)
    for name in (
        "idhazh.json",
        "ledgers.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
        "llm_council.json",
        "judges/content-similarity-judge.json",
        pointer,
    ):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONFIG_DIR / name, destination)
    if models is not None:
        (target / pointer).write_text(canonical_json(models), encoding="utf-8", newline="\n")
    return pointer


def entry_with(**fields: Any) -> dict[str, Any]:
    """The committed entry with some of its own fields edited, as raw JSON.

    Built off the committed file rather than written out here, so a required
    field added to the entry later fails these tests at the edit that added it
    rather than leaving them asserting against a shape nothing declares.
    """
    payload = committed_models_raw()
    payload["summarizer"] |= fields
    return payload


def swapped_summarizer() -> dict[str, Any]:
    """The committed model file with `summarize` pointed at other weights.

    Every field an operator edits to swap a model IN PLACE, and nothing else.
    Since 2026-09-14 that is no longer the swap an operator makes - a swap is a
    second file and one pointer line - but it is still the edit this refusal
    exists to catch, because it is what somebody does when they mean to move
    fast in the file they already have open.
    """
    raw = committed_models_raw()
    raw["summarizer"] |= {
        "id": "some-other-model-q4-k-m",
        "repo": "someone/Other-GGUF",
        "file": "Other-Q4_K_M.gguf",
        "revision": "f" * 40,
        "sha256": "1" * 64,
        "hf_base_repo": None,
    }
    return raw


def desk(**overrides: Any) -> dict[str, Any]:
    """One vertical of a plan, spelled the way an earlier build wrote it."""
    return {"id": "ai", "considered": 40, "planned": 5, "live_feeds": 3, **overrides}


def taxonomy_fixture(stem: str) -> Taxonomy:
    """One of the two fixture vocabularies the definition oracle is driven from."""
    return Taxonomy.from_json(read_text(FIXTURES_DIR / "taxonomy" / f"{stem}.json"))


def mutate(path: Path, **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(read_text(path))
    payload.update(changes)
    return payload


#: The five the planning step computes and the day payload started carrying on
#: 2026-08-31. Every day published before that omits all five.
RANKING_SIGNAL = ("carried_by", "watchlist_hit", "on_front_page", "rank_score", "time_source")


def a_day_missing(names: tuple[str, ...], where: str = "items") -> tuple[str, int]:
    """The committed-day fixture with `names` removed from every `where` entry.

    The read-side migration each of these checks is a property of one payload
    (`CLAUDE.md` section 11), and the committed tree was parsed once per
    published day to re-ask it. Worse, each of those walks counted how many
    entries still LACK the field and failed at zero - a fuse timed to the day the
    last unmigrated payload ages out of retention, which is a date rather than a
    change. Removing the keys here cannot age out.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    stripped = 0
    for entry in payload[where]:
        for name in names:
            entry.pop(name, None)
        stripped += 1
    return json.dumps(payload), stripped
