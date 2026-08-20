"""Contract-tier tests: the generated schemas against the models that produced
them, and the models against real committed payloads.

No mocks and no network (Holy Law #7): every input here is a file in
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
    assert minimal.run.item_cap_per_day == committed.run.item_cap_per_day
    assert minimal.retention.image_months == -1, "retention ships disabled"
    assert minimal.retention.dry_run is True


def test_every_configured_feed_names_a_declared_vertical() -> None:
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    declared = {vertical.id for vertical in taxonomy.verticals}
    for feed in sources.feeds:
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
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "article" / "fetch-failed.json", failure_detail=None
    )
    with pytest.raises(ValueError, match="must record why"):
        Article.model_validate(payload)


def test_truncation_is_flagged_and_located_together() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "article" / "truncated.json", truncated_at_tokens=None
    )
    with pytest.raises(ValueError, match="truncated"):
        Article.model_validate(payload)


def test_a_routed_to_nothing_item_carries_no_spec() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "route" / "none.json", spec="anything")
    with pytest.raises(ValueError, match="no spec"):
        Route.model_validate(payload)


def test_only_a_rendered_visual_has_an_asset_path() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "route" / "chart-rendered.json", visual_state="absent"
    )
    with pytest.raises(ValueError, match="asset_path"):
        Route.model_validate(payload)


def test_hhem_delta_is_rebuilt_not_trusted() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json", hhem_delta=0.9)
    with pytest.raises(ValueError, match="hhem_delta"):
        EvalRow.model_validate(payload)


def test_a_retired_entry_must_carry_its_date() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["verticals"][2]["retired_on"] = None
    with pytest.raises(ValueError, match="retired_on"):
        Taxonomy.model_validate(payload)


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


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'
