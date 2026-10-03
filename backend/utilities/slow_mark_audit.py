"""Does each test module's `slow` mark agree with a measured average test time?

Reads a pytest JUnit XML report (`--junitxml`), averages each test module's
durations, and compares that average against the threshold
`config/test-marks.json` declares - the same number `pyproject.toml`'s `slow`
marker describes in words. Prints every module where the mark and the
measurement disagree, in both directions, each with its measured average.

This never gates CI (`docs/how-to/run-the-gates.md`): the `slow` mark is an
optional local shortcut, and CI runs the whole suite regardless of it. This
tool is how a developer re-checks that shortcut against reality after a round
of speed work, instead of guessing from a noisy local run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final
from xml.etree import ElementTree

from utilities.mark_census import REPO_ROOT, module_marks

CONFIG_PATH: Final = REPO_ROOT / "config" / "test-marks.json"


def slow_threshold_seconds(config_path: Path = CONFIG_PATH) -> float:
    """The average-seconds-per-test bound `pyproject.toml`'s `slow` marker names."""
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return float(data["slow_threshold_seconds"])


def threshold_phrase(seconds: float) -> str:
    """How the marker text should name the bound, in English.

    `pyproject.toml`'s `slow` marker is read by a person, not by this tool, so
    its words name the bound in English rather than carrying a second copy of
    the number `config/test-marks.json` holds. This is what the two sides say
    when they agree; `backend/tests/test_marks.py` checks that they do.
    """
    if seconds == 1.0:
        return "a second"
    if seconds == int(seconds):
        return f"{int(seconds)} seconds"
    return f"{seconds:g} seconds"


def _dotted_module_path(path: Path, repo_root: Path) -> str:
    """A test module's dotted, extension-free path, relative to `repo_root`.

    This is the same spelling pytest's own JUnit XML writes into `classname`
    (`backend.tests.test_entity_gap`), because `rootdir` is `repo_root` and
    `classname` is dotted from the collected file's path.
    """
    return path.relative_to(repo_root).with_suffix("").as_posix().replace("/", ".")


def _module_for_classname(classname: str, dotted_to_stem: dict[str, str]) -> str | None:
    """The test module stem a JUnit `classname` belongs to, or `None`.

    A class-scoped test's `classname` carries `.ClassName` appended after its
    module's dotted path, so this matches the longest known module path that
    is either the whole classname or a dotted prefix of it. Every module stem
    under `backend/tests` is unique, so no two module paths can both match.
    """
    for dotted in sorted(dotted_to_stem, key=len, reverse=True):
        if classname == dotted or classname.startswith(dotted + "."):
            return dotted_to_stem[dotted]
    return None


def report_modules(junit_path: Path, *, repo_root: Path = REPO_ROOT) -> list[Path]:
    """Name source files from one report, without discovering neighbouring tests."""
    found: set[Path] = set()
    for testcase in ElementTree.parse(junit_path).getroot().iter("testcase"):
        parts = testcase.get("classname", "").split(".")
        positions = [index for index, part in enumerate(parts) if part.startswith("test_")]
        if not positions:
            continue
        # Class names follow the module. Only a test_* component names its file.
        end = positions[-1]
        if any(not part.isidentifier() for part in parts[: end + 1]):
            raise ValueError("JUnit classname contains an invalid module name")
        found.add(repo_root.joinpath(*parts[: end + 1]).with_suffix(".py"))
    if not found:
        raise ValueError("JUnit report names no test modules")
    return sorted(found)


def average_seconds_by_module(
    junit_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    known_modules: list[Path] | None = None,
) -> dict[str, float]:
    """Each represented test module's stem, mapped to its average test time.

    A skipped testcase reports close to no time and never ran its body, so it
    is excluded rather than pulling a module's average toward zero. A module
    this JUnit report never ran (because the run was scoped, or the module
    collects nothing) is simply absent from the result - this never guesses.

    `known_modules` defaults to source paths named in this JUnit report.
    """
    known = (
        known_modules
        if known_modules is not None
        else report_modules(junit_path, repo_root=repo_root)
    )
    dotted_to_stem = {_dotted_module_path(path, repo_root): path.stem for path in known}

    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    root = ElementTree.parse(junit_path).getroot()
    for testcase in root.iter("testcase"):
        if testcase.find("skipped") is not None:
            continue
        classname = testcase.get("classname", "")
        stem = _module_for_classname(classname, dotted_to_stem)
        if stem is None:
            continue
        totals[stem] += float(testcase.get("time", "0"))
        counts[stem] += 1

    return {stem: totals[stem] / counts[stem] for stem in counts}


def slow_marked_module_stems(named: list[Path]) -> frozenset[str]:
    """Only reported test modules whose source carries `slow`."""
    return frozenset(path.stem for path in named if "slow" in module_marks(path))


def disagreements(
    averages: dict[str, float], threshold: float, *, marked: frozenset[str]
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Modules the mark and the measurement disagree about, both ways.

    Returns `(should_be_marked, should_not_be_marked)`: modules measured over
    `threshold` that carry no `slow` mark, and modules marked `slow` that
    measured at or under it. Both lists are sorted by stem and only cover
    modules this report actually measured.

    `marked` is the set found in the report's named source files.
    """
    should_be_marked = sorted(
        (stem, avg) for stem, avg in averages.items() if avg > threshold and stem not in marked
    )
    should_not_be_marked = sorted(
        (stem, avg) for stem, avg in averages.items() if avg <= threshold and stem in marked
    )
    return should_be_marked, should_not_be_marked


def _format_section(title: str, rows: list[tuple[str, float]]) -> str:
    if not rows:
        return f"{title}: none"
    lines = [f"{title} ({len(rows)}):"]
    lines.extend(f"  {stem:<55s} {avg:.2f}s" for stem, avg in rows)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "junit_xml", type=Path, help="a pytest --junitxml report, from a run of the whole suite"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="where the threshold lives "
        f"(default: {CONFIG_PATH.relative_to(REPO_ROOT).as_posix()})",
    )
    args = parser.parse_args(argv)

    threshold = slow_threshold_seconds(args.config)
    averages = average_seconds_by_module(args.junit_xml)
    named = report_modules(args.junit_xml)
    unmeasured = {path.stem for path in named} - averages.keys()
    should_be_marked, should_not_be_marked = disagreements(
        averages, threshold, marked=slow_marked_module_stems(named)
    )

    print(f"threshold: {threshold:g}s (from {args.config.as_posix()})")
    print(_format_section("measured over the threshold but not marked slow", should_be_marked))
    print(
        _format_section("marked slow but measured at or under the threshold", should_not_be_marked)
    )
    if unmeasured:
        print(f"not represented in this report (not run, or collected no tests): {len(unmeasured)}")

    return 1 if should_be_marked or should_not_be_marked else 0


if __name__ == "__main__":
    sys.exit(main())
