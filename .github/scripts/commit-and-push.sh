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
# A job that only RECORDS what it saw rebases. Every writer owns the file it
# writes - a work shard's segment is named for that shard of that run - so two
# jobs racing this loop are never touching one path, and the rebase applies both
# sides whole.
#
# Until 2026-09-19 they did share files, `.gitattributes` gave those files a
# union merge driver, and this script ran a settling pass after the rebase to
# take the repeats back out. The union is gone with the shared writes: a second
# attempt that races its own first attempt now stops the push instead of
# stacking a row, which is the failure the settling pass could only repair after
# the fact.
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
#
# The last three are word-split on spaces, so no path and no argument may carry
# one. The first two are given together or not at all.
#
# Outputs, when the caller is a workflow step:
#   rebased  true when the push lost a race and this script rewrote the
#            checkout, false when what it pushed is what it was handed
set -euo pipefail

: "${COMMIT_MESSAGE:?commit-and-push.sh needs COMMIT_MESSAGE}"
: "${NOTHING_STAGED_MESSAGE:?commit-and-push.sh needs NOTHING_STAGED_MESSAGE}"
: "${PUSH_FAILED_MESSAGE:?commit-and-push.sh needs PUSH_FAILED_MESSAGE}"
REFRESH_PATHS="${REFRESH_PATHS:-}"
REGENERATE_COMMAND="${REGENERATE_COMMAND:-}"
DROP_RACED_ASSETS_COMMAND="${DROP_RACED_ASSETS_COMMAND:-}"

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
if [ -n "$REFRESH_PATHS" ]; then
  IFS=' ' read -r -a REFRESH <<< "$REFRESH_PATHS"
  IFS=' ' read -r -a REGENERATE <<< "$REGENERATE_COMMAND"
fi
if [ -n "$DROP_RACED_ASSETS_COMMAND" ]; then
  IFS=' ' read -r -a DROP_RACED <<< "$DROP_RACED_ASSETS_COMMAND"
fi

# The work is in a commit by the time the loop runs, so anything still in the
# working tree is runner noise - a line ending, a build artifact, a file some
# step left behind. A rebase refuses to start while any of it is there, and
# refusing costs the reader a day the run already finished (section 1a: degrade,
# do not fail). Discard the noise, and print it so the run log names whatever
# produced it.
#
# Most untracked files are left alone: nothing upstream is going to write over
# them, and a later step may still want them. The ones the tip DOES write over
# are cleared separately, below.
discard_noise() {
  local noise
  noise=$(git status --porcelain --untracked-files=no) || return 1
  if [ -n "$noise" ]; then
    echo "discarding working-tree noise before the rebase:"
    echo "$noise"
    git checkout -- . || return 1
  fi
}

# An untracked file CAN block a rebase, and until 2026-09-17 this script said it
# could not. A rebase detaches HEAD onto the tip first, and that checkout refuses
# when a file the incoming commits add is already sitting untracked in the
# working tree: `error: The following untracked working tree files would be
# overwritten by checkout`. The rebase never starts, so `git rebase --abort` has
# nothing to abort, and the loop spends its whole budget on the first attempt.
#
# Run `35152132574` is the record. A work shard wrote
# `state/host-fingerprint/2026/09/16.csv`, which its commit step did not stage
# yet, so the file stayed untracked. A sibling shard pushed the same path while
# this one was reading articles, and the rebase would not start: 303 rows over
# six ledgers were committed locally and thrown away with the runner. The staging
# list has since gained that path, which closes THAT collision and not the next
# one - the list is written by hand, and a new `state/` writer has arrived
# without it three times.
#
# So the tolerance is here, and it is narrow: only a file the tip is about to
# write is removed, and each one is named in the log. A file this job did not
# stage is a file this job is not pushing, so removing it costs nothing the push
# was going to carry, and the rebase then lands every path that WAS staged
# (section 1a: degrade, do not fail). Everything else untracked survives -
# `llama-server.log` and the memory samples are read by later steps.
clear_what_the_tip_will_write_over() {
  local tip="$1" untracked path blocked=()
  untracked=$(git ls-files --others --exclude-standard) || return 1
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    # Absent upstream means nothing is going to write over it.
    git rev-parse --verify --quiet "$tip:$path" > /dev/null || continue
    blocked+=("$path")
  done <<< "$untracked"
  [ "${#blocked[@]}" -gt 0 ] || return 0
  echo "removing untracked files origin/main carries, which would block the rebase:"
  printf '  %s\n' "${blocked[@]}"
  rm -f -- "${blocked[@]}" || return 1
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
# a visual planner and then threw the whole day away here.
#
# The tip's copy is published and a reader may already hold that address, and
# the rebuild keeps the tip's item over this run's in any case - so this run's
# file is the one nothing will reference. Deleting it is what lets the rebase
# apply, and the visual payload still names a file that is really in the tree.
spare_the_published_assets() {
  local tip="$1"
  shift
  git ls-tree -r --name-only "$tip" -- "$@" | "${DROP_RACED[@]}" || return 1
}

# Whether the tree this script pushed is still the tree it was handed. A push
# that lands first try leaves the checkout every earlier step read; a push that
# rebases replaces it with origin's, and a later step that measured the old one
# is measuring a tree nobody has.
#
# So the answer is written where a workflow can read it, and the step that
# rebuilds the site keys its `if:` off it. Both values are written explicitly:
# an output nobody wrote is the empty string, which is falsy and would look
# exactly like this script dying before it got here.
#
# `GITHUB_OUTPUT` is absent when a test drives this script in a temporary clone,
# and `set -u` would end the run on the expansion. The guard is what lets the
# same bytes run in both places.
#
# Actions gives every step its own output file, so the three other steps that
# call this script write into their own and reach nothing. Only a step with an
# `id` is addressable at all, and only the two in `assemble` have one.
#
# Every call is guarded, like every other command here. A runner whose output
# file will not take a line is broken, and by then the push has either happened
# or is past saving; the rebuild is skipped, which costs a red gate rather than
# the day (section 1a: degrade, do not fail).
REBASED=false
report_rebased() {
  [ -n "${GITHUB_OUTPUT:-}" ] || return 0
  echo "rebased=$REBASED" >> "$GITHUB_OUTPUT"
}

git config user.name "miztiik"
git config user.email "miztiik@users.noreply.github.com"
git add "$@"
if git diff --cached --quiet; then
  echo "$NOTHING_STAGED_MESSAGE"
  report_rebased || echo "could not say whether the push rebased" >&2
  exit 0
fi
git commit -m "$COMMIT_MESSAGE"

# Every command below is guarded. An unguarded one ends the script where it
# stands under `bash -e`, which is how a loop that looks like it retries three
# times spent one attempt and left the checkout mid-rebase.
for attempt in 1 2 3; do
  if git push; then
    report_rebased || echo "could not say whether the push rebased" >&2
    exit 0
  fi
  echo "push rejected, rebasing (attempt $attempt)"
  # Set before the rebase rather than after it. Every path out of here has
  # either rewritten the checkout or is about to, and a later step that skipped
  # its rebuild on a maybe is the failure this output exists to stop.
  REBASED=true
  if ! discard_noise; then
    echo "could not clear the working tree before the rebase" >&2
    break
  fi
  if ! git fetch origin main; then
    echo "could not read origin/main" >&2
    break
  fi
  # After the fetch, because the answer is a question about the tip.
  if ! clear_what_the_tip_will_write_over FETCH_HEAD; then
    echo "could not clear the untracked files origin/main would write over" >&2
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
    report_rebased || echo "could not say whether the push rebased" >&2
    exit 0
  fi
  if ! git commit -m "$COMMIT_MESSAGE"; then
    echo "could not commit the rebuild" >&2
    break
  fi
done
report_rebased || echo "could not say whether the push rebased" >&2
echo "$PUSH_FAILED_MESSAGE" >&2
exit 1
