"""Which subcommand of `idhazh telemetry` runs, and what does it take?

Routing only. Every subcommand's body is in the module that owns its question
(CLAUDE.md section 1a): `inventory.py` reads what one day recorded,
`republish.py` writes one day's projections again, and `prune.py` deletes one
store's days. Nothing in this file opens a payload, derives a store path or
counts a row.

    idhazh telemetry show    --date <d>   which instrument files that day has
    idhazh telemetry census  --date <d>   how that day's items ended
    idhazh telemetry rollup  --date <d>   how long that day's spans took
    idhazh telemetry publish --date <d>   write that day's projections again
    idhazh telemetry prune   --target <s> --since <d> --until <d>
                                          delete one store's days in a range

Every subcommand is bounded by what it is handed - four of them by one date and
`prune` by the range it names - so none of them costs more as the archive grows
(Guardrail #12).

**A subcommand's own flags are declared by the module that owns it.** Four of
them take the same four arguments and nothing else, which is why those are
spelled once below; `prune` takes a store and a range as well, and those belong
beside the body that reads them rather than in the router that hands them over.

The roots arrive from the caller rather than being derived here. `idhazh/cli.py`
already resolves the committed state and digest trees for every other verb, and
a second derivation of either path would be a second answer to where they are
(Guardrail #6). A flag overrides both, which is what lets a test drive this
against a tree of its own.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import config
from idhazh.assemble import day_dir, utc_now
from idhazh.telemetry import inventory, prune, republish

#: The word that reaches this router. `idhazh/cli.py` holds it in one place -
#: the verb it lists and the verb it hands over on are the same string.
VERB: Final = "telemetry"


@dataclass(frozen=True)
class Subcommand:
    """One question this router answers, and the one-line help that names it.

    `arguments` is the hook for a subcommand that takes more than the four every
    one of them takes. It is supplied by the module that owns the body, so the
    flag and the code that reads it are declared in one file and this router
    stays a router.
    """

    name: str
    summary: str
    arguments: Callable[[argparse.ArgumentParser], None] | None = None


#: Every subcommand, in the order `--help` lists them. This tuple IS the surface:
#: the parser is built from it and the dispatch below is keyed on it, so a
#: subcommand added here gets its flags and a subcommand not here does not run.
#:
#: The two that write come first, because those are the two a person has to mean.
SUBCOMMANDS: Final[tuple[Subcommand, ...]] = (
    Subcommand("publish", "Write one day's projections again from the day already on disk."),
    Subcommand(
        "prune",
        "Delete one store's day files over a range of days. Reports and removes "
        "nothing without --no-dry-run.",
        prune.add_arguments,
    ),
    Subcommand("rollup", "Total one day's spans, by span name."),
    Subcommand("census", "Count how one day's items ended."),
    Subcommand("show", "List the instrument files one day has."),
)


def _parser() -> argparse.ArgumentParser:
    """One parser per subcommand, built from `SUBCOMMANDS` rather than by hand.

    Every subcommand takes the same four arguments because every one of them
    asks about one date in one pair of trees. Spelling them once means a
    subcommand cannot be added with a different idea of what `--date` means.
    """
    parser = argparse.ArgumentParser(prog=f"idhazh {VERB}", description=__doc__)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for subcommand in SUBCOMMANDS:
        child = subparsers.add_parser(subcommand.name, help=subcommand.summary)
        child.add_argument("--date", default=None, help="Defaults to today, UTC.")
        child.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
        child.add_argument(
            "--state-root",
            type=Path,
            default=None,
            help="The state tree to read. Defaults to the committed one.",
        )
        child.add_argument(
            "--digest-root",
            type=Path,
            default=None,
            help="The published digest tree. Defaults to the committed one.",
        )
        if subcommand.arguments is not None:
            subcommand.arguments(child)
    return parser


#: What each reading subcommand calls. `publish` is not here: it is the one that
#: writes, and it takes inputs no reader needs.
READERS: Final[dict[str, Callable[..., list[str]]]] = {
    "show": inventory.files,
    "census": inventory.outcomes,
    "rollup": inventory.spans,
}


def main(argv: Sequence[str] | None, *, state_root: Path, digest_root: Path) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    logging.basicConfig(
        level=settings.app.logging.level.value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    date = args.date or utc_now()[:10]
    try:
        date_type.fromisoformat(date)
    except ValueError:
        parser.error(f"--date takes a YYYY-MM-DD day, not {date!r}")
    state = args.state_root or state_root
    digest = args.digest_root or digest_root

    if args.subcommand == "prune":
        # Neither `--date` nor `--digest-root` reaches this one: it is told its
        # days by name and it reads no published tree. Both stay on the shared
        # four so that a subcommand cannot arrive with its own idea of what
        # `--date` means, which is the trade that spelling them once buys.
        #
        # The vocabulary and the range are the prune's own rules, so it refuses
        # and this reports the refusal the way argparse reports every other bad
        # argument: the message, the usage, and exit 2.
        try:
            outcome = prune.prune_range(
                state,
                target=args.target,
                since=args.since,
                until=args.until,
                dry_run=args.dry_run,
            )
        except ValueError as refusal:
            parser.error(str(refusal))
        for line in prune.report(outcome):
            print(line)
        return 0

    if args.subcommand == "publish":
        target = day_dir(digest, date)
        if not (target / "digest.json").exists():
            parser.error(
                f"{date} is not published in that tree, so there is nothing to publish "
                f"the instrument for: no digest.json under "
                f"{target.relative_to(digest).as_posix()}"
            )
        published = republish.republish_day(
            state_root=state,
            digest_root=digest,
            date=date,
            settings=settings,
            repo_root=config.REPO_ROOT,
        )
        print(f"{date}: {len(published.dispatched)} projections written")
        print("  " + ", ".join(published.dispatched))
        return 0

    for line in READERS[args.subcommand](state, date=date):
        print(line)
    return 0
