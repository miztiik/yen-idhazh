"""How does each named ledger's declared compaction pack a migrated root?"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from idhazh import config
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy, ForeverWindow, Window
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from idhazh.ledger import paths
from utilities.ledger_migration.csv_cells import row_contract
from utilities.ledger_migration.csv_layouts import CSV_LEDGERS
from utilities.ledger_migration.packing_files import packing_paths
from utilities.ledger_migration.path_labels import label_path
from utilities.ledger_migration.refusals import NotProvenError, RefusedError


def _spelled(window: Window) -> str:
    """A window as a refusal quotes it."""
    return "forever" if isinstance(window, ForeverWindow) else f"{window.value} {window.unit}"


def declared(which: Sequence[LedgerName], config_dir: Path) -> dict[LedgerName, CompactionPolicy]:
    """Each ledger's compaction, taken live and unbounded for this one pass, or a refusal.

    Asked before anything is read or written. A ledger `config/ledgers.json` still
    files as CSV has no door to move into; one with no compaction has nothing to
    say which days are packed; and a compaction that keeps less than the CSV was
    kept would delete, at its first live pass, days the CSV still held - unless
    the ledger's `CsvLedger` entry names the person's decision that allowed it.
    """
    registry = LedgersConfig.from_json((config_dir / "ledgers.json").read_text(encoding="utf-8"))
    entries = {entry.name: entry for family in registry.families for entry in family.ledgers}
    tasks = config.load_gardener(config_dir).tasks
    declared: dict[LedgerName, CompactionPolicy] = {}
    for name in which:
        row_contract(name)
        grain = entries[name].grain
        if grain is not Grain.RAW_AND_COMPACT:
            raise RefusedError(
                f"config/ledgers.json files {name.value} as {grain.value}, so it has no door "
                f"to move into yet: its entry becomes {Grain.RAW_AND_COMPACT.value} in the "
                "change that moves its writers and readers"
            )
        task = config.compaction_task(name, registry=entries)
        policy = tasks.get(task)
        if not isinstance(policy, CompactionPolicy):
            raise RefusedError(
                f"config/idhazh_gardener.json task_names does not list {task}, so nothing can "
                "say which days the packing rule admits"
            )
        kept = CSV_LEDGERS[name].old_window
        if (
            not config.compaction_reaches(policy, kept)
            and CSV_LEDGERS[name].shorter_by is None
        ):
            raise RefusedError(
                f"config/gardener/{task}.json keeps daily_keep_days {policy.daily_keep_days} "
                f"and monthly_window {_spelled(policy.monthly_window)}, which does not reach "
                f"the window of {_spelled(kept)} that kept {name.value} on CSV, so its first "
                "live pass would delete days the CSV still held. A person's decision to keep "
                "it for less goes in its CsvLedger entry, as shorter_by"
            )
        # Validated, because model_copy(update=...) is not: a misspelt key there would be
        # kept beside the real one, and the declaration's own month deletes would run.
        declared[name] = packing_policy(policy)
    return declared


def packing_policy(policy: CompactionPolicy) -> CompactionPolicy:
    """Pack live while keeping every monthly deletion report-only."""
    return CompactionPolicy.model_validate(
        {**policy.model_dump(), "dry_run": False, "month_deletes_dry_run": True}
    )


def policies_for_roots(
    which: Sequence[LedgerName],
    roots: Sequence[Path],
    config_dir: Path,
) -> dict[Path, dict[LedgerName, CompactionPolicy | None]]:
    """Select each explicitly governed root after requiring every production declaration."""
    production = declared(which, config_dir)
    tasks = config.load_gardener(config_dir).tasks
    config_root = config_dir.parent.resolve()
    selected: dict[Path, dict[LedgerName, CompactionPolicy | None]] = {}
    for state_dir in roots:
        try:
            root_name = state_dir.resolve().relative_to(config_root).as_posix()
        except ValueError:
            root_name = ""
        selected[state_dir] = {}
        for name in which:
            if root_name == "state":
                selected[state_dir][name] = production[name]
                continue
            trial = tasks.get(config.compaction_task(name, trial=True))
            if isinstance(trial, CompactionPolicy) and root_name in trial.state_roots:
                # The declaration's own `owns` names tier-first addresses under the
                # shared production `state/`, for the registry-overlay root gardener
                # compaction now packs trial files against (row 7). This caller packs
                # a root migration passes in directly - `root_name` itself is the
                # state_dir, with no overlay - so its folders are `<root_name>/raw/`
                # and `<root_name>/compact/` nested under that root, not a filtered
                # slice of the shared declaration's own paths.
                root_owns = [
                    "/".join((root_name, tier, *paths.door_folders(name)))
                    for tier in (paths.RAW_DIRNAME, paths.COMPACT_DIRNAME)
                ]
                selected[state_dir][name] = CompactionPolicy.model_validate(
                    {
                        **packing_policy(trial).model_dump(),
                        "owns": root_owns,
                        "state_roots": [root_name],
                    }
                )
            else:
                selected[state_dir][name] = None
    return selected


def packs_here(state_dir: Path, config_dir: Path) -> bool:
    """Whether any compaction declaration names this root for packing."""
    try:
        root_name = state_dir.resolve().relative_to(config_dir.parent.resolve()).as_posix()
    except ValueError:
        return False
    return any(
        isinstance(policy, CompactionPolicy) and root_name in policy.state_roots
        for policy in config.load_gardener(config_dir).tasks.values()
    )


def pack(
    state_dir: Path,
    which: LedgerName,
    identity: WriterIdentity,
    *,
    repo_root: Path,
    policy: CompactionPolicy,
    today: date,
    months: Sequence[str],
    first_ledger_year: str,
) -> tuple[list[str], list[str], list[str]]:
    """Pack only the named months until a pass writes and deletes no selected period.

    The first and last named month are each pass's range, as a person's `--from`
    and `--to` would be. `first_ledger_year` is `config/idhazh_gardener.json`'s,
    which a pass that rebuilds an absent index looks from.
    """
    context = f"{label_path(state_dir)}: {which.value}"
    written: list[str] = []
    deleted: list[str] = []
    packed: set[str] = set()
    while True:
        folders = tuple(folder for folder in policy.owns if (repo_root / folder).is_dir())
        try:
            outcome = compaction.run(
                TaskContext(
                    state_dir=state_dir,
                    repo_root=repo_root,
                    today=today,
                    policy=policy,
                    run_id=identity.run_id,
                    attempt=identity.attempt,
                    job=ServerJob.RUN_TASKS,
                    shard=identity.shard,
                    git_sha=identity.git_sha,
                    owned_folders=folders,
                    listing=FileListing.from_disk(
                        repo_root, policy.owns, paths=packing_paths(state_dir, which, months)
                    ),
                    first_ledger_year=first_ledger_year,
                    period_range=(min(months), max(months)),
                ),
            )
        except ValueError as refusal:
            raise NotProvenError(f"{context}: packing refused: {refusal}") from refusal
        written.extend(outcome.written)
        deleted.extend(outcome.taken)
        for path in outcome.written:
            parts = path.split("/")
            if "daily" in parts:
                index = parts.index("daily")
                if len(parts) > index + 3 and parts[-1].endswith(".parquet"):
                    day_parts = (
                        *parts[index + 1 : index + 3],
                        parts[index + 3].removesuffix(".parquet"),
                    )
                    packed.add(date.fromisoformat("-".join(day_parts)).isoformat())
        if outcome.fault is not None:
            raise NotProvenError(
                f"{context}: the compaction refused at {outcome.resume_from} "
                f"({outcome.fault.value}); CSV files are kept"
            )
        if outcome.written or outcome.taken:
            continue
        if outcome.stopped_because is not StopReason.EXHAUSTED:
            raise NotProvenError(
                f"{context}: the compaction stopped at {outcome.resume_from} without "
                "writing or deleting a period; CSV files are kept"
            )
        return sorted(packed), list(dict.fromkeys(written)), list(dict.fromkeys(deleted))
