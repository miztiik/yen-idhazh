"""Which trees did a pipeline-test dispatch write, and may they be pushed?

Every runner of every test case writes its ledgers tier-first under `state/`:
a raw ledger file sits under `state/raw/pipeline-tests/<case>/`, beside every
other ledger's own `state/raw/<ledger>`, and a trace file stays at
`state/pipeline-tests/<case>/traces/` - exempt from that move because nesting
it under `state/traces` would collide with production's own 7-day retention
there (`ledger.paths.overlay_registry`). The job that pushes them is a
separate job holding `contents: write`, and artifacts are the only thing
between them - so this module is what moves the trees onto and off those
artifacts, and what reads them before anything is staged. The artifact's own
internal tree keeps one shape regardless of where each piece sits under
`state/`: `<case>/traces/<YYYY>/<MM>/<DD>/<name>.jsonl` and
`<case>/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.<format>`; `gather` and
`place` are what translate between that shape and the tier-first state layout.

**The check is the control, not the job split.** Every byte here is downstream of
text this project did not write (Guardrail #11). Two shapes may be in the tree
and nothing else: `<case>/traces/<YYYY>/<MM>/<DD>/<name>.jsonl`, one JSON object
a line, and `<case>/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.<format>`, one file
the ledger door wrote, read row by row through the contract
`ledger.door_contract` names. `<case>` has to be a test case
`config/pipeline-tests.json` declares, and `<ledger>` a ledger the door files,
so every directory name comes from committed config rather than from the artifact.
A raw file also has to sit under a real UTC day, at the one path `ledger.raw_path`
builds from the file's own envelope, so its name is rebuilt rather than trusted.
A test case run never compacts a ledger, so nothing under `compact/` is accepted.

**Gather and place are here rather than in the workflow** because both need the
same two facts the check needs - which test cases are declared, and what each
one's trial root is called - and a copy of either in a `run:` body is a second
spelling that drifts. They also fix the artifact's root directory, which a glob
would leave to whichever test cases happened to produce a file.

**Two streams, and the split is not tidiness.** `place`'s staged paths go to
stdout, where the step reads them with `mapfile`, and every line a person reads
goes to stderr - so a progress line can never be staged as a path.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from idhazh import day_partition, ledger
from idhazh.contracts.file_envelope import Format, Tier
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.pipeline_tests import TRIAL_STATE_PREFIX, PipelineTestsConfig
from utilities.named_inputs import day_files

#: How deep a writer's file sits below a trial root: the ledger, a year, a month,
#: a day, and the filename. A ledger row and a trace share the grammar, so they
#: share the number.
DAY_SHARD_PARTS = 5
TRACES = "traces"


def _roots(config_root: Path) -> list[str]:
    """Every declared test case's child slug, including disabled cases."""
    settings = PipelineTestsConfig.from_json(
        (config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    return [test_case.id for test_case in settings.test_cases]


def _refuse_raw_file(path: Path, relative: str, root: Path) -> list[str]:
    """One raw file the ledger door wrote: where it sits, what its envelope says, and every row.

    Where the file sits is checked, never trusted. The ledger has to be one the
    door files and `config/ledgers.json` lists as raw-and-compact, the three date
    folders a real UTC day, and the file's own envelope has to say raw, that
    ledger and that day. The path then has to be the one `ledger.raw_path` builds
    from the envelope's file id, and every row has to read back through the
    ledger's contract.
    """
    # Below `raw/`, a door file is as deep as a day shard: ledger, year, month, day, name.
    below = relative.split("/")[1:]
    if len(below) != DAY_SHARD_PARTS:
        return [
            f"{relative} is not "
            f"{ledger.paths.RAW_DIRNAME}/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.<format>"
        ]
    name, year, month, day, _ = below
    try:
        which = LedgerName(name)
        model = ledger.door_contract(which)
    except ValueError:
        return [f"{relative} names {name}, which is not a ledger the door files"]
    if ledger.entry(which).grain is not Grain.RAW_AND_COMPACT:
        return [
            f"{relative} names {name}, which config/ledgers.json does not list as "
            f"{Grain.RAW_AND_COMPACT.value}"
        ]
    if not (
        day_partition.is_segment(year, day_partition.YEAR_WIDTH)
        and day_partition.is_segment(month, day_partition.SEGMENT_WIDTH)
        and day_partition.is_segment(day, day_partition.SEGMENT_WIDTH)
    ):
        return [f"{relative} is not filed under <YYYY>/<MM>/<DD> folders"]
    covers = f"{year}-{month}-{day}"
    try:
        date.fromisoformat(covers)
    except ValueError:
        return [f"{relative} is filed under {covers}, which is not a real UTC day"]
    try:
        envelope = ledger.read_envelope(path)
    except ValueError as refusal:
        return [f"{relative} is not a ledger file this build can read: {refusal}"]
    if (envelope.tier, envelope.ledger, envelope.covers) != (Tier.RAW, which, covers):
        return [
            f"{relative} says it holds {envelope.tier.value} {envelope.ledger.value} "
            f"{envelope.covers}, and it sits in the raw {which.value} folder for {covers}"
        ]
    try:
        built = ledger.raw_path(
            root, which, covers, envelope.file_id, fmt=Format(path.suffix.removeprefix("."))
        )
    except ValueError as refusal:
        return [f"{relative} is not a name the ledger door gives a file: {refusal}"]
    if built != path:
        return [f"{relative} is not named {built.name}, the name the door gives this file"]
    try:
        ledger.load_stored([path], model=model)
    except ValueError as refusal:
        return [f"{relative} does not read back as {which.value}: {refusal}"]
    return []


def _refuse_trace(path: Path, relative: str) -> list[str]:
    """Every line of one trace file, each of which has to be one span object."""
    parts = relative.split("/")
    if len(parts) != DAY_SHARD_PARTS or path.suffix != ".jsonl":
        return [f"{relative} is not {TRACES}/<YYYY>/<MM>/<DD>/<name>.jsonl"]
    found: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            span = json.loads(line)
        except json.JSONDecodeError as refusal:
            found.append(f"{relative} line {lineno} is not JSON: {refusal}")
            continue
        if not isinstance(span, dict):
            found.append(f"{relative} line {lineno} is not a span object")
    return found


def refusals(tree: Path, *, roots: frozenset[str]) -> list[str]:
    """Why this tree may not be pushed, one line each, or an empty list.

    A tree that never arrived holds nothing to refuse: a dispatch whose runners
    all failed before writing a ledger uploads nothing, and the download makes
    no folder for it.
    """
    if not tree.is_dir():
        return []
    found: list[str] = []
    for path in sorted(entry for entry in tree.rglob("*") if entry.is_file()):
        relative = path.relative_to(tree).as_posix()
        parts = relative.split("/")
        if parts[0] not in roots:
            found.append(f"{relative} is filed under {parts[0]}, which no declared test case names")
        elif len(parts) < 3:
            found.append(f"{relative} sits directly under a trial root and names no ledger")
        elif parts[1] == TRACES:
            found += _refuse_trace(path, "/".join(parts[1:]))
        elif parts[1] == ledger.paths.RAW_DIRNAME:
            found += _refuse_raw_file(path, "/".join(parts[1:]), tree / parts[0])
        else:
            found.append(f"{relative} names {parts[1]}, which a test case run does not write")
    return found


def gather(state: Path, tree: Path, *, roots: list[str], days: Sequence[str]) -> list[str]:
    """Copy named UTC days from declared trial roots, and say which arrived.

    One fixed destination rather than a glob over `state/`, so the artifact's
    root directory is the same whichever test cases produced a file. Each
    copied directory holds one named day, never a trial root's accumulated days.
    A raw ledger's files are read tier-first, from
    `state/raw/pipeline-tests/<case>/<ledger>/`
    (`ledger.paths.overlay_registry`); a trace file stays exempt from that
    move and is read from `state/pipeline-tests/<case>/traces/`, where it
    already sat before the tier-first registry existed.
    """
    dated = day_files(Path(), days, filename="")
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    arrived = []
    for name in roots:
        copied = False
        trace_base = state / TRIAL_STATE_PREFIX / name / TRACES
        for day in dated:
            source = trace_base / day
            if source.is_dir():
                destination = tree / name / TRACES / day
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, destination)
                copied = True
        with ledger.use_registry(ledger.overlay_registry((TRIAL_STATE_PREFIX, name))):
            ledger_bases = {
                which: ledger.raw_root(state, which)
                for which in LedgerName
                if ledger.entry(which).grain is Grain.RAW_AND_COMPACT
            }
        for which, base in ledger_bases.items():
            for day in dated:
                source = base / day
                if source.is_dir():
                    destination = tree / name / ledger.paths.RAW_DIRNAME / which.value / day
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source, destination)
                    copied = True
        if copied:
            arrived.append(name)
    return arrived


def place(tree: Path, state: Path, *, roots: list[str]) -> list[str]:
    """Copy the checked trees back under `state/`, and name every root to stage.

    Every declared case's two roots - its traces root and its tier-first raw
    root - are created whether or not the dispatch wrote one. The commit
    script hands its arguments straight to `git add`, which aborts on a path
    the checkout does not hold - and an empty directory git cannot see is a
    staged path that costs nothing.
    """
    staged = []
    for name in roots:
        trace_destination = state / TRIAL_STATE_PREFIX / name
        trace_destination.mkdir(parents=True, exist_ok=True)
        trace_source = tree / name / TRACES
        if trace_source.is_dir():
            shutil.copytree(trace_source, trace_destination / TRACES, dirs_exist_ok=True)
        staged.append(trace_destination.as_posix())

        raw_destination = state / ledger.paths.RAW_DIRNAME / TRIAL_STATE_PREFIX / name
        raw_destination.mkdir(parents=True, exist_ok=True)
        raw_source = tree / name / ledger.paths.RAW_DIRNAME
        if raw_source.is_dir():
            shutil.copytree(raw_source, raw_destination, dirs_exist_ok=True)
        staged.append(raw_destination.as_posix())
    return staged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("gather", "check", "place"))
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=Path(ledger.STATE_DIRNAME))
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--day", action="append", default=[], help="UTC day to gather; repeatable.")
    args = parser.parse_args(argv)

    roots = _roots(args.config_root)

    if args.verb == "gather":
        if not args.day:
            parser.error("gather requires at least one --day YYYY-MM-DD")
        for name in gather(args.state, args.tree, roots=roots, days=args.day):
            print(f"gathered {name}", file=sys.stderr)
        if not any(args.tree.rglob("*")):
            print(
                "no test case left a ledger tree behind, so there is nothing to push",
                file=sys.stderr,
            )
        return 0

    if args.verb == "check":
        refused = refusals(args.tree, roots=frozenset(roots))
        for line in refused:
            print(f"refused: {line}", file=sys.stderr)
        if refused:
            return 1
        if not args.tree.is_dir():
            print("no ledger arrived, so there is nothing to check", file=sys.stderr)
            return 0
        for path in sorted(entry for entry in args.tree.rglob("*") if entry.is_file()):
            print(f"read {path.relative_to(args.tree).as_posix()}", file=sys.stderr)
        return 0

    for path in place(args.tree, args.state, roots=roots):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
