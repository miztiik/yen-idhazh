"""Which subcommand of `idhazh telemetry` runs, and what does it take?

Routing only. Every subcommand's body is in the module that owns its question
(CLAUDE.md section 1a): `inventory.py` reads what one day recorded, and
`republish.py` writes one day's projections again. Nothing in this file opens a
payload, derives a store path or counts a row.

    idhazh telemetry show    --date <d>   which instrument files that day has
    idhazh telemetry census  --date <d>   how that day's items ended
    idhazh telemetry rollup  --date <d>   how long that day's spans took
    idhazh telemetry publish --date <d>   write that day's projections again

Every subcommand takes one date and nothing wider, so none of them costs more as
the archive grows (Guardrail #12).

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
from idhazh.telemetry import inventory, republish

#: The word that reaches this router. `idhazh/cli.py` holds it in one place -
#: the verb it lists and the verb it hands over on are the same string.
VERB: Final = "telemetry"


@dataclass(frozen=True)
class Subcommand:
    """One question this router answers, and the one-line help that names it."""

    name: str
    summary: str


#: Every subcommand, in the order `--help` lists them. This tuple IS the surface:
#: the parser is built from it and the dispatch below is keyed on it, so a
#: subcommand added here gets its flags and a subcommand not here does not run.
SUBCOMMANDS: Final[tuple[Subcommand, ...]] = (
    Subcommand("publish", "Write one day's projections again from the day already on disk."),
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
