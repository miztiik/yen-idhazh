"""Where is a model's turn envelope declared, and what does a run record of it?"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import cli, config, ledger, source_health
from idhazh.contracts.app_config import (
    SUPERSEDED_COLLECT_NAMES,
    SUPERSEDED_RETENTION_NAMES,
    AppConfig,
    CollectConfig,
    ConsoleConfig,
    ModelEntry,
    ModelRef,
    ModelsConfig,
    ObservabilityConfig,
    PageWeightConfig,
)
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest, VerticalCount
from idhazh.contracts.run_plan import PUBLISHED_AGE_BANDS, PublishedAgeBand, RunPlan, VerticalPlan
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.retention import oldest_month_kept

from ._fixtures import (
    APP_CONFIG_EVERY_KNOB_DIFFERS,
    committed_models,
    committed_models_raw,
    desk,
    swapped_summarizer,
)

pytestmark = pytest.mark.contract


def turns_of(raw: dict[str, Any], role: str = "summarize") -> dict[str, Any]:
    block: dict[str, Any] = raw[role]["turns"]
    return block

def test_a_model_swap_can_no_longer_inherit_markers_nothing_declared_for_it() -> None:
    """The Oracle for the envelope, and the same rule the settings block obeys.

    A wrong marker is worse than a wrong number: it renders a prompt with no
    turn structure that the decoder's grammar still accepts, so the run
    publishes a plausible day and nothing anywhere raises.

    The swap here is the half-done one - `inference` re-declared for the new
    weights and `turns` left behind - because a swap that moved neither block is
    already refused by the settings gate above and would prove nothing here.
    """
    committed = committed_models()
    assert committed.summarize.turns.declared_for == committed.summarize.sha256

    raw = swapped_summarizer()
    raw["summarize"]["inference"]["declared_for"] = "1" * 64
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(raw)
    message = str(raised.value)
    assert "models.summarize.turns" in message, "the message names the block"
    assert "re-record them for these weights" in message, "and what to do about it"
    assert "1" * 64 in message, "and the weights the entry now names"

def test_an_entry_with_no_turn_envelope_at_all_is_refused() -> None:
    """Required with no default. An entry that forgets its markers fails at load."""
    raw = committed_models_raw()
    del raw["summarize"]["turns"]
    with pytest.raises(ValidationError, match="turns"):
        ModelsConfig.model_validate(raw)

@pytest.mark.parametrize("marker", ["turn_closing", "reply_opening", "reply_opening_thinking"])
def test_an_empty_marker_is_refused(marker: str) -> None:
    """`continued_prompt` splices call 2 onto `turn_closing`.

    An empty seam joins two turns into one, the grammar still answers, and the
    prefix the two-call design rests on is gone with nothing to read it off.
    """
    raw = committed_models_raw()
    turns_of(raw)[marker] = ""
    with pytest.raises(ValidationError, match="at least 1 character"):
        ModelsConfig.model_validate(raw)

@pytest.mark.parametrize("opening", ["<|im_start|>\n", "<|im_start|>$speaker\n"])
def test_a_turn_opening_that_names_no_role_is_refused(opening: str) -> None:
    """A substitution over a string that names nothing returns it unchanged.

    Every turn then renders with no role header, the prompt is still
    syntactically fine, and no reader downstream can tell. The second arm is the
    renamed placeholder, which raises at the first render rather than at load -
    late, and in the middle of a shard.
    """
    raw = committed_models_raw()
    turns_of(raw)["turn_opening"] = opening
    with pytest.raises(ValidationError, match=re.escape("must name $role")):
        ModelsConfig.model_validate(raw)

def test_a_run_records_which_weights_ran_and_not_how_their_turns_are_written() -> None:
    """The split the envelope is required on one shape and absent from the other for.

    `ModelUse` embeds `ModelRef`, and no `model_ref` a run has ever written
    carries markers - requiring it there would stop this build reading them
    (`CLAUDE.md` section 11). So the entry is narrowed on the way into the
    record, and this asserts the narrowing rather than trusting it: a leaked
    `turns` would pass `extra="forbid"` on write and fail on the next read.

    What is given up is that `run.json` never says how the turns were written.
    `RunRecord.inputs.prompt_sha256` digests both turns rendered through them,
    so a marker that moved still moves the stamp.
    """
    entry = committed_models().summarize
    assert "turns" not in ModelRef.model_fields
    assert "turns" in ModelEntry.model_fields

    use = ModelUse(role=ModelRole.SUMMARIZE, model_ref=entry)
    recorded = json.loads(use.model_dump_json())

    assert "turns" not in recorded["model_ref"]
    assert recorded["model_ref"]["sha256"] == entry.sha256
    ModelUse.model_validate(recorded), "and the record it wrote reads back"

def test_the_retired_marker_file_is_refused_if_it_comes_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file nothing reads is a set of markers an operator believes are live.

    The package directory is exactly where somebody would put them back, so the
    path is checked rather than forgotten. Proved by making the file and watching
    the refusal, never by asserting it is absent - an assertion that it is absent
    passes on a tree where the check does not exist.

    The file is made at a redirected path, and the real one is pinned by a
    separate assertion. The suite runs several processes over one working tree,
    so a file written into the package refuses every config load a sibling
    process happens to be making at that moment.
    """
    assert config.RETIRED_TURN_MARKERS == (
        REPO_ROOT / "backend" / "idhazh" / "prompts" / "turn_markers.json"
    ), "the check must name the package directory, which is where they would come back"
    assert not config.RETIRED_TURN_MARKERS.exists(), "the row deleted it"

    came_back = tmp_path / "turn_markers.json"
    came_back.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(config, "RETIRED_TURN_MARKERS", came_back)
    with pytest.raises(ValueError, match=re.escape("models.<role>.turns")):
        config.load(CONFIG_DIR)

    monkeypatch.undo()
    assert config.load(CONFIG_DIR).models.summarize.turns.turn_closing

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
    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS)).collect
    assert committed.availability_strikes_before_rest == 5
    assert tuned.availability_strikes_before_rest == 3

    source = read_text(REPO_ROOT / "backend" / "idhazh" / "stages" / "plan.py")
    assert "after_failures=collect.availability_strikes_before_rest" in source

def test_the_router_exposes_no_name_a_stage_owns() -> None:
    """`idhazh.cli` picks which stage runs. It is never a second name for one.

    A re-export reads as convenience and costs two things. It is an import path
    nobody declared - a caller writes `cli.stage_work` and the router becomes
    the listed home of code it does not contain, so the next reader looks for
    the work in the wrong file. And it makes one shape of redirect silent:
    `setattr(cli, "_picture_faults", ...)` rebinds the router's copy while the
    stage goes on calling the shipped rule out of its own module, so the test
    passes against the thing it meant to replace.

    So the router imports stage modules and never the names inside them. This
    reads the imported module rather than its source, because an import written
    anywhere in the chain republishes a name just as effectively as one written
    in `cli.py`.
    """
    owned: dict[str, str] = {}
    for path in sorted((REPO_ROOT / "backend" / "idhazh" / "stages").glob("*.py")):
        if path.stem == "__init__":
            continue
        for node in ast.parse(read_text(path)).body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                owned.setdefault(node.name, path.stem)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                owned.setdefault(node.target.id, path.stem)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        owned.setdefault(target.id, path.stem)
    assert owned, "no stage modules were read, so this test proves nothing"

    leaked = sorted(
        f"cli.{name} is really idhazh.stages.{stem}.{name}"
        for name, stem in owned.items()
        if not name.startswith("__") and hasattr(cli, name)
    )
    assert not leaked, (
        "the router re-exports a name a stage owns, so a caller can reach the stage "
        "through cli and a redirect left on cli would bind a copy nothing reads. "
        "Import the module, not the name: " + "; ".join(leaked)
    )

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

def test_the_published_window_is_unbounded_or_outlives_the_first_sight_store() -> None:
    """The Oracle for the cover setting: `-1`, or strictly longer than the seen window.

    The mistake this makes impossible is a republication. An address the archive
    has forgotten, whose first-sighting row expires in the same week, reads as
    first-seen-today: it clears the freshness gate and goes out as new. So EQUAL
    IS A HOLE, NOT A BOUND - at 90 and 90 the two stores forget the same address
    on the same day and neither one is left holding the evidence. Only two
    answers are safe: never forget, or forget later than the first-sight store
    does.

    `-1` is the only sentinel for unbounded. Not `0`, not `null`, and not a very
    large number - a large number is a cover that silently becomes finite the
    day the archive outgrows it, and it fails quietly at exactly the size where
    the hole matters most.
    """
    fresh = CollectConfig()
    assert fresh.published_window_days == -1, "the machinery ships unbounded"
    assert fresh.seen_window_days == 90

    for refused in (0, 89, 90):
        with pytest.raises(ValidationError) as raised:
            CollectConfig(published_window_days=refused)
        message = str(raised.value)
        assert "collect.seen_window_days, which is 90" in message, message

    for accepted in (-1, 91, 120):
        assert CollectConfig(published_window_days=accepted).published_window_days == accepted

    # Cross-field, so it re-runs when the OTHER number moves. Raising the
    # first-sight window past a finite cover must fail the config rather than
    # open the hole quietly.
    with pytest.raises(ValidationError) as widened:
        CollectConfig(published_window_days=120, seen_window_days=180)
    assert "collect.seen_window_days, which is 180" in str(widened.value)
    assert (
        CollectConfig(published_window_days=120, seen_window_days=119).published_window_days == 120
    )

    # A finite cover under an unbounded first-sight store is not expressible -
    # `seen_window_days` is `ge=1` - so the only pairing left to check is the
    # committed one, and it must ship unbounded.
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert raw["collect"]["published_window_days"] == -1, (
        "the committed config must ship the cover unbounded"
    )
    assert (
        AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).collect.published_window_days
        == -1
    )

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

@pytest.mark.parametrize(
    ("block", "knob"),
    [
        ("models", "visual_planner"),
        ("models", "route"),
        ("run", "two_calls_per_item"),
        ("run", "visual_planner_budget_minutes"),
        ("run", "route_budget_minutes"),
        ("finetune", "student"),
    ],
)
def test_a_config_still_spelling_a_retired_knob_is_refused_by_name(block: str, knob: str) -> None:
    """Section 11's read-side migration for plan 11 row #6, one key at a time.

    Six spellings died with the visual planner: the four keys the row deleted,
    and the two older names that used to be read as two of them. A rename onto a
    deleted key is worse than no migration at all - it takes an operator's
    number, files it under a key nothing reads, and raises nothing - so the
    rename went and this refusal took its place.

    Every model here forbids unknown keys, so any of these already fails. What
    the row owes is that it fails by NAME: "extra inputs are not permitted" does
    not tell an operator their planner is gone.

    Two documents since 2026-09-14: the `models` spellings are top-level keys of
    the model file now, and the rest are blocks of `config/idhazh.json`.
    """
    if block == "models":
        payload = committed_models_raw()
        assert knob not in payload, "the committed file must not spell the retired knob"
        payload[knob] = payload["summarize"]
        with pytest.raises(ValidationError, match=re.escape(f"{block}.{knob}")):
            ModelsConfig.model_validate(payload)
        return

    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert knob not in payload[block], "the committed file must not spell the retired knob"
    payload[block][knob] = 1

    with pytest.raises(ValidationError, match=re.escape(f"{block}.{knob}")):
        AppConfig.model_validate(payload)

def test_a_retired_knob_is_not_offered_a_replacement_that_does_not_exist() -> None:
    """The refusal says the knob is gone, never that it moved somewhere.

    `refuse_a_removed_knob` reads an empty replacement as "gone and nothing
    replaces it". Pointing a lost operator at a key that is also missing is the
    same defect one level down, and it is the one this wording exists to avoid.
    """
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    payload["run"]["two_calls_per_item"] = True

    with pytest.raises(ValidationError, match="is gone and nothing replaces it"):
        AppConfig.model_validate(payload)

def test_a_finetune_teacher_still_naming_the_retired_model_is_answered_by_name() -> None:
    """A role is spelled as a VALUE, so the key check cannot see it.

    `models.visual_planner` is refused as a key by the map above. A teacher
    naming that role is a string inside a legal key, and without this it would
    fail as "must name one of models: summarize" - which reads as a typo rather
    than as a model that was retired.
    """
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    payload["finetune"]["teacher"] = "visual_planner"

    with pytest.raises(ValidationError, match="retired with the visuals stage"):
        AppConfig.model_validate(payload)

def test_no_page_number_names_a_route_that_grows_when_a_run_publishes() -> None:
    """This test was the opposite of itself until 2026-09-10, and the inversion is
    the point.

    It used to insist `/archive/` and the three `/console/` routes each carried a
    byte number, on the argument that an unnamed route grows unwatched. What
    actually happened is that those four numbers moved when the pipeline
    published rather than when anybody wrote code, so the gate fired on ordinary
    publishing and the recorded answer was always a bigger number - `/archive/`
    twice in one day on 2026-08-26. Meanwhile `/console/` drifted to 7.2 times
    the page it bounded and stood there four days with the build green. A number
    that cannot tell correct from far-too-loose is not an instrument.

    **The property those numbers were a proxy for is asserted directly**, by
    `frontend/tests/payload-weight.spec.ts`: no document that does not render a
    day may contain a day payload marker. That is the one regression this surface
    has ever had - a layout inlining a day, 313,300 gzipped bytes on 2026-08-26 -
    and the marker check returns the same verdict whatever the archive holds.

    So the assertion is now on absence. `/404` and `/evals/` stay, because they
    pass the test in the name: they move only when a person edits source, never
    when a run appends a day. Owner ruling, 2026-09-10.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    ceilings = committed.page_weight.ceilings_bytes

    assert PageWeightConfig().ceilings_bytes == {}, "the model default must stay empty"
    assert ceilings["/404"] > 0
    assert ceilings["/evals/"] > 0
    for route in ("/archive/", "/console/", "/console/model/", "/console/machine/"):
        assert route not in ceilings, (
            f"{route} has a byte number again. Its weight moves when the pipeline "
            "publishes, so the number has to move too, and the only way past it is to "
            "type a bigger one - which is what got these four deleted. The regression "
            "worth catching here is a day payload inlined by a layout, and "
            "frontend/tests/payload-weight.spec.ts asserts that directly."
        )

def test_the_committed_config_caps_what_a_cold_console_load_fetches() -> None:
    """The page ceilings above cannot see these bytes, and that is why they exist.

    The console stopped inlining its telemetry on 2026-09-09. That took 3.4 MB out
    of a document a ceiling watched and put it into files nothing watched, and a
    reader still waits for them - measured 2026-09-10 in a real browser, a cold
    `/console/` load fetches two telemetry shards worth 303,306 bytes on the wire
    and no other payload at all. A document ceiling now reads as a bound on what
    the console costs a reader, and it is not one.

    `cold_console_load_bytes` bounds the design rather than the data: the per-file
    ceilings say how heavy one shard may be, this says how many of them one
    opening of the page is allowed to want. The two are asserted against each
    other here, because a total below the sum of its parts is a gate that cannot
    be satisfied at the limit and a total far above it is a gate that never fires.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    weight = committed.page_weight
    payloads = weight.payload_ceilings_bytes

    assert PageWeightConfig().payload_ceilings_bytes == {}, "the model default must stay empty"
    assert PageWeightConfig().cold_console_load_bytes == 0, "the model default must stay empty"

    for path in ("console/band.json", "telemetry/"):
        assert path in payloads, (
            f"{path} is fetched by a reader's browser and has no ceiling - the bundle "
            "gate cannot fail a file nobody named, so this one would grow unwatched"
        )

    # The worst case a run of N consecutive days can land in, because February is
    # the shortest month there is. Mirrors the arithmetic in bundle-gate.mjs.
    window = committed.console.default_window_days
    months_touched = 1 + -(-(window - 1) // 28)
    worst = payloads["console/band.json"] + months_touched * payloads["telemetry/"]
    assert weight.cold_console_load_bytes >= worst, (
        "a cold load of every payload sitting exactly on its own ceiling is already "
        f"over cold_console_load_bytes ({worst} against "
        f"{weight.cold_console_load_bytes}) - the two gates contradict each other"
    )
    assert weight.cold_console_load_bytes < worst + payloads["telemetry/"], (
        "cold_console_load_bytes has room for one more telemetry shard than the "
        "default window reaches, so widening console.default_window_days past a "
        "month would not fire it - which is the one thing it exists to catch"
    )

def test_a_page_ceiling_bounds_a_route_and_bounds_it_above_zero() -> None:
    """A ceiling of zero passes nothing and a key that is not a route bounds nothing."""
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(ceilings_bytes={"/evals/": 0})
    with pytest.raises(ValueError, match="is not a route"):
        PageWeightConfig(ceilings_bytes={"evals": 2475})

def test_a_payload_ceiling_bounds_a_path_in_the_build() -> None:
    """The leading slash is what tells the two objects apart.

    A route ceiling has one and a payload ceiling does not, so a number typed
    into the wrong object is refused by shape here rather than discovered later
    as a gate quietly checking nothing.
    """
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry/": 0})
    with pytest.raises(ValueError, match="is a route, not a path"):
        PageWeightConfig(payload_ceilings_bytes={"/telemetry/": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry\\2026-09.csv": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"../telemetry/": 500_000})

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
        if vertical.status is not LifecycleStatus.ACTIVE:
            continue
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

    Three listings - newest year, newest month, newest day - rather than a walk
    of the tree. The ledger files by day, so the newest file's own path IS the
    date, and the cost stays at most twelve plus thirty-one entries however long
    the project runs (`CLAUDE.md` section 13, Guardrail #12). It used to glob the
    month shards and hand back `<stem>-28`, which at day grain names a file the
    ledger may never have held.
    """
    root = state / ledger.HEALTH_DIRNAME
    years = [path for path in root.iterdir() if path.is_dir()] if root.is_dir() else []
    if not years:
        return "1970-01-01"
    year = max(years)
    month = max(path for path in year.iterdir() if path.is_dir())
    day = max(path for path in month.iterdir() if path.suffix == ".csv")
    return f"{year.name}-{month.name}-{day.stem}"

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

def bare_plan(**extra: Any) -> dict[str, Any]:
    """The smallest plan payload that validates, for the fields under test."""
    return {
        "date": "2026-08-21",
        "run_id": "2026-08-21-1",
        "generated_at": "2026-08-21T06:00:04Z",
        **extra,
    }

def test_a_plan_written_before_the_guard_was_counted_reads_as_unknown() -> None:
    """Null is unknown, never a run where the guard refused nothing.

    A zero would say this run was offered addresses the ledger held and refused
    none of them, which is a measurement. A payload written before anything
    counted cannot make it, and inventing one is how an unread number turns into
    an argument about how wide the cover should be.
    """
    built = RunPlan.model_validate(bare_plan())
    assert built.dropped_published is None
    assert built.dropped_published_ages is None

def test_the_guard_count_and_its_bands_are_recorded_together() -> None:
    """Either half alone reads as a measurement while being unable to support one."""
    bands = [band.model_dump(mode="json") for band in PublishedAgeBand.histogram([1, 200])]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=2))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published_ages=bands))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=bands))

def test_every_declared_band_is_written_and_a_short_histogram_is_refused() -> None:
    """An absent band and a band holding nothing are different answers.

    Dropping the empty ones would shorten the payload and lose the finding.
    Measured 2026-09-08 on an Intel Core i7-1265U, over the ledger as it stood at
    the end of 2026-09-07: its 7,600 rows span 16 published days, 2026-08-23 to
    2026-09-07, so every band from 30 days on is a measured zero on every run
    today - and that zero is why nobody can yet say what a finite cover would
    cost.
    """
    bands = PublishedAgeBand.histogram([0, 1, 200])
    assert [(band.from_days, band.to_days) for band in bands] == list(PUBLISHED_AGE_BANDS)
    assert [band.addresses for band in bands] == [1, 1, 0, 0, 0, 1, 0]

    short = [band.model_dump(mode="json") for band in bands if band.addresses]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=short))

def test_a_manifest_written_before_the_floor_was_recorded_reads_as_unknown() -> None:
    """`VerticalCount` never carried either number, so both are null on every
    manifest committed before today - and null is unknown rather than a desk
    with no sources."""
    count = VerticalCount.model_validate({"id": "ai", "planned": 5, "published": 4})
    assert count.eligible_feeds is None
    assert count.feed_floor is None

def test_every_committed_run_manifest_still_reads_today() -> None:
    """The release blocker this class of change carries: a payload yesterday's run
    wrote that today's build cannot open (section 11).

    Driven from the fixture with the two fields removed, not from the committed
    tree. Walking the tree cost one parse per published day and carried a fuse:
    it counted the desks that still LACK the field and failed at zero, so it goes
    red on the day the last unmigrated day ages out of retention - a date on the
    calendar rather than a change anybody made.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    stripped = 0
    for run in payload["runs"]:
        for written in run.get("verticals", []):
            written.pop("eligible_feeds", None)
            written.pop("feed_floor", None)
            stripped += 1
    assert stripped, "the fixture declares no desk, so removing the fields proved nothing"

    parsed = RunManifest.model_validate(payload)
    counts = [count for record in parsed.runs for count in record.verticals]
    assert len(counts) == stripped
    assert all(count.eligible_feeds is None for count in counts)
    assert all(count.feed_floor is None for count in counts)

def test_the_manifest_keeps_the_keys_its_python_names_stopped_matching() -> None:
    """Three Python names moved on 2026-09-05 and no published key was allowed to.

    The rename is a read-side alias, so the payload keeps `items_routed` and
    `route_ms` and the model answers to `items_decided` and `decision_ms`. That
    is a property of the model against one payload, and the committed tree was
    parsed once per published day to re-ask it.
    """
    assert ModelRole.VISUAL_PLANNER.value == "route"

    raw = read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    payload = json.loads(raw)
    carrying = 0
    for run in payload["runs"]:
        if "items_routed" not in run:
            continue
        carrying += 1
    assert carrying, "the fixture carries no items_routed, so the alias is untested"

    parsed = RunManifest.model_validate(payload)
    for record, written in zip(parsed.runs, payload["runs"], strict=True):
        if "items_routed" not in written:
            continue
        assert record.items_decided == written["items_routed"]
        assert record.decision_ms == written["route_ms"]
    # The published key is the contract. A writer that started emitting the
    # Python name would break every reader of every day already committed.
    assert "items_decided" not in raw
    assert "decision_ms" not in raw

    # And the round trip puts the keys back, which is what a reader fetches.
    written_back = json.loads(parsed.to_json())["runs"][-1]
    assert "items_routed" in written_back and "route_ms" in written_back

def test_the_watchlist_stays_inside_its_configured_cap() -> None:
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert len(watchlist.entities) <= config.collect.watchlist_max_entities
