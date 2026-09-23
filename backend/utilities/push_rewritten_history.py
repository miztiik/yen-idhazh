"""Push the history the prune rewrote, unless `main` moved while it was rewriting.

`.github/workflows/prune.yml` is the one job here that force-pushes `main`
(CLAUDE.md section 8). A forcing push is a whole-ref operation. It replaces the
branch with whatever this checkout holds, so a commit another run pushed while
the squash was running is deleted, and nothing records that it existed.

What held that off until now was a schedule with a gap in it: the prune wakes at
23:37, inside the one 266-minute window the serial digest schedule leaves idle.
A gap is not a lock. GitHub queues scheduled runs by load, and no workflow here
can hold a lock against another one.

So the tip is read again immediately before the push and compared with the
commit this job checked out. A tip that moved means another run pushed while the
squash ran, and this refuses instead of forcing. Nothing is retried and nothing
is rebased: the commits below this checkout have already been rewritten, so
there is no base left to replay them onto.

Refusing leaves the prune unstamped, and `backend/utilities/prune_due.py` calls
an unstamped prune due. The cron wakes daily, so the prune runs again the next
day - one wake, not one cadence.

It imports nothing from this project. This is the step that recovers a job whose
history was already rewritten, and a failed `pip install -e .` is one of the
ways that job needs recovering.

Environment:
  BASE_COMMIT  the commit this job checked out, read before the squash
  SQUASHED     `true` when the squash rewrote history, so the push must force
"""

from __future__ import annotations

import os
import subprocess
import sys

#: The commit the prune checked out, remembered before the squash rewrote it.
BASE_COMMIT_ENV = "BASE_COMMIT"

#: Whether the squash rewrote history. Only a rewrite earns a forcing push.
SQUASHED_ENV = "SQUASHED"

#: What the squash step writes into the job environment when it rewrote history.
SQUASHED = "true"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """One git call, or the end of the program carrying git's own exit code.

    The shell this replaced ran under `set -e`. Reading the exit code rather
    than the message keeps that behaviour whatever git prints.
    """
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if done.returncode:
        sys.stderr.write(done.stderr)
        raise SystemExit(done.returncode)
    return done


def main() -> int:
    base = os.environ.get(BASE_COMMIT_ENV, "")
    if not base:
        print(
            f"this needs {BASE_COMMIT_ENV}: the commit this job checked out",
            file=sys.stderr,
        )
        return 1

    _git("fetch", "origin", "main")
    tip = _git("rev-parse", "FETCH_HEAD").stdout.strip()

    if tip != base:
        for line in (
            "main moved while the prune was rewriting it, so nothing was pushed",
            f"  this job checked out {base}",
            f"  origin/main is now {tip}",
            "pushing would discard every commit between the two.",
            "the prune is unstamped, so it is due again at the next daily wake.",
        ):
            print(line, file=sys.stderr)
        return 1

    # Written as two whole command lines rather than one with a computed flag,
    # so the one forcing push in this repository is legible to a reader and to
    # the test that holds it to being the only one.
    #
    # Not captured either: this is the push whose output a person reads in the
    # step log when it fails.
    if os.environ.get(SQUASHED_ENV, "") == SQUASHED:
        return subprocess.run(
            ["git", "push", "--force", "origin", "main"], check=False
        ).returncode
    return subprocess.run(["git", "push", "origin", "main"], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
