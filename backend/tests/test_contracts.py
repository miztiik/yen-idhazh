"""Contract-tier tests: the generated schemas against the models that produced
them, and the models against real committed payloads.

No mocks and no network (Rule #7): every input here is a file in
`tests/fixtures/` or `config/`.
"""

from __future__ import annotations

import ast
import csv
import json
import logging
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    REPO_ROOT,
    SCHEMAS_DIR,
    read_text,
)
from pydantic import ValidationError

from idhazh import ledger, source_health
from idhazh.cli import main, stage_validate_days
from idhazh.contracts import canonical_json, derive_url_key
from idhazh.contracts.app_config import (
    SUPERSEDED_COLLECT_NAMES,
    SUPERSEDED_RETENTION_NAMES,
    AppConfig,
    CollectConfig,
    ConsoleConfig,
    EvaluationConfig,
    ObservabilityConfig,
    PageWeightConfig,
    UiConfig,
    VisualSide,
    months_a_window_can_touch,
)
from idhazh.contracts.appearance_config import AppearanceConfig, ChartConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestVerticalRef, DigestVisual
from idhazh.contracts.digest_view import DigestView, DigestViewItem, DigestViewVisual
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.item_health import (
    FAILURE_CODE_STAGES,
    SOURCE_NEUTRAL_FAILURE_CODES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.route import Route
from idhazh.contracts.run_manifest import RunManifest, VerticalCount
from idhazh.contracts.run_plan import RunPlan, TimeSource, VerticalPlan
from idhazh.contracts.runtime_counters import SERIES, RuntimeCountersRow
from idhazh.contracts.sources import Sources
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.watchlist import EntityKind, Watchlist
from idhazh.fingerprint import text_digest
from idhazh.publish_telemetry import PUBLIC_COLUMNS
from idhazh.retention import oldest_month_kept
from utilities import build_canary_day

pytestmark = pytest.mark.contract

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}
CONFIG_FILES: dict[str, type[Contract]] = {
    "idhazh.json": AppConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}
LONG_HEX = re.compile(r"[0-9a-f]{16,}")
#: Four real `GET /metrics` bodies, one per work shard of run `2026-08-26-5`,
#: pulled from that run's `runtime-log-*` artifacts before they expired. Real
#: captures rather than hand-written text (Rule #7): the upstream README at tag
#: b10598 lists neither `prompt_tokens_cached_total` nor the wording that says
#: what `prompt_tokens_total` counts, so only the binary's own output settles it.
METRICS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))
#: The memory sampler's own files and the head of llama-server's own log, one
#: pair per work shard of run `2026-08-29-3`, pulled from that run's
#: `runtime-log-*` artifacts before they expired. Real captures for the same
#: reason the metrics bodies are: the timestamp llama.cpp stamps a log line with
#: is four dot-separated numbers whose units no page states, and only a real
#: capture of a job whose length is known settles which is which.
RSS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.rss-samples.tsv"))
SERVER_LOG_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.server-head.txt"))
#: One real `/proc/stat` pair, twenty seconds apart, captured on a GitHub-hosted
#: `ubuntu-latest` runner on 2026-08-30. The gap is what makes it an oracle: the
#: tick delta has to reproduce twenty seconds of four processors at 100 Hz, and
#: no hand-written file can be checked that way.
PROC_STAT_AT_START = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-start.txt"
PROC_STAT_AT_END = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-end.txt"
#: What the probe slept for, what the runner reported to `nproc`, and the
#: kernel's tick rate. Rule #2 fixes the second at 4.
PROBE_SECONDS = 20
PROBE_PROCESSORS = 4
USER_HZ = 100
#: The two pages that spell the item-health failure vocabulary out by hand.
DOC_ITEM_HEALTH = REPO_ROOT / "docs" / "architecture" / "sources" / "item-health.md"
DOC_ONE_URL = REPO_ROOT / "docs" / "how-to" / "troubleshoot-one-url.md"


def backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", text))


def paragraph_after(text: str, lead: str) -> str:
    _, found, rest = text.partition(lead)
    assert found, f"the page no longer says {lead!r}"
    return rest.split("\n\n", 2)[1]


def fixture_paths() -> list[Path]:
    return sorted(CONTRACT_FIXTURES_DIR.glob("*/*.json"))


def fixture_id(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


def load(path: Path) -> Contract:
    return BY_STEM[path.parent.name].from_json(read_text(path))


# --- The Oracle: round-trip ------------------------------------------------


@pytest.mark.parametrize("path", fixture_paths(), ids=fixture_id)
def test_fixture_round_trips_byte_identically(path: Path) -> None:
    """Serialize, validate, deserialize, re-serialize - same bytes."""
    text = read_text(path)
    once = load(path).to_json()
    assert once == text
    twice = BY_STEM[path.parent.name].from_json(once).to_json()
    assert twice == once


def test_every_contract_has_at_least_one_fixture() -> None:
    covered = {path.parent.name for path in fixture_paths()}
    assert covered == set(BY_STEM), "a contract without a fixture has never been proven to load"


# --- The drift gate --------------------------------------------------------


def test_committed_schemas_match_the_models(tmp_path: Path) -> None:
    export(tmp_path)
    for contract in CONTRACTS:
        name = contract.schema_filename()
        assert read_text(SCHEMAS_DIR / name) == read_text(tmp_path / name), (
            f"{name} is stale - edit the Pydantic model and regenerate, never the schema"
        )


def test_schemas_directory_holds_exactly_the_generated_files() -> None:
    on_disk = {path.name for path in SCHEMAS_DIR.glob("*.json")}
    assert on_disk == expected_filenames()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_schema_is_self_describing(contract: type[Contract]) -> None:
    schema: dict[str, Any] = json.loads(read_text(SCHEMAS_DIR / contract.schema_filename()))
    assert schema["$id"] == contract.schema_filename(), "$id is a relative filename, never a URL"
    assert schema["version"] == schema["changelog"][0]["version"]
    versions = [entry["version"] for entry in schema["changelog"]]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    for entry in schema["changelog"]:
        assert entry["change"] and entry["why"]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_version_defaults_to_the_newest_changelog_entry(contract: type[Contract]) -> None:
    assert contract.schema_version() == contract.__changelog__[0].version


def test_an_older_payload_still_validates() -> None:
    """A payload yesterday's run wrote must load today, or it is a release blocker."""
    path = CONTRACT_FIXTURES_DIR / "summary" / "ok.json"
    payload = json.loads(read_text(path))
    payload["version"] = "2026-01-01"
    assert load_summary(payload).version == "2026-01-01"


def load_summary(payload: dict[str, Any]) -> Contract:
    return BY_STEM["summary"].model_validate(payload)


def test_a_payload_written_before_a_field_existed_still_reads() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    A payload from before the summarizer wrote titles has no `title` key at all.
    It must still load, and its committed `output_digest` must still verify -
    which it does because a null title is left out of the digested payload
    rather than digested as null.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["title"]
    assert load_summary(payload).title is None  # type: ignore[attr-defined]


def test_version_is_stamped_when_a_writer_omits_it() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["version"]
    assert load_summary(payload).version == BY_STEM["summary"].schema_version()


# --- Config ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CONFIG_FILES), ids=lambda n: n)
def test_config_file_validates(name: str) -> None:
    CONFIG_FILES[name].from_json(read_text(CONFIG_DIR / name))


def test_a_fresh_clone_runs_on_the_defaults() -> None:
    """Every knob but the model refs has a default, so an empty config is usable."""
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    minimal = AppConfig.model_validate({"models": committed.models.model_dump()})
    assert minimal.run.safety_ceiling_per_run == committed.run.safety_ceiling_per_run
    assert minimal.retention.image_months == -1, "retention ships disabled"
    assert minimal.retention.dry_run is True


def test_the_runtime_counters_are_on_without_being_asked_for() -> None:
    """A run that did not count is a run that cannot say how close it came.

    `n_ctx` is 8192 and llama-server publishes the high watermark only under
    `--metrics`. Off by default would mean the number exists on the runs nobody
    thought to switch it on for, which is every ordinary day.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    models = committed.models.model_dump()
    del models["inference"]
    fresh = AppConfig.model_validate({"models": models})

    assert fresh.models.inference.metrics is True, "a fresh clone must count"
    assert committed.models.inference.metrics is True, "the committed config must count"


def test_the_console_chart_size_is_a_knob_the_frontend_agrees_with() -> None:
    """A prerendered chart has no element to measure, so the size is given to it.

    Three copies of one number, and the test has to hold the two that decide the
    picture. Until 2026-09-05 it held the wrong pair: it compared the contract
    default against `config/idhazh.json` and then against the frontend's own
    fallback, and all three were 600 - while every console page drew at 760,
    because `consoleConfig()` merges `config/appearance.json` last and that file
    said 760. A green gate over three copies of a number nothing draws with is
    worse than no gate, because it reads as coverage.

    So the resolved value leads. `config/appearance.json` is the last merge
    layer, so what it declares is what the server draws at, and a clone with no
    `config/` has to draw the same picture - which means the contract default
    and the frontend's fallback have to be that same number, or a first paint
    somewhere is at a width nothing measured.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    fresh = ConsoleConfig()
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")

    for field in ("chart_width", "chart_height"):
        shipped = getattr(drawn, field)
        assert getattr(fresh, field) == shipped, (
            f"config/appearance.json draws a console chart at {field}={shipped} and a "
            f"clone with no config/ would draw it at {getattr(fresh, field)}"
        )
        mirrored = re.search(rf"{field}:\s*(\d+)", reader)
        assert mirrored is not None, f"the frontend console defaults dropped {field}"
        assert int(mirrored.group(1)) == shipped, (
            f"the frontend's own {field} fallback is {mirrored.group(1)} and the "
            f"console draws at {shipped}"
        )


def test_a_console_chart_may_not_be_narrower_than_its_own_labels() -> None:
    with pytest.raises(ValueError):
        AppConfig.model_validate({"console": {"chart_width": 0}})


def test_the_window_the_console_opens_on_is_one_the_control_can_name() -> None:
    """A default outside the preset list opens the page on a window nothing selects.

    The control is four radio buttons, so a span that is not one of them leaves
    every button unchecked and the operator with no way back to what he is
    looking at.
    """
    with pytest.raises(ValidationError, match="window_presets"):
        ConsoleConfig(default_window_days=21)

    tuned = ConsoleConfig(default_window_days=21, window_presets=[7, 21, 60])
    assert tuned.default_window_days in tuned.window_presets


def test_a_preset_list_that_is_out_of_order_or_out_of_bounds_is_refused() -> None:
    """The presets are the only way the page sets its span.

    So `min_window_days` and `max_window_days` have no other reader, and a
    preset outside them would make both knobs decorative.
    """
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[30, 7, 90], default_window_days=30)
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[7, 7, 30], default_window_days=30)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[3, 30], default_window_days=30)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[30, 400], default_window_days=30)


def test_the_console_window_presets_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem the chart size has, one field along.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. If the two lists drift, the page draws a button for a window the
    contract would refuse.

    The committed list leads for the same reason it does above: it is the last
    merge layer, so it is the list the control really offers. Measured
    2026-09-05, all three copies read `[7, 14, 30, 90]` - unlike the chart size,
    this one had not drifted.
    """
    offered = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    assert offered.window_presets == ConsoleConfig().window_presets, (
        "config/appearance.json offers a window list a clone with no config/ would not"
    )

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"window_presets:\s*\[([\d,\s]+)\]", reader)
    assert mirrored is not None, "the frontend console defaults dropped window_presets"
    assert [int(part) for part in mirrored.group(1).split(",")] == offered.window_presets


def test_the_readout_cap_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem again, in the chart block.

    The cap is applied in the browser, off the frontend's own copy. Let the two
    drift and the browser test asserts one number while the contract bounds a
    different one, which is a gate that passes for the wrong reason.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"readout_max_share:\s*([\d.]+)", reader)
    assert mirrored is not None, "the frontend chart defaults dropped readout_max_share"
    assert float(mirrored.group(1)) == ChartConfig().readout_max_share


def test_the_seed_the_shell_carries_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on the one digest knob a browser never sees.

    `shell_seed_items` decides how many of a day's stories a prerendered
    document carries, so the build reads it on its own rather than through
    `uiConfig()` - everything that reader returns is inlined into every
    document, and no page reads this number. Two copies of it drift like any
    other pair, and a drift here would put a different number of stories in a
    document than the contract bounds.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const SHELL_SEED_ITEMS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its shell_seed_items fallback"
    assert int(mirrored.group(1)) == UiConfig().shell_seed_items


def test_the_leading_block_is_a_knob_the_frontend_agrees_with() -> None:
    """The third digest knob a browser never sees, and the newest of the three.

    A dated document's seed is the head of the day UNION its leads, because a
    lead is chosen across the whole day and need not sit inside a prefix. So
    this number is the second term of what that document may carry, and
    `frontend/tests/payload-weight.spec.ts` reads it as the bound. A drift here
    would bound a dated document at a count the contract never agreed to.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const LEADING_STORIES = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its leading_stories fallback"
    assert int(mirrored.group(1)) == UiConfig().leading_stories


def test_the_days_the_archive_lists_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on another digest knob a browser never sees.

    `archive_recent_days` decides how many days the archive lists as rows of
    their own before the months take over, so the build reads it on its own
    rather than through `uiConfig()`. A drift here would put a different number
    of days on the page than the contract bounds, and on a clone with no
    `config/` there is nothing else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const ARCHIVE_RECENT_DAYS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its archive_recent_days fallback"
    assert int(mirrored.group(1)) == UiConfig().archive_recent_days


def test_the_side_a_figure_sits_on_is_a_knob_the_frontend_agrees_with() -> None:
    """The knob nothing reads yet, pinned to the position the page renders.

    `visual_side` sat in both config files with two different values for a
    week, and nothing caught it because no component branches on it - the
    fallback merge just took one and dropped the other. It is reserved rather
    than dead: a figure gets a column of its own when the render spec is handed
    the width it will occupy (docs/concepts/design-system.md), and until then a
    default that names a position the page does not draw is a wrong answer
    waiting for a reader.

    So the three copies are checked against each other in one place: the
    contract's default, the frontend's fallback for a clone with no `config/`,
    and what `DigestItem.svelte` puts after what.
    """
    assert UiConfig().visual_side is VisualSide.TRAILING

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    block = re.search(r"const DEFAULTS: UiConfig = \{(.*?)\};", reader, re.DOTALL)
    assert block is not None, "config.ts no longer declares a DEFAULTS block"
    mirrored = re.search(r"visual_side:\s*'(\w+)',", block.group(1))
    assert mirrored is not None, "the frontend dropped its visual_side default"
    assert mirrored.group(1) == UiConfig().visual_side.value

    card = read_text(
        REPO_ROOT / "frontend" / "src" / "lib" / "components" / "DigestItem.svelte"
    )
    assert card.index("<ItemVisual") > card.index("data-item-summary"), (
        "the card draws its figure before the summary, so `trailing` is the wrong default"
    )


def test_the_wait_worth_a_sentence_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem on the one digest knob only a browser reads.

    `payload_slow_ms` bounds a wait that happens in a reader's browser, so a
    fresh clone with no config file resolves it from the frontend's own copy.
    Let the two drift and the sentence about a slow day fires at a moment the
    contract does not bound - and on a clone with no `config/` there is nothing
    else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"payload_slow_ms:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its payload_slow_ms default"
    assert int(mirrored.group(1)) == UiConfig().payload_slow_ms


def test_the_seed_covers_what_a_reading_surface_draws_before_a_reader_acts() -> None:
    """The seed is what a document holds once the rest of the day arrives by fetch.

    Every lead is an anchor into the stream, so a document that carries fewer
    stories than the leading block holds is a block whose links scroll to
    nothing. That is the floor, and it is not the whole answer: the leads are
    chosen across the WHOLE day, so a lead can sit at position 300 of the
    published order and outside any prefix. Whichever row moves the item list
    to a browser fetch owns that, and this is the number it starts from.
    """
    ui = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).ui
    assert ui.shell_seed_items >= ui.leading_stories, (
        f"a {ui.shell_seed_items}-story seed cannot hold {ui.leading_stories} leads"
    )


def test_a_shared_subject_is_worth_less_than_a_second_feed_carrying_the_story() -> None:
    """Decision 3's ceiling, derived rather than spelled.

    A second trade-press carrier of one address multiplies that story's
    authority by `1 + repetition_weight`, which on the committed config is a
    flat 0.6 added to the score. A recurring subject must not outrank a story
    two independent feeds carried today, so the shared-subject term stays under
    it. Measured 2026-09-01 over 11 committed days: a second carrier fires on
    4.49 percent of the stories that record one and a shared subject on 12.85
    percent, so the commoner signal is the one that has to be worth less.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    collect = committed.collect
    second_carrier = collect.tier_weights.trade_press * collect.repetition_weight
    assert committed.ui.lead_shared_subject_weight < second_carrier, (
        f"a shared subject is worth {committed.ui.lead_shared_subject_weight} against "
        f"{second_carrier} for a second trade-press carrier"
    )
    assert UiConfig().lead_shared_subject_weight < second_carrier


def test_a_leading_block_that_could_never_draw_is_refused() -> None:
    """A floor above the ceiling fails silently: the block never appears."""
    with pytest.raises(ValidationError, match="leading_min"):
        UiConfig(leading_stories=3, leading_min=4)
    with pytest.raises(ValidationError, match="leading_per_desk"):
        UiConfig(leading_stories=3, leading_per_desk=4)


def test_a_reject_ceiling_under_the_brief_gate_is_refused() -> None:
    """The one edit that would silence a gate instead of tightening it.

    A refused item writes no score, so it leaves the corpus `brief_copying_ceiling`
    reads. Drop the reject to the gate's own number and every item the gate could
    have failed is gone before it looks - the gate stops failing, which reads
    exactly like a pipeline that stopped copying.
    """
    gate = EvaluationConfig().brief_compression_ceiling
    for silenced in (gate, gate / 2):
        with pytest.raises(ValidationError):
            EvaluationConfig(verbatim_reject_ceiling=silenced)
    assert EvaluationConfig(verbatim_reject_ceiling=gate + 0.01).verbatim_reject_ceiling > gate


def test_the_committed_reject_ceiling_leaves_the_brief_gate_a_live_band() -> None:
    """0.75 against a 0.5 gate, so (0.5, 0.75] is a band the gate can still fail in."""
    evaluation = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).evaluation
    assert evaluation.verbatim_reject_ceiling == 0.75
    assert evaluation.brief_compression_ceiling == 0.5


def test_a_fresh_clone_measures_itself_and_the_committed_config_agrees() -> None:
    """Every instrument is on unconfigured, and the committed file did not turn one off.

    Written as an agreement between two configs rather than as three literals: a
    default that is asserted by value is a test that fails the day somebody
    legitimately changes it, which teaches people to edit the test.

    Tracing is the exception and is asserted by value, because its default is
    the claim: a span tree is the one instrument nothing reads, so it stays off
    until a developer asks for it and CI never builds one.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    fresh = AppConfig.model_validate({"models": committed.models.model_dump()})

    assert fresh.observability == committed.observability
    assert fresh.observability.evaluation_enabled
    assert fresh.observability.telemetry_publish
    assert fresh.observability.runtime_counters_scrape
    assert not fresh.observability.tracing_enabled


def test_the_item_health_census_is_not_switchable() -> None:
    """The denominator under every rate this project publishes has no off switch.

    Turning the census off would not thin a measurement, it would make every
    other measurement unreadable - a failure rate with no denominator beside it
    is the exact defect the census exists to prevent. The guard is the switch
    list itself, so adding a fifth boolean fails here and has to be argued for.

    `tracing_enabled` was the fourth, added 2026-08-30. The argument it had to
    make: it switches an instrument nothing else divides by. No page reads a
    span, no gate consults one, and every rate the console prints still has its
    denominator with tracing off - which is not true of any of the other three
    in the same way, and is why it was allowed to be off by default.
    """
    switches = {
        name
        for name, field in ObservabilityConfig.model_fields.items()
        if field.annotation is bool
    }
    assert switches == {
        "evaluation_enabled",
        "telemetry_publish",
        "runtime_counters_scrape",
        "tracing_enabled",
    }
    assert "census" in (ObservabilityConfig.__doc__ or "")


def test_a_sample_rate_of_zero_is_refused_because_the_toggle_already_says_off() -> None:
    """Two ways to say off is how two ways of saying it end up disagreeing."""
    for refused in (0.0, -0.1, 1.1):
        with pytest.raises(ValidationError):
            ObservabilityConfig(sample_rate=refused)
    assert ObservabilityConfig(sample_rate=1.0).sample_rate == 1.0


def test_a_month_may_not_be_deleted_before_it_has_been_downsampled() -> None:
    """A summary has to outlive the full-grain window it replaces, both times."""
    fresh = ObservabilityConfig()
    for summary, full_grain in (
        ("item_health_aggregate_keep_months", "item_health_full_grain_months"),
        ("score_archive_keep_months", "scores_full_grain_months"),
    ):
        keep = getattr(fresh, full_grain)
        for early in (keep, keep - 1):
            with pytest.raises(ValidationError, match=summary):
                ObservabilityConfig(**{summary: early})
        assert ObservabilityConfig(**{summary: keep + 1}) is not None


def test_every_cleanup_age_outlives_the_shards_a_console_read_selects() -> None:
    """The check the old `keep_months` never made, and the reason 13 was wrong.

    `console.max_window_days` is 366, and `ledger.shards_in_window` walks 367
    inclusive days - so a window ending on the first of a month can start on the
    last day of another and open **14** month files. The retired check compared
    `months * 30` against the window, which passed 13 while a reader could still
    ask for a fourteenth shard.
    """
    window = ConsoleConfig().max_window_days
    shards = months_a_window_can_touch(window)
    assert window == 366
    assert shards == 14, "a 366-day read reaches fourteen month shards, not thirteen"
    assert 13 * 30 > window, "the retired check passed 13, which is the whole point"

    fresh = ObservabilityConfig()
    assert set(fresh.full_grain_months()) == {
        "item_health_full_grain_months",
        "feed_health_keep_months",
        "scores_full_grain_months",
        "public_telemetry_keep_months",
    }
    models = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models.model_dump()
    for name, months in fresh.full_grain_months().items():
        assert months >= shards, f"observability.{name} is shorter than a console read"
        short = {name: months - 1}
        # The projection and its source ledger are held equal by their own rule,
        # so lowering either one has to lower both to reach this check.
        if name in {"item_health_full_grain_months", "public_telemetry_keep_months"}:
            short = {
                "item_health_full_grain_months": months - 1,
                "public_telemetry_keep_months": months - 1,
            }
        with pytest.raises(ValidationError, match=name):
            AppConfig.model_validate({"models": models, "observability": short})


def test_the_published_copy_lasts_exactly_as_long_as_the_ledger_it_copies() -> None:
    """Either way round leaves a month nothing can answer for."""
    for skew in (-1, 1):
        with pytest.raises(ValidationError, match="public_telemetry_keep_months"):
            ObservabilityConfig(
                item_health_full_grain_months=20, public_telemetry_keep_months=20 + skew
            )
    assert (
        ObservabilityConfig(
            item_health_full_grain_months=20, public_telemetry_keep_months=20
        ).public_telemetry_keep_months
        == 20
    )


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
        ("observability", "keep_months", "item_health_full_grain_months"),
        ("observability", "hard_delete_after_months", "item_health_aggregate_keep_months"),
        ("collect", "quarantine_after_failures", "availability_strikes_before_rest"),
    ):
        model = ObservabilityConfig if block == "observability" else CollectConfig
        with pytest.raises(ValidationError, match=successor) as raised:
            model.model_validate({removed: 13})
        assert f"{block}.{removed}" in str(raised.value)


def test_the_removed_names_are_the_three_this_row_retired() -> None:
    """The map is what the refusal message reads, so it is the map that is asserted."""
    assert dict(SUPERSEDED_COLLECT_NAMES) == {
        "quarantine_after_failures": "availability_strikes_before_rest"
    }
    assert dict(SUPERSEDED_RETENTION_NAMES) == {
        "keep_months": "item_health_full_grain_months",
        "hard_delete_after_months": "item_health_aggregate_keep_months",
    }


def test_an_unrelated_knob_in_a_block_with_no_removed_name_is_untouched() -> None:
    """The refusal fires on the removed name and on nothing else."""
    assert ObservabilityConfig.model_validate({"sample_rate": 0.5}).sample_rate == 0.5
    assert CollectConfig.model_validate({"max_per_source": 3}).max_per_source == 3


def test_never_hard_deleting_is_the_default_a_reader_gets() -> None:
    """A summary costs kilobytes and is what makes a year-over-year claim citable."""
    fresh = ObservabilityConfig()
    assert fresh.item_health_aggregate_keep_months is None
    assert fresh.score_archive_keep_months is None


def test_the_committed_config_no_longer_emits_a_removed_name() -> None:
    """The Oracle: the committed file loads, and no lifecycle value is defaulted.

    Defaulted is the failure to catch. A knob deleted from the file and never
    re-spelled under its new name would still load - on the contract's default -
    and nothing would say the operator's number had gone.
    """
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert not set(raw["observability"]) & set(SUPERSEDED_RETENTION_NAMES)
    assert not set(raw["collect"]) & set(SUPERSEDED_COLLECT_NAMES)
    assert raw["observability"]["item_health_full_grain_months"] == 14
    assert raw["observability"]["public_telemetry_keep_months"] == 14

    for successor in (*SUPERSEDED_COLLECT_NAMES.values(), "availability_rest_runs"):
        assert successor in raw["collect"], f"collect.{successor} is defaulted, not set"
    loaded = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    assert loaded.collect.availability_strikes_before_rest == 5


def test_the_rest_rule_reads_the_knob_the_committed_config_spells() -> None:
    """The rename cost the pipeline nothing, and this is where that is checked.

    `discover.resting` took `collect.quarantine_after_failures` until
    2026-09-03. The committed file carried 5 under both names and the tuned
    fixture carried 3 under both, so moving the reader could not move a
    decision - and that is the difference between a rename and a change of
    behaviour.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).collect
    tuned = AppConfig.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "app-config" / "tuned.json")
    ).collect
    assert committed.availability_strikes_before_rest == 5
    assert tuned.availability_strikes_before_rest == 3

    source = read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py")
    assert "after_failures=collect.availability_strikes_before_rest" in source


def test_the_console_falls_back_to_the_strike_count_the_pipeline_reads() -> None:
    """The console keeps its own copy of this knob, and nothing held the two together.

    `frontend/src/lib/server/config.ts` names the field it reads out of
    `config/idhazh.json` and the value it uses when there is no file. A rename
    on either side is silent: the console would fall back to its default and
    draw a rule the run does not follow, and no build would fail. This is the
    gate that was missing when the knob was renamed.
    """
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    declared = re.search(r"const COLLECT_DEFAULTS: CollectConfig = \{(.*?)\};", source, re.DOTALL)
    assert declared is not None, "config.ts no longer declares COLLECT_DEFAULTS"
    fallback = dict(re.findall(r"(\w+):\s*(\d+)", declared.group(1)))

    fresh = CollectConfig()
    assert fallback == {"availability_strikes_before_rest": str(fresh.availability_strikes_before_rest)}
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["collect"]
    for name, value in fallback.items():
        assert str(committed[name]) == value, (
            f"config.ts falls back to collect.{name} = {value} and the committed file says "
            f"{committed[name]}"
        )
    for removed in SUPERSEDED_COLLECT_NAMES:
        assert removed not in source, f"config.ts still reads collect.{removed}"


def test_no_configured_age_deletes_a_shard_a_366_day_read_still_selects() -> None:
    """The oracle: every end date in one 400-year Gregorian cycle.

    A cleanup age is only right if, on every day it could ever run, the oldest
    month it keeps is at or before the oldest month the reader opens. The
    calendar repeats every 400 years, so sweeping one cycle is exhaustive rather
    than a sample - 146,097 end dates, which is every arrangement of leap years,
    month lengths and weekday offsets that can occur.

    The sweep uses the oldest day the window reaches instead of walking all 367
    days per date, and the first thousand dates prove the two agree, so the
    shortcut is checked rather than assumed.
    """
    window = ConsoleConfig().max_window_days
    span = timedelta(days=window)
    start = date(2000, 1, 1)
    cycle = (date(2400, 1, 1) - start).days
    assert cycle == 146_097, "one Gregorian cycle is 146,097 days"

    for offset in range(1000):
        anchor = start + timedelta(days=offset)
        walked = min(ledger.shards_in_window(anchor.isoformat(), window))
        assert walked == (anchor - span).isoformat()[:7]

    kept = ObservabilityConfig().item_health_full_grain_months
    too_short = 0
    for offset in range(cycle):
        anchor = start + timedelta(days=offset)
        oldest_read = (anchor - span).isoformat()[:7]
        assert oldest_month_kept(anchor, kept) <= oldest_read, (
            f"{kept} months on {anchor.isoformat()} keeps back to "
            f"{oldest_month_kept(anchor, kept)}, and the console still reads {oldest_read}"
        )
        if oldest_month_kept(anchor, kept - 1) > oldest_read:
            too_short += 1

    assert too_short > 0, (
        "one month less has to fail somewhere, or the value is not the minimum"
    )


def test_a_config_written_before_observability_existed_still_reads() -> None:
    """Section 11's release blocker: yesterday's file has no such key at all."""
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    del payload["observability"]
    assert AppConfig.model_validate(payload).observability == ObservabilityConfig()


def test_the_committed_config_carries_the_capped_routes() -> None:
    """`frontend/scripts/bundle-gate.mjs` reads the file, never the model, and
    the model default is empty - so the committed config is the only place the
    capped routes live. If it lost them the gate would check nothing while every
    other knob still read correctly.

    `/archive/` is capped again since 2026-08-27, because it stopped inlining the
    day payloads and now grows by one day link a day. The assertion below is on
    its size rather than on its presence: a ceiling at the megabyte the page used
    to weigh is a gate that never fires, so the number has to stay in the
    thousands. The three `/console/` routes are capped for the same reason - the
    regression a page ceiling exists to catch on that surface is a day payload
    inlined by a layout, which cost 313,300 gzipped bytes when it last happened,
    so a ceiling more than that above the page could never see it land again.

    All three console routes are asserted, and that is the point of splitting
    them: one key over three surfaces still fails when any of them grows and
    cannot say which one did, so the operator raises the shared number and the
    regression lands under it.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    ceilings = committed.page_weight.ceilings_bytes

    assert PageWeightConfig().ceilings_bytes == {}, "the model default must stay empty"
    assert ceilings["/404"] > 0
    assert ceilings["/evals/"] > 0
    assert ceilings["/archive/"] < 100_000, (
        "the archive ceiling is back above the weight of the payloads row #4 removed - "
        "a ceiling that high never fires again"
    )
    for route in ("/console/", "/console/model/", "/console/machine/"):
        assert route in ceilings, (
            f"{route} is a prerendered route with no ceiling - the bundle gate reports "
            "an unnamed route without failing it, so this one would grow unwatched"
        )
        assert ceilings[route] < 433_000, (
            f"the ceiling on {route} is above the heaviest console document plus the "
            "313,300 a day payload cost when a layout last inlined one - a ceiling that "
            "high cannot catch the one regression this surface has actually had"
        )


def test_a_page_ceiling_bounds_a_route_and_bounds_it_above_zero() -> None:
    """A ceiling of zero passes nothing and a key that is not a route bounds nothing."""
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(ceilings_bytes={"/evals/": 0})
    with pytest.raises(ValueError, match="is not a route"):
        PageWeightConfig(ceilings_bytes={"evals": 2475})


def test_every_configured_feed_names_a_declared_vertical() -> None:
    """Retired feeds too - a tombstone still labels published items by vertical."""
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    declared = {vertical.id for vertical in taxonomy.verticals}
    for feed in sources.known_feeds():
        assert feed.vertical in declared, f"feed {feed.id} names an undeclared vertical"


def test_every_vertical_clears_its_own_feed_floor() -> None:
    """A vertical under `min_feeds` plans nothing at all, so this is a live gate.

    `rank.plan_vertical` returns an empty list for a vertical below its floor -
    the desk does not thin out, it goes silent. Nothing else notices: the run
    succeeds, the digest publishes, and one section is simply absent.

    That was one edit away from happening on 2026-08-29. Retiring the 40 feeds
    that had never published anything took `ai` to 28 against a floor of 35 and
    `business-economy` to 12 against 21 - 34 percent of that day's items, gone
    quietly. A throwaway assertion in a migration script caught it; nothing in
    the repository would have. This is that assertion, kept.

    Since 2026-09-02 it counts what a run may lawfully ask rather than what a
    curator left active, which is the count the floor is actually compared
    against - so it reads the committed retirement ledger and the committed
    health record as well as the config. Measured on this checkout 2026-09-02
    the two counts are identical on every desk, because no committed row records
    a permission or a retirement yet.

    It reads the committed config on purpose. The number that decides a run is
    the one in `config/`, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    state = REPO_ROOT / ledger.STATE_DIRNAME
    records = source_health.endpoint_records(
        ledger.load_health(state, today=newest_health_date(state), within_days=400)
    )
    retired = {row.endpoint_key for row in ledger.load_retirements(state)}
    active = Counter(
        feed.vertical for feed in sources.feeds if feed.status is LifecycleStatus.ACTIVE
    )
    for vertical in taxonomy.verticals:
        askable = source_health.eligible(
            sources.feeds, vertical.id, retired_keys=retired, records=records
        )
        assert len(askable) >= vertical.min_feeds, (
            f"{vertical.id} has {len(askable)} feeds it may ask against a floor of "
            f"{vertical.min_feeds}, so it would publish nothing - of "
            f"{active[vertical.id]} a curator left active"
        )


def newest_health_date(state: Path) -> str:
    """The last day the committed record covers, so the read does not move with the clock.

    A window ending at today would make this test's answer depend on when it
    ran, and the question it asks is about committed evidence rather than about
    the hour.
    """
    stems = sorted(path.stem for path in (state / "feed-health").glob("*.csv"))
    return f"{stems[-1]}-28" if stems else "1970-01-01"


def desk(**overrides: Any) -> dict[str, Any]:
    """One vertical of a plan, spelled the way an earlier build wrote it."""
    return {"id": "ai", "considered": 40, "planned": 5, "live_feeds": 3, **overrides}


def test_a_plan_that_spells_live_feeds_still_reads() -> None:
    """The rename landed on 2026-09-02 and the model forbids unknown keys.

    Without the read migration a plan an earlier build wrote would be refused
    outright rather than degrade, which is a release blocker by section 11.
    """
    parsed = VerticalPlan.model_validate(desk())
    assert parsed.eligible_feeds == 3


def test_the_real_payload_an_earlier_build_committed_still_opens() -> None:
    """The same migration, against bytes a build actually wrote and committed.

    `tests/fixtures/superseded/run-plan-live-feeds.json` is the run-plan fixture
    exactly as it stood in the tree before the 2026-09-02 rename, recovered from
    git and kept unedited. A migration checked only against a payload this test
    file builds proves the builder, not the migration - and this is the whole
    reason the migration outlived the config knobs renamed beside it.
    """
    raw = read_text(FIXTURES_DIR / "superseded" / "run-plan-live-feeds.json")
    assert '"live_feeds"' in raw and '"eligible_feeds"' not in raw

    plan = RunPlan.from_json(raw)
    assert [(desk.id, desk.eligible_feeds) for desk in plan.verticals] == [("ai", 3), ("energy", 4)]
    assert all(desk.feed_floor is None for desk in plan.verticals), (
        "no floor is invented for a payload that never carried one"
    )


def test_a_plan_that_never_carried_a_floor_is_given_none() -> None:
    """Absent reads as unknown, never as a floor of zero.

    A zero would say the desk had no floor to clear, which on a payload that
    recorded `below_feed_floor` is a claim the payload itself can contradict.
    """
    assert VerticalPlan.model_validate(desk()).feed_floor is None
    assert VerticalPlan.model_validate(desk(below_feed_floor=True, planned=0)).feed_floor is None


def test_a_plan_may_not_spell_the_count_twice() -> None:
    """The migration maps the old name and never merges two answers.

    A payload carrying both is not an old payload; it is a writer nobody has,
    and quietly preferring one of the two is how a count starts disagreeing
    with itself.
    """
    with pytest.raises(ValidationError):
        VerticalPlan.model_validate(desk(eligible_feeds=9))


def test_a_manifest_written_before_the_floor_was_recorded_reads_as_unknown() -> None:
    """`VerticalCount` never carried either number, so both are null on every
    manifest committed before today - and null is unknown rather than a desk
    with no sources."""
    count = VerticalCount.model_validate({"id": "ai", "planned": 5, "published": 4})
    assert count.eligible_feeds is None
    assert count.feed_floor is None


def test_every_committed_run_manifest_still_reads_today() -> None:
    """The release blocker this class of change carries, asked of the real files.

    A payload yesterday's run wrote that today's build cannot open is a contract
    break, and every one of these was written before the two fields existed.
    """
    manifests = sorted((REPO_ROOT / "frontend" / "public" / "digest").glob("*/*/*/run.json"))
    assert manifests, "no day is committed, so this proves nothing"
    oldest = manifests[0]
    assert oldest.parts[-4:-1] == ("2026", "08", "21"), (
        f"the oldest committed run payload moved to {'/'.join(oldest.parts[-4:-1])}"
    )
    absent = 0
    for path in manifests:
        raw = json.loads(read_text(path))
        parsed = RunManifest.from_json(read_text(path))
        for record, verticals in zip(
            parsed.runs, (run.get("verticals", []) for run in raw["runs"]), strict=True
        ):
            for count, written in zip(record.verticals, verticals, strict=True):
                if "eligible_feeds" in written:
                    continue
                absent += 1
                assert count.eligible_feeds is None, path.name
                assert count.feed_floor is None, path.name
    assert absent, "every committed desk already carries the field, so nothing was migrated"


def test_the_watchlist_stays_inside_its_configured_cap() -> None:
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert len(watchlist.entities) <= config.collect.watchlist_max_entities


# --- Structural rules ------------------------------------------------------


def test_contracts_import_no_other_subpackage() -> None:
    """Contracts are the bottom of the dependency graph (CLAUDE.md section 4)."""
    package = REPO_ROOT / "backend" / "idhazh" / "contracts"
    for module in sorted(package.glob("*.py")):
        tree = ast.parse(read_text(module), filename=str(module))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith("idhazh.") and not name.startswith("idhazh.contracts"):
                    pytest.fail(f"{module.name} imports {name}")


@pytest.mark.parametrize(
    "path",
    sorted(SCHEMAS_DIR.glob("*.json")) + sorted(CONFIG_DIR.glob("*.json")) + fixture_paths(),
    ids=lambda p: p.name,
)
def test_repo_text_is_ascii_and_lf(path: Path) -> None:
    raw = path.read_bytes()
    raw.decode("ascii")
    assert b"\r\n" not in raw


def test_no_hash_appears_in_any_published_path() -> None:
    """Decision 2: an item is addressed <vertical>-<NN>, never by a digest."""
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in day.items:
        assert not LONG_HEX.search(item.item_id)
        if item.visual is not None and item.visual.path is not None:
            assert not LONG_HEX.search(item.visual.path)
    route = Route.from_json(read_text(CONTRACT_FIXTURES_DIR / "route" / "chart-rendered.json"))
    assert route.asset_path is not None
    assert not LONG_HEX.search(route.asset_path)


def test_the_eval_ledger_columns_are_defined_once() -> None:
    columns = EvalRow.csv_columns()
    assert len(set(columns)) == len(columns)
    for required in ("date", "source_url", "title", "url_key", "band", "version"):
        assert required in columns, "a ledger row must still mean something after a prune"


def test_the_recorded_premise_digest_names_the_article_fixture() -> None:
    """The populated shape, checked against text this repository holds.

    A fixture digest nobody can recompute proves the field parses and nothing
    else. This one is the digest of `article/ok.json`'s sanitized text, so the
    fixture also pins the convention: sha256 over the UTF-8 bytes, all 64 hex
    characters, which is what `text_digest` spells everywhere else.
    """
    source = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    scored = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "premise-recorded.json"))

    assert scored.source_digest == text_digest(source.text or "")
    assert scored.source_digest != scored.output_digest


def test_the_item_health_ledger_columns_are_defined_once() -> None:
    assert ItemHealthRow.csv_columns() == (
        "version",
        "date",
        "run_id",
        "item_id",
        "url_key",
        "canonical_url",
        "vertical",
        "source_id",
        "stage",
        "outcome",
        "code",
        "http_status",
        "source_chars",
        "source_words",
        "summary_words",
        "detail",
        "fetch_ms",
        "extract_ms",
        "summarize_ms",
        "prefill_ms",
        "decode_ms",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "source_words_before_cap",
        "shard",
    )


def test_the_feed_health_ledger_columns_are_defined_once() -> None:
    """The five columns of 2026-09-02 are appended, so the old header is still a prefix.

    `ledger.require_matching_header` compares the whole list, so a column filed
    beside the one it relates to would put every historical value one place to
    the right under a reader that maps by position. Appending is what keeps the
    narrow header readable as the head of the wide one.
    """
    assert FeedHealthRow.csv_columns() == (
        "version",
        "run_id",
        "date",
        "feed_id",
        "checked_at",
        "outcome",
        "status",
        "items",
        "detail",
        "endpoint_key",
        "robots_outcome",
        "robots_checked_at",
        "robots_status",
        "target_attempted",
    )


def test_a_retirement_names_distinct_runs_and_only_one_cause() -> None:
    """Five failures inside one run is one run's evidence, not five runs' worth.

    `http_410` is the only cause the enum admits, and that is the design rather
    than a starting point: nothing softer than `410 Gone` says the address is
    not coming back (docs/architecture/sources/health.md).
    """
    assert [cause.value for cause in RetirementCause] == ["http_410"]

    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    repeated = row.model_dump(mode="json") | {"evidence_run_ids": ["2026-08-23-1"] * 5}

    with pytest.raises(ValidationError, match="distinct runs"):
        FeedRetirementRow.model_validate(repeated)


def test_a_retirement_row_survives_the_ledger_round_trip() -> None:
    """The evidence list is one cell, so the header cannot grow with the evidence."""
    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    cells = row.csv_row()

    assert cells["evidence_run_ids"].count(" ") == len(row.evidence_run_ids) - 1
    assert "," not in cells["evidence_run_ids"], "a comma would need quoting in a union merge"
    assert FeedRetirementRow.from_csv_row(cells) == row


def test_the_canary_writes_every_column_the_item_health_ledger_defines() -> None:
    """The canary's own copy of the header, held against the contract.

    `frontend/scripts/build-canary.mjs` restates the column names because it is
    JavaScript and the contract is Python. A name added to the row and not to
    that array writes a canary `publish_telemetry` refuses, and until this test
    existed the only thing that caught it was a frontend build in CI.
    """
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == ItemHealthRow.csv_columns()


def test_the_canary_writes_every_column_the_counters_ledger_defines() -> None:
    """The same guard, over the second header the canary restates.

    The canary gained a `state/runtime-counters.csv` on 2026-08-31, because
    without one the Machine route draws every panel in its empty state and the
    browser suite can assert nothing else. That file is written by hand in
    JavaScript for the same reason the item-health one is, so it needs the same
    guard: a column added to `RuntimeCountersRow` and not to that array writes a
    canary whose cells sit one place to the left, and every backend gate stays
    green while the console reads the wrong number.
    """
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COUNTER_COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COUNTER_COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == RuntimeCountersRow.csv_columns()


def test_the_canary_writes_every_column_the_feed_health_ledger_defines(tmp_path: Path) -> None:
    """Every column filled by at least one canary feed, not merely present in the header.

    The browser suite runs against this ledger, so a column no canary row fills
    is a console state that suite cannot reach - which is how the five columns
    added on 2026-09-02 would ship drawn only in their empty state.
    """
    build_canary_day.health(tmp_path)
    path = tmp_path / "feed-health" / f"{build_canary_day.DATE[:7]}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert tuple(rows[0]) == FeedHealthRow.csv_columns()
    unfilled = [name for name in FeedHealthRow.csv_columns() if not any(row[name] for row in rows)]
    assert unfilled == [], "a canary column nothing fills is a console state no test can reach"
    assert {row["robots_outcome"] for row in rows} == {"allowed", "denied", "unreachable", ""}


def test_the_frontend_names_every_live_lens_and_no_retired_one() -> None:
    """The page's own copy of the lens display names, held against the config.

    `frontend/src/lib/payload/lenses.ts` restates them because it is TypeScript
    and the vocabulary is JSON, and it holds them rather than taking them
    through `data` so the six names are not repeated inside every prerendered
    day page. Drift either way is a defect a build never catches: a missing name
    renders nothing where a chip belongs, and a stale one puts a tombstone back
    on the page.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "lenses.ts")
    declared = re.search(r"LENS_NAMES: Readonly<Record<string, string>> = \{(.*?)\};", source, re.DOTALL)
    assert declared is not None, "lenses.ts no longer declares LENS_NAMES"
    named = dict(re.findall(r"(\S+): '([^']+)'", declared.group(1)))
    live = {
        lens.id.value: lens.display_name
        for lens in taxonomy.lenses
        if lens.status is not LifecycleStatus.RETIRED
    }
    assert named == live, "the page and config/taxonomy.json disagree about the lens names"

    retired = {lens.id.value for lens in taxonomy.lenses if lens.status is LifecycleStatus.RETIRED}
    assert not (retired & set(named)), f"a retired lens can still render: {sorted(retired & set(named))}"


def test_the_console_reads_a_prefix_of_the_published_telemetry_columns() -> None:
    """The browser's copy of the projection header, held against the writer.

    `frontend/src/lib/charts/series.ts` restates `PUBLIC_COLUMNS` because it is
    TypeScript and the writer is Python, and its header check reads a prefix on
    purpose - a browser holding a cached bundle keeps working when a column is
    appended. So this test allows an append and refuses an insert, a rename or a
    reorder at any position the browser reads, and refuses a name the writer
    never writes. Nothing else ties the two lists together.
    """
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "charts" / "series.ts")
    declared = re.search(
        r"export const TELEMETRY_COLUMNS = \[(.*?)\] as const;", source, re.DOTALL
    )
    assert declared is not None, "series.ts no longer declares a TELEMETRY_COLUMNS array"
    names = tuple(re.findall(r"'([^']+)'", declared.group(1)))
    assert names, "TELEMETRY_COLUMNS matched but held no column names"
    assert names == PUBLIC_COLUMNS[: len(names)], (
        "series.ts and publish_telemetry.py disagree about the telemetry header: "
        f"the console reads {list(names)}, the writer writes "
        f"{list(PUBLIC_COLUMNS[: len(names)])} in those positions"
    )


def test_the_console_fallback_bands_match_the_committed_ladder() -> None:
    """The console's fallback length ladder, held against the file it stands in for.

    `summarizeConfig()` in `frontend/src/lib/server/config.ts` returns
    `SUMMARIZE_DEFAULTS` when `config/idhazh.json` cannot be read, and those
    bands draw the compression plot's target zone and set its y axis. A stale
    copy draws a wrong chart and says nothing, so the copy is pinned here.
    """
    committed: list[dict[str, int]] = json.loads(read_text(CONFIG_DIR / "idhazh.json"))[
        "summarize"
    ]["bands"]
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    declared = re.search(
        r"const SUMMARIZE_DEFAULTS: SummarizeConfig = \{\s*bands: \[(.*?)\]\s*\};",
        source,
        re.DOTALL,
    )
    assert declared is not None, "config.ts no longer declares a SUMMARIZE_DEFAULTS ladder"
    fallback = [
        {name: int(value) for name, value in re.findall(r"(\w+): (\d+)", band)}
        for band in re.findall(r"\{([^{}]*)\}", declared.group(1))
    ]
    assert fallback, "SUMMARIZE_DEFAULTS matched but held no bands"
    keys = ("min_source_words", "target_words_min", "target_words_max")
    expected = [{key: band[key] for key in keys} for band in committed]
    assert fallback == expected, (
        "config.ts and config/idhazh.json disagree about the summary bands: "
        f"the console falls back to {fallback}, the committed ladder is {expected}"
    )


def test_recorded_item_health_codes_never_count_against_a_source() -> None:
    assert len(SOURCE_NEUTRAL_FAILURE_CODES) == 15
    assert FailureCode.NOT_ATTEMPTED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_UNREACHABLE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.NOT_PROSE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.BOILERPLATE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.HTTP_CLIENT_ERROR not in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_is_the_models_fault_and_never_the_feeds(code: FailureCode) -> None:
    """A wire service publishing short briefs must not be quarantined for our model.

    `collect.availability_strikes_before_rest` is 5, so leaving either code out
    of the source-neutral set would take a working feed off the list on the fifth
    copy.
    """
    assert FAILURE_CODE_STAGES[code] == frozenset({ItemStage.SUMMARIZE})
    assert code in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_survives_the_ledger_round_trip(code: FailureCode) -> None:
    """The census row is the only durable record of a dropped item, so it must read back."""
    published = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    row = published.model_copy(
        update={
            "stage": ItemStage.SUMMARIZE,
            "outcome": ItemOutcome.FAILED,
            "code": code,
            "summary_words": 44,
        }
    )

    restored = ItemHealthRow.from_csv_row(row.csv_row())
    assert restored.code is code
    assert restored.summary_words == 44
    assert restored.counts_against_source is False
    assert restored == row


def test_a_prompt_that_did_not_fit_is_our_budget_and_not_the_sources_fault() -> None:
    """The article was long. The context window and the truncation cap are ours."""
    assert FailureCode.CONTEXT_EXCEEDED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FAILURE_CODE_STAGES[FailureCode.CONTEXT_EXCEEDED] == frozenset({ItemStage.SUMMARIZE})


def test_an_item_health_row_written_before_the_context_code_still_reads() -> None:
    """Section 11's release blocker for an additive enum member.

    A row this month's ledger already holds carries the previous schema stamp
    and a code minted before today. It must still load, and it must still read
    as source-neutral, or a committed ledger stops parsing on the day the
    vocabulary grows.
    """
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "summarize-model-unreachable.json")
    )

    assert row.version == "2026-08-24T18:30"
    assert row.version != ItemHealthRow.schema_version()
    assert row.code is FailureCode.MODEL_UNREACHABLE
    assert row.counts_against_source is False
    assert ItemHealthRow.from_csv_row(row.csv_row()) == row


def test_item_health_csv_round_trip_uses_empty_cells_for_absent_values() -> None:
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    cells = row.csv_row()
    assert cells["code"] == ""
    assert cells["http_status"] == ""
    assert ItemHealthRow.from_csv_row(cells) == row


def test_the_pages_that_name_the_summarize_codes_still_agree_with_the_enum() -> None:
    """Two pages enumerate the summarize codes by hand, and neither is generated.

    `copied_source` and `leaked_address` were minted on 2026-08-27 and both pages
    kept the old list for a day, so each one asserted a vocabulary the code had
    already outgrown. `unknown` is excluded because it belongs to every stage and
    `to_summary` never returns it.
    """
    summarize_only = {
        code.value
        for code, stages in FAILURE_CODE_STAGES.items()
        if stages == frozenset({ItemStage.SUMMARIZE})
    }

    tabled = re.findall(r"^\| `summarize` \|(.+)\|$", read_text(DOC_ITEM_HEALTH), re.MULTILINE)
    assert len(tabled) == 1, "the item-health stage table no longer has one summarize row"
    assert backticked(tabled[0]) == summarize_only

    listed = re.findall(r"^\| Summary `([a-z_]+)`", read_text(DOC_ONE_URL), re.MULTILINE)
    assert set(listed) == summarize_only
    assert len(listed) == len(summarize_only), "the one-URL page lists a code twice"


def test_the_item_health_page_splits_the_codes_the_way_the_contract_does() -> None:
    """The source-neutral split is a promise about which feed gets quarantined."""
    text = read_text(DOC_ITEM_HEALTH)
    neutral = {code.value for code in SOURCE_NEUTRAL_FAILURE_CODES}

    assert backticked(paragraph_after(text, "never count against a source:")) == neutral
    assert backticked(paragraph_after(text, "can count against the source:")) == {
        code.value for code in FailureCode
    } - neutral


def test_the_runtime_counters_columns_are_defined_once() -> None:
    assert RuntimeCountersRow.csv_columns() == (
        "version",
        "date",
        "run_id",
        "shard",
        "shards",
        "scraped_at",
        "prompt_tokens_total",
        "prompt_tokens_cached_total",
        "prompt_seconds_total",
        "tokens_predicted_total",
        "tokens_predicted_seconds_total",
        "n_decode_total",
        "n_tokens_max",
        "n_busy_slots_per_decode",
        "job_seconds",
        "cpu_model",
        "cpu_busy_pct",
        "peak_rss_bytes",
        "model_load_ms",
    )


@pytest.mark.parametrize("path", METRICS_CAPTURES, ids=lambda p: p.stem)
def test_the_server_agrees_with_itself_about_what_a_prompt_token_is(path: Path) -> None:
    """The Oracle for the definition: the server's own rate over its own counters.

    llama-server publishes `prompt_tokens_seconds` as well as the two counters it
    is made of. If `prompt_tokens_total` counted cached tokens too, the published
    gauge and the counters would disagree - so this reproduces the gauge from the
    counters and proves the field means what the row says it means: prompt tokens
    the model actually read, which is the ledger's `input_tokens - cached_tokens`.
    """
    text = read_text(path)
    row = RuntimeCountersRow.from_metrics_text(
        text,
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=int(path.stem[-1]),
        shards=len(METRICS_CAPTURES),
        scraped_at="2026-08-26T21:12:05Z",
    )
    published = {
        line.split(" ")[0]: float(line.split(" ")[1])
        for line in text.splitlines()
        if line.startswith("llamacpp:")
    }

    assert row.prompt_tokens_total is not None
    assert row.prompt_seconds_total is not None
    reproduced = row.prompt_tokens_total / row.prompt_seconds_total
    # The gauge is printed to six significant figures, so the comparison is too.
    assert reproduced == pytest.approx(published["llamacpp:prompt_tokens_seconds"], rel=1e-5)
    assert row.prompt_tokens_cached_total is not None
    assert row.prompt_tokens_cached_total > 0, "a capture with no cache hits proves nothing here"


def test_a_series_this_build_does_not_publish_is_null_and_never_zero() -> None:
    """A rename has to look like a missing column, not like a server that read nothing."""
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
    )
    for field in SERIES.values():
        assert getattr(row, field) is None
    cells = row.csv_row()
    assert all(cells[field] == "" for field in SERIES.values())
    assert RuntimeCountersRow.from_csv_row(cells) == row


def test_a_count_that_stops_being_whole_raises_instead_of_truncating() -> None:
    """A silently truncated counter is a wrong number that nothing can spot later."""
    with pytest.raises(ValueError, match="prompt_tokens_total"):
        RuntimeCountersRow.from_metrics_text(
            "llamacpp:prompt_tokens_total 23411.5\n",
            date="2026-08-26",
            run_id="2026-08-26-5",
            shard=0,
            shards=4,
            scraped_at="2026-08-26T21:32:30Z",
        )


def test_a_shard_index_must_sit_inside_the_run_it_names() -> None:
    with pytest.raises(ValueError, match="below the shard count"):
        RuntimeCountersRow.model_validate(
            {
                "date": "2026-08-26",
                "run_id": "2026-08-26-5",
                "shard": 4,
                "shards": 4,
                "scraped_at": "2026-08-26T21:32:30Z",
            }
        )


def test_the_shard_clock_is_measured_against_the_scrape_that_carries_it() -> None:
    """The rollback trigger reads this cell, so it may not be a second opinion.

    `job_seconds` and `scraped_at` describe the same instant from two ends. The
    row works the difference out for itself rather than taking a caller's
    arithmetic, so the two cells cannot end up saying different things about one
    scrape.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
        # 2026-08-26T20:00:00Z, an hour and 32.5 minutes before the scrape.
        job_started_at=1787774400,
        cpu_model="  AMD EPYC 7763 64-Core Processor  ",
    )

    assert row.job_seconds == 5550
    assert row.cpu_model == "AMD EPYC 7763 64-Core Processor"
    assert RuntimeCountersRow.from_csv_row(row.csv_row()) == row


def test_a_shard_with_no_stamp_and_no_host_reports_absence_not_zero() -> None:
    """A job whose stamp went missing and a job that took no time are not one fact.

    The stamp comes from a workflow step, and a stage that runs anywhere else -
    a developer machine, a re-run of one shard - has neither it nor
    `/proc/cpuinfo`. Both cells stay empty there, and an empty cell reads back as
    absent (`job_seconds is None`) rather than as `0`.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
        cpu_model="",
    )
    cells = row.csv_row()

    assert row.job_seconds is None
    assert row.cpu_model is None
    assert cells["job_seconds"] == ""
    assert cells["cpu_model"] == ""
    assert RuntimeCountersRow.from_csv_row(cells) == row


def _aggregate_cpu_line(text: str) -> list[int]:
    """The ten counters on the one `cpu ` line of a /proc/stat capture."""
    aggregate = [line for line in text.splitlines() if line.split()[:1] == ["cpu"]]
    assert len(aggregate) == 1, "a /proc/stat capture has exactly one aggregate cpu line"
    return [int(cell) for cell in aggregate[0].split()[1:]]


def test_every_runtime_capture_an_oracle_reads_is_committed() -> None:
    """A parametrized oracle over an empty glob is green and proves nothing.

    `.gitignore` carries `*.log`, so the first spelling of the server-log
    capture was ignored the moment it was named after the file it came from -
    and the test over it collected zero cases without saying so.
    """
    assert len(METRICS_CAPTURES) == 4
    assert len(RSS_CAPTURES) == 4
    assert len(SERVER_LOG_CAPTURES) == 4
    for path in (PROC_STAT_AT_START, PROC_STAT_AT_END):
        assert path.is_file(), path.name


def test_the_processor_busy_share_is_read_from_a_real_proc_stat_pair() -> None:
    """The Oracle for `cpu_busy_pct`: the capture proves its own window.

    Twenty seconds of four processors at 100 Hz is 8,000 ticks. A real pair
    reproduces that, and a hand-written pair only does so by arithmetic somebody
    already did - which is the same arithmetic under test. The busy share itself
    is worked out here from the raw text, field by field, so this cannot pass by
    agreeing with the contract about a mistake.

    The reading is near zero because the probe slept through its own window. The
    shape is what is under test; the expected value on a work shard is near 100.
    """
    at_start = read_text(PROC_STAT_AT_START)
    at_end = read_text(PROC_STAT_AT_END)
    start = _aggregate_cpu_line(at_start)
    end = _aggregate_cpu_line(at_end)
    # guest sits inside user and guest_nice inside nice, so a plain sum of the
    # line counts both twice. idle and iowait are the processors standing free.
    available = (sum(end) - end[8] - end[9]) - (sum(start) - start[8] - start[9])
    idle = (end[3] + end[4]) - (start[3] + start[4])

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-30",
        run_id="2026-08-30-1",
        shard=0,
        shards=4,
        scraped_at="2026-08-30T02:45:02Z",
        cpu_stat_at_start=at_start,
        cpu_stat_at_end=at_end,
    )

    assert available == pytest.approx(PROBE_SECONDS * PROBE_PROCESSORS * USER_HZ, rel=0.01)
    assert row.cpu_busy_pct == pytest.approx(100 * (available - idle) / available, abs=0.005)
    assert RuntimeCountersRow.from_csv_row(row.csv_row()) == row


@pytest.mark.parametrize("path", RSS_CAPTURES, ids=lambda p: p.name)
def test_the_memory_high_point_is_the_highest_the_sampler_saw(path: Path) -> None:
    """The Oracle for `peak_rss_bytes`: the column is found by name, in bytes.

    `VmHWM` is a high-water mark, so the last sample carries the whole life of
    the process - but a sample can come back blank, and a column can move. The
    expected value is worked out here off the sampler's own header rather than
    off a position, which is the failure this would otherwise hide.
    """
    text = read_text(path)
    rows = [line.split("\t") for line in text.splitlines()]
    column = rows[0].index("llama_vmhwm_kb")
    peaks = [int(cells[column]) for cells in rows[1:] if cells[column].strip().isdigit()]

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(RSS_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        rss_samples=text,
    )

    assert row.peak_rss_bytes == max(peaks) * 1024
    # The unit is what a wrong answer gets wrong. A 9B at `n_ctx` 8192 holds
    # gigabytes, so kilobytes read as bytes would land a thousandfold low.
    assert row.peak_rss_bytes > 8 * 1024**3


@pytest.mark.parametrize("path", SERVER_LOG_CAPTURES, ids=lambda p: p.name)
def test_the_model_load_time_is_the_gap_between_the_servers_own_two_lines(path: Path) -> None:
    """The Oracle for `model_load_ms`: llama.cpp's stamp decoded from a real job.

    The stamp is four dot-separated numbers and no page says what they are. The
    third field reaches 809 on a real line, so it cannot be seconds-in-a-minute;
    the last field steps by 15 between two lines printed back to back, and the
    first field of the last line of a 99-minute job reads 99. That fixes it as
    minutes, seconds, milliseconds, microseconds - and only a capture of a job
    whose length is known settles it.
    """
    text = read_text(path)
    stamps: dict[str, int] = {}
    for line in text.splitlines():
        for marker in ("load_model: loading model", "llama_server: model loaded"):
            if marker in line and marker not in stamps:
                minutes, seconds, milli, micro = (int(p) for p in line.split(" ")[0].split("."))
                stamps[marker] = (((minutes * 60) + seconds) * 1000 + milli) * 1000 + micro
    assert len(stamps) == 2, f"{path.name} does not bracket a model load"

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(SERVER_LOG_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        server_log=text,
    )

    expected = stamps["llama_server: model loaded"] - stamps["load_model: loading model"]
    assert row.model_load_ms == expected / 1000
    # Seconds, not minutes and not microseconds. A unit slip is the one mistake
    # a gap between two stamps can make and still look plausible.
    assert 1000 < row.model_load_ms < 60_000


def test_a_shard_whose_host_readings_never_arrived_reports_absence_not_zero() -> None:
    """A machine nobody read and a machine that did nothing are not one fact.

    The readings come from workflow steps and from files a job writes as it
    goes. A stage run anywhere else - a developer machine, a re-run of one shard
    whose first step never fired - has none of them, and one end of the
    processor window on its own says nothing either.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=0,
        shards=4,
        scraped_at="2026-08-29T23:15:35Z",
        cpu_stat_at_start="",
        cpu_stat_at_end="cpu  2088 1 1373 304131 3508 0 30 0 0 0",
        rss_samples="",
        # The two lines under the markers llama.cpp uses today, renamed. A build
        # that renames one leaves the cell empty rather than reporting a load
        # that took no time.
        server_log="0.00.011.682 I srv    load_model: opening weights\n",
    )
    cells = row.csv_row()

    assert row.cpu_busy_pct is None
    assert row.peak_rss_bytes is None
    assert row.model_load_ms is None
    assert cells["cpu_busy_pct"] == ""
    assert cells["peak_rss_bytes"] == ""
    assert cells["model_load_ms"] == ""
    assert RuntimeCountersRow.from_csv_row(cells) == row


def test_a_host_name_that_could_split_a_row_is_refused() -> None:
    """`state/runtime-counters.csv` merges with the union driver, which is line-based.

    Eight shards append to one branch, and the merge keeps lines rather than
    parsing CSV. A cell holding a newline would be quoted correctly by the writer
    and still split one row in two the first time two shards raced.
    """
    for hostile in ("AMD EPYC\n7763", "AMD EPYC\r7763"):
        with pytest.raises(ValueError, match="cpu_model"):
            RuntimeCountersRow.model_validate(
                {
                    "date": "2026-08-26",
                    "run_id": "2026-08-26-5",
                    "shard": 0,
                    "shards": 4,
                    "scraped_at": "2026-08-26T21:32:30Z",
                    "cpu_model": hostile,
                }
            )


# --- Invariants the shape exists to carry ----------------------------------


def mutate(path: Path, **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(read_text(path))
    payload.update(changes)
    return payload


def test_url_key_is_rebuilt_not_trusted() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "article" / "ok.json",
        canonical_url="https://blog.example-lab.org/2026/08/other",
    )
    with pytest.raises(ValueError, match="url_key"):
        Article.model_validate(payload)
    payload["url_key"] = derive_url_key(payload["canonical_url"])
    assert Article.model_validate(payload).url_key == derive_url_key(payload["canonical_url"])


def test_an_ok_article_must_carry_text() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "ok.json", text=None)
    with pytest.raises(ValueError, match="title and text"):
        Article.model_validate(payload)


def test_a_failed_article_must_record_why() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "fetch-failed.json", failure_detail=None)
    with pytest.raises(ValueError, match="must record why"):
        Article.model_validate(payload)


def test_truncation_is_flagged_and_located_together() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "truncated.json", truncated_at_tokens=None)
    with pytest.raises(ValueError, match="truncated"):
        Article.model_validate(payload)


def test_a_routed_to_nothing_item_carries_no_spec() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "route" / "none.json", spec="anything")
    with pytest.raises(ValueError, match="no spec"):
        Route.model_validate(payload)


def test_only_a_rendered_visual_has_an_asset_path() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "route" / "chart-rendered.json", visual_state="absent")
    with pytest.raises(ValueError, match="asset_path"):
        Route.model_validate(payload)


def test_hhem_delta_is_rebuilt_not_trusted() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json", hhem_delta=0.9)
    with pytest.raises(ValueError, match="hhem_delta"):
        EvalRow.model_validate(payload)


#: The four columns the owner refused to delete on 2026-08-30, and the two things
#: each description has to carry. Every one of them is a cell a reader cannot
#: interpret from its value: a constant that looks like a count, a derived cell
#: that looks like a measurement, a flag that changed meaning on a fixed date, and
#: a timing that is not on the path it sits beside. Each entry is
#: (model, field, unit phrases, reader phrases) and one phrase from each group has
#: to appear, so a later edit cannot quietly strip the unit or the reader back out.
KEPT_COLUMNS: tuple[tuple[type[Contract], str, tuple[str, ...], tuple[str, ...]], ...] = (
    (Summary, "attempt", ("A count, not a duration",), ("Nothing reads it",)),
    (EvalRow, "score_ms", ("Milliseconds",), ("observability.sample_rate",)),
    (EvalRow, "hhem_delta", ("0-to-1 faithfulness scale",), ("no band reads it",)),
    (EvalRow, "truncation_flagged", ("True when",), ("model-work.ts",)),
)


@pytest.mark.parametrize(("model", "field", "units", "readers"), KEPT_COLUMNS)
def test_a_kept_column_says_what_it_holds_and_who_reads_it(
    model: type[Contract], field: str, units: tuple[str, ...], readers: tuple[str, ...]
) -> None:
    """A column kept for history still has to explain itself.

    The owner asked what two of these four meant, which is what a description
    that is not doing its job looks like. A test that only checks the field
    exists would have passed on every one of them.
    """
    described = model.model_fields[field].description or ""
    assert described.strip(), f"{model.__name__}.{field} carries no description"
    assert any(unit in described for unit in units), (
        f"{model.__name__}.{field} does not say what its value is measured in"
    )
    assert any(reader in described for reader in readers), (
        f"{model.__name__}.{field} does not say who reads it"
    )


def test_every_kept_column_reaches_its_generated_schema() -> None:
    """A description a reader never sees is a comment. These are read by people."""
    for model, field, units, readers in KEPT_COLUMNS:
        schema = json.loads(read_text(SCHEMAS_DIR / f"{model.__schema_stem__}.schema.json"))
        described = schema["properties"][field]["description"]
        assert any(unit in described for unit in units)
        assert any(reader in described for reader in readers)


def test_the_model_cannot_have_read_more_words_than_the_article_holds() -> None:
    """The impossible direction, refused.

    610 of 2,346 committed rows carried a seen count LARGER than the full
    count, because the two cells were filled by two different counters over the
    same truncated string. Nothing compared them, so nothing could see it.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1874,
    )
    with pytest.raises(ValueError, match="not more"):
        EvalRow.model_validate(payload)


def test_an_article_shorter_than_the_cap_reads_the_same_length_twice() -> None:
    """Equal is the normal case, not an error: nothing was cut."""
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1875,
    )
    assert EvalRow.model_validate(payload).source_word_count == 1875


def test_an_eval_row_may_not_know_how_long_its_article_was() -> None:
    """Null and not zero (section 11).

    A row written before 2026-08-27 whose article was truncated has no full
    length anywhere: extract discarded the pre-cap body. Zero would claim the
    article was empty.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=None,
    )
    row = EvalRow.model_validate(payload)
    assert row.source_word_count is None
    assert row.source_seen_word_count == 1875, "the seen count is still a measurement"


def test_an_ok_item_health_row_carries_only_recorded_extract_signals() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.UNKNOWN,
        detail="unclassified failure",
    )
    with pytest.raises(ValueError, match="recorded extract signal"):
        ItemHealthRow.model_validate(payload)

    signalled = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.NOT_PROSE,
    )
    assert ItemHealthRow.model_validate(signalled).code is FailureCode.NOT_PROSE


def test_item_health_failure_code_must_belong_to_stage() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.HTTP_CLIENT_ERROR,
    )
    with pytest.raises(ValueError, match="does not belong"):
        ItemHealthRow.model_validate(payload)


def test_item_health_http_status_belongs_only_to_fetch() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json", http_status=200)
    with pytest.raises(ValueError, match="http_status"):
        ItemHealthRow.model_validate(payload)


def test_unknown_item_health_failure_carries_the_only_detail() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.UNKNOWN,
        detail="source shape did not match a known bucket",
    )
    assert ItemHealthRow.model_validate(payload).code is FailureCode.UNKNOWN

    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        detail="short source",
    )
    with pytest.raises(ValueError, match="detail belongs only"):
        ItemHealthRow.model_validate(payload)


def test_a_retired_entry_must_carry_its_date() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["verticals"][2]["retired_on"] = None
    with pytest.raises(ValueError, match="retired_on"):
        Taxonomy.model_validate(payload)


# --- The registry holds two kinds of entry ---------------------------------


def watchlist_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "watchlist" / "seeded.json")
    )
    return payload


def test_a_subject_needs_neither_a_filer_id_nor_a_feed() -> None:
    """The whole point of the widening.

    A pandemic, a tournament or an export-control regime has no SEC filer id
    and no newsroom of its own. Before `kind` the registry described itself as
    a list of named organisations, so an entry like this had no way in.
    """
    seeded = Watchlist.model_validate(watchlist_payload())
    subject = next(entity for entity in seeded.entities if entity.kind is EntityKind.SUBJECT)
    assert subject.cik is None
    assert subject.feeds == []
    assert subject.aliases, "a subject with no alias is never matched (EntityDef.aliases)"


def test_a_subject_may_not_carry_a_filer_id() -> None:
    """Only an organisation files with the SEC, so the pairing is a data error."""
    payload = watchlist_payload()
    payload["entities"][0]["kind"] = EntityKind.SUBJECT.value
    with pytest.raises(ValueError, match="cik belongs to an organisation"):
        Watchlist.model_validate(payload)


def test_a_watchlist_written_before_the_kind_field_reads_as_organisations() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    Every entry the registry held on 2026-08-31 was a standing organisation, so
    absence has exactly one honest meaning and the change needs no migration.
    """
    payload = watchlist_payload()
    for entity in payload["entities"]:
        del entity["kind"]
    payload["version"] = "2026-08-26"
    older = Watchlist.model_validate(payload)
    assert {entity.kind for entity in older.entities} == {EntityKind.ORGANISATION}


def test_every_committed_registry_entry_is_still_an_organisation() -> None:
    """The row's oracle, and the reason the gap measurement is worth taking.

    A half-life on a company is meaningless - its gap between our own mentions
    is near zero. Until a subject is curated in, the widening carries no
    behaviour, and this test says so out loud rather than leaving it implied.
    """
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert [entity.id for entity in watchlist.entities if entity.kind is EntityKind.SUBJECT] == []


def test_the_committed_watchlist_survives_a_read_and_a_rewrite() -> None:
    """A hand-edited config re-serializes to the bytes on disk.

    Without that, a curator's next edit arrives buried in a whole-file
    reshuffle and the diff stops showing what changed.
    """
    text = read_text(CONFIG_DIR / "watchlist.json")
    assert Watchlist.from_json(text).to_json() == text


# --- Two feed lists, and the line between them ------------------------------


def sources_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json")
    )
    return payload


def test_a_retired_feed_cannot_sit_in_the_live_list() -> None:
    """The split is only real if the shape refuses the old arrangement.

    `feeds` is the list Collect loops. A retired entry there would cost a
    request every run and reach a reader, which is the exact failure the split
    exists to end - so it is a load error, not a filter someone remembers.
    """
    payload = sources_payload()
    payload["feeds"].append(payload["retired"].pop())
    with pytest.raises(ValueError, match="belongs in `retired`"):
        Sources.model_validate(payload)


def test_a_live_feed_cannot_hide_on_the_tombstone_shelf() -> None:
    """The other direction, which is the quieter bug.

    A feed parked in `retired` with an active status is never fetched, and
    nothing says so. It just stops producing, and the config still reads as
    though it were being consulted.
    """
    payload = sources_payload()
    payload["retired"][0]["status"] = "active"
    payload["retired"][0]["retired_on"] = None
    with pytest.raises(ValueError, match="without a retired status"):
        Sources.model_validate(payload)


def test_yesterdays_sources_file_fails_loudly_and_names_the_key() -> None:
    """The migration ruling, pinned.

    `config/sources.json` is written by a person in the same commit as the
    model, so there is no read-side migration and no silent coercion at the
    boundary. What replaces it is a load error that names the key the entry has
    to move to - which is only worth relying on if it is tested.
    """
    legacy = sources_payload()
    legacy["feeds"].extend(legacy.pop("retired"))
    with pytest.raises(ValueError, match="`retired`"):
        Sources.model_validate(legacy)


def test_an_id_is_unique_across_all_three_lists() -> None:
    """A duplicate id is what makes a published `source_id` ambiguous.

    Checking `feeds` alone would have let a tombstone shadow a live feed - two
    titles and two kinds for one id, with the winner decided by list order.
    """
    payload = sources_payload()
    payload["retired"][0]["id"] = payload["feeds"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)

    payload = sources_payload()
    payload["salience"][0]["id"] = payload["retired"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)


def test_an_address_is_not_read_twice_under_two_ids() -> None:
    """Retiring a feed and re-adding it under a new id is a real editing move.

    Left unchecked it doubles every request to that host and carries the same
    story twice, which reads as corroboration.
    """
    payload = sources_payload()
    payload["retired"][0]["url"] = payload["feeds"][0]["url"]
    with pytest.raises(ValueError, match="urls must be distinct"):
        Sources.model_validate(payload)


def test_a_tombstone_still_answers_for_the_items_it_published() -> None:
    """`known_feeds` is the union both label maps read (`assemble.py`).

    An item published before a feed retired keeps its `source_id` forever. If
    the id stops resolving, the page shows the raw slug and the item is
    republished as `reporting` - relabelling an announcement as journalism.
    """
    sources = Sources.from_json(read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json"))
    known = {feed.id for feed in sources.known_feeds()}
    assert known == {feed.id for feed in sources.feeds} | {feed.id for feed in sources.retired}
    assert "example-defunct-daily" in known


def test_the_lens_vocabulary_is_closed() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["lenses"].pop()
    with pytest.raises(ValueError, match="every LensId"):
        Taxonomy.model_validate(payload)


def test_runs_are_append_only() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][1]["n"] = 3
    payload["runs"][1]["run_id"] = "2026-08-21-3"
    with pytest.raises(ValueError, match="without gaps"):
        RunManifest.model_validate(payload)


def test_run_counts_reconcile() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][0]["items_failed"] = 0
    with pytest.raises(ValueError, match="must equal planned"):
        RunManifest.model_validate(payload)


def test_a_manifest_written_before_charts_were_counted_still_reads() -> None:
    """Section 11's release blocker for `charts_drafted`, tested against the key."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in payload["runs"]:
        del run["charts_drafted"]
    assert [run.charts_drafted for run in RunManifest.model_validate(payload).runs] == [0, 0]


def test_a_published_chart_written_before_the_field_reads_as_a_chart_draft() -> None:
    """A chart on the page was necessarily the chart the model asked for.

    Defaulting the missing key to false would make the manifest report fewer
    drafts than published charts, which is the one thing `charts_drafted` exists
    to measure.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "route" / "chart-rendered.json"))
    del payload["drafted_chart"]
    assert Route.model_validate(payload).drafted_chart is True

    absent = json.loads(read_text(CONTRACT_FIXTURES_DIR / "route" / "none.json"))
    del absent["drafted_chart"]
    assert Route.model_validate(absent).drafted_chart is False


def test_a_later_run_appends_and_never_reorders() -> None:
    """Row 13's monotonicity rule, made mechanical."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"].insert(0, payload["items"].pop())
    with pytest.raises(ValueError, match="never reorders"):
        DigestDay.model_validate(payload)


def test_a_partial_day_says_so() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json", partial=False)
    with pytest.raises(ValueError, match="partial"):
        DigestDay.model_validate(payload)


def test_vertical_counts_agree_with_the_items() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["verticals"][0]["count"] = 5
    with pytest.raises(ValueError, match="count disagrees"):
        DigestDay.model_validate(payload)


def test_a_revision_names_the_run_that_wrote_it() -> None:
    """Either both revision fields are set or neither is. One of the two alone is a wrong join."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)

    payload["items"][0]["updated_by_run"] = 2
    assert DigestDay.model_validate(payload).items[0].updated_by_run == 2

    del payload["items"][0]["updated_at"]
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)


def test_a_revision_cannot_precede_the_run_that_introduced_the_item() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][2]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][2]["updated_by_run"] = 1
    with pytest.raises(ValueError, match="cannot precede"):
        DigestDay.model_validate(payload)


def test_an_item_cannot_name_a_revising_run_the_day_never_recorded() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][0]["updated_by_run"] = 3
    with pytest.raises(ValueError, match="revised by a run that is not recorded"):
        DigestDay.model_validate(payload)


def test_a_day_written_before_the_revision_field_still_loads() -> None:
    """Additive and null-defaulted, so no committed payload had to be rewritten."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in payload["items"]:
        del item["updated_by_run"]

    day = DigestDay.model_validate(payload)

    assert [item.updated_by_run for item in day.items] == [None] * len(day.items)


# --- the ranking signal and the clock behind published_at ------------------

#: The five the planning step computes and the day payload started carrying on
#: 2026-08-31. Every day published before that omits all five.
RANKING_SIGNAL = ("carried_by", "watchlist_hit", "on_front_page", "rank_score", "time_source")
DESK_SHORTFALL = ("considered", "too_old", "below_feed_floor")


def committed_days() -> list[Path]:
    return sorted((REPO_ROOT / "frontend" / "public" / "digest").glob("*/*/*/digest.json"))


def test_the_published_tree_holds_days_to_migrate() -> None:
    """The denominator, asserted on its own.

    The migration test below loops over the committed days. An empty tree would
    loop zero times and report the same pass as a tree that checked every day.
    """
    assert committed_days(), "no digest.json under frontend/public/digest"


# --- the guard that replaced the one prerendering used to give free ---------


def a_day_that_validates() -> dict[str, Any]:
    """A committed day, taken off the real tree rather than written here.

    A day composed by hand drifts from the one the pipeline writes, and the
    guard under test is about the real file.
    """
    day: dict[str, Any] = json.loads(read_text(committed_days()[-1]))
    return day


def a_tree_holding(tmp_path: Path, day: dict[str, Any], date: str = "2026-08-30") -> Path:
    """One committed day on disk, in the layout `published_days` globs for."""
    year, month, dom = date.split("-")
    where = tmp_path / "digest" / year / month / dom
    where.mkdir(parents=True)
    (where / "digest.json").write_text(json.dumps(day), encoding="utf-8")
    return tmp_path / "digest"


def test_every_committed_day_passes_the_gate_that_replaced_the_build(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The CI step, run here so it is not first seen on a runner.

    Until the reading routes were split on 2026-09-01 every story was serialised
    into a document at build time, so a story the contract refused took the
    build down. A reading document now carries a seed, so the build never opens
    the stories past it. This is what took that over.
    """
    with caplog.at_level(logging.INFO):
        assert stage_validate_days(REPO_ROOT / "frontend" / "public" / "digest") == 0
    assert "committed days match both contracts" in caplog.text


def test_a_story_past_the_seed_is_the_one_this_gate_exists_for(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The exact hole the migration opened, and the reason a step replaced a build.

    The story is broken at the END of a day longer than `ui.shell_seed_items`,
    so no prerendered document carries it and no build would ever open it. A
    reader's browser fetches it. The gate has to find it there.
    """
    day = a_day_that_validates()
    seed = UiConfig().shell_seed_items
    assert len(day["items"]) > seed, "a day no longer than the seed proves nothing here"
    day["items"][-1]["key_points"] = []

    root = a_tree_holding(tmp_path, day)
    with caplog.at_level(logging.ERROR):
        assert stage_validate_days(root) == 1
    assert "2026-08-30" in caplog.text, "the failing day has to be named"
    assert "digest-view.schema.json" in caplog.text, "which contract refused it"


def test_a_day_that_is_not_json_at_all_is_named_rather_than_thrown(tmp_path: Path) -> None:
    """Degrade, do not fail: one unreadable file must not stop the other days."""
    root = a_tree_holding(tmp_path, a_day_that_validates(), date="2026-08-29")
    broken = root / "2026" / "08" / "30"
    broken.mkdir(parents=True)
    (broken / "digest.json").write_text("{ not json", encoding="utf-8")

    assert stage_validate_days(root) == 1


def test_a_tree_with_no_committed_day_fails_rather_than_passes(tmp_path: Path) -> None:
    """A run over nothing prints the same line as a run over every day."""
    empty = tmp_path / "digest"
    empty.mkdir()
    assert stage_validate_days(empty) == 1


def test_the_gate_defaults_to_the_one_committed_tree() -> None:
    """Unlike `--site-tree`, which has no default because there are two trees.

    There is exactly one committed digest tree, so a default cannot point at the
    wrong one - and a step nobody has to give a path to is a step nobody gets
    wrong in a workflow.
    """
    assert main(["validate-days"]) == 0


def test_a_committed_day_reads_an_absent_ranking_field_as_unknown() -> None:
    """The read-side migration (`CLAUDE.md` section 11), over the real payloads.

    A day written before the five fields existed omits them, and every one must
    come back as `None`. `0` for `carried_by` would claim no feed carried the
    story, `false` for `on_front_page` would claim a vote that was never
    counted, and `0.0` for `rank_score` would put the story bottom of its desk -
    three different false claims dressed as a default.

    The oracle reads the raw payload beside the parsed day and only judges a
    field the file does not carry. Asserting instead that no committed day
    carries any of the five was true for one afternoon and false from the first
    run that published with the new writer.
    """
    items = 0
    absent = 0
    for path in committed_days():
        text = read_text(path)
        written = json.loads(text)["items"]
        day = DigestDay.from_json(text)
        for payload, item in zip(written, day.items, strict=True):
            items += 1
            for name in RANKING_SIGNAL:
                if name in payload:
                    continue
                absent += 1
                assert getattr(item, name) is None, f"{path.name} {item.item_id}: {name} invented"

    assert items, "the loop above must have had something to read"
    assert absent, "every committed item carries all five, so nothing here reads an absent field"


def test_every_committed_day_revalidates_with_no_shortfall_counts() -> None:
    """The read-side migration for the desk shortfall (`CLAUDE.md` section 11).

    Every day published before 2026-09-02 carries a desk as three keys - id,
    name and count - so the three counts appended today have to be absent and
    have to come back as `None`. A `0` for `considered` would say the sources
    offered that desk nothing, which is the opposite of what a day with 216
    stories on it means.

    The oracle reads the raw payload beside the parsed day, so it keeps working
    from the first run that publishes with the new writer: it judges only a key
    the file does not carry.
    """
    days = 0
    desks = 0
    absent = 0
    for path in committed_days():
        text = read_text(path)
        written = json.loads(text)["verticals"]
        day = DigestDay.from_json(text)
        days += 1
        for payload, desk in zip(written, day.verticals, strict=True):
            desks += 1
            for name in DESK_SHORTFALL:
                if name in payload:
                    continue
                absent += 1
                assert getattr(desk, name) is None, f"{path.name} {desk.id}: {name} invented"

    assert days, "no committed day was read, so this proved nothing"
    assert desks, "the committed days carry no desks to read"
    assert absent, "every committed desk carries all three, so nothing read an absent field"


def test_a_desk_carries_every_shortfall_count_or_none_of_them() -> None:
    """Three fields written by one step, so a desk holding two is a writer bug.

    It also keeps the read side simple: a page asks whether the desk knows why
    it is thin, not whether it knows two thirds of it.
    """
    with pytest.raises(ValueError, match="every shortfall field or none"):
        DigestVerticalRef(id="ai", display_name="AI", count=3, considered=40)

    whole = DigestVerticalRef(
        id="ai", display_name="AI", count=3, considered=40, too_old=31, below_feed_floor=False
    )
    assert whole.considered == 40


def test_a_desk_cannot_drop_more_stories_than_it_considered() -> None:
    """The same bound `VerticalPlan` carries, kept on the field a reader sees.

    The sentence names both numbers, so a payload where the second exceeds the
    first prints a page saying more stories were too old than were ever offered.
    """
    with pytest.raises(ValueError, match="more stories than it considered"):
        DigestVerticalRef(
            id="ai", display_name="AI", count=1, considered=3, too_old=4, below_feed_floor=False
        )


def test_the_thin_desk_floor_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem again, on the knob that decides whether a desk speaks.

    The rule runs in the browser off the frontend's own default, so a fresh
    clone with no `config/` resolves it there. Let the two drift and the page
    explains a desk the contract would call healthy, or stays silent on one it
    would call thin - and nothing else would catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"desk_thin_max:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its desk_thin_max default"
    assert int(mirrored.group(1)) == UiConfig().desk_thin_max


def test_a_published_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestDay.model_validate(payload)


def test_a_published_item_with_no_time_may_only_say_unknown() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "unknown"

    day = DigestDay.model_validate(payload)

    assert day.items[0].time_source is TimeSource.UNKNOWN
    assert day.items[0].published_at is None


def test_a_planned_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "first_seen"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        RunPlan.model_validate(payload)


def test_the_ranking_signal_survives_a_round_trip_with_values_in_it() -> None:
    """The fixture carries nulls, so the populated shape needs its own oracle."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0].update(
        carried_by=3, watchlist_hit=True, on_front_page=True, rank_score=3.4, time_source="feed"
    )

    once = DigestDay.model_validate(payload).to_json()
    twice = DigestDay.from_json(once)

    assert twice.to_json() == once
    assert twice.items[0].carried_by == 3
    assert twice.items[0].rank_score == 3.4
    assert twice.items[0].time_source is TimeSource.FEED


def test_a_story_no_feed_carried_cannot_be_published() -> None:
    """`carried_by` counts the feeds that carried one address, so its floor is 1.

    Null is how a run that did not record the count says so. Zero would be a
    story that arrived from nowhere.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["carried_by"] = 0
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        DigestDay.model_validate(payload)


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'


# --- the served day --------------------------------------------------------

#: The projector that writes the served file. It runs in node at build time, so
#: the shape lives here and the behaviour lives there - and these tests are what
#: stop the two halves of one payload drifting across two languages.
PROJECT_TS = REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "project.ts"


def projector_array(name: str) -> list[str]:
    match = re.search(
        rf"export const {name}: readonly string\[\] = \[(.*?)\];", read_text(PROJECT_TS), re.DOTALL
    )
    assert match, f"{name} is no longer a string array in project.ts"
    return re.findall(r"'([a-z_]+)'", match.group(1))


def projector_version() -> str:
    match = re.search(r"export const VIEW_VERSION = '([^']+)';", read_text(PROJECT_TS))
    assert match, "VIEW_VERSION is no longer a string literal in project.ts"
    return match.group(1)


def without_description(shape: dict[str, Any]) -> dict[str, Any]:
    """The same field, minus the prose.

    The served item says what an absent value means to a reader; the published
    item says what the run recorded. Different sentences, same field.
    """
    return {key: value for key, value in shape.items() if key != "description"}


def test_the_projector_writes_exactly_the_shape_the_contract_names() -> None:
    """Rule #3, across a language boundary.

    The file a browser fetches is written by node and described by a Pydantic
    model. Nothing else connects them, so a name added on one side and not the
    other ships a payload that does not match its own schema.
    """
    assert projector_version() == DigestView.schema_version()
    assert set(projector_array("ITEM_FIELDS")) == set(DigestViewItem.model_fields)
    assert set(projector_array("VISUAL_FIELDS")) == set(DigestViewVisual.model_fields)
    assert set(projector_array("DAY_FIELDS")) | {"version"} == set(DigestView.model_fields)


def test_the_block_this_projection_exists_to_drop_can_never_be_served() -> None:
    forbidden = set(projector_array("FORBIDDEN_FIELDS"))
    assert "embeddings" in forbidden, "the vector block is why this projection exists"
    kept = set(DigestViewItem.model_fields) | set(DigestView.model_fields)
    assert forbidden.isdisjoint(kept), f"served and forbidden at once: {sorted(forbidden & kept)}"


def test_the_served_item_is_a_narrowing_of_the_published_one() -> None:
    """A field means one thing, whichever file it is in.

    The served day is a projection, not a second vocabulary. Every name on it is
    a name the published item already has, with the same type and the same
    bounds - so a page reading the fetched file and a page reading the committed
    one cannot disagree about what they read.
    """
    published = DigestItem.model_json_schema()["properties"]
    served = DigestViewItem.model_json_schema()["properties"]

    assert set(served) < set(published), "the served item names a field the published one does not"
    for name, shape in served.items():
        if name == "visual":
            continue
        assert without_description(shape) == without_description(published[name]), name

    # The visual is the one field that is itself narrowed: `kind` is read at
    # build time for the console's chart count and no browser needs it.
    assert set(DigestViewVisual.model_fields) < set(DigestVisual.model_fields)


def test_every_committed_day_serves_a_view_that_validates() -> None:
    """The migration, over every day a reader can already fetch.

    Each committed day must project to a payload the contract accepts, and a
    field the file does not carry must come back unknown rather than as a number
    the run never recorded.

    The oracle reads the raw payload beside the served item and only judges a
    field the file omits, for the same reason the published-day test next to it
    does: asserting that no committed day carries any of the five was true for
    one afternoon and false from the first run that published with the new
    writer.
    """
    days = 0
    items = 0
    absent = 0
    for path in committed_days():
        written = json.loads(read_text(path))
        view = DigestView.project(written)
        days += 1
        for payload, item in zip(written["items"], view.items, strict=True):
            items += 1
            for name in RANKING_SIGNAL:
                if name in payload:
                    continue
                absent += 1
                assert getattr(item, name) is None, f"{path.name} {item.item_id}: {name} invented"

    assert days and items, "the loop above must have had something to read"
    assert absent, "every committed item carries all five, so nothing here reads an absent field"


def test_a_served_day_refuses_a_field_it_does_not_know() -> None:
    """The build is strict where the shell is tolerant, and that pairing is the design.

    A reader's browser must render a payload from a newer build, so its read is
    `JSON.parse` and nothing else. The build has no such excuse: a key nobody
    declared is a projection that widened without a decision, and it fails here
    rather than shipping.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["a_field_from_a_later_build"] = "a value no shell has ever seen"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DigestView.model_validate(payload)


def test_a_served_day_keeps_the_order_a_reader_already_read() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"].insert(0, payload["items"].pop())
    payload["items"][0]["introduced_by_run"] = 2
    with pytest.raises(ValueError, match="never reorders"):
        DigestView.model_validate(payload)


def test_a_served_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestView.model_validate(payload)


def test_a_served_day_written_before_the_version_existed_still_reads() -> None:
    """Section 11's release blocker, at the boundary that cannot be upgraded.

    A shell fetching a file this build did not write is the case the version is
    here for. The payload still loads and the stamp says which shape it is.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    del payload["version"]

    assert DigestView.model_validate(payload).version == DigestView.schema_version()
