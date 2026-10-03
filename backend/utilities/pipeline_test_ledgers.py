"""Which trees did a pipeline-test dispatch write, and may they be pushed?

Every runner of every test case writes its ledgers under `state/`, one tree per
test case. The job that pushes them is a separate job holding `contents: write`,
and artifacts are the only thing between them - so this module is what moves
the trees onto and off those artifacts, and what reads them before anything is
staged.

**The check is the control, not the job split.** Every byte here is downstream of
text this project did not write (Guardrail #11). Three shapes may be in the tree
and nothing else: `<root>/<ledger>/<YYYY>/<MM>/<DD>/<name>.csv`, read row by row
through the contract `ledger.segment_contract` names;
`<root>/traces/<YYYY>/<MM>/<DD>/<name>.jsonl`, one JSON object a line; and
`<root>/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.<format>`, one file the ledger door
wrote, read row by row through the contract `ledger.door_contract` names. `<root>`
has to be the trial root of a test case `config/pipeline-tests.json` declares, and
`<ledger>` a day tree in the first shape and a ledger the door files in the third,
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
import sqlite3
import sys
from datetime import date
from pathlib import Path

from idhazh import day_partition, day_shards, ledger
from idhazh.contracts.file_envelope import Format, Tier
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.observation_lookup import ObservationLookupNode, ObservationLookupRoot
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.evals.lookup_nodes import leaf_entries, node_path, read_node, read_page
from idhazh.evals.observation_batches import lookup_root
from idhazh.evals.observation_lookup import LOCK_NAME, ROOT_NAME, TRANSACTION_NAME

#: How deep a writer's file sits below a trial root: the ledger, a year, a month,
#: a day, and the filename. A ledger row and a trace share the grammar, so they
#: share the number.
DAY_SHARD_PARTS = 5
TRACES = "traces"



def _roots(config_root: Path) -> list[str]:
    """Every declared test case's trial root, in the order config declares them."""
    settings = PipelineTestsConfig.from_json(
        (config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    return [test_case.trial_state_dirname for test_case in settings.test_cases]


def _a_day_tree(name: str) -> LedgerName | None:
    """The day tree this directory name is, or `None` for anything else.

    `LedgerName` covers every ledger under `state/`, so reading a name back is no
    no longer the same question as "does a writer file a segment here". A test
    case run writes day trees, traces and the ledger door's raw files, so anything
    else under a trial root is reported rather than read.
    """
    try:
        which = LedgerName(name)
    except ValueError:
        return None
    return which if which in DAY_TREES else None


def _refuse_segment(path: Path, relative: str, which: LedgerName) -> list[str]:
    """Every row of one day shard, read through the contract its ledger declares."""
    parts = relative.split("/")
    if len(parts) != DAY_SHARD_PARTS or path.suffix != ".csv":
        return [f"{relative} is not <ledger>/<YYYY>/<MM>/<DD>/<name>.csv"]
    model = ledger.segment_contract(which)
    found: list[str] = []
    for lineno, row in day_shards.rows_of(path):
        try:
            day_shards.parsed(path, lineno, row, model)
        except (ValueError, TypeError) as refusal:
            found.append(f"{relative} row {lineno} does not read back as {which.value}: {refusal}")
    return found


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


def _lookup_files(root: Path) -> tuple[set[Path], list[str]]:
    """Validate the trial lookup's referenced files without accepting an unrelated tree."""
    directory = lookup_root(root)
    if not directory.exists():
        return set(), []
    root_path = directory / ROOT_NAME
    accepted = {root_path}
    try:
        manifest = ObservationLookupRoot.read(root_path)
        if manifest.key_fields != ledger.OBSERVATION_KEY:
            raise ValueError("the trial lookup uses another measurement key")

        def read(node: ObservationLookupNode, prefix: str) -> None:
            accepted.add(node_path(directory, node))
            if node.kind == "leaf":
                entries = leaf_entries(read_node(directory, node, manifest.settings.max_leaf_bytes))
                if any(not key.startswith(prefix) for key in entries):
                    raise ValueError("a trial lookup entry sits under another routing prefix")
            else:
                page = read_page(directory, node, prefix, manifest.settings.max_leaf_bytes)
                for digit, child in page.children.items():
                    read(child, prefix + digit)

        read(manifest.node, "")
    except (OSError, ValueError, sqlite3.DatabaseError) as error:
        return accepted, [
            f"{root_path.relative_to(root).as_posix()} is not a valid trial lookup: {error}"
        ]
    return accepted, []


def refusals(tree: Path, *, roots: frozenset[str]) -> list[str]:
    """Why this tree may not be pushed, one line each, or an empty list.

    A tree that never arrived holds nothing to refuse: a dispatch whose runners
    all failed before writing a ledger uploads nothing, and the download makes
    no folder for it.
    """
    if not tree.is_dir():
        return []
    found: list[str] = []
    lookup_files: set[Path] = set()
    for name in sorted(roots):
        accepted, invalid = _lookup_files(tree / name)
        lookup_files.update(accepted)
        found.extend(invalid)
    for path in sorted(entry for entry in tree.rglob("*") if entry.is_file()):
        relative = path.relative_to(tree).as_posix()
        parts = relative.split("/")
        if parts[0] not in roots:
            found.append(f"{relative} is filed under {parts[0]}, which no declared test case names")
        elif path in lookup_files:
            continue
        elif len(parts) < 3:
            found.append(f"{relative} sits directly under a trial root and names no ledger")
        elif parts[1] == TRACES:
            found += _refuse_trace(path, "/".join(parts[1:]))
        elif parts[1] == ledger.paths.RAW_DIRNAME:
            found += _refuse_raw_file(path, "/".join(parts[1:]), tree / parts[0])
        else:
            which = _a_day_tree(parts[1])
            if which is None:
                found.append(f"{relative} names {parts[1]}, which a test case run does not write")
            else:
                found += _refuse_segment(path, "/".join(parts[1:]), which)
    return found


def _local_lookup_files(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    if path != lookup_root(path.parent.parent):
        return set()
    return {
        name
        for name in names
        if name == TRANSACTION_NAME or name == LOCK_NAME or name.startswith(f"{LOCK_NAME}-")
    }


def gather(state: Path, tree: Path, *, roots: list[str]) -> list[str]:
    """Copy every declared test case's trial root into one directory, and say which arrived.

    One fixed destination rather than a glob over `state/`, so the artifact's
    root directory is the same whichever test cases produced a file.
    """
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    arrived = []
    for name in roots:
        source = state / name
        if not source.is_dir():
            continue
        shutil.copytree(source, tree / name, ignore=_local_lookup_files)
        arrived.append(name)
    return arrived


def place(tree: Path, state: Path, *, roots: list[str]) -> list[str]:
    """Copy the checked trees back under `state/`, and name every root to stage.

    Every declared root is created whether or not the dispatch wrote one. The
    commit script hands its arguments straight to `git add`, which aborts on a
    path the checkout does not hold - and an empty directory git cannot see is a
    staged path that costs nothing.
    """
    staged = []
    for name in roots:
        destination = state / name
        destination.mkdir(parents=True, exist_ok=True)
        source = tree / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        staged.append(destination.as_posix())
    return staged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("gather", "check", "place"))
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=Path(ledger.STATE_DIRNAME))
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)

    roots = _roots(args.config_root)

    if args.verb == "gather":
        for name in gather(args.state, args.tree, roots=roots):
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
