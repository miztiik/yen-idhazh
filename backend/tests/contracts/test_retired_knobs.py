"""Is a config still spelling a knob this build removed refused by name?"""

from __future__ import annotations

import pytest
from conftest import CONFIG_DIR
from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.collect import SUPERSEDED_COLLECT_NAMES, CollectConfig
from idhazh.contracts.knobs.observability import SUPERSEDED_RETENTION_NAMES, ObservabilityConfig

pytestmark = pytest.mark.contract


def test_a_config_still_carrying_a_removed_knob_is_refused_by_name() -> None:
    """Decision 2: a removed knob fails loudly and names what to use instead.

    Every model here forbids unknown keys, so all three names already failed -
    with "extra inputs are not permitted", which does not tell an operator where
    their number went. Ignoring the key would be worse still: an edit that takes
    no effect is a value somebody believes.

    The old value is not carried forward either. `keep_months` was set against a
    check that compared `months * 30` against the console window instead of the
    shards that window selects, so honouring it would honour the defect.
    """
    for block, removed, successor in (
        (
            "observability",
            "keep_months",
            "series.full-grain.value in config/gardener/telemetry-aggregate.json",
        ),
        (
            "observability",
            "hard_delete_after_months",
            "series.aggregate in config/gardener/telemetry-aggregate.json",
        ),
        ("collect", "quarantine_after_failures", "availability_strikes_before_rest"),
    ):
        model = ObservabilityConfig if block == "observability" else CollectConfig
        with pytest.raises(ValidationError) as raised:
            model.model_validate({removed: 13})
        assert f"{block}.{removed}" in str(raised.value)
        assert successor in str(raised.value)


def test_an_age_whose_store_is_gone_says_so_instead_of_naming_a_successor() -> None:
    """The ledgers these three governed were deleted, so there is nowhere to send the value.

    `refuse_a_removed_knob` reads an empty replacement as "gone and nothing
    replaces it". Pointing the two ages at the scores task's window would be
    worse than silence: that window governs `state/scores/`, which is still there,
    so an operator would move their number onto a live ledger's age. And
    `runtime_counters_scrape` switched off a row in a ledger that no longer
    exists, so honouring it today would switch off nothing at all.
    """
    for removed, value in (
        ("public_scores_keep_months", 13),
        ("public_feed_health_keep_months", 13),
        ("runtime_counters_scrape", False),
    ):
        with pytest.raises(ValidationError, match="nothing replaces it") as raised:
            ObservabilityConfig.model_validate({removed: value})
        assert f"observability.{removed}" in str(raised.value)


def test_every_removed_name_is_sent_somewhere_or_said_to_be_gone() -> None:
    """The map is what the refusal message reads, so it is the map that is asserted.

    Every cleanup age that left `observability` went to the declaration of the
    gardener task that spends it, so its replacement names that file.
    """
    assert dict(SUPERSEDED_COLLECT_NAMES) == {
        "quarantine_after_failures": "availability_strikes_before_rest"
    }
    gone = {"public_scores_keep_months", "public_feed_health_keep_months", "runtime_counters_scrape"}
    assert {name for name, successor in SUPERSEDED_RETENTION_NAMES.items() if not successor} == gone
    for name, successor in SUPERSEDED_RETENTION_NAMES.items():
        if successor:
            assert " in config/gardener/" in successor and successor.endswith(".json"), (
                f"observability.{name} is sent to {successor!r}, which names no declaration"
            )


def test_an_unrelated_knob_in_a_block_with_no_removed_name_is_untouched() -> None:
    """The refusal fires on the removed name and on nothing else."""
    assert ObservabilityConfig.model_validate({"sample_rate": 0.5}).sample_rate == 0.5
    assert CollectConfig.model_validate({"max_per_source": 3}).max_per_source == 3


def test_the_prune_block_is_refused_naming_both_collection_declarations() -> None:
    """The two collections' ages left for the declarations of the tasks that prune them.

    An old local config that still carries the block would otherwise fail with
    "extra inputs are not permitted", and its operator would not know the age
    they set now lives in two files under `config/gardener/`.
    """
    old = {
        "collections": {"workflow-artifacts": {"retain_days": 30, "max_deletes_per_run": 50}},
        "dry_run": True,
    }
    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate({"prune": old})
    refusal = str(raised.value)
    assert "config.prune is now window.value in config/gardener/workflow-artifacts.json" in refusal
    assert "config/gardener/workflow-runs.json" in refusal
    for successor in ("workflow-artifacts", "workflow-runs"):
        assert (CONFIG_DIR / "gardener" / f"{successor}.json").is_file(), successor
