#!/usr/bin/env bash
# Push the history the prune rewrote, unless `main` moved while it was rewriting.
#
# `.github/workflows/prune.yml` is the one job here that force-pushes `main`
# (CLAUDE.md section 8). A force push is a whole-ref operation. It replaces the
# branch with whatever this checkout holds, so a commit another run pushed while
# the squash was running is deleted, and nothing records that it existed.
#
# What held that off until now was a schedule with a gap in it: the prune wakes
# at 23:37, inside the one 266-minute window the serial digest schedule leaves
# idle. A gap is not a lock. GitHub queues scheduled runs by load, and no
# workflow here can hold a lock against another one.
#
# So the tip is read again immediately before the push and compared with the
# commit this job checked out. A tip that moved means another run pushed while
# the squash ran, and this refuses instead of forcing. Nothing is retried and
# nothing is rebased: the commits below this checkout have already been
# rewritten, so there is no base left to replay them onto.
#
# Refusing leaves the prune unstamped, and `backend/utilities/prune_due.py` calls
# an unstamped prune due. The cron wakes daily, so the prune runs again the next
# day - one wake, not one cadence.
#
# Usage: push-rewritten-history.sh
#
# Environment:
#   BASE_COMMIT  the commit this job checked out, read before the squash
#   SQUASHED     `true` when the squash rewrote history, so the push needs --force
set -euo pipefail

: "${BASE_COMMIT:?push-rewritten-history.sh needs BASE_COMMIT: the commit this job checked out}"
SQUASHED="${SQUASHED:-false}"

git fetch origin main
TIP=$(git rev-parse FETCH_HEAD)

if [ "$TIP" != "$BASE_COMMIT" ]; then
  echo "main moved while the prune was rewriting it, so nothing was pushed" >&2
  echo "  this job checked out $BASE_COMMIT" >&2
  echo "  origin/main is now $TIP" >&2
  echo "pushing would discard every commit between the two." >&2
  echo "the prune is unstamped, so it is due again at the next daily wake." >&2
  exit 1
fi

if [ "$SQUASHED" = "true" ]; then
  git push --force origin main
else
  git push origin main
fi
