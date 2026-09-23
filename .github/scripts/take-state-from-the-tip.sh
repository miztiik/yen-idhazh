#!/usr/bin/env bash
# Replace this checkout's run state with the one origin's tip carries.
#
# `actions/checkout` restores the commit a run was TRIGGERED at. The run then
# waits for a runner, and another run of the same workflow may be committing
# under `state/` the whole time, so nothing bounds the distance between those
# two moments. Run 35660521768 was created at 22:02 and its plan job started at
# 22:48, five commits behind, and every one of those commits wrote `state/`.
#
# For most of the pipeline a stale base costs nothing: a work shard writes a
# segment named for one shard of one run, so a rebase applies both sides whole.
# The catch-up fold is the exception, because it DERIVES a committed file from
# other committed files. Against a stale store it folds segments the run ahead
# already folded and deleted, and writes a day head that run has already
# written - two derived versions of one file, which no rebase can settle and no
# merge driver should. That is what cost run 35660521768 a whole day's digest.
#
# Only `state` moves. The code this job runs stays pinned to the trigger commit,
# so a run cannot change its own behaviour halfway through.
#
# Run this before anything in the job writes under `state/`, or it discards what
# that step wrote. A test executes it against a real repository.
#
# Usage: take-state-from-the-tip.sh <path>
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "take-state-from-the-tip.sh needs exactly one path to take" >&2
  exit 2
fi
TAKEN="$1"

git fetch origin main
TIP=$(git rev-parse FETCH_HEAD)

# `git checkout <tip> -- <path>` restores what the tip carries and leaves behind
# whatever it does not, and what it does not carry is precisely the drained
# segment that starts the double fold. Emptying the path first is what makes the
# result the tip's tree rather than a union of the tip's and the trigger's.
#
# `-r` has no long spelling here: `git rm --recursive` exits 129 with a usage
# message, which under `set -e` reads as an unexplained job failure.
git rm -r --quiet --force --ignore-unmatch -- "$TAKEN"
git checkout "$TIP" -- "$TAKEN"

moved=$(git diff --cached --name-only -- "$TAKEN" | wc -l)
echo "$TAKEN taken from $(git rev-parse --short "$TIP"); $moved paths differed from the commit this run was triggered at"
