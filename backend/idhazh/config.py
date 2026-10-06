"""Load `config/` once, validate it, and hand it to the stages.

A stage never reads a file by itself and never reaches for an environment
variable. Everything tunable arrives here, schema-validated, so a bad config is
a startup failure with a readable message rather than a strange result four
hundred seconds into a run.

The digests of the files that were read travel with the run, because a knob
edited between two runs changes every output and is otherwise invisible. The
active model's file is one of them: it is named by `models_file` rather than
fixed, so a run that did not record it could not say which model's numbers it
read.

The gardener reads its own two inputs through `load_gardener`: its knobs in
`config/idhazh_gardener.json` and one declaration per task under
`config/gardener/`. They are loaded apart from `load`, because a digest run has
no use for them and a gardener run has no use for the model files. Every
refusal that needs only those files and `config/idhazh.json` is made here, as
they load; the two that need the task modules are the gardener runner's.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date as date_type
from functools import cache
from itertools import combinations
from operator import attrgetter
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.base import SLUG_PATTERN
from idhazh.contracts.knobs.gardener import (
    CollectionTaskPolicy,
    CompactionPolicy,
    DaysWindow,
    ForeverWindow,
    GardenerConfig,
    MonthsWindow,
    RetentionPolicy,
    TaskPolicy,
    Window,
)
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import ConfigDigest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.llm.server import SETTING_KEYS, refuse_a_sampling_key_a_route_sets

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR: Final = REPO_ROOT / "config"


_FILES: Final[tuple[str, ...]] = ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json")
#: Read for validation and not digested. It owns the console window every
#: cleanup age has to outlive, so a run that deletes a shard has to have checked
#: against the file the published console really reads - `AppConfig.console` is
#: the layer under it and can disagree. Its digest is not recorded because
#: nothing in the run reads a value out of it.
_APPEARANCE_FILE: Final = "appearance.json"


def refuse_a_model_nothing_could_run(models_file: str, models: ModelsConfig) -> None:
    """Four questions asked once, before anything is fetched and before any server.

    The settings blocks are plain mappings, so llama-server refuses a flag it
    does not accept and nothing here second-guesses it. These four are the ones
    the binary cannot answer for.

    **The window is required**, because this project computes on it and a
    default of ours beside a default of the server's is two answers for one
    value. It is real arithmetic in `idhazh.classify.dag` and
    `idhazh.evals.qualify`, and the published site reads it at build time. The
    per-request timeout is required too and the entry itself enforces that, so a
    string there raises naming the key rather than inside a request mid-item.

    **A sampling key that a route sets itself is refused here**, where an
    operator is reading a message about the file they just edited. Left to the
    builder it fires on the first item of every shard at once, after each has
    already restored the cache and loaded the weights.

    **`declared_for` catches one specific edit**: a weights string changed in
    place with the settings left behind. Nothing else in the tree sees a
    half-done model swap, and a stale weights reference is silent.

    **The judge rule catches a second entry naming weights nobody serves.** No
    server is started for it, so it decodes on the weights the summariser's
    server holds while every verdict is recorded under a model that never saw
    the pair.
    """
    for role, entry in models.entries():
        key = SETTING_KEYS["n_ctx"]
        if key not in entry.server:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} declares no {key}. "
                "This project computes on it, so there is no server-side default "
                "to fall back to"
            )
        taken = refuse_a_sampling_key_a_route_sets(entry.sampling)
        if taken is not None:
            raise ValueError(
                f"config/{models_file} is refused: models.{role}.sampling is not free "
                f"to set every key, and {taken}. A request key that re-spells or "
                "disables constrained decoding is the route's own"
            )
        if entry.declared_for != entry.sha256:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} is declared for "
                f"{entry.declared_for or 'no weights at all'} and names "
                f"{entry.sha256 or 'no weights at all'}. Every setting and every marker "
                "on that entry was derived against one model on one runner, so re-derive "
                f"them for these weights and set models.{role}.declared_for to the digest "
                "the entry carries - or put the entry back"
            )
        if role not in type(models).roles() and entry.sha256 != models.summarizer.sha256:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} names weights "
                f"{entry.sha256 or 'nothing at all'} and models.summarizer names "
                f"{models.summarizer.sha256 or 'nothing at all'}. No server is started "
                f"for models.{role}, so it decodes on the weights the summariser's "
                "server holds - name those, or make it a role of its own"
            )


def models_path(config_dir: Path, app: AppConfig) -> Path:
    """Where the active model is, following the pointer and nothing else.

    One function so that a test, an operator utility and the loader all resolve
    it the same way. The grammar on `AppConfig.models_file` is what keeps this
    inside `config/models/`, so this joins rather than checks.
    """
    return config_dir / app.models_file


@dataclass(frozen=True, slots=True)
class Settings:
    """Every tunable the run will consult, already validated."""

    app: AppConfig
    models: ModelsConfig
    appearance: AppearanceConfig
    sources: Sources
    taxonomy: Taxonomy
    watchlist: Watchlist
    digests: tuple[ConfigDigest, ...]


def load(config_dir: Path = DEFAULT_CONFIG_DIR) -> Settings:
    """A fresh clone runs on the committed defaults; a missing file is a failure, not a default."""
    read = {name: (config_dir / name).read_text(encoding="utf-8") for name in _FILES}
    app = AppConfig.from_json(read["idhazh.json"])
    read[app.models_file] = models_path(config_dir, app).read_text(encoding="utf-8")
    try:
        models = ModelsConfig.from_json(read[app.models_file])
    except ValidationError as error:
        # Which file, named in the first line. Every model has a file of its own
        # now, so the one thing a refusal could no longer say for itself is the
        # one an operator needs before they can edit anything.
        raise ValueError(f"config/{app.models_file} is refused: {error}") from error
    refuse_a_model_nothing_could_run(app.models_file, models)
    appearance = AppearanceConfig.from_json(
        (config_dir / _APPEARANCE_FILE).read_text(encoding="utf-8")
    )
    window = appearance.console.max_window_days
    app.observability.refuse_windows_shorter_than(
        months_a_window_can_touch(window), window_days=window
    )
    return Settings(
        app=app,
        models=models,
        appearance=appearance,
        sources=Sources.from_json(read["sources.json"]),
        taxonomy=Taxonomy.from_json(read["taxonomy.json"]),
        watchlist=Watchlist.from_json(read["watchlist.json"]),
        digests=tuple(
            ConfigDigest(
                path=f"config/{name}",
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
            for name, text in sorted(read.items())
        ),
    )


# --- the gardener ------------------------------------------------------------

#: The gardener's own knobs: how a wake is sharded and how hard a shard pushes.
GARDENER_FILE: Final = "idhazh_gardener.json"
#: One declaration a task, named for the task. A missing folder means no tasks.
GARDENER_TASKS_DIR: Final = "gardener"
#: What a declaration's name ends in. The plan job's glob reads the same suffix.
DECLARATION_SUFFIX: Final = ".json"

#: The knobs in `config/idhazh.json` that say how many days back a reader opens a
#: ledger. Whichever declaration governs the ledger now - its compaction once it
#: files under the two roots, its retention task before - may not delete a day
#: inside that span, or the reader opens a day nothing kept. A negative knob
#: reads every day there is, so nothing may delete the ledger at all.
_WINDOW_FLOORS: Final[Mapping[LedgerName, str]] = MappingProxyType(
    {
        LedgerName.SEEN: "collect.seen_window_days",
        LedgerName.COUNTERFACTUAL_SCORES: "lens_weights.window_days",
        LedgerName.PUBLISHED: "collect.published_window_days",
    }
)

#: The name of a task's series that its own `window` must equal: the rows kept
#: one by one, which every task that keeps series has.
FULL_GRAIN: Final = "full-grain"

#: The telemetry task's series for the browser's copy of the ledger it folds.
PUBLIC_COPY: Final = "public-copy"


@dataclass(frozen=True, slots=True)
class _Series:
    """One series a task may keep, and the ledger under `state/` whose files it deletes."""

    #: The published copy covers a tree outside `state/`, so it names none.
    ledger: LedgerName | None


#: Every task that keeps several series of one tree family at different ages,
#: and each series it may keep.
_SERIES: Final[Mapping[str, Mapping[str, _Series]]] = MappingProxyType(
    {
        "telemetry-aggregate": MappingProxyType(
            {
                FULL_GRAIN: _Series(LedgerName.ITEM_HEALTH),
                PUBLIC_COPY: _Series(None),
                "aggregate": _Series(LedgerName.ITEM_HEALTH_SUMMARY),
            }
        ),
    }
)

#: The summary series of a task, which has to outlive its full-grain series or
#: a month is deleted before it was ever summarised.
_SUMMARY_SERIES: Final[Mapping[str, str]] = MappingProxyType({"telemetry-aggregate": "aggregate"})

#: Each ledger whose files a console read can still open. The declaration that
#: governs it keeps every month file the widest read can select.
_CONSOLE_READ_LEDGERS: Final[tuple[LedgerName, ...]] = (LedgerName.FEED_HEALTH,)

#: Each task series whose files a console read can still open, held the same way.
_CONSOLE_READ_SERIES: Final[tuple[tuple[str, str], ...]] = (
    ("telemetry-aggregate", FULL_GRAIN),
    ("telemetry-aggregate", PUBLIC_COPY),
)

#: The tasks that delete what the archive page promises to keep for
#: `retention.image_months`, and how many days that knob counts a month as.
#: Thirty because that is the arithmetic the promise was first made in; a
#: calendar month would move what every picture window selects.
_PICTURE_WINDOW_TASKS: Final = ("digest-fragments", "visual-prune")
_DAYS_A_PICTURE_MONTH: Final = 30

#: The ledger the published machine shard is folded from, so the declaration
#: that governs it may not keep less than `observability.public_machine_keep_months`.
_MACHINE_SOURCE: Final = LedgerName.HOST_FINGERPRINT

_TASK_POLICY: Final[TypeAdapter[TaskPolicy]] = TypeAdapter(TaskPolicy)
_A_TASK_NAME: Final = re.compile(SLUG_PATTERN)


@dataclass(frozen=True, slots=True)
class GardenerSettings:
    """The gardener's knobs and every declaration, validated as one set."""

    config: GardenerConfig
    #: Every declaration whatever its status, keyed by task name in sorted order.
    tasks: Mapping[str, TaskPolicy]
    #: The rest of the configuration the declarations were checked against.
    app: AppConfig


def load_gardener(config_dir: Path = DEFAULT_CONFIG_DIR) -> GardenerSettings:
    """The gardener's settings, or a refusal naming the file and the rule it broke.

    The declarations are validated as one set and never one at a time, because
    most of what can be wrong with a declaration is a clash: with another
    declaration, or with a knob in `config/idhazh.json` it has to outlive.
    """
    gardener = _gardener_config(config_dir)
    tasks = _declarations(config_dir, gardener.task_names)
    app = AppConfig.from_json((config_dir / _FILES[0]).read_text(encoding="utf-8"))
    appearance = AppearanceConfig.from_json(
        (config_dir / _APPEARANCE_FILE).read_text(encoding="utf-8")
    )
    refuse_what_the_declarations_break(
        tasks, app=app, appearance=appearance, repo_root=config_dir.parent
    )
    return GardenerSettings(config=gardener, tasks=MappingProxyType(tasks), app=app)


def _gardener_config(config_dir: Path) -> GardenerConfig:
    text = (config_dir / GARDENER_FILE).read_text(encoding="utf-8")
    try:
        return GardenerConfig.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(f"config/{GARDENER_FILE} is refused: {error}") from error


def _declarations(config_dir: Path, names: tuple[str, ...]) -> dict[str, TaskPolicy]:
    """The configured declarations, by name, opened without listing their directory."""
    folder = config_dir / GARDENER_TASKS_DIR
    found: dict[str, TaskPolicy] = {}
    for name in sorted(names):
        path = folder / f"{name}{DECLARATION_SUFFIX}"
        where = f"config/{GARDENER_TASKS_DIR}/{path.name}"
        if not _A_TASK_NAME.fullmatch(name):
            raise ValueError(
                f"{where} is refused: a task is named by its file, and {name!r} is "
                "not a lower-case word or words joined by hyphens"
            )
        if not path.is_file():
            raise ValueError(f"{where} is missing; config/{GARDENER_FILE} names it in task_names")
        try:
            found[path.stem] = _TASK_POLICY.validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(
                f"{where} is refused: this configured task declaration is missing"
            ) from error
        except ValidationError as error:
            raise ValueError(f"{where} is refused: {error}") from error
    return found


def refuse_what_the_declarations_break(
    tasks: Mapping[str, TaskPolicy],
    *,
    app: AppConfig,
    appearance: AppearanceConfig,
    repo_root: Path,
) -> None:
    """Every rule the declarations must keep that needs no task module to check."""
    _refuse_overlapping_claims(tasks)

    _refuse_a_file_where_a_folder_belongs(tasks, repo_root)
    _refuse_a_window_under_its_floor(tasks, app)
    _refuse_a_series_the_task_cannot_keep(tasks)
    _refuse_a_summary_that_goes_first(tasks)
    _refuse_a_copy_that_is_not_its_source(tasks)
    _refuse_a_window_a_console_read_still_opens(tasks, appearance)
    _refuse_a_machine_source_shorter_than_its_copy(tasks, app)
    _refuse_a_picture_window_the_archive_does_not_state(tasks, app)
    for name, policy in tasks.items():
        if isinstance(policy, CompactionPolicy):
            _refuse_a_compaction_that_cuts_its_ledger(
                name, policy, tasks, app=app, appearance=appearance
            )
        if isinstance(policy, CollectionTaskPolicy):
            _refuse_a_collection_named_for_another(name, policy)


def _refuse_a_collection_named_for_another(name: str, policy: CollectionTaskPolicy) -> None:
    """One collection, one task: a collection task is named for the collection it prunes.

    A collection task owns no folder, so the overlap check cannot keep two tasks
    off one collection. The file name can, because two files cannot share one.
    """
    if name != policy.collection.value:
        raise ValueError(
            f"config/{GARDENER_TASKS_DIR}/{name}.json prunes {policy.collection.value}, and a "
            f"collection task is named for its collection: call it "
            f"{policy.collection.value}.json"
        )


def _nested(one: str, other: str) -> bool:
    """Whether two folders are the same folder or one holds the other, segment by segment."""
    first, second = PurePosixPath(one).parts, PurePosixPath(other).parts
    shorter = min(len(first), len(second))
    return first[:shorter] == second[:shorter]


def _refuse_overlapping_claims(tasks: Mapping[str, TaskPolicy]) -> None:
    """Two tasks may not own one folder, or one folder and a folder inside it.

    Every status takes part. A paused task still owns what it owns, and a retired
    one keeps its claim so its window stays readable after its tree has moved.
    Every task names its folders directly. A task cannot claim an accumulating
    parent and discover its children at run time.
    """
    for (first, one), (second, other) in combinations(tasks.items(), 2):
        for mine in one.owns:
            for theirs in other.owns:
                if _nested(mine, theirs):
                    raise ValueError(
                        f"config/{GARDENER_TASKS_DIR}/{first}.json owns {mine} and "
                        f"config/{GARDENER_TASKS_DIR}/{second}.json owns {theirs}. Two "
                        "tasks may not own one folder or a folder inside the other's, "
                        "whatever their status, or both would delete in it"
                    )


def _refuse_a_file_where_a_folder_belongs(tasks: Mapping[str, TaskPolicy], repo_root: Path) -> None:
    """A shard lists the files under each folder a task owns, so an owned file would list none."""
    for name, policy in tasks.items():
        for claimed in policy.claims():
            if (repo_root / claimed).is_file():
                raise ValueError(
                    f"config/{GARDENER_TASKS_DIR}/{name}.json owns {claimed}, which is a "
                    "file. A task owns folders: the shard that runs it lists the files "
                    "under each one, and a file there would list nothing"
                )


@cache
def _month_run_days(months: int) -> tuple[int, int]:
    """The fewest and the most days `months` calendar months in a row can hold.

    Swept over the month-firsts of one 400-year Gregorian cycle, which is exact
    rather than a sample: the calendar repeats every 400 years.
    """
    lengths: list[int] = []
    for year in range(2000, 2400):
        for month in range(1, 13):
            later = year * 12 + month - 1 + months
            start = date_type(year, month, 1)
            end = date_type(later // 12, later % 12 + 1, 1)
            lengths.append((end - start).days)
    return min(lengths), max(lengths)


def _days_kept(window: Window) -> int | None:
    """The fewest days a window keeps, wherever the calendar puts it. None is forever."""
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return window.value
    return _month_run_days(window.value)[0]


def _days_needed(window: Window) -> int | None:
    """The most days a window can ask for, wherever the calendar puts it. None is forever."""
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return window.value
    return _month_run_days(window.value)[1]


def _reaches(kept: Window, needed: Window) -> bool:
    """Whether a window that deletes keeps at least as far back as one that is needed.

    One unit against the same unit compares the numbers, because both count the
    same calendar the same way. Days against months is compared where it is
    hardest to pass: the fewest days the kept window can hold against the most
    the needed one can ask for, so the answer never depends on the build's date.
    """
    if isinstance(needed, ForeverWindow):
        return isinstance(kept, ForeverWindow)
    if isinstance(kept, ForeverWindow):
        return True
    if type(kept) is type(needed):
        return kept.value >= needed.value
    kept_days, needed_days = _days_kept(kept), _days_needed(needed)
    assert kept_days is not None and needed_days is not None
    return kept_days >= needed_days


def _spelled(window: Window) -> str:
    if isinstance(window, ForeverWindow):
        return "forever"
    return f"{window.value} {window.unit}"


def _reach(policy: CompactionPolicy) -> int | None:
    """The fewest days a compaction's two periods reach back, or None when it keeps for ever.

    A month file lives `monthly_window` after its month is absorbed, and a month
    is absorbed `daily_keep_days` after it ends, so no pair of the two can leave a
    day in no period. The months are counted at the fewest days they can hold.
    """
    monthly = _days_kept(policy.monthly_window)
    return None if monthly is None else policy.daily_keep_days + monthly


def compaction_reaches(policy: CompactionPolicy, needed: Window) -> bool:
    """Whether this compaction keeps every day `needed` asks for.

    A `monthly_window` of forever reaches anything, and nothing shorter reaches a
    floor of forever. Otherwise the pair's reach is set against the most days
    `needed` can ask for, so the answer never depends on the day the build ran.
    """
    reach = _reach(policy)
    if reach is None:
        return True
    wanted = _days_needed(needed)
    return wanted is not None and reach >= wanted


def _governing(
    ledger: LedgerName, tasks: Mapping[str, TaskPolicy]
) -> tuple[str, RetentionPolicy | CompactionPolicy] | None:
    """The one declaration that says how long this ledger is kept now, with its task name.

    The ledger's compaction, once it files under the two roots; else the
    retention task whose `owns` holds the ledger's folder under `state/`; else
    none, and nothing deletes the ledger. The name comes back with it so a
    refusal names the file an operator edits.
    """
    # Imported here rather than at the top: the ledger package reads this module
    # while it loads, so importing it back at module scope would be a cycle.
    from idhazh.ledger.paths import STATE_DIRNAME, entry

    name = f"compact-{'-'.join(entry(ledger).prefix)}"
    compaction = tasks.get(name)
    if isinstance(compaction, CompactionPolicy) and compaction.ledger is ledger:
        return name, compaction
    folder = "/".join((STATE_DIRNAME, *entry(ledger).prefix))
    for task, policy in tasks.items():
        if isinstance(policy, RetentionPolicy) and folder in policy.owns:
            return task, policy
    return None


def _keeps(policy: RetentionPolicy | CompactionPolicy, needed: Window) -> bool:
    """Whether the declaration that governs a ledger keeps every day `needed` asks for."""
    if isinstance(policy, CompactionPolicy):
        return compaction_reaches(policy, needed)
    return _reaches(policy.window, needed)


def _kept_by(policy: RetentionPolicy | CompactionPolicy) -> str:
    """How far back a governing declaration keeps, in the words a refusal quotes."""
    if isinstance(policy, RetentionPolicy):
        return f"keeps {_spelled(policy.window)}"
    reach = _reach(policy)
    if reach is None:
        return "keeps every month file for ever"
    return (
        f"reaches back {reach} days with daily_keep_days {policy.daily_keep_days} and "
        f"monthly_window {_spelled(policy.monthly_window)}"
    )


def _a_floor(days: int) -> Window:
    """How far back a reader opens, as a window. A negative count reads every day."""
    if days < 0:
        return ForeverWindow(unit="forever")
    return DaysWindow(unit="days", value=days)


def _refuse_a_window_under_its_floor(tasks: Mapping[str, TaskPolicy], app: AppConfig) -> None:
    """The declaration that governs a ledger keeps every day a reader's knob opens."""
    for ledger, knob in _WINDOW_FLOORS.items():
        governing = _governing(ledger, tasks)
        if governing is None:
            continue
        name, policy = governing
        days: int = attrgetter(knob)(app)
        if not _keeps(policy, _a_floor(days)):
            reads = f"reads {days} days back" if days >= 0 else f"is {days}, which reads every day"
            raise ValueError(
                f"{_where(name)} {_kept_by(policy)} and {knob} {reads}, so the task would "
                "delete days a reader still opens"
            )


def _where(name: str) -> str:
    return f"config/{GARDENER_TASKS_DIR}/{name}.json"


def _series_of(policy: TaskPolicy, series: str | None) -> Window:
    """A task's window when `series` is None, else that series, which must be declared."""
    if series is None:
        return policy.window
    kept = policy.series if isinstance(policy, RetentionPolicy) else None
    assert kept is not None and series in kept, "checked by the series rule, which runs first"
    return kept[series]


def _outlives(longer: Window, shorter: Window) -> bool:
    """Whether a window keeps strictly further back than another, wherever the calendar falls."""
    if isinstance(longer, ForeverWindow):
        return not isinstance(shorter, ForeverWindow)
    if isinstance(shorter, ForeverWindow):
        return False
    if type(longer) is type(shorter):
        return longer.value > shorter.value
    longer_days, shorter_days = _days_kept(longer), _days_needed(shorter)
    assert longer_days is not None and shorter_days is not None
    return longer_days > shorter_days


def _refuse_a_series_the_task_cannot_keep(tasks: Mapping[str, TaskPolicy]) -> None:
    """Series belong to the tasks that keep several at once, and each names every one it keeps.

    A task that keeps series keeps its own `window` equal to its full-grain one,
    so one number is never spelled twice with room to disagree.
    """
    for name, policy in tasks.items():
        carries = isinstance(policy, RetentionPolicy) and bool(policy.series)
        if name not in _SERIES and carries:
            raise ValueError(
                f"{_where(name)} keeps series, and only "
                f"{', '.join(sorted(_SERIES))} may keep several series at once"
            )
    for keeper_name, allowed in _SERIES.items():
        keeper = tasks.get(keeper_name)
        if keeper is None:
            continue
        where = _where(keeper_name)
        if not isinstance(keeper, RetentionPolicy) or not keeper.series:
            raise ValueError(
                f"{where} keeps no series. It is a retention task that keeps several, so it "
                "names each one with its window"
            )
        unknown = sorted(set(keeper.series) - set(allowed))
        if unknown:
            raise ValueError(
                f"{where} keeps a series called {unknown[0]}, which is not one of its "
                f"trees. It keeps {', '.join(sorted(allowed))}"
            )
        missing = sorted(set(allowed) - set(keeper.series))
        if missing:
            raise ValueError(
                f"{where} names no window for its {missing[0]} series. It keeps "
                f"{', '.join(sorted(allowed))}, and a tree with no window is a tree "
                "nothing bounds"
            )
        full_grain = keeper.series[FULL_GRAIN]
        if full_grain != keeper.window:
            raise ValueError(
                f"{where} keeps its window {_spelled(keeper.window)} and its {FULL_GRAIN} "
                f"series {_spelled(full_grain)}. The window is the {FULL_GRAIN} series, so "
                "the two are one number"
            )
        if keeper.max_deletes_per_run is not None:
            raise ValueError(
                f"{where} names a ceiling of {keeper.max_deletes_per_run}. It summarises a "
                "whole month before that month's files go, and a ceiling could stop it part "
                "way through one, so the next pass would summarise what was left over the "
                "summary of the whole month. It carries none"
            )


def _refuse_a_summary_that_goes_first(tasks: Mapping[str, TaskPolicy]) -> None:
    """A summary series keeps strictly longer than the rows it summarises."""
    for name, summary in _SUMMARY_SERIES.items():
        policy = tasks.get(name)
        if policy is None:
            continue
        kept, rows = _series_of(policy, summary), _series_of(policy, FULL_GRAIN)
        if not _outlives(kept, rows):
            raise ValueError(
                f"{_where(name)} keeps its {summary} series {_spelled(kept)} and its "
                f"{FULL_GRAIN} series {_spelled(rows)}. The {summary} must sit above the "
                f"{FULL_GRAIN}, or a month is deleted before it is ever summarised"
            )


def _refuse_a_copy_that_is_not_its_source(tasks: Mapping[str, TaskPolicy]) -> None:
    """The browser's copy of a ledger and the ledger itself age as one number."""
    policy = tasks.get("telemetry-aggregate")
    if policy is None:
        return
    copy, source = _series_of(policy, PUBLIC_COPY), _series_of(policy, FULL_GRAIN)
    if copy != source:
        raise ValueError(
            f"{_where('telemetry-aggregate')} keeps its {PUBLIC_COPY} series "
            f"{_spelled(copy)} and its {FULL_GRAIN} series {_spelled(source)}. The copy is "
            "the browser's copy of that ledger, so any other pair leaves either a published "
            "month nothing can check or a window the console cannot draw"
        )


def _refuse_a_window_a_console_read_still_opens(
    tasks: Mapping[str, TaskPolicy], appearance: AppearanceConfig
) -> None:
    """A task may not delete a month file the widest console read can still select."""
    window_days = appearance.console.max_window_days
    shards = months_a_window_can_touch(window_days)
    floor = MonthsWindow(unit="months", value=shards)

    def refused(name: str, kept: str) -> ValueError:
        return ValueError(
            f"{_where(name)} {kept}, and a {window_days}-day console read can select "
            f"{shards} month shards. It must keep at least {shards} months, or a panel "
            "blanks for a month that ran"
        )

    for ledger in _CONSOLE_READ_LEDGERS:
        governing = _governing(ledger, tasks)
        if governing is not None and not _keeps(governing[1], floor):
            raise refused(governing[0], _kept_by(governing[1]))
    for name, series in _CONSOLE_READ_SERIES:
        policy = tasks.get(name)
        if policy is None:
            continue
        kept = _series_of(policy, series)
        if not _reaches(kept, floor):
            raise refused(name, f"keeps its {series} series {_spelled(kept)}")


def _refuse_a_machine_source_shorter_than_its_copy(
    tasks: Mapping[str, TaskPolicy], app: AppConfig
) -> None:
    """The published machine shard is rebuilt from its ledger, so the ledger lasts as long."""
    governing = _governing(_MACHINE_SOURCE, tasks)
    if governing is None:
        return
    name, policy = governing
    published = app.observability.public_machine_keep_months
    if not _keeps(policy, MonthsWindow(unit="months", value=published)):
        raise ValueError(
            f"{_where(name)} {_kept_by(policy)} and "
            f"observability.public_machine_keep_months is {published}. The published "
            "machine shard is folded from the host-fingerprint ledger, so a source month "
            "deleted while the published one is still kept is a shard nothing can rebuild"
        )


def _refuse_a_picture_window_the_archive_does_not_state(
    tasks: Mapping[str, TaskPolicy], app: AppConfig
) -> None:
    """The archive page states `retention.image_months`, so the cleanup keeps exactly that."""
    months = app.retention.image_months
    stated: Window = (
        ForeverWindow(unit="forever")
        if months < 0
        else DaysWindow(unit="days", value=months * _DAYS_A_PICTURE_MONTH)
    )
    for name in _PICTURE_WINDOW_TASKS:
        policy = tasks.get(name)
        if policy is not None and policy.window != stated:
            raise ValueError(
                f"{_where(name)} keeps {_spelled(policy.window)} and retention.image_months "
                f"is {months}, which the archive page states to a reader as "
                f"{_spelled(stated)}. The cleanup keeps exactly the window the page states, "
                "so a reader is never told a picture stays that the cleanup takes"
            )


def _old_tree_floor(
    ledger: LedgerName, tasks: Mapping[str, TaskPolicy]
) -> tuple[str, str, Window] | None:
    """The series that still summarises a ledger's months: its task, its name and its window.

    A task that summarises a ledger's months reads them for as long as the series
    that covers the ledger lasts, whether or not it still owns the tree they sat
    in. How long a retention task kept a moved ledger's CSV is not read here:
    `CSV_LEDGERS` in `backend/utilities/ledger_migration/csv_layouts.py` records it, and
    that table's test holds every moved ledger's compaction to it.
    """
    for name, policy in tasks.items():
        if not isinstance(policy, RetentionPolicy):
            continue
        allowed = _SERIES.get(name, {})
        for series, window in (policy.series or {}).items():
            kept = allowed.get(series)
            if kept is not None and kept.ledger is ledger:
                return name, series, window
    return None


def _refuse_a_published_reach_that_grows_or_falls_short(
    where: str,
    policy: CompactionPolicy,
    reach: int | None,
    *,
    appearance: AppearanceConfig,
) -> None:
    """What a browser fetches for a published ledger stays bounded, and covers the console.

    Month files kept forever would make the monthly index a reader fetches first
    grow with the archive, unless the ledger packs each finished year into one
    file: its month files then last until their year is packed, and the yearly
    index grows by one entry a year. A ledger that packs years keeps every month
    until its year is packed and every year for ever, so it reaches back past any
    span the console offers, and it waits as long as its own declaration says. A
    ledger that deletes its month files reaches back at least the widest span the
    console offers.
    """
    ledger = policy.ledger.value
    if policy.monthly_keep_days is not None:
        return
    if reach is None:
        raise ValueError(
            f"{where} keeps monthly_window forever and {ledger} is in ledger.published, and "
            "it sets no monthly_keep_days. A published ledger keeps its month files forever "
            "only when it packs each finished year into one file, or what a reader's first "
            "request fetches grows with the archive"
        )
    widest = max(appearance.console.window_presets)
    if reach < widest:
        raise ValueError(
            f"{where} reaches back {reach} days with daily_keep_days "
            f"{policy.daily_keep_days} and monthly_window "
            f"{_spelled(policy.monthly_window)}, and console.window_presets offers "
            f"{widest}. The widest span the console offers would have days no file holds"
        )


def _refuse_a_compaction_that_cuts_its_ledger(
    name: str,
    policy: CompactionPolicy,
    tasks: Mapping[str, TaskPolicy],
    *,
    app: AppConfig,
    appearance: AppearanceConfig,
) -> None:
    """Once a ledger is compacted its periods are its retention, so they must reach.

    How far back the pair reaches is `compaction_reaches`. The floor here is a
    series that still summarises the ledger's months; the floors a reader's knob,
    the console and the machine shard set are checked where those are.
    """
    where = f"config/{GARDENER_TASKS_DIR}/{name}.json"
    ledger = policy.ledger
    raw_roots = sorted(
        folder.removeprefix("state/raw/")
        for folder in policy.owns or ()
        if folder.startswith("state/raw/")
    )
    expected = (
        f"compact-{raw_roots[0].replace('/', '-')}"
        if len(raw_roots) == 1
        else f"compact-{ledger.value}"
    )
    if name != expected:
        raise ValueError(
            f"{where} compacts {ledger.value}, and a compaction is named for its folder: "
            f"call it {expected}.json"
        )
    reach = _reach(policy)
    if ledger in app.ledger.published:
        _refuse_a_published_reach_that_grows_or_falls_short(
            where, policy, reach, appearance=appearance
        )
    floor = _old_tree_floor(ledger, tasks)
    if floor is None or compaction_reaches(policy, floor[2]):
        return
    task, series, kept = floor
    raise ValueError(
        f"{where} {_kept_by(policy)}, and the {series} series of {_where(task)} keeps "
        f"{ledger.value} {_spelled(kept)}. The pair would delete a month before that series "
        "is done with it"
    )
