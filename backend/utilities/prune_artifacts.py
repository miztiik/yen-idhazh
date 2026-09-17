"""Which members of a GitHub collection may this pass delete, and where does the next one start?

GitHub holds two collections no file in this repository represents: the
artifacts jobs upload and the workflow runs that produced them. Nothing in
`state/` or `frontend/public/` names either, so no retention rule this project
already has can reach them.

    python backend/utilities/prune_artifacts.py --collection workflow-artifacts
    python backend/utilities/prune_artifacts.py --collection workflow-runs --no-dry-run

**It reports and removes nothing until it is told twice.** `--dry-run` follows
`prune.dry_run` in `config/idhazh.json`, which ships true, and `--no-dry-run` is
the second word. The same default `idhazh telemetry prune` holds, for the same
reason: a deletion nobody asked for twice is a deletion nobody can undo.

**One pass is bounded.** It deletes at most the collection's
`max_deletes_per_run` and then stops, naming the member the next pass resumes
at. Run it again, or schedule it - each run is the same shape and the same cost
whatever the backlog is.

Every default is read from `config/`. Nothing tunable is spelled in this file
(Guardrail #6), and the work is in `idhazh.prune.one_at_a_time` and
`idhazh.prune.github_collections` - this routes arguments to them and prints
what came back.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from idhazh import config
from idhazh.contracts.knobs.prune import PrunableCollection
from idhazh.prune import github_collections, one_at_a_time, report

#: Names a member whose delete failed, so a scheduler can tell "there is more to
#: do" from "something is wrong". A ceiling reached is exit 0: it is the normal
#: end of a bounded pass.
EXIT_A_DELETE_FAILED = 1


def build_parser(defaults: dict[str, object]) -> argparse.ArgumentParser:
    """The flags, with every default handed in rather than spelled here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection",
        required=True,
        metavar="NAME",
        help=(
            "Which collection to delete from. One of "
            + ", ".join(sorted(item.value for item in PrunableCollection))
            + ". Never a path."
        ),
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get(github_collections.REPO_ENV, ""),
        metavar="OWNER/NAME",
        help=(
            f"Which repository's collection. Defaults to ${github_collections.REPO_ENV}, "
            "which Actions sets."
        ),
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=None,
        metavar="DAYS",
        help=(
            "Delete members created more than this many days ago. Defaults to the "
            "collection's prune.collections.<name>.retain_days."
        ),
    )
    parser.add_argument(
        "--since", default=None, metavar="YYYY-MM-DD", help="The oldest day to delete from."
    )
    parser.add_argument(
        "--until",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "The newest day to delete, inclusive. Name --since and --until together for "
            "an exact range, or --older-than-days for an age."
        ),
    )
    parser.add_argument(
        "--max-deletes",
        type=int,
        default=None,
        metavar="COUNT",
        help=(
            "How many this pass may delete before it stops and says where to resume. "
            "Defaults to the collection's prune.collections.<name>.max_deletes_per_run. "
            "0 surveys and deletes nothing."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=defaults["dry_run"],
        help=(
            "Report what a live pass would delete and delete nothing. Follows "
            "prune.dry_run, which ships true. Pass --no-dry-run to delete."
        ),
    )
    parser.add_argument(
        "--record",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write the pass as a collection-prune-row JSON payload to this path.",
    )
    parser.add_argument("--config-root", type=Path, default=config.DEFAULT_CONFIG_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Parsed twice on purpose: --config-root decides what the other defaults
    # are, so it has to be read before the parser that carries them is built.
    # The alternative is a default spelled in this file, which is the one thing
    # Guardrail #6 rules out.
    root = argparse.ArgumentParser(add_help=False)
    root.add_argument("--config-root", type=Path, default=config.DEFAULT_CONFIG_DIR)
    known, _ = root.parse_known_args(argv)
    settings = config.load(known.config_root).app.prune

    parser = build_parser({"dry_run": settings.dry_run})
    args = parser.parse_args(argv)

    try:
        named = PrunableCollection(args.collection)
    except ValueError:
        parser.error(
            one_at_a_time.refuse_by_name(
                args.collection,
                allowed=sorted(item.value for item in PrunableCollection),
                refused={},
            )
        )
    policy = settings.collections.get(named)
    if policy is None:
        parser.error(
            f"--collection {named.value} is a collection this repository has drawn no "
            "line for. Add it to prune.collections in config/idhazh.json"
        )

    today = datetime.now(tz=UTC).date().isoformat()
    try:
        window = _window(args, policy.retain_days, today)
        api = github_collections.RestApi(args.repo)
    except ValueError as refusal:
        parser.error(str(refusal))

    ceiling = policy.max_deletes_per_run if args.max_deletes is None else args.max_deletes
    failed = False
    try:
        outcome = one_at_a_time.take(
            github_collections.collection_named(named.value, api),
            window=window,
            ceiling=ceiling,
            dry_run=args.dry_run,
        )
    except one_at_a_time.PruneInterruptedError as stop:
        outcome, failed = stop.so_far, True

    for line in report.lines(outcome):
        print(line)
    if args.record is not None:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(
            report.row(outcome, date=today).to_json(), encoding="utf-8", newline="\n"
        )
    return EXIT_A_DELETE_FAILED if failed else 0


def _window(args: argparse.Namespace, retain_days: int, today: str) -> one_at_a_time.Window:
    """An age or a range, never both, and the age is what config already decided."""
    named_days = args.since is not None or args.until is not None
    if args.older_than_days is not None and named_days:
        raise ValueError(
            "--older-than-days names an age and --since/--until name a range. Pass one "
            "of the two, so the window has one meaning"
        )
    if named_days:
        return one_at_a_time.Window(since=args.since, until=args.until)
    return one_at_a_time.Window.older_than(
        today=today, days=args.older_than_days or retain_days
    )


if __name__ == "__main__":
    raise SystemExit(main())
