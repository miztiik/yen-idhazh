"""Which subcommand of `idhazh gardener` runs, and what does it take?

Routing only. Every subcommand's body is in the module that owns its question
(CLAUDE.md section 1a): `listing.py` says what is declared and how a wake would
split, `shards.py` splits it, and `runner.py` runs a shard or one task. Nothing
in this file reads a declaration, splits a wake or runs a task.

    idhazh gardener list-tasks            every task, its status, its window, what it owns
    idhazh gardener plan-shards [--json]  this wake's shards, and the fullest one
    idhazh gardener run-task NAME | --shard N --run-id R --attempt A --git-sha SHA
                                          run one task, or one shard of this wake

**`run-task` never pushes.** It runs the tasks and writes the record into the
checkout, and stops there. Landing runs git, and nothing under `backend/idhazh/`
may start a process, so a shard that lands is run by
`backend/utilities/gardener_publish.py`, which takes the same line without
`--git-sha` - it reads the commit itself - and builds it from `add_the_run` and
`chosen` below, so the two cannot drift.

The run's identity arrives as flags rather than from the environment, the way
every other verb that writes a record takes it: a stage reads no environment
variable (`idhazh.config`).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import config, month_partition
from idhazh.config import GardenerSettings
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    MonthsWindow,
    RetentionPolicy,
)
from idhazh.gardener import event_log, listing, runner, shards
from idhazh.gardener.outcome import EXIT_INTEGRITY

#: The word that reaches this router. `idhazh/cli.py` holds it in one place -
#: the verb it lists and the verb it hands over on are the same string.
VERB: Final = "gardener"

LIST_TASKS: Final = "list-tasks"
PLAN_SHARDS: Final = "plan-shards"
RUN_TASK: Final = "run-task"


def add_the_run(parser: argparse.ArgumentParser) -> None:
    """The arguments that say which tasks run and which run they belong to."""
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("name", nargs="?", default=None, help="One task, by its name.")
    which.add_argument("--shard", type=int, default=None, help="One shard, counted from 0.")
    parser.add_argument("--run-id", required=True, help="The run this is, as YYYY-MM-DD-N.")
    parser.add_argument(
        "--attempt",
        type=int,
        required=True,
        help="Which attempt of that run. A re-run keeps its run id and counts this up.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=config.REPO_ROOT,
        help="The checkout to run in. Defaults to this one.",
    )
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)


def settings_or_none(config_dir: Path, *, github: bool = False) -> GardenerSettings | None:
    """The loaded declarations with the event log installed at their level, or None once refused.

    `github` says the caller runs as a step on GitHub, so the log also writes
    the workflow commands GitHub reads (`event_log.GitHubLines`). Only the
    landing utility knows that, and it says so.
    """
    try:
        settings = config.load_gardener(config_dir)
    except ValueError as refusal:
        print(refusal, file=sys.stderr)
        return None
    event_log.install(settings.app.logging.level.value, github=github)
    return settings


def chosen(
    settings: GardenerSettings, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[tuple[str, ...], int]:
    """The tasks this line runs and the shard it runs them as, or the parser's refusal."""
    if not re.fullmatch(RUN_ID_PATTERN, args.run_id):
        parser.error(f"--run-id takes YYYY-MM-DD-N, not {args.run_id!r}")
    if args.attempt < 1:
        parser.error(f"--attempt counts from 1, not {args.attempt}")
    try:
        if args.name is not None:
            return (runner.runnable(settings, args.name),), 0
        return runner.tasks_of_shard(settings, args.shard), args.shard
    except ValueError as refusal:
        parser.error(str(refusal))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"idhazh {VERB}", description=__doc__)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    listed = subparsers.add_parser(LIST_TASKS, help="List every declared task.")
    planned = subparsers.add_parser(PLAN_SHARDS, help="Show how this wake splits into shards.")
    planned.add_argument(
        "--json",
        action="store_true",
        help="Print the plan payload on one line, exactly as the plan job does.",
    )
    for child in (listed, planned):
        child.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    ran = subparsers.add_parser(RUN_TASK, help="Run one task, or one shard of this wake.")
    add_the_run(ran)
    ran.add_argument(
        "--git-sha",
        required=True,
        help="The commit this checkout is at, which the record names: git rev-parse HEAD.",
    )
    ran.add_argument(
        "--from",
        dest="from_period",
        help="Inclusive UTC date or month for a one-task backlog pass.",
    )
    ran.add_argument(
        "--to",
        dest="to_period",
        help="Inclusive UTC date or month for a one-task backlog pass.",
    )
    return parser


def period_range(
    settings: GardenerSettings, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[str, str] | None:
    """Validate a named inclusive range against the one task's period grain."""
    start = args.from_period
    end = args.to_period
    if start is None and end is None:
        return None
    if start is None or end is None:
        parser.error("--from and --to must be supplied together")
    if args.name is None:
        parser.error("--from and --to are available only with one named task")
    policy = settings.tasks[args.name]
    if isinstance(policy, CompactionPolicy) or isinstance(policy.window, MonthsWindow):
        if not month_partition.is_month_stem(start) or not month_partition.is_month_stem(end):
            parser.error("--from and --to must be real YYYY-MM months for this task")
        if start > end:
            parser.error("--from must not be later than --to")
        return start, end
    if isinstance(policy, RetentionPolicy) and isinstance(policy.window, DaysWindow):
        try:
            first = date.fromisoformat(start)
            last = date.fromisoformat(end)
        except ValueError:
            parser.error("--from and --to must be YYYY-MM-DD dates for this task")
        if first.isoformat() != start or last.isoformat() != end:
            parser.error("--from and --to must be YYYY-MM-DD dates for this task")
        if first > last:
            parser.error("--from must not be later than --to")
        return start, end
    parser.error("this task has no date- or month-based backlog range")


def main(argv: Sequence[str] | None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    settings = settings_or_none(args.config)
    if settings is None:
        return EXIT_INTEGRITY

    if args.subcommand == LIST_TASKS:
        print("\n".join(listing.tasks(settings)))
        return 0
    if args.subcommand == PLAN_SHARDS:
        planned = shards.plan(settings)
        print(shards.payload(planned) if args.json else "\n".join(listing.plan(planned)))
        return 0

    if not re.fullmatch(COMMIT_SHA_PATTERN, args.git_sha):
        parser.error(f"--git-sha takes the forty hex digits of a commit, not {args.git_sha!r}")
    names, shard = chosen(settings, args, parser)
    selected_range = period_range(settings, args, parser)
    # No commit listing: this package starts no process, so a task lists its
    # configured period paths as the checkout holds them.
    outcome = runner.run(
        names,
        settings=settings,
        repo_root=args.repo_root,
        run_id=args.run_id,
        attempt=args.attempt,
        shard=shard,
        git_sha=args.git_sha,
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        period_range=selected_range,
    )
    if outcome.record is not None:
        written = outcome.record.relative_to(args.repo_root).as_posix()
        print(f"shard {shard}: wrote {written} and pushed nothing")
    return outcome.exit_code
