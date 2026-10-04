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
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR
from gardener._garden import GARDENER_FIXTURES, a_config
from pydantic import TypeAdapter, ValidationError

from idhazh import config, ledger
from idhazh.contracts.knobs.gardener import (
    DEFAULT_CLOSED_AFTER_DAYS,
    GITHUB_RERUN_DAYS,
    JANUARY_DAYS,
    CollectionTaskPolicy,
    CompactionPolicy,
    FoldPolicy,
    GardenerConfig,
    HistoryPolicy,
    RetentionPolicy,
    Window,
)
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.pipeline_tests import PipelineTestsConfig

pytestmark = pytest.mark.contract

GARDEN = GARDENER_FIXTURES / "garden"


def a_garden(tmp_path: Path, **declarations: dict[str, Any] | None) -> Path:
    """The fixture garden, with each named declaration replaced, added, or removed (None)."""
    config_dir = a_config(tmp_path, GARDEN)
    gardener_config = config_dir / "idhazh_gardener.json"
    settings = json.loads(gardener_config.read_text(encoding="utf-8"))
    names = set(settings["task_names"])
    for name, declared in declarations.items():
        task_name = name.replace("_", "-")
        path = config_dir / "gardener" / f"{task_name}.json"
        if declared is None:
            path.unlink()
            names.discard(task_name)
        else:
            path.write_text(json.dumps(declared), encoding="ascii")
            names.add(task_name)
    settings["task_names"] = sorted(names)
    gardener_config.write_text(json.dumps(settings, indent=2) + "\n", encoding="ascii")
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
    return (
        fixture(
            "compact-gardener",
            ledger=ledger,
            owns=[f"state/raw/{ledger}", f"state/compact/{ledger}"],
        )
        | changes
    )


MONTHS = {"unit": "months", "value": 14}

#: Why two of the ledgers the console reads are packed at every wake.
PACKED_FOR_THE_CONSOLE: Final = (
    "packed live by owner decision: the console reads this ledger from its packed "
    "files only, so a finished day is packed within about two days and a month 31 "
    "days after it ends"
)

#: Why the monthly window of those two ledgers deletes month files live.
WINDOW_LIVE_WITH_ITS_PACKING: Final = (
    "the person turned this ledger's packing live while one switch still ran the "
    "packing and the monthly window together, so the window went live with it; the "
    "loader holds that window to every month a reader of the ledger still opens"
)

#: The two packing tasks a person turned live.
PACKED_LIVE: Final = ("compact-host-fingerprint", "compact-item-health")

#: Why a ledger's packing ships live in the change that moves it to the door.
PACKED_ON_THE_MOVE: Final = (
    "packing writes every row into a coarser file before it deletes one, and the "
    "monthly window beside it only reports"
)

#: Every switch that ships live, keyed by its task and by the key a person edits
#: to turn it off, each beside the decision that put it there. Every other switch
#: ships `dry_run: true`: a task earns its first deletion from a person reading
#: its records, never from the change that added it.
LIVE_BY_DECISION: Final = {
    ("compact-candidate-models", "dry_run"): PACKED_ON_THE_MOVE,
    ("compact-counterfactual-scores", "dry_run"): PACKED_ON_THE_MOVE,
    ("compact-feed-health", "dry_run"): PACKED_ON_THE_MOVE,
    ("compact-host-fingerprint", "dry_run"): PACKED_FOR_THE_CONSOLE,
    ("compact-host-fingerprint", "month_deletes_dry_run"): WINDOW_LIVE_WITH_ITS_PACKING,
    ("compact-item-health", "dry_run"): PACKED_FOR_THE_CONSOLE,
    ("compact-item-health", "month_deletes_dry_run"): WINDOW_LIVE_WITH_ITS_PACKING,
    ("compact-published", "dry_run"): PACKED_ON_THE_MOVE,
    ("compact-seen", "dry_run"): PACKED_ON_THE_MOVE,
    ("corpus-squash", "dry_run"): (
        "the squash has run live since 2026-08-28 by owner decision (CLAUDE.md "
        "section 8), so its declaration transcribes a live squash rather than starting one"
    ),
}

#: The CSV day trees no task folds, each with why. A tree that joins `DAY_TREES`
#: is folded by the task that owns it, or it is named here with its reason.
UNFOLDED_BY_DECISION: Final[dict[LedgerName, str]] = {}


#: The switch a compaction's monthly window has of its own. It acts only through
#: the declaration's own `dry_run`, so it is live only while both are false.
WINDOW_SWITCHES: Final = frozenset({"month_deletes_dry_run"})


def _switches(declared: Mapping[str, Any], prefix: str = "") -> dict[str, bool]:
    """Every switch a declaration carries, at any depth, by the dotted key a person edits.

    True where the switch only reports. A window switch reports while its own
    `dry_run` or the declaration's does.
    """
    found: dict[str, bool] = {}
    for key, value in declared.items():
        path = f"{prefix}{key}"
        if key == "dry_run" and isinstance(value, bool):
            found[path] = value
        elif key in WINDOW_SWITCHES and isinstance(value, bool):
            found[path] = value or declared.get("dry_run") is not False
        elif isinstance(value, Mapping):
            found |= _switches(value, f"{path}.")
    return found


def test_the_committed_gardener_config_loads_and_the_squash_is_its_one_history_task() -> None:
    settings = config.load_gardener()
    assert (settings.config.attempts, settings.config.shards) == (6, 5)
    history = [name for name, policy in settings.tasks.items() if isinstance(policy, HistoryPolicy)]
    assert history == ["corpus-squash"]
    squash = settings.tasks["corpus-squash"]
    assert isinstance(squash, HistoryPolicy)
    assert (squash.push_attempts, squash.push_retry_delay_seconds) == (3, 60)


@pytest.mark.parametrize("key", ["push_attempts", "push_retry_delay_seconds"])
def test_a_history_declaration_without_a_push_key_is_refused_by_name(
    tmp_path: Path, key: str
) -> None:
    """Neither has a default: the file says how often the squash pushes and how long it waits."""
    declared = {name: value for name, value in fixture("history").items() if name != key}
    message = refused(a_garden(tmp_path, history=declared))
    assert "config/gardener/history.json is refused" in message and key in message


@pytest.mark.parametrize(
    ("changes", "loads"),
    [
        ({"push_attempts": 0}, False),
        ({"push_attempts": 1}, True),
        ({"push_retry_delay_seconds": -1}, False),
        ({"push_retry_delay_seconds": 0}, True),
    ],
)
def test_a_squash_pushes_at_least_once_and_never_waits_less_than_nothing(
    tmp_path: Path, changes: dict[str, int], loads: bool
) -> None:
    config_dir = a_garden(tmp_path, history=fixture("history", **changes))
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "config/gardener/history.json is refused" in message
        assert all(key in message for key in changes)


def test_a_switch_ships_in_dry_run_unless_a_named_decision_put_it_live() -> None:
    """The review gate on onboarding: a new task deletes nothing until a person has read it.

    Held over the committed tree rather than over one change, because a test
    cannot see which change added a file. Every `dry_run` a declaration carries
    is found by walking the declaration, a fold's as well as the task's own, and
    so is a compaction's `month_deletes_dry_run`, live only while the task's
    own `dry_run` is false too. The switches that are live must be exactly the
    ones named above. So turning one live is an edit to that list - a line a
    reviewer reads, with its reason beside it - and a decision left behind after
    its switch went is caught too.
    """
    tasks = config.load_gardener().tasks
    assert tasks, "nothing is declared, so this checks nothing"
    live = {
        (name, key)
        for name, policy in tasks.items()
        for key, dry_run in _switches(policy.model_dump(mode="json")).items()
        if not dry_run
    }
    assert live == set(LIVE_BY_DECISION), (
        f"{sorted(live - set(LIVE_BY_DECISION))} ship live with no decision named, and "
        f"{sorted(set(LIVE_BY_DECISION) - live)} are named and do not. A switch ships in "
        "dry run, and one goes live only by a decision named in LIVE_BY_DECISION with its "
        "reason"
    )


def test_the_two_packing_tasks_the_person_turned_on_pack_a_month_31_days_after_it_ends() -> None:
    """31 is the shortest wait no GitHub re-run can outlast; eval packing only reports."""
    tasks = config.load_gardener().tasks
    for name in PACKED_LIVE:
        policy = tasks[name]
        assert isinstance(policy, CompactionPolicy), name
        assert (policy.dry_run, policy.daily_keep_days) == (False, GITHUB_RERUN_DAYS + 1), name
    evals = tasks["compact-summary-quality-evals"]
    assert isinstance(evals, CompactionPolicy) and evals.dry_run


@pytest.mark.parametrize("name", PACKED_LIVE)
def test_a_live_packing_task_that_waits_30_days_is_refused_by_name(
    tmp_path: Path, name: str
) -> None:
    """A month absorbed 30 days after it ends could still take a re-run's rows."""
    config_dir = a_config(tmp_path, CONFIG_DIR / "gardener")
    path = config_dir / "gardener" / f"{name}.json"
    declared = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(declared | {"daily_keep_days": 30}), encoding="ascii")
    message = refused(config_dir)
    assert f"config/gardener/{name}.json is refused" in message and "daily_keep_days" in message


def test_every_csv_day_tree_is_folded_by_the_task_that_owns_it() -> None:
    """A tree nobody folds keeps a file per writer per day for ever (Guardrail #12).

    And a fold on a task that owns no such tree folds nothing, so it is a switch
    a reviewer could believe does something.
    """
    tasks = config.load_gardener().tasks
    trees = {ledger.tree_relpath(tree): tree for tree in DAY_TREES}
    folding: dict[str, str] = {}
    for name, policy in tasks.items():
        if not isinstance(policy, RetentionPolicy) or policy.fold is None:
            continue
        owned = set(policy.owns or ()) & set(trees)
        assert owned, f"config/gardener/{name}.json folds and owns no CSV day tree"
        folding |= dict.fromkeys(owned, name)
    for relpath, tree in sorted(trees.items()):
        if tree in UNFOLDED_BY_DECISION:
            assert relpath not in folding, f"{relpath} is folded and still excused from it"
            continue
        assert relpath in folding, (
            f"{relpath} is a CSV day tree and no declaration that owns it folds it. Give "
            "its owner a fold block, or name it in UNFOLDED_BY_DECISION with its reason"
        )


def test_a_fold_that_names_no_wait_closes_a_day_after_the_shared_one() -> None:
    """A compaction writes its own wait as `compact_after_days`; both count whole days alike."""
    assert FoldPolicy(dry_run=True).after_days == DEFAULT_CLOSED_AFTER_DAYS


#: The keys every kind shares that a declaration may leave out, plus compaction's
#: optional lookback, whose default is two months.
SHARED_OPTIONAL_KEYS: Final = frozenset({"reads", "appends_to"})
COMPACTION_OPTIONAL_KEYS: Final = SHARED_OPTIONAL_KEYS | {"lookback"}

#: Every key a compaction declaration has to write.
COMPACTION_KEYS: Final = tuple(
    sorted(name for name, field in CompactionPolicy.model_fields.items() if field.is_required())
)


def test_no_setting_a_compaction_runs_with_has_a_default() -> None:
    """The file a person reads holds every number a pass uses.

    The keys that may be left out are the ones every kind shares to say what a
    task owns and reads, and none of them is a number a pass runs with.
    """
    optional = {
        name for name, field in CompactionPolicy.model_fields.items() if not field.is_required()
    }
    assert optional == COMPACTION_OPTIONAL_KEYS


@pytest.mark.parametrize("key", COMPACTION_KEYS)
def test_a_compaction_that_leaves_out_any_one_key_is_refused_naming_it(
    tmp_path: Path, key: str
) -> None:
    """Nothing fills a missing setting in from code, so the loader names the one left out."""
    declared = {name: value for name, value in fixture("compact-gardener").items() if name != key}
    message = refused(a_garden(tmp_path, compact_gardener=declared))
    assert "config/gardener/compact-gardener.json is refused" in message and key in message


def test_a_compaction_that_carries_the_old_name_of_its_month_delete_switch_is_refused_naming_it(
    tmp_path: Path,
) -> None:
    """`month_deletes_dry_run` has no alias, so its old name is named as a key nothing reads."""
    declared = fixture("compact-gardener")
    declared["monthly_window_dry_run"] = declared.pop("month_deletes_dry_run")
    message = refused(a_garden(tmp_path, compact_gardener=declared))
    assert "config/gardener/compact-gardener.json is refused" in message
    assert "monthly_window_dry_run\n  Extra inputs are not permitted" in message


def test_a_fold_settles_a_month_only_where_its_own_declaration_asks() -> None:
    """Off by default, so a tree keeps one file a closed day unless its task says otherwise."""
    assert FoldPolicy(dry_run=True).settles_months is False


@pytest.mark.parametrize(
    ("window", "loads"),
    [({"unit": "days", "value": 7}, False), (MONTHS, True), ({"unit": "forever"}, True)],
)
def test_a_month_settles_only_beside_a_window_that_keeps_whole_months(
    tmp_path: Path, window: dict[str, Any], loads: bool
) -> None:
    """A settled month's file names no day, so a window of days would take it whole.

    It would take the month once the month's first day aged out, and with it the
    rows of every later day the window still keeps.
    """
    declared = fixture("traces", window=window, fold={"dry_run": False, "settles_months": True})
    config_dir = a_garden(tmp_path, traces=declared)
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "config/gardener/traces.json is refused" in message
        assert "settles_months" in message


def test_attempts_at_or_below_shards_is_refused_naming_both() -> None:
    GardenerConfig(version="2026-09-27", task_names=(), attempts=6, shards=5)
    with pytest.raises(ValidationError, match="attempts is 5 and shards is 5"):
        GardenerConfig(version="2026-09-27", task_names=(), attempts=5, shards=5)


def test_task_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="task_names repeats a task"):
        GardenerConfig(
            version="2026-09-27", task_names=("seen", "seen"), attempts=6, shards=5
        )


def test_each_declaration_is_read_by_the_member_its_kind_names(tmp_path: Path) -> None:
    tasks = config.load_gardener(a_garden(tmp_path)).tasks
    assert isinstance(tasks["seen"], RetentionPolicy)
    assert isinstance(tasks["workflow-artifacts"], CollectionTaskPolicy)
    assert isinstance(tasks["history"], HistoryPolicy)
    compaction = tasks["compact-gardener"]
    assert isinstance(compaction, CompactionPolicy)
    assert compaction.daily_keep_days == 45


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


def test_a_declaration_must_name_its_owned_folders(tmp_path: Path) -> None:
    declaration = fixture("traces")
    del declaration["owns"]
    assert "owns" in refused(a_garden(tmp_path / "missing", traces=declaration))
    legacy = fixture("trials", owns_everything_else_under=["state"])
    assert "owns_everything_else_under" in refused(
        a_garden(tmp_path / "legacy", trials=legacy)
    )


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


def test_trials_owns_only_configured_pipeline_test_roots() -> None:
    policy = config.load_gardener().tasks["trials"]
    tests = PipelineTestsConfig.from_json(
        (CONFIG_DIR / "pipeline-tests.json").read_text(encoding="utf-8")
    )

    assert policy.owns == [
        f"state/{test_case.trial_state_dirname}" for test_case in tests.test_cases
    ]
    assert "state" not in policy.owns


@pytest.mark.parametrize("reads", [["state/traces"], ["state/traces/2026"], ["state"]])
def test_a_task_does_not_read_a_folder_it_owns_or_one_that_holds_it(
    tmp_path: Path, reads: list[str]
) -> None:
    """A folder a task owns is listed for it already, so naming it again is a mistake."""
    message = refused(a_garden(tmp_path, traces=fixture("traces", reads=reads)))
    assert "config/gardener/traces.json is refused" in message and "is in reads" in message


def test_trials_declares_no_additional_reads() -> None:
    """Every trial path it may read is in its explicit root list."""
    trials = config.load_gardener().tasks["trials"]
    assert not trials.reads


def test_a_task_may_read_a_folder_another_task_owns(tmp_path: Path) -> None:
    tasks = config.load_gardener(
        a_garden(tmp_path, traces=fixture("traces", reads=["state/seen"]))
    ).tasks
    assert tasks["traces"].reads == ["state/seen"] and tasks["seen"].owns == ["state/seen"]


def test_the_census_summary_reads_both_folders_of_the_census_it_summarises() -> None:
    """Its due months and its rows sit in folders the census compaction owns.

    A folder it did not declare is refused when it asks, so the summary cannot
    report success over a census it could not see from another shard.
    """
    tasks = config.load_gardener().tasks
    census = tasks["compact-item-health"].owns or []
    assert sorted(tasks["telemetry-aggregate"].reads) == sorted(census)


def test_a_file_named_as_owned_is_refused(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, seen=fixture("seen", owns=["state/seen.csv"]))
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "seen.csv").write_text("a file, not a folder\n", encoding="ascii")
    assert "owns state/seen.csv, which is a file" in refused(config_dir)


@pytest.mark.parametrize(
    ("name", "window", "loads"),
    [
        ("seen", {"unit": "days", "value": 30}, False),
        ("seen", {"unit": "days", "value": 89}, False),
        ("seen", {"unit": "days", "value": 90}, True),
        ("seen", {"unit": "months", "value": 2}, False),
        ("seen", {"unit": "months", "value": 4}, True),
        ("seen", {"unit": "forever"}, True),
    ],
)
def test_a_window_a_reader_still_opens_is_not_deleted_under_it(
    tmp_path: Path, name: str, window: dict[str, Any], loads: bool
) -> None:
    """Days against months are compared at the fewest days the months can hold."""
    owns = [f"state/{name}"]
    config_dir = a_garden(
        tmp_path, **{name.replace("-", "_"): fixture("seen", owns=owns, window=window)}
    )
    if loads:
        config.load_gardener(config_dir)
    else:
        assert "a reader still opens" in refused(config_dir)


@pytest.mark.parametrize(
    ("name", "monthly", "loads"),
    [
        ("seen", {"unit": "months", "value": 1}, False),
        ("seen", {"unit": "months", "value": 2}, True),
        ("published", {"unit": "months", "value": 13}, False),
        ("published", {"unit": "forever"}, True),
    ],
)
def test_a_compaction_keeps_every_day_a_reader_still_opens(
    tmp_path: Path, name: str, monthly: dict[str, Any], loads: bool
) -> None:
    """Once a ledger moves, its compaction governs it in place of its retention task.

    The garden's `seen` task keeps 90 days, and it no longer counts. The pair
    reaches back 45 days and the fewest days its months hold: one month is 73
    days, under the 90 `collect.seen_window_days` reads, and two are 104.
    `collect.published_window_days` is -1, which reads every day, so a published
    compaction with a forever window also has to pack years to bound its first
    index fetch.
    """
    compaction = a_compaction(name, monthly_window=monthly)
    if name == "published" and monthly["unit"] == "forever":
        compaction["monthly_keep_days"] = 93
    config_dir = a_garden(tmp_path, **{f"compact_{name}": compaction})
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert f"compact-{name}.json reaches back" in message
        assert "a reader still opens" in message


@pytest.mark.parametrize(
    ("monthly", "loads"),
    [({"unit": "months", "value": 1}, False), ({"unit": "months", "value": 2}, True)],
)
def test_the_lens_window_is_held_against_the_counterfactual_compaction(
    tmp_path: Path, monthly: dict[str, Any], loads: bool
) -> None:
    """The counterfactual scores' reader floor binds the compaction that governs them.

    The committed 30 days sit under the 59 days the shortest legal compaction
    reaches, so the floor is raised to 90 here: one month reaches back 73 days
    and two reach 104.
    """
    compaction = a_compaction("counterfactual-scores", monthly_window=monthly)
    config_dir = a_garden(tmp_path, compact_counterfactual_scores=compaction)
    app_path = config_dir / "idhazh.json"
    app: dict[str, Any] = json.loads(app_path.read_text(encoding="utf-8"))
    app["lens_weights"]["window_days"] = 90
    app_path.write_text(json.dumps(app), encoding="ascii")
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "compact-counterfactual-scores.json reaches back 73 days" in message
        assert "lens_weights.window_days reads 90 days back" in message


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
    assert "only telemetry-aggregate may keep several series at once" in refused(
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


@pytest.mark.parametrize(("name", "summary"), [("telemetry-aggregate", "aggregate")])
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


@pytest.mark.parametrize("name", ["telemetry-aggregate"])
def test_a_window_a_console_read_still_opens_is_refused(tmp_path: Path, name: str) -> None:
    """A 366-day read reaches fourteen month shards, and thirteen is one short of it.

    The retired check compared `months * 30` against the window, which passed 13
    while a reader could still ask for a fourteenth shard - so the check is
    against the shards the read selects.
    """
    message = refused(a_garden(tmp_path, **{name.replace("-", "_"): _thirteen_months(name)}))
    assert f"{name}.json keeps" in message
    assert "366-day console read can select 14 month shards" in message


@pytest.mark.parametrize(("months", "loads"), [(12, False), (13, True)])
def test_a_compaction_keeps_every_month_file_a_console_read_still_selects(
    tmp_path: Path, months: int, loads: bool
) -> None:
    """Feed health's compaction governs it, and the widest read still floors it.

    Fourteen month shards can hold 428 days. Forty-five days and twelve months
    reach back 410; with thirteen months, 438.
    """
    compaction = a_compaction("feed-health", monthly_window={"unit": "months", "value": months})
    config_dir = a_garden(tmp_path, compact_feed_health=compaction)
    if loads:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "compact-feed-health.json reaches back 410 days" in message
        assert "366-day console read can select 14 month shards" in message


@pytest.mark.parametrize(
    ("name", "refusal"),
    [
        ("host-fingerprint", "host-fingerprint.json keeps 13 months"),
        ("compact-host-fingerprint", "compact-host-fingerprint.json reaches back 410 days"),
    ],
    ids=["its-retention-task", "its-compaction"],
)
def test_the_machine_ledger_lasts_as_long_as_the_published_shard_folded_from_it(
    tmp_path: Path, name: str, refusal: str
) -> None:
    """A published month whose source months are gone is a shard nothing can rebuild.

    Whichever declaration governs the ledger is held: its retention task while it
    has one, and its compaction once the ledger files under the two roots.
    """
    short = (
        fixture(name, window={"unit": "months", "value": 13})
        if name == "host-fingerprint"
        else a_compaction("host-fingerprint", monthly_window={"unit": "months", "value": 12})
    )
    message = refused(a_garden(tmp_path, **{name.replace("-", "_"): short}))
    assert refusal in message
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


@pytest.mark.parametrize("name", ["telemetry-aggregate"])
def test_a_task_that_summarises_whole_months_carries_no_ceiling(tmp_path: Path, name: str) -> None:
    """A ceiling could stop part way through a month, and the next summary would be partial."""
    declared = fixture(name, max_deletes_per_run=50)
    message = refused(a_garden(tmp_path, **{name.replace("-", "_"): declared}))
    assert f"{name}.json names a ceiling of 50" in message


def test_a_compaction_is_named_for_its_ledger(tmp_path: Path) -> None:
    config_dir = a_garden(tmp_path, compact_gardener=None, compact_old=a_compaction("gardener"))
    assert "call it compact-gardener.json" in refused(config_dir)


def test_a_collection_task_is_named_for_its_collection(tmp_path: Path) -> None:
    """A collection task owns no folder, so its name is what keeps one collection to one task."""
    misnamed = fixture("workflow-artifacts", collection="workflow-runs")
    message = refused(a_garden(tmp_path, workflow_artifacts=misnamed))
    assert "workflow-artifacts.json prunes workflow-runs" in message
    assert "call it workflow-runs.json" in message


@pytest.mark.parametrize("window", [MONTHS, {"unit": "forever"}])
def test_a_collection_window_is_whole_days_and_nothing_else(
    tmp_path: Path, window: dict[str, Any]
) -> None:
    """GitHub dates a member by its day and the pass counts whole days back from the wake."""
    declared = fixture("workflow-artifacts", window=window)
    assert "config/gardener/workflow-artifacts.json is refused" in refused(
        a_garden(tmp_path, workflow_artifacts=declared)
    )


def test_a_collection_outside_the_vocabulary_is_refused(tmp_path: Path) -> None:
    """The collection is a closed word, so a file cannot point the task at anything else."""
    declared = fixture("workflow-artifacts", collection="workflow-caches")
    assert "config/gardener/workflow-artifacts.json is refused" in refused(
        a_garden(tmp_path, workflow_artifacts=declared)
    )


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


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"monthly_keep_days": 77}, "It must be forever"),
        ({"monthly_window": {"unit": "forever"}, "monthly_keep_days": 76}, "set at least 77"),
        ({"monthly_window": {"unit": "forever"}, "monthly_keep_days": 77}, None),
    ],
    ids=["a-window-that-deletes-a-month-first", "a-wait-that-changes-nothing", "packs"],
)
def test_packing_years_keeps_every_month_until_its_year_and_waits_past_the_next_january(
    tmp_path: Path, changes: dict[str, Any], refusal: str | None
) -> None:
    """A window would drop a month its year never gets; a wait below 77 acts as 77 does."""
    config_dir = a_garden(tmp_path, compact_gardener=a_compaction("gardener", **changes))
    if refusal is None:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "config/gardener/compact-gardener.json is refused" in message
        assert refusal in message


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
        (
            {"monthly_window": {"unit": "forever"}},
            "keeps its month files forever only when it packs each finished year",
        ),
        (
            {"daily_keep_days": 31, "monthly_window": {"unit": "days", "value": 40}},
            "would have days no file holds",
        ),
        ({"monthly_window": {"unit": "months", "value": 13}}, None),
    ],
    ids=["forever", "short-of-the-widest-window", "long-enough"],
)
def test_a_published_ledger_reaches_the_widest_window_and_keeps_months_forever_only_packed(
    tmp_path: Path, changes: dict[str, Any], refusal: str | None
) -> None:
    """What a reader fetches first stays bounded, and the console's widest span has its days."""
    compaction = a_compaction("gardener", **changes)
    config_dir = published(a_garden(tmp_path, compact_gardener=compaction), "gardener")
    if refusal is None:
        config.load_gardener(config_dir)
    else:
        assert refusal in refused(config_dir)


@pytest.mark.parametrize(
    ("days_past_the_earliest", "refusal"),
    [(-1, "set at least"), (0, None)],
    ids=["a-day-under-the-earliest-wait", "the-earliest-wait"],
)
def test_a_published_ledger_that_packs_years_waits_what_its_declaration_says(
    tmp_path: Path, days_past_the_earliest: int, refusal: str | None
) -> None:
    """Publishing a ledger adds no wait: the knob's own floor is the only one it meets."""
    declared = CompactionPolicy.model_validate(fixture("compact-gardener"))
    earliest = declared.daily_keep_days + JANUARY_DAYS + 1
    packs = {
        "monthly_window": {"unit": "forever"},
        "monthly_keep_days": earliest + days_past_the_earliest,
    }
    config_dir = published(
        a_garden(tmp_path, compact_gardener=a_compaction("gardener", **packs)), "gardener"
    )
    if refusal is None:
        config.load_gardener(config_dir)
    else:
        message = refused(config_dir)
        assert "config/gardener/compact-gardener.json is refused" in message
        assert f"{refusal} {earliest}" in message


#: Reads a window off the dict a declaration spells it as.
WINDOW: Final[TypeAdapter[Window]] = TypeAdapter(Window)


@pytest.mark.parametrize(
    ("floor", "monthly", "reaches"),
    [
        (MONTHS, {"unit": "months", "value": 12}, False),
        (MONTHS, {"unit": "months", "value": 13}, True),
        (MONTHS, {"unit": "forever"}, True),
        ({"unit": "forever"}, {"unit": "months", "value": 13}, False),
        ({"unit": "forever"}, {"unit": "forever"}, True),
    ],
    ids=["bounded-short", "bounded-long", "bounded-forever", "forever-bounded", "forever-forever"],
)
def test_a_compaction_reaches_a_floor_by_its_two_periods(
    floor: dict[str, Any], monthly: dict[str, Any], reaches: bool
) -> None:
    """The five cases, read off `daily_keep_days` and `monthly_window` alone.

    Forty-five days and twelve months reach back 410 days where fourteen months
    can ask for 428, and thirteen months reach back 438. A window of forever
    reaches anything, and nothing shorter reaches a floor of forever, because a
    person chose never to delete that ledger.
    """
    policy = CompactionPolicy.model_validate(a_compaction("gardener", monthly_window=monthly))
    assert config.compaction_reaches(policy, WINDOW.validate_python(floor)) is reaches


def test_a_retention_task_that_kept_an_old_tree_sets_no_floor_on_its_compaction(
    tmp_path: Path,
) -> None:
    """A task that owned a moved ledger's CSV tree runs nothing, so it bounds nothing.

    How long the CSV was kept is `CSV_LEDGERS` in
    `backend/utilities/ledger_migration/csv_layouts.py`, whose own test holds every moved
    ledger's committed compaction to it.
    """
    config_dir = a_garden(
        tmp_path,
        visual_prunes=a_retention(["state/visual-prunes"], MONTHS, "retired"),
        compact_visual_prunes=a_compaction(
            "visual-prunes", monthly_window={"unit": "months", "value": 3}
        ),
    )
    config.load_gardener(config_dir)


def test_a_ledger_no_task_ever_limited_has_no_floor(tmp_path: Path) -> None:
    short = a_compaction("visual-prunes", monthly_window={"unit": "months", "value": 3})
    config.load_gardener(a_garden(tmp_path, compact_visual_prunes=short))


def test_a_series_is_the_floor_of_the_ledger_it_covers(tmp_path: Path) -> None:
    """`item-health` reaches back as far as the full-grain series, not the aggregate one."""
    short = a_compaction("item-health", monthly_window={"unit": "months", "value": 12})
    message = refused(a_garden(tmp_path, compact_item_health=short))
    assert "compact-item-health.json reaches back 410 days" in message
    assert (
        "the full-grain series of config/gardener/telemetry-aggregate.json keeps item-health "
        "14 months" in message
    )


def test_the_month_rule_counts_the_fewest_and_the_most_days() -> None:
    assert config._month_run_days(1) == (28, 31)
    assert config._month_run_days(12) == (365, 366)
