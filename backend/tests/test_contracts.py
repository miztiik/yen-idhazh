"""Contract-tier tests: the generated schemas against the models that produced
them, and the models against real committed payloads.

No mocks and no network (Rule #7): every input here is a file in
`tests/fixtures/` or `config/`.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, SCHEMAS_DIR, read_text

from idhazh.contracts import canonical_json, derive_url_key
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.item_health import (
    SOURCE_NEUTRAL_FAILURE_CODES,
    FailureCode,
    ItemHealthRow,
)
from idhazh.contracts.route import Route
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}
CONFIG_FILES: dict[str, type[Contract]] = {
    "idhazh.json": AppConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}
LONG_HEX = re.compile(r"[0-9a-f]{16,}")


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


def test_every_configured_feed_names_a_declared_vertical() -> None:
    """Retired feeds too - a tombstone still labels published items by vertical."""
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    declared = {vertical.id for vertical in taxonomy.verticals}
    for feed in sources.known_feeds():
        assert feed.vertical in declared, f"feed {feed.id} names an undeclared vertical"


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
    )


def test_recorded_item_health_codes_never_count_against_a_source() -> None:
    assert len(SOURCE_NEUTRAL_FAILURE_CODES) == 12
    assert FailureCode.NOT_ATTEMPTED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_UNREACHABLE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.NOT_PROSE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.BOILERPLATE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.HTTP_CLIENT_ERROR not in SOURCE_NEUTRAL_FAILURE_CODES


def test_item_health_csv_round_trip_uses_empty_cells_for_absent_values() -> None:
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    cells = row.csv_row()
    assert cells["code"] == ""
    assert cells["http_status"] == ""
    assert ItemHealthRow.from_csv_row(cells) == row


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
