"""The committed archive has a small, named set of readers, and it may only shrink.

A test that walks every published day costs more every day the pipeline runs.
Measured on 2026-09-05 against 16 committed days and 6,539 stories, on an Intel
Core i7-1265U: reading and parsing the whole tree takes **0.15 s**, and calling
the function under test on every story takes a further **0.02 s**. The two specs
that assert once per story took **270 s** and **93 s** in the same run. Almost
none of that is the archive; it is the assertion machinery, run tens of
thousands of times to re-check a handful of cases.

It also does not saturate. Those 6,539 stories carry six distinct combinations
of `time_source` and printed form, so story 6,539 exercises exactly what story
12 did - while the corpus grows by about 400 stories a day and the published
tree is bounded only by `retention.site_budget_mb` and the 1 GiB Pages cap
(Rule #2). The cost compounds; the coverage does not.

So the rule is about the DEPENDENCY, not about the loop: a test may not read the
committed archive at all. A bounded fixture is the right instrument for a
per-item rule - the canary day under `backend/var/canary/` is one, and it can
carry a case the archive has never produced. The archive is checked by the
producer instead, once per item at write time, by `idhazh validate-days` and by
the contract models; re-checking a frozen day on every later run buys nothing.

**Two rules decide what happens to a reader when it is migrated** (owner ruling,
2026-09-06):

1. **A test checks code functionality, not data hygiene.** A check that reads
   committed data to ask whether the data is well-formed is not a test. It has
   three legal fates and no fourth: delete it where a fixture-driven test
   already covers the same rule; move it into the producer that writes the data,
   the way the one-picture-one-story rule moved into `idhazh validate-days`; or
   make it an operator surface under `backend/utilities/`, which pytest does not
   run.
2. **Drive it with a built parameter, never a loop over what the archive
   happens to hold.** The awkward shape is a thing to build. `console-failures`
   used to read every published telemetry shard because the real ledger has
   eleven causes and a 529-to-1 spread; it now builds exactly that, plus a
   source sitting on the cap, which the archive has never produced.

**A walk over the archive tends to carry a fuse, and that is the second reason
to remove one.** Six of the tests migrated in this work counted how many
committed entries still LACK a migrated field and asserted the count was not
zero - so each one goes red on the day the last unmigrated payload ages out of
retention, which is a date on the calendar rather than a change anybody made.
`docs/reference/agent-notes.md` records the day that fired and took every open
pull request red at once.

`ARCHIVE_READERS` below is the migration list, not a permission. Every entry is
a test that still reads the tree and has yet to move to a fixture. It is
expected to fall to one auditor per language. Nothing may be added to it: a new
name here is the defect this module exists to refuse.
"""

from __future__ import annotations

import re
from typing import Final

from conftest import REPO_ROOT, read_text

#: Where a test would touch the published tree or the committed ledgers.
#: `backend/var/canary/` is deliberately absent - the canary is a fixture, it is
#: bounded, and it is what a per-item rule should be driven from.
ARCHIVE_IN_PYTHON: Final = re.compile(
    r"""REPO_ROOT\s*/\s*"state"|REPO_ROOT\s*/\s*STATE_DIRNAME"""
    r"""|REPO_ROOT\s*/\s*"frontend"\s*/\s*"public"|digest_paths\(\s*REPO_ROOT|\bSTATE_DIR\b"""
)
ARCHIVE_IN_TYPESCRIPT: Final = re.compile(r"""['"]public['"]\s*,\s*['"](?:digest|telemetry)['"]""")

#: A name that only borrows the constant from `conftest` has not read anything.
AN_IMPORT: Final = re.compile(r"^\s*(?:from|import)\s")

#: Every test that still reads the committed archive, and therefore still gets
#: slower every day the pipeline publishes. **This list may only shrink.**
#:
#: Two of them are deliberate and stay: `whole-day.spec.ts` and
#: `reading-page.spec.ts` ask what a reading page does at a real day's scale,
#: which is a question the eight-story canary cannot answer, and both are held
#: to one day rather than to the whole tree. Every other entry is scheduled to
#: move to a fixture, with the per-item rules driven from the canary and one
#: aggregate auditor left per language.
ARCHIVE_READERS: Final = frozenset(
    {
        "backend/tests/test_contracts.py",
        "backend/tests/test_labels.py",
        "backend/tests/test_leading_stories.py",
        "backend/tests/test_ledger.py",
        "backend/tests/test_pipeline.py",
        "backend/tests/test_publish_telemetry.py",
        "backend/tests/test_search_index.py",
        "backend/tests/test_telemetry.py",
        "backend/tests/test_workflows.py",

        "frontend/tests/malformed-day.spec.ts",
        "frontend/tests/reading-page.spec.ts",
        "frontend/tests/staged-day.spec.ts",
        "frontend/tests/whole-day.spec.ts",
    }
)


def _reads_archive(source: str, pattern: re.Pattern[str]) -> str | None:
    """The first line that reaches for the archive, or None because none does."""
    for line in source.splitlines():
        if AN_IMPORT.match(line):
            continue
        if pattern.search(line):
            return line.strip()
    return None


def archive_readers() -> dict[str, str]:
    """Every test file that reads the committed archive, and the line that does.

    Keyed by repository-relative POSIX path (`CLAUDE.md` section 2).
    """
    found: dict[str, str] = {}
    for directory, glob, pattern in (
        (REPO_ROOT / "backend" / "tests", "test_*.py", ARCHIVE_IN_PYTHON),
        (REPO_ROOT / "frontend" / "tests", "**/*.spec.ts", ARCHIVE_IN_TYPESCRIPT),
    ):
        for path in sorted(directory.glob(glob)):
            line = _reads_archive(read_text(path), pattern)
            if line is not None:
                found[path.relative_to(REPO_ROOT).as_posix()] = line
    return found


def test_a_test_that_is_not_named_here_may_not_read_the_committed_archive() -> None:
    """A new reader is a test whose cost grows with the corpus. Use a fixture."""
    found = archive_readers()
    assert found, "nothing reads the archive, so the patterns above stopped matching"

    appeared = sorted(set(found) - ARCHIVE_READERS)
    named = "\n".join(f"  {path}: {found[path]}" for path in appeared)
    assert not appeared, (
        "these tests read the committed archive, so they get slower every day the "
        f"pipeline publishes:\n{named}\n"
        "Drive the rule from a fixture instead - the canary day under "
        "backend/var/canary/ is bounded and can carry a case the archive has never "
        "produced. If the question really is about the whole tree, ask it once and "
        "assert on the total rather than once per story."
    )


def test_a_name_here_that_no_longer_reads_the_archive_leaves_the_list() -> None:
    """The list is a migration, so a finished migration has to show up in it."""
    vanished = sorted(ARCHIVE_READERS - set(archive_readers()))
    assert not vanished, (
        f"ARCHIVE_READERS names {vanished}, which no longer reads the committed "
        "archive. Drop the entry: the list is the work left to do, and an entry "
        "that is done hides how much of it remains."
    )
