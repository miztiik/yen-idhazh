#!/usr/bin/env bash
# Commit what a job produced and push it, rebasing when the push loses a race.
#
# Both commit steps in .github/workflows/digest.yml call this. They differ only
# in what they stage and in the three strings they pass, so the retry behaviour
# is written once and a test can execute it against a real repository.
#
# The runner checked out a commit that may be minutes old, and a scheduled job
# must not lose its work because someone pushed while it ran.
#
# Usage: commit-and-push.sh <path>...
#
# Environment:
#   COMMIT_MESSAGE          the commit subject
#   NOTHING_STAGED_MESSAGE  printed when the staged paths hold no change
#   PUSH_FAILED_MESSAGE     printed to stderr when every attempt is spent
set -euo pipefail

: "${COMMIT_MESSAGE:?commit-and-push.sh needs COMMIT_MESSAGE}"
: "${NOTHING_STAGED_MESSAGE:?commit-and-push.sh needs NOTHING_STAGED_MESSAGE}"
: "${PUSH_FAILED_MESSAGE:?commit-and-push.sh needs PUSH_FAILED_MESSAGE}"

if [ "$#" -eq 0 ]; then
  echo "commit-and-push.sh needs at least one path to stage" >&2
  exit 2
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add "$@"
if git diff --cached --quiet; then
  echo "$NOTHING_STAGED_MESSAGE"
  exit 0
fi
git commit -m "$COMMIT_MESSAGE"
# The work is in a commit by this point, so anything still in the working tree
# is runner noise - a line ending, a build artifact, a file some step left
# behind. A rebase refuses to start while any of it is there, and refusing costs
# the reader a day the run already finished (section 1a: degrade, do not fail).
# Discard the noise, and print it so the run log names whatever produced it.
#
# Untracked files are left alone: they cannot block a rebase, and a later step
# may still want them.
for attempt in 1 2 3; do
  if git push; then
    exit 0
  fi
  echo "push rejected, rebasing (attempt $attempt)"
  NOISE=$(git status --porcelain --untracked-files=no)
  if [ -n "$NOISE" ]; then
    echo "discarding working-tree noise before the rebase:"
    echo "$NOISE"
    git checkout -- .
  fi
  git pull --rebase origin main
done
echo "$PUSH_FAILED_MESSAGE" >&2
exit 1
