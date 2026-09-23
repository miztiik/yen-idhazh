"""Which pages a change touched, for `doc_load.py --changed`?

Prints the two `$GITHUB_OUTPUT` lines the docs job reads. It never fails a run:
this measures and gates nothing, so a range it cannot resolve answers "no pages"
rather than reddening a check. That is why every git call here is read for its
exit code rather than trusted - a checkout this program cannot ask about is a
reason to say nothing, not a reason to redden the step that says it.

It runs before the docs job installs anything, so it imports the standard
library and nothing else.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

#: What a push names as its base when there is no earlier tip - a branch's first
#: push, or a branch a force-push rewrote. No commit has this id, so a range
#: starting at it is not a range.
EMPTY_SHA = "0" * 40


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def changed_pages(base: str, head: str, repo_root: Path) -> list[str]:
    """Every `.md` file the range still holds, or nothing where there is no range.

    A force-push or a first push on a branch leaves a base this clone cannot
    resolve. Asking git for a range it does not hold is a failure rather than an
    answer, so the base is confirmed present before the range is asked for.
    """
    if not base or base == EMPTY_SHA or not head:
        return []
    if _git(repo_root, "cat-file", "-e", f"{base}^{{commit}}").returncode:
        return []
    listed = _git(repo_root, "diff", "--name-only", "--diff-filter=d", base, head, "--", "*.md")
    if listed.returncode:
        return []
    return [line for line in listed.stdout.splitlines() if line]


def output_lines(pages: Sequence[str]) -> list[str]:
    """The `KEY=value` lines the step appends to `$GITHUB_OUTPUT`.

    `paths` is absent rather than empty when there are none, because the step
    that reads it is skipped on `any` and an empty value would reach a command
    line as no argument at all.
    """
    if not pages:
        return ["any=false"]
    return ["any=true", "paths=" + " ".join(pages)]


def main() -> int:
    pages = changed_pages(os.environ.get("BASE", ""), os.environ.get("HEAD", ""), Path.cwd())
    for line in output_lines(pages):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
