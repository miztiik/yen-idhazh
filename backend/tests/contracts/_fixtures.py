"""Builders and committed-file readers more than one contract module needs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts import CONTRACTS, canonical_json
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.base import Contract
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
    "app-config/every-knob-differs-from-the-committed-config.json",
    "appearance-config/knobs-set-away-from-the-defaults.json",
    "article/brief.json",
    "article/fetch-failed.json",
    "article/ok.json",
    "article/truncated.json",
    "collection-prune-row/a-live-fold-beside-a-dry-window.json",
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
    "council-shard-outcome/a-unit-that-ran-no-model.json",
    "council-shard-outcome/a-unit-that-stopped-on-its-own-clock.json",
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
    "machine-shard-row/a-shard-both-instruments-reached.json",
    "machine-shard-row/a-shard-that-kept-nothing.json",
    "observation-batch/one-measurement.json",
    "observation-index-row/one.json",
    "observation-lookup-page/one-child.json",
    "observation-lookup-receipt/already-recorded.json",
    "observation-lookup-root/empty.json",
    "observation-lookup-transaction/initialization.json",
    "observation-preparation/one-batch.json",
    "pipeline-tests-config/the-smallest-list-that-draws.json",
    "public-run-day/five-runs.json",
    "public-telemetry/fetch-failed.json",
    "public-telemetry/published.json",
    "publication-inventory/published.json",
    "published-row/one-item.json",
    "qualification-report/qualified.json",
    "qualification-samples/two-samples.json",
    "qualification-shard/one-shard.json",
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
    "run-timeline-row/died-at-fetch.json",
    "run-timeline-row/every-step.json",
    "search-index/one-month.json",
    "seen-row/first-sight.json",
    "similarity-holdout-pair/two-stories-a-person-marked-apart.json",
    "source-health-view/four-facts.json",
    "sources/two-verticals.json",
    "story-similarity-distribution/a-narrow-band-with-one-day-counted.json",
    "story-similarity-pair/a-headline-match-scores-one.json",
    "story-similarity-pair/judged-the-same-in-both-orders.json",
    "story-similarity-pair/scored-but-not-yet-judged.json",
    "summary/failed.json",
    "summary/ok.json",
    "summary/titled.json",
    "taxonomy/with-tombstones.json",
    "validation-row/confirmed.json",
    "validation-row/not-reported.json",
    "visual-aggregate-row/a-gate-that-refused.json",
    "visual-aggregate-row/a-group-nothing-measured.json",
    "visual-aggregate-row/published-charts.json",
    "visual-attempt-row/nothing-was-measured.json",
    "visual-attempt-row/published-chart.json",
    "visual-attempt-row/refused-by-the-validator.json",
    "visual-data/bars-from-the-committed-plan.json",
    "visual-decision/chart-render-failed.json",
    "visual-decision/chart-rendered.json",
    "visual-decision/none-the-gate-refused.json",
    "visual-decision/none.json",
    "visual-plan/bar-chart.json",
    "visual-plan/declined.json",
    "visual-prune-row/fuse-tripped.json",
    "visual-prune-row/policy-off.json",
    "watchlist/seeded.json",
    "watermark/a-daily-watermark.json",
    "watermark/a-monthly-watermark.json",
    "watermark/a-yearly-watermark.json",
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


def copy_config(root: Path, *, models: dict[str, Any] | None = None) -> str:
    """The config loader's named inputs, with the active model file replaced.

    Copy only the files `config.load` consumes, not unrelated declarations.

    Returns the pointer the copy carries, which is the path a refusal has to
    name and the value a swap has to move.
    """
    target = root / "config"
    pointer = str(AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models_file)
    for name in ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json", "appearance.json", pointer):
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
