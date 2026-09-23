"""Replace this checkout's run state with the one origin's tip carries.

`actions/checkout` restores the commit a run was TRIGGERED at. The run then
waits for a runner, and another run of the same workflow may be committing
under `state/` the whole time, so nothing bounds the distance between those two
moments. Run 35660521768 was created at 22:02 and its plan job started at 22:48,
five commits behind, and every one of those commits wrote `state/`.

For most of the pipeline a stale base costs nothing: a work shard writes a
segment named for one shard of one run, so a rebase applies both sides whole.
The catch-up fold is the exception, because it DERIVES a committed file from
other committed files. Against a stale store it folds segments the run ahead
already folded and deleted, and writes a day head that run has already written -
two derived versions of one file, which no rebase can settle and no merge driver
should. That is what cost run 35660521768 a whole day's digest.

Only the named path moves. The code this job runs stays pinned to the trigger
commit, so a run cannot change its own behaviour halfway through.

Run this before anything in the job writes under `state/`, or it discards what
that step wrote. A test executes it against a real repository.

It imports nothing from this project. A job reaches for this program to recover
a checkout, and a failed `pip install -e .` is one of the ways a checkout gets
into the state it exists to repair.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


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


def main(argv: list[str] | None = None) -> int:
    # One path, and argparse refuses none and refuses two with exit 2. A
    # workflow edit that drops the argument must stop the job, because the
    # `git rm -r` below would otherwise run over an empty pathspec and git
    # reads that as the whole repository.
    parser = argparse.ArgumentParser(description="Take one path from origin's tip.")
    parser.add_argument("path", help="the one path to take, as the workflow spells it")
    taken = parser.parse_args(argv).path

    _git("fetch", "origin", "main")
    tip = _git("rev-parse", "FETCH_HEAD").stdout.strip()

    # `git checkout <tip> -- <path>` restores what the tip carries and leaves
    # behind whatever it does not, and what it does not carry is precisely the
    # drained segment that starts the double fold. Emptying the path first is
    # what makes the result the tip's tree rather than a union of the tip's and
    # the trigger's.
    #
    # `-r` has no long spelling: `git rm --recursive` exits 129 with a usage
    # message.
    _git("rm", "-r", "--quiet", "--force", "--ignore-unmatch", "--", taken)
    _git("checkout", tip, "--", taken)

    listed = _git("diff", "--cached", "--name-only", "-z", "--", taken).stdout
    moved = len([name for name in listed.split("\0") if name])
    short = _git("rev-parse", "--short", tip).stdout.strip()
    print(
        f"{taken} taken from {short}; {moved} paths differed from the commit "
        "this run was triggered at"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
