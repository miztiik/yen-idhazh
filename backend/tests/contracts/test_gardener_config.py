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


def test_the_committed_gardener_config_loads_and_the_squash_is_its_one_history_task() -> None:
    settings = config.load_gardener()
    assert (settings.config.attempts, settings.config.shards) == (6, 5)
    history = [name for name, policy in settings.tasks.items() if isinstance(policy, HistoryPolicy)]
    assert history == ["corpus-squash"]


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
    ("change", "refusal"),
    [
        ("unknown", "keeps a series called hourly, which is not one of its trees"),
        ("missing", "names no window for its public-copy series"),
        ("none", "keeps no series"),
    ],
)
def test_a_series_task_names_every_series_it_keeps_and_no_other(
    tmp_path: Path, change: str, refusal: str
) -> None:
    kept: dict[str, Any] = fixture("telemetry-aggregate")["series"]
    series = {
        "unknown": kept | {"hourly": {"unit": "days", "value": 7}},
        "missing": {name: window for name, window in kept.items() if name != "public-copy"},
        "none": {},
    }[change]
    declared = fixture("telemetry-aggregate", series=series)
    assert refusal in refused(a_garden(tmp_path, telemetry_aggregate=declared))


def test_only_the_tasks_that_keep_several_series_carry_series(tmp_path: Path) -> None:
    declared = fixture("traces", series={"full-grain": MONTHS})
    assert "Only scores, telemetry-aggregate keep several series" in refused(
        a_garden(tmp_path, traces=declared)
    )


def test_a_task_that_keeps_series_keeps_its_window_as_its_full_grain_series(
    tmp_path: Path,
) -> None:
    """One number spelled twice is two numbers the day somebody edits one of them."""
    declared = fixture("telemetry-aggregate", window={"unit": "months", "value": 15})
    assert "The window is the full-grain series" in refused(
        a_garden(tmp_path, telemetry_aggregate=declared)
    )


@pytest.mark.parametrize(
    ("name", "summary"), [("telemetry-aggregate", "aggregate"), ("scores", "archive")]
)
@pytest.mark.parametrize(("months", "loads"), [(13, False), (14, False), (15, True)])
def test_a_summary_series_sits_above_the_rows_it_summarises(
    tmp_path: Path, name: str, summary: str, months: int, loads: bool
) -> None:
    """At or under the full-grain window a month would be deleted before it was summarised."""
    kept = fixture(name)["series"] | {summary: {"unit": "months", "value": months}}
    config_dir = a_garden(tmp_path, **{name.replace("-", "_"): fixture(name, series=kept)})
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert f"{name}.json keeps its {summary} series {months} months" in message
        assert "or a month is deleted before it is ever summarised" in message


@pytest.mark.parametrize("months", [13, 15])
def test_the_public_copy_lasts_exactly_as_long_as_the_ledger_it_copies(
    tmp_path: Path, months: int
) -> None:
    """Either way round leaves a month nothing can answer for."""
    kept = fixture("telemetry-aggregate")["series"] | {
        "public-copy": {"unit": "months", "value": months}
    }
    message = refused(
        a_garden(tmp_path, telemetry_aggregate=fixture("telemetry-aggregate", series=kept))
    )
    assert f"keeps its public-copy series {months} months and its full-grain series" in message


def _thirteen_months(name: str) -> dict[str, Any]:
    """One task's declaration with every window of its full-grain rows at thirteen months."""
    short = {"unit": "months", "value": 13}
    declared = fixture(name, window=short)
    if declared.get("series"):
        declared["series"] = declared["series"] | {"full-grain": short}
        if "public-copy" in declared["series"]:
            declared["series"]["public-copy"] = short
    return declared


@pytest.mark.parametrize("name", ["feed-health", "scores", "telemetry-aggregate"])
def test_a_window_a_console_read_still_opens_is_refused(tmp_path: Path, name: str) -> None:
    """A 366-day read reaches fourteen month shards, and thirteen is one short of it.

    The retired check compared `months * 30` against the window, which passed 13
    while a reader could still ask for a fourteenth shard - so the check is
    against the shards the read selects.
    """
    message = refused(a_garden(tmp_path, **{name.replace("-", "_"): _thirteen_months(name)}))
    assert f"{name}.json keeps" in message
    assert "366-day console read can select 14 month shards" in message


def test_the_machine_ledger_lasts_as_long_as_the_published_shard_folded_from_it(
    tmp_path: Path,
) -> None:
    """A published month whose source months are gone is a shard nothing can rebuild."""
    short = fixture("host-fingerprint", window={"unit": "months", "value": 13})
    message = refused(a_garden(tmp_path, host_fingerprint=short))
    assert "host-fingerprint.json keeps 13 months" in message
    assert "observability.public_machine_keep_months is 14" in message


def a_picture_task(window: dict[str, Any]) -> dict[str, Any]:
    return fixture(
        "traces", owns=["frontend/public/digest"], window=window, max_deletes_per_run=200
    )


@pytest.mark.parametrize(
    ("window", "loads"),
    [
        ({"unit": "days", "value": 390}, True),
        ({"unit": "days", "value": 389}, False),
        ({"unit": "months", "value": 13}, False),
        ({"unit": "forever"}, False),
    ],
)
def test_a_picture_window_is_the_one_the_archive_page_states(
    tmp_path: Path, window: dict[str, Any], loads: bool
) -> None:
    """`retention.image_months` is 13, which the page states as 390 thirty-day days."""
    config_dir = a_garden(tmp_path, visual_prune=a_picture_task(window))
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "visual-prune.json keeps" in message and "retention.image_months is 13" in message


def test_with_no_picture_window_the_cleanup_keeps_every_picture(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, visual_prune=a_picture_task({"unit": "forever"}))
    app = json.loads((config_dir / "idhazh.json").read_text(encoding="utf-8"))
    app["retention"]["image_months"] = -1
    (config_dir / "idhazh.json").write_text(json.dumps(app), encoding="utf-8")

    config.load_gardener(config_dir)


@pytest.mark.parametrize("name", ["scores", "telemetry-aggregate"])
def test_a_task_that_summarises_whole_months_carries_no_ceiling(tmp_path: Path, name: str) -> None:
    """A ceiling could stop part way through a month, and the next summary would be partial."""
    declared = fixture(name, max_deletes_per_run=50)
    message = refused(a_garden(tmp_path, **{name.replace("-", "_"): declared}))
    assert f"{name}.json names a ceiling of 50" in message


def test_a_compaction_is_named_for_its_ledger(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, compact_gardener=None, compact_old=a_compaction("gardener"))
    assert "call it compact-gardener.json" in refused(config_dir)


def test_a_compaction_keeps_its_raw_listings_as_long_as_its_daily_period(tmp_path: Path) -> None:
    config_dir = a_garden(
        tmp_path, compact_gardener=a_compaction("gardener", raw_index_keep_days=30)
    )
    assert "raw index must outlive the daily period" in refused(config_dir)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"window": {"unit": "days", "value": 90}}, "window"),
        ({"max_deletes_per_run": 50}, "max_deletes_per_run"),
        ({"daily_keep_days": 30}, "daily_keep_days"),
    ],
    ids=["a-window-nothing-reads", "a-ceiling-that-halves-a-month", "a-month-a-re-run-can-reach"],
)
def test_a_compaction_carries_no_second_window_no_ceiling_and_no_month_a_re_run_reaches(
    tmp_path: Path, changes: dict[str, Any], field: str
) -> None:
    """Two periods are its retention, a period goes whole, and a re-run lands for 30 days."""
    message = refused(a_garden(tmp_path, compact_gardener=a_compaction("gardener", **changes)))
    assert "config/gardener/compact-gardener.json is refused" in message and field in message


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
            {"daily_keep_days": 31, "monthly_window": {"unit": "days", "value": 40}},
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
