"""Contract-tier tests: the generated schemas against the models that produced
them, and the models against real committed payloads.

No mocks and no network (Rule #7): every input here is a file in
`tests/fixtures/` or `config/`.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
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

from idhazh.contracts import canonical_json, derive_url_key
from idhazh.contracts.app_config import (
    AppConfig,
    ConsoleConfig,
    EvaluationConfig,
    PageWeightConfig,
)
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.item_health import (
    FAILURE_CODE_STAGES,
    SOURCE_NEUTRAL_FAILURE_CODES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.route import Route
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.runtime_counters import SERIES, RuntimeCountersRow
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.fingerprint import text_digest
from idhazh.publish_telemetry import PUBLIC_COLUMNS

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


def test_the_console_chart_width_is_a_knob_the_frontend_agrees_with() -> None:
    """A prerendered chart has no element to measure, so the width is given to it.

    The frontend keeps its own copy of every console default so a fresh clone
    renders without `config/`. Two copies of one number drift, so the copy is
    checked against the model rather than trusted.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    minimal = AppConfig.model_validate({"models": committed.models.model_dump()})
    assert committed.console.chart_width == minimal.console.chart_width

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"chart_width:\s*(\d+)", reader)
    assert mirrored is not None, "the frontend console defaults dropped chart_width"
    assert int(mirrored.group(1)) == minimal.console.chart_width


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
    """The same two-copies problem `chart_width` has, one field along.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. If the two lists drift, the page draws a button for a window the
    contract would refuse.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"window_presets:\s*\[([\d,\s]+)\]", reader)
    assert mirrored is not None, "the frontend console defaults dropped window_presets"
    assert [int(part) for part in mirrored.group(1).split(",")] == ConsoleConfig().window_presets


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


def test_the_committed_config_carries_the_capped_routes() -> None:
    """`frontend/scripts/bundle-gate.mjs` reads the file, never the model, and
    the model default is empty - so the committed config is the only place the
    capped routes live. If it lost them the gate would check nothing while every
    other knob still read correctly.

    `/archive/` is capped again since 2026-08-27, because it stopped inlining the
    day payloads and now grows by one day link a day. The assertion below is on
    its size rather than on its presence: a ceiling at the megabyte the page used
    to weigh is a gate that never fires, so the number has to stay in the
    thousands. `/console/` is capped since 2026-08-29 and its assertion has the
    same shape for the same reason - the regression a page ceiling exists to
    catch on this route is a day payload inlined by a layout, which cost 313,300
    gzipped bytes when it last happened, so a ceiling more than that above the
    page could never see it land again.
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
    assert ceilings["/console/"] < 482_000, (
        "the console ceiling is above the 170,281 the page measured plus the 313,300 a "
        "day payload cost when a layout last inlined one - a ceiling that high cannot "
        "catch the one regression this route has actually had"
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

    It reads the committed config on purpose. The number that decides a run is
    the one in `config/`, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    live = Counter(
        feed.vertical for feed in sources.feeds if feed.status is LifecycleStatus.ACTIVE
    )
    for vertical in taxonomy.verticals:
        assert live[vertical.id] >= vertical.min_feeds, (
            f"{vertical.id} has {live[vertical.id]} active feeds against a floor of "
            f"{vertical.min_feeds}, so it would publish nothing"
        )


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

    `collect.quarantine_after_failures` is 5, so leaving either code out of the
    source-neutral set would take a working feed off the list on the fifth copy.
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


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'
