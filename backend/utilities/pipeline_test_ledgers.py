"""Which trees did a pipeline-test dispatch write, and may they be pushed?

The cases run on one runner and write their ledgers under `state/`, one tree per
case. The job that pushes them is a second job holding `contents: write`, and an
artifact is the only thing between the two - so this module is what moves the
trees onto and off that artifact, and what reads them before anything is staged.

**The check is the control, not the job split.** Every byte here is downstream of
text this project did not write (Guardrail #11). Two shapes may be in the tree
and nothing else: `<root>/<ledger>/<YYYY>/<MM>/<DD>/<name>.csv`, read row by row
through the contract `ledger.segment_contract` names, and
`<root>/traces/<YYYY>/<MM>/<DD>/<name>.jsonl`, one JSON object a line. `<root>`
has to be the trial root of a case `config/pipeline-tests.json` declares and
`<ledger>` a `SegmentLedger` member, so every directory name comes from committed
config rather than from the artifact.

**Gather and place are here rather than in the workflow** because both need the
same two facts the check needs - which cases are declared, and what each one's
trial root is called - and a copy of either in a `run:` body is a second spelling
that drifts. They also fix the artifact's root directory, which a glob would
leave to whichever cases happened to produce a file.

**Two streams, and the split is not tidiness.** A line another program reads goes
to stdout: `gather`'s `ledgers=<true|false>`, which the step appends to
`$GITHUB_OUTPUT`, and `place`'s staged paths, which the step reads with
`mapfile`. Every line a person reads goes to stderr. `$GITHUB_OUTPUT` takes
`key=value` and nothing else, so a progress line on stdout is not untidy output -
it is a step that fails on a line it cannot parse, and it takes the push of a
whole dispatch's ledgers with it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from idhazh import day_shards, ledger
from idhazh.contracts.pipeline_tests import PipelineTestsConfig

#: How deep a writer's file sits below a trial root: the store, a year, a month,
#: a day, and the filename. A ledger row and a trace share the grammar, so they
#: share the number.
DAY_SHARD_PARTS = 5
TRACES = "traces"

#: What `gather` prints for the step output the commit job reads. A dispatch that
#: died before the first case wrote nothing, and a download of an artifact nobody
#: uploaded fails the step it is in.
FOUND_KEY = "ledgers"


def _roots(config_root: Path) -> list[str]:
    """Every declared case's trial root, in the order config declares them."""
    settings = PipelineTestsConfig.from_json(
        (config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    return [case.trial_state_dirname for case in settings.cases]


def _refuse_segment(path: Path, relative: str, which: ledger.SegmentLedger) -> list[str]:
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
    """Why this tree may not be pushed, one line each, or an empty list."""
    found: list[str] = []
    for path in sorted(entry for entry in tree.rglob("*") if entry.is_file()):
        relative = path.relative_to(tree).as_posix()
        parts = relative.split("/")
        if parts[0] not in roots:
            found.append(f"{relative} is filed under {parts[0]}, which no declared case names")
        elif len(parts) < 3:
            found.append(f"{relative} sits directly under a trial root and names no store")
        elif parts[1] == TRACES:
            found += _refuse_trace(path, "/".join(parts[1:]))
        else:
            try:
                which = ledger.SegmentLedger(parts[1])
            except ValueError:
                found.append(f"{relative} names {parts[1]}, which a case run does not write")
            else:
                found += _refuse_segment(path, "/".join(parts[1:]), which)
    return found


def gather(state: Path, tree: Path, *, roots: list[str]) -> list[str]:
    """Copy every declared case's trial root into one directory, and say which arrived.

    One fixed destination rather than a glob over `state/`, so the artifact's
    root directory is the same whether three cases produced a file or one.
    """
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    arrived = []
    for name in roots:
        source = state / name
        if not source.is_dir():
            continue
        shutil.copytree(source, tree / name)
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
        found = any(args.tree.rglob("*"))
        if not found:
            print("no case left a ledger tree behind, so there is nothing to push", file=sys.stderr)
        print(f"{FOUND_KEY}={'true' if found else 'false'}")
        return 0

    if args.verb == "check":
        refused = refusals(args.tree, roots=frozenset(roots))
        for line in refused:
            print(f"refused: {line}", file=sys.stderr)
        if refused:
            return 1
        for path in sorted(entry for entry in args.tree.rglob("*") if entry.is_file()):
            print(f"read {path.relative_to(args.tree).as_posix()}", file=sys.stderr)
        return 0

    for path in place(args.tree, args.state, roots=roots):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
