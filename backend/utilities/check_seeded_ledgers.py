"""Does this checkout carry the state ledgers a run stages before it has written one?

One ledger ships with the contract rather than appearing on the first run that
has something to put in it. `backend/utilities/commit_and_push.py` stages
every path a job owns in one `git add`, so a path that is not there fails that
call, stops the whole commit step, and takes every sibling ledger staged beside
it. A header-only file is what makes the path exist on day one.

This is a check on a clone, not a check on code. Nothing a commit can change
makes it fail: it goes red on a short checkout, a sparse checkout, or a
half-finished `git clone`, which is a condition of the working copy rather than
a defect in the repository. A test that asks it fails a pull request that did
not touch it, so `CLAUDE.md` section 13 puts the question here instead - pytest
collects `backend/tests` only, and never this directory.

What is deliberately not here: the day trees. A day tree cannot carry a header
of its own and does not need one, because the step that writes it stages `state`
whole and reaches a file the run created without ever naming it. The layout the
path helpers return is a code question and stays under test.

Usage, from the root of a checkout:

    python backend/utilities/check_seeded_ledgers.py

Exit code 1 when a ledger is missing or carries a header this checkout would not
write, so a shell can gate on it.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import ledger

REPO_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Ledger:
    """One seeded path, and the header a run of this checkout would append under."""

    name: str
    relpath: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    """What one ledger looked like, in words a person can act on."""

    ledger: Ledger
    fault: str | None

    @property
    def ok(self) -> bool:
        return self.fault is None


def seeded_ledgers() -> tuple[Ledger, ...]:
    """The ledgers whose header ships with the contract, read off the contract.

    None is left. The feed retirements were one until 2026-09-28, and the
    similarity holdout marks were the other until they moved onto the ledger
    door: a writer there creates its own file, and the step that commits it
    stages `state` whole, so no path has to exist on day one.
    """
    return ()


def audit(repo_root: Path) -> list[Finding]:
    """Each seeded ledger against the checkout, in declaration order."""
    findings: list[Finding] = []
    for seeded in seeded_ledgers():
        path = repo_root / seeded.relpath
        if not path.is_file():
            findings.append(Finding(seeded, "missing - git add would abort the commit step"))
            continue
        header = ledger.read_header(path)
        if header != seeded.columns:
            findings.append(
                Finding(
                    seeded,
                    f"header names {len(header)} columns where this checkout writes "
                    f"{len(seeded.columns)}",
                )
            )
            continue
        findings.append(Finding(seeded, None))
    return findings


def report(findings: list[Finding]) -> str:
    """One line per ledger, longest name padded so the verdicts line up."""
    width = max((len(finding.ledger.relpath) for finding in findings), default=0)
    lines = [
        f"{finding.ledger.relpath:<{width}}  {'ok' if finding.ok else finding.fault}"
        for finding in findings
    ]
    broken = [finding for finding in findings if not finding.ok]
    lines.append(
        f"{len(findings) - len(broken)} of {len(findings)} seeded ledgers are in this checkout"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="the checkout to audit; defaults to the one this file sits in",
    )
    args = parser.parse_args(argv)
    findings = audit(args.repo_root)
    print(report(findings))
    return 0 if all(finding.ok for finding in findings) else 1


if __name__ == "__main__":
    sys.exit(main())
