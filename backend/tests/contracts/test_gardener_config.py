"""Does the gardener's config load as one set, and refuse every clash by name as it loads?

Every declaration here starts as a fixture under `tests/fixtures/gardener/garden/`
- eleven tasks covering every kind and every status - and each refusal is made
by editing one of them in a copy, so the rule under test is the only thing that
differs from a garden that loads. A refusal has to name the file an operator
edits and the rule it broke, because a declaration refused with a stack trace is
one nobody can fix at the first reading.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from gardener._garden import GARDENER_FIXTURES, a_config
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.knobs.gardener import (
    CollectionTaskPolicy,
    CompactionPolicy,
    GardenerConfig,
    HistoryPolicy,
    RetentionPolicy,
)

pytestmark = pytest.mark.contract

GARDEN = GARDENER_FIXTURES / "garden"


def a_garden(tmp_path: Path, **declarations: dict[str, Any] | None) -> Path:
    """The fixture garden, with each named declaration replaced, added, or removed (None)."""
    config_dir = a_config(tmp_path, GARDEN)
    for name, declared in declarations.items():
        path = config_dir / "gardener" / f"{name.replace('_', '-')}.json"
        if declared is None:
            path.unlink()
        else:
            path.write_text(json.dumps(declared), encoding="ascii")
    return config_dir


def fixture(name: str, **changes: Any) -> dict[str, Any]:
    """One fixture declaration as a dict, with some keys changed."""
    declared: dict[str, Any] = json.loads((GARDEN / f"{name}.json").read_text(encoding="utf-8"))
    return declared | changes


def refused(config_dir: Path) -> str:
    with pytest.raises(ValueError) as refusal:
        config.load_gardener(config_dir)
    return str(refusal.value)


def a_retention(owns: list[str], window: dict[str, Any], status: str = "active") -> dict[str, Any]:
    return fixture("traces", owns=owns, window=window, lifecycle_status=status)


def a_compaction(ledger: str, **changes: Any) -> dict[str, Any]:
    return fixture(
        "compact-gardener",
        ledger=ledger,
        owns=[f"state/raw/{ledger}", f"state/compact/{ledger}"],
    ) | changes


MONTHS = {"unit": "months", "value": 14}

#: The declarations that ship live, each beside the decision that put it there.
#: Every other declaration ships `dry_run: true`: a task earns its first deletion
#: from a person reading its records, never from the change that added it.
LIVE_BY_DECISION: Final = {
    "corpus-squash": (
        "the squash has run live since 2026-08-28 by owner decision (CLAUDE.md "
        "section 8), so its declaration transcribes a live squash rather than starting one"
    ),
}


def test_the_committed_gardener_config_loads_with_the_corpus_squash_alone() -> None:
    settings = config.load_gardener()
    assert (settings.config.attempts, settings.config.shards) == (6, 5)
    assert set(settings.tasks) == {"corpus-squash"}
    assert isinstance(settings.tasks["corpus-squash"], HistoryPolicy)


def test_a_declaration_ships_in_dry_run_unless_a_named_decision_put_it_live() -> None:
    """The review gate on onboarding: a new task deletes nothing until a person has read it.

    Held over the committed tree rather than over one change, because a test
    cannot see which change added a file. So every declaration is `dry_run: true`
    except the ones named above, and turning one live is an edit to that list - a
    line a reviewer reads, with its reason beside it.
    """
    tasks = config.load_gardener().tasks
    assert tasks, "nothing is declared, so this checks nothing"
    for name, policy in tasks.items():
        assert policy.dry_run is (name not in LIVE_BY_DECISION), (
            f"config/gardener/{name}.json ships dry_run {str(policy.dry_run).lower()}. A "
            "declaration ships in dry run, and one goes live only by a decision named in "
            "LIVE_BY_DECISION with its reason"
        )
    assert set(LIVE_BY_DECISION) <= set(tasks), "an exception names a task nobody declares"


def test_attempts_at_or_below_shards_is_refused_naming_both() -> None:
    GardenerConfig(version="2026-09-27", attempts=6, shards=5)
    with pytest.raises(ValidationError, match="attempts is 5 and shards is 5"):
        GardenerConfig(version="2026-09-27", attempts=5, shards=5)


def test_each_declaration_is_read_by_the_member_its_kind_names(tmp_path: Path) -> None:
    tasks = config.load_gardener(a_garden(tmp_path)).tasks
    assert isinstance(tasks["seen"], RetentionPolicy)
    assert isinstance(tasks["workflow-artifacts"], CollectionTaskPolicy)
    assert isinstance(tasks["history"], HistoryPolicy)
    compaction = tasks["compact-gardener"]
    assert isinstance(compaction, CompactionPolicy)
    assert (compaction.daily_keep_days, compaction.raw_index_keep_days) == (45, 90)


def test_a_key_that_belongs_to_another_member_is_refused_by_name(tmp_path: Path) -> None:
    message = refused(a_garden(tmp_path, seen=fixture("seen", every_days=30)))
    assert "config/gardener/seen.json is refused" in message and "every_days" in message


@pytest.mark.parametrize("window", [MONTHS, {"unit": "forever"}])
def test_a_history_window_is_whole_days_and_nothing_else(
    tmp_path: Path, window: dict[str, Any]
) -> None:
    """The squash counts back whole days from 00:00 UTC, so a month would be read as a day."""
    assert "config/gardener/history.json is refused" in refused(
        a_garden(tmp_path, history=fixture("history", window=window))
    )


@pytest.mark.parametrize(
    "window",
    [{"unit": "days", "value": 0}, {"unit": "months", "value": 0}, {"unit": "forever", "value": 3}],
)
def test_a_window_that_includes_today_or_numbers_forever_is_refused(
    tmp_path: Path, window: dict[str, Any]
) -> None:
    assert "config/gardener/traces.json is refused" in refused(
        a_garden(tmp_path, traces=fixture("traces", window=window))
    )


def test_a_declaration_owns_one_way_and_only_one(tmp_path: Path) -> None:
    both = fixture("traces", owns_everything_else_under=["frontend"])
    assert "exactly one of owns" in refused(a_garden(tmp_path / "both", traces=both))
    neither = {key: value for key, value in fixture("traces").items() if key != "owns"}
    assert "exactly one of owns" in refused(a_garden(tmp_path / "neither", traces=neither))


@pytest.mark.parametrize(
    ("owns", "status"),
    [
        (["state/traces"], "active"),
        (["state/traces/2026"], "paused"),
        (["state"], "retired"),
    ],
)
def test_two_tasks_may_not_own_one_folder_or_one_inside_the_other(
    tmp_path: Path, owns: list[str], status: str
) -> None:
    """Whatever the status: a retired task keeps its claim, so nothing else may take it."""
    extra = a_retention(owns, {"unit": "days", "value": 7}, status)
    message = refused(a_garden(tmp_path, traces_copy=extra))
    assert "config/gardener/traces" in message and "may not own one folder" in message


def test_a_folder_that_only_shares_a_prefix_of_letters_is_not_nested(tmp_path: Path) -> None:
    extra = a_retention(["state/traces-archive"], {"unit": "days", "value": 7})
    assert "traces-archive" in config.load_gardener(a_garden(tmp_path, traces_archive=extra)).tasks


def test_one_task_at_most_takes_the_complement(tmp_path: Path) -> None:
    second = fixture("trials", owns_everything_else_under=["frontend/public"])
    assert "One task may take the complement" in refused(a_garden(tmp_path, strays=second))


def test_a_file_named_as_owned_is_refused(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, seen=fixture("seen", owns=["state/seen.csv"]))
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "seen.csv").write_text("a file, not a folder\n", encoding="ascii")
    assert "owns state/seen.csv, which is a file" in refused(config_dir)


@pytest.mark.parametrize(
    ("name", "window", "loads"),
    [
        ("seen", {"unit": "days", "value": 30}, False),
        ("seen", {"unit": "months", "value": 2}, False),
        ("seen", {"unit": "months", "value": 4}, True),
        ("seen", {"unit": "forever"}, True),
        ("counterfactual-scores", {"unit": "days", "value": 7}, False),
        ("counterfactual-scores", {"unit": "days", "value": 30}, True),
    ],
)
def test_a_window_a_reader_still_opens_is_not_deleted_under_it(
    tmp_path: Path, name: str, window: dict[str, Any], loads: bool
) -> None:
    """Days against months are compared at the fewest days the months can hold."""
    owns = [f"state/{name}"]
    config_dir = a_garden(tmp_path, **{name.replace("-", "_"): fixture("seen", owns=owns, window=window)})
    if loads:
        config.load_gardener(config_dir)
    else:
        assert "a reader still opens" in refused(config_dir)


@pytest.mark.parametrize(
    ("series", "refusal"),
    [
        ({"full-grain": {"unit": "months", "value": 13}}, "item_health_full_grain_months is 14"),
        ({"aggregate": {"unit": "months", "value": 99}}, "is never delete"),
        ({"hourly": {"unit": "days", "value": 7}}, "covers no observability key"),
        ({}, "keeps no series"),
    ],
)
def test_a_series_is_held_to_the_knob_it_covers(
    tmp_path: Path, series: dict[str, Any], refusal: str
) -> None:
    kept = fixture("telemetry-aggregate")["series"] | series if series else {}
    declared = fixture("telemetry-aggregate", series=kept)
    assert refusal in refused(a_garden(tmp_path, telemetry_aggregate=declared))


def test_only_the_series_task_keeps_series(tmp_path: Path) -> None:
    declared = fixture("traces", series={"full-grain": MONTHS})
    assert "Only telemetry-aggregate keeps several series" in refused(
        a_garden(tmp_path, traces=declared)
    )


def test_a_compaction_is_named_for_its_ledger(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, compact_gardener=None, compact_old=a_compaction("gardener"))
    assert "call it compact-gardener.json" in refused(config_dir)


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"raw_index_keep_days": 30}, "raw index must outlive the daily period"),
        ({"monthly_window": {"unit": "months", "value": 2}}, "less than one whole month"),
    ],
)
def test_a_compaction_keeps_its_own_periods_in_order(
    tmp_path: Path, changes: dict[str, Any], refusal: str
) -> None:
    config_dir = a_garden(tmp_path, compact_gardener=a_compaction("gardener", **changes))
    assert refusal in refused(config_dir)


def published(config_dir: Path, *ledgers: str) -> Path:
    """The same config, with these ledgers in `ledger.published`."""
    app = config_dir / "idhazh.json"
    held = json.loads(app.read_text(encoding="utf-8"))
    held["ledger"]["published"] = list(ledgers)
    app.write_text(json.dumps(held), encoding="utf-8")
    return config_dir


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"monthly_window": {"unit": "forever"}}, "may not keep its month files forever"),
        (
            {"daily_keep_days": 1, "monthly_window": {"unit": "days", "value": 40}},
            "would have days no file holds",
        ),
        ({"monthly_window": {"unit": "months", "value": 13}}, None),
    ],
    ids=["forever", "short-of-the-widest-window", "long-enough"],
)
def test_a_published_ledger_reaches_the_widest_window_and_is_never_kept_forever(
    tmp_path: Path, changes: dict[str, Any], refusal: str | None
) -> None:
    compaction = a_compaction("gardener", **changes)
    config_dir = published(a_garden(tmp_path, compact_gardener=compaction), "gardener")
    if refusal is None:
        config.load_gardener(config_dir)
    else:
        assert refusal in refused(config_dir)


@pytest.mark.parametrize(
    ("floor", "monthly", "refusal"),
    [
        (MONTHS, {"unit": "months", "value": 12}, "silently cut how far back"),
        (MONTHS, {"unit": "months", "value": 13}, None),
        (MONTHS, {"unit": "forever"}, None),
        ({"unit": "forever"}, {"unit": "months", "value": 13}, "kept it forever"),
        ({"unit": "forever"}, {"unit": "forever"}, None),
    ],
    ids=["bounded-short", "bounded-long", "bounded-forever", "forever-bounded", "forever-forever"],
)
def test_a_compaction_reaches_as_far_back_as_the_task_that_limited_its_ledger(
    tmp_path: Path, floor: dict[str, Any], monthly: dict[str, Any], refusal: str | None
) -> None:
    """The five cases. The old task is retired: its declaration is the record of how far back."""
    config_dir = a_garden(
        tmp_path,
        visual_prunes=a_retention(["state/visual-prunes"], floor, "retired"),
        compact_visual_prunes=a_compaction("visual-prunes", monthly_window=monthly),
    )
    if refusal is None:
        config.load_gardener(config_dir)
    else:
        assert refusal in refused(config_dir)


def test_a_ledger_no_task_ever_limited_has_no_floor(tmp_path: Path) -> None:
    short = a_compaction("visual-prunes", monthly_window={"unit": "months", "value": 3})
    config.load_gardener(a_garden(tmp_path, compact_visual_prunes=short))


def test_a_series_is_the_floor_of_the_ledger_it_covers(tmp_path: Path) -> None:
    """`item-health` reaches back as far as the full-grain series, not the aggregate one."""
    short = a_compaction("item-health", monthly_window={"unit": "months", "value": 12})
    message = refused(a_garden(tmp_path, compact_item_health=short))
    assert "compact-item-health.json" in message and "kept 14 months" in message


def test_the_month_rule_counts_the_fewest_and_the_most_days() -> None:
    assert config._month_run_days(1) == (28, 31)
    assert config._month_run_days(12) == (365, 366)
