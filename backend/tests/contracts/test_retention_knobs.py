"""What does the committed config say about deleting, tracing and how long a shard lives?"""

from __future__ import annotations

import ast
import json
import re
from datetime import date, timedelta

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import cli, ledger
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.collect import SUPERSEDED_COLLECT_NAMES, CollectConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.observability import SUPERSEDED_RETENTION_NAMES, ObservabilityConfig
from idhazh.retention import oldest_month_kept

from ._fixtures import APP_CONFIG_EVERY_KNOB_DIFFERS, committed_models_raw

pytestmark = pytest.mark.contract


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
