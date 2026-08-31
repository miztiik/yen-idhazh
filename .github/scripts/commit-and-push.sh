#!/usr/bin/env bash
# Commit what a job produced and push it, rebuilding when the push loses a race.
#
# Both commit steps in .github/workflows/digest.yml call this. They differ in
# what they stage, in the three strings they pass, and in whether they can
# rebuild what they commit, so the retry behaviour is written once and a test
# can execute it against a real repository.
#
# The runner checked out main's tip at trigger time and a daily run takes hours,
# so the base a job commits against is old by then. A scheduled job must not
# lose its work because someone pushed while it ran.
#
# There are two ways to lose that race and they need different answers.
#
# A job that only RECORDS what it saw rebases. Its ledgers are append-only and
# line-independent, so the union of both sides is the right answer, and
# `.gitattributes` says so.
#
# The union is the right answer for two runs writing different rows and the
# wrong one for two attempts writing the same row, and an appending stage cannot
# tell them apart: it filters against the file it checked out, and that checkout
# is pinned to the commit its run was triggered at. So a recording job whose
# ledgers declare a key names `DROP_REPEATED_ROWS_COMMAND`, which runs after the
# rebase - on the merged file, the only place both sides have ever been at once.
#
# A job that REBUILDS its output rebuilds. A digest day is derived from origin's
# tip plus this run's artifacts, so the answer to a stale base is a current
# base - not a text merge of two derived files, which produces a payload no
# producer would ever write. Such a job hands the derived paths back to the tip
# the push wants, then runs its producer again against that tip.
#
# Usage: commit-and-push.sh <path>...
#
# Environment:
#   COMMIT_MESSAGE          the commit subject
#   NOTHING_STAGED_MESSAGE  printed when the staged paths hold no change
#   PUSH_FAILED_MESSAGE     printed to stderr when every attempt is spent
#   REFRESH_PATHS           optional: the committed paths this job rebuilds
#   REGENERATE_COMMAND      optional: the producer that rebuilds them
#   DROP_RACED_ASSETS_COMMAND optional: deletes this attempt's rendered assets
#                           from the paths the tip already publishes
#   DROP_REPEATED_ROWS_COMMAND optional: settles the keyed ledgers after a merge
#
# The last four are word-split on spaces, so no path and no argument may carry
# one. The first two are given together or not at all.
set -euo pipefail

: "${COMMIT_MESSAGE:?commit-and-push.sh needs COMMIT_MESSAGE}"
: "${NOTHING_STAGED_MESSAGE:?commit-and-push.sh needs NOTHING_STAGED_MESSAGE}"
: "${PUSH_FAILED_MESSAGE:?commit-and-push.sh needs PUSH_FAILED_MESSAGE}"
REFRESH_PATHS="${REFRESH_PATHS:-}"
REGENERATE_COMMAND="${REGENERATE_COMMAND:-}"
DROP_RACED_ASSETS_COMMAND="${DROP_RACED_ASSETS_COMMAND:-}"
DROP_REPEATED_ROWS_COMMAND="${DROP_REPEATED_ROWS_COMMAND:-}"

if [ "$#" -eq 0 ]; then
  echo "commit-and-push.sh needs at least one path to stage" >&2
  exit 2
fi
# A refresh with no producer hands this job's work to origin and never rebuilds
# it. A producer with no refresh rebuilds on top of its own last attempt and
# reads that attempt as the day's history.
if [ -n "$REFRESH_PATHS" ] && [ -z "$REGENERATE_COMMAND" ]; then
  echo "REFRESH_PATHS needs REGENERATE_COMMAND: a refresh with no rebuild discards work" >&2
  exit 2
fi
if [ -z "$REFRESH_PATHS" ] && [ -n "$REGENERATE_COMMAND" ]; then
  echo "REGENERATE_COMMAND needs REFRESH_PATHS: a rebuild with no refresh reads its own last attempt" >&2
  exit 2
fi
# Only the amend below carries a drop into the commit the rebase replays, and
# only a rebuilding job amends. Elsewhere the file would be deleted and then
# left out of the push.
if [ -n "$DROP_RACED_ASSETS_COMMAND" ] && [ -z "$REGENERATE_COMMAND" ]; then
  echo "DROP_RACED_ASSETS_COMMAND needs REGENERATE_COMMAND: only a rebuilding job commits the drops" >&2
  exit 2
fi

REFRESH=()
REGENERATE=()
DROP_RACED=()
DROP_REPEATED=()
if [ -n "$REFRESH_PATHS" ]; then
  IFS=' ' read -r -a REFRESH <<< "$REFRESH_PATHS"
  IFS=' ' read -r -a REGENERATE <<< "$REGENERATE_COMMAND"
fi
if [ -n "$DROP_RACED_ASSETS_COMMAND" ]; then
  IFS=' ' read -r -a DROP_RACED <<< "$DROP_RACED_ASSETS_COMMAND"
fi
if [ -n "$DROP_REPEATED_ROWS_COMMAND" ]; then
  IFS=' ' read -r -a DROP_REPEATED <<< "$DROP_REPEATED_ROWS_COMMAND"
fi

# The work is in a commit by the time the loop runs, so anything still in the
# working tree is runner noise - a line ending, a build artifact, a file some
# step left behind. A rebase refuses to start while any of it is there, and
# refusing costs the reader a day the run already finished (section 1a: degrade,
# do not fail). Discard the noise, and print it so the run log names whatever
# produced it.
#
# Untracked files are left alone: they cannot block a rebase, and a later step
# may still want them.
discard_noise() {
  local noise
  noise=$(git status --porcelain --untracked-files=no) || return 1
  if [ -n "$noise" ]; then
    echo "discarding working-tree noise before the rebase:"
    echo "$noise"
    git checkout -- . || return 1
  fi
}

# Hand the rebuilt paths back to the tip the push wants, so the rebase finds no
# derived state to text-merge. What that tip carries is restored; what only this
# attempt created is removed, or the producer below reads its own last attempt
# as the day's history and counts itself twice.
#
# Every path is named. A directory that also holds this run's rendered assets is
# never refreshed whole: those assets came from another job's artifact and no
# producer here can make them again.
hand_back() {
  local tip="$1" ours path
  ours=$(git diff --name-only --diff-filter=A "$tip" HEAD -- "${REFRESH[@]}") || return 1
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    git rm --quiet --force -- "$path" || return 1
  done <<< "$ours"
  for path in "${REFRESH[@]}"; do
    # Absent upstream means this attempt introduced it, and the loop above has
    # already removed it.
    git rev-parse --verify --quiet "$tip:$path" > /dev/null || continue
    git checkout "$tip" -- "$path" || return 1
  done
}

# A rendered asset is filed under the item's own id, so a path both sides hold
# is one story rendered twice - never two stories under one name. Two runs of a
# day overlap, neither checkout sees what the other has not pushed, and git
# cannot rebase two adds of one path: run 32869125768 finished eight workers and
# a router and then threw the whole day away here.
#
# The tip's copy is published and a reader may already hold that address, and
# the rebuild keeps the tip's item over this run's in any case - so this run's
# file is the one nothing will reference. Deleting it is what lets the rebase
# apply, and the route payload still names a file that is really in the tree.
spare_the_published_assets() {
  local tip="$1"
  shift
  git ls-tree -r --name-only "$tip" -- "$@" | "${DROP_RACED[@]}" || return 1
}

git config user.name "yen-idhazh pipeline"
git config user.email "pipeline@yen-idhazh.invalid"
git add "$@"
if git diff --cached --quiet; then
  echo "$NOTHING_STAGED_MESSAGE"
  exit 0
fi
git commit -m "$COMMIT_MESSAGE"

# Every command below is guarded. An unguarded one ends the script where it
# stands under `bash -e`, which is how a loop that looks like it retries three
# times spent one attempt and left the checkout mid-rebase.
for attempt in 1 2 3; do
  if git push; then
    exit 0
  fi
  echo "push rejected, rebasing (attempt $attempt)"
  if ! discard_noise; then
    echo "could not clear the working tree before the rebase" >&2
    break
  fi
  if ! git fetch origin main; then
    echo "could not read origin/main" >&2
    break
  fi
  if [ "${#DROP_RACED[@]}" -gt 0 ]; then
    if ! spare_the_published_assets FETCH_HEAD "$@"; then
      echo "could not drop this attempt's copies of the assets origin publishes" >&2
      break
    fi
  fi
  if [ "${#REFRESH[@]}" -gt 0 ]; then
    if ! hand_back FETCH_HEAD; then
      echo "could not hand the rebuilt paths back to origin/main" >&2
      break
    fi
    # The drops above are worktree deletions, which no index knows about yet.
    if ! git add "$@"; then
      echo "could not stage the refreshed paths" >&2
      break
    fi
    if ! git commit --amend --no-edit --allow-empty; then
      echo "could not fold the refreshed paths into the commit" >&2
      break
    fi
  fi
  if ! git rebase FETCH_HEAD; then
    echo "the rebase did not apply cleanly" >&2
    git rebase --abort || echo "the rebase could not be aborted" >&2
    break
  fi
  # The merge has just happened, and this is the only moment both sides of it
  # exist in one file. A row this attempt appended because its checkout could
  # not see the tip's copy is now sitting next to that copy, so it goes here or
  # it never goes at all.
  if [ "${#DROP_REPEATED[@]}" -gt 0 ]; then
    if ! "${DROP_REPEATED[@]}"; then
      echo "could not settle the ledgers after the merge" >&2
      break
    fi
    if ! git add "$@"; then
      echo "could not stage the settled ledgers" >&2
      break
    fi
    if ! git commit --amend --no-edit --allow-empty; then
      echo "could not fold the settled ledgers into the commit" >&2
      break
    fi
  fi
  [ "${#REFRESH[@]}" -gt 0 ] || continue
  # Keep the content, drop the commit: the producer is about to rewrite most of
  # it, and one run leaves one commit however many attempts it took.
  if ! git reset --soft FETCH_HEAD; then
    echo "could not reopen the commit for the rebuild" >&2
    break
  fi
  echo "rebuilding the day against origin/main"
  if ! "${REGENERATE[@]}"; then
    echo "the rebuild failed against origin/main" >&2
    break
  fi
  if ! git add "$@"; then
    echo "could not stage the rebuilt paths" >&2
    break
  fi
  if git diff --cached --quiet; then
    # origin already carries everything this run made.
    echo "$NOTHING_STAGED_MESSAGE"
    exit 0
  fi
  if ! git commit -m "$COMMIT_MESSAGE"; then
    echo "could not commit the rebuild" >&2
    break
  fi
done
echo "$PUSH_FAILED_MESSAGE" >&2
exit 1
