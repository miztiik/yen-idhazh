"""Does this checkout carry the state stores a run stages before it has written one?

Three ledgers ship with the contract rather than appearing on the first run that
has something to put in them. `commit-and-push.sh` runs `git add "$@"` under
`set -euo pipefail`, so a path that is not there aborts the whole commit step and
takes every sibling ledger staged in the same call with it. A header-only file
is what makes the path exist on day one.

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

    python backend/utilities/check_seeded_stores.py

Exit code 1 when a store is missing or carries a header this checkout would not
write, so a shell can gate on it.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair

REPO_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Store:
    """One seeded path, and the header a run of this checkout would append under."""

    name: str
    relpath: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    """What one store looked like, in words a person can act on."""

    store: Store
    fault: str | None

    @property
    def ok(self) -> bool:
        return self.fault is None


def seeded_stores() -> tuple[Store, ...]:
    """The stores whose header ships with the contract, read off the contract."""
    return (
        Store(
            name="runtime counters",
            relpath=ledger.runtime_counters_relpath(),
            columns=RuntimeCountersRow.csv_columns(),
        ),
        Store(
            name="feed retirements",
            relpath=ledger.feed_retirements_relpath(),
            columns=FeedRetirementRow.csv_columns(),
        ),
        Store(
            name="similarity holdout pairs",
            relpath=ledger.similarity_holdout_relpath(),
            columns=SimilarityHoldoutPair.csv_columns(),
        ),
    )


def audit(repo_root: Path) -> list[Finding]:
    """Each seeded store against the checkout, in declaration order."""
    findings: list[Finding] = []
    for store in seeded_stores():
        path = repo_root / store.relpath
        if not path.is_file():
            findings.append(Finding(store, "missing - git add would abort the commit step"))
            continue
        header = ledger.read_header(path)
        if header != store.columns:
            findings.append(
                Finding(
                    store,
                    f"header names {len(header)} columns where this checkout writes "
                    f"{len(store.columns)}",
                )
            )
            continue
        findings.append(Finding(store, None))
    return findings


def report(findings: list[Finding]) -> str:
    """One line per store, longest name padded so the verdicts line up."""
    width = max((len(finding.store.relpath) for finding in findings), default=0)
    lines = [
        f"{finding.store.relpath:<{width}}  {'ok' if finding.ok else finding.fault}"
        for finding in findings
    ]
    broken = [finding for finding in findings if not finding.ok]
    lines.append(
        f"{len(findings) - len(broken)} of {len(findings)} seeded stores are in this checkout"
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
