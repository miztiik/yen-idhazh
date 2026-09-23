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
# The loop is bounded by a wall clock rather than by three attempts, and prints
# what each attempt spent. See the six stamps below.
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
# When the rebase does conflict, who wrote a path decides it - never which side
# of the rebase the version came from. A writer's filename carries
# `<run_id>-<attempt>-<job>-<shard>`, so a conflicted name carrying this job's
# four values is this job's own work and what this job wrote is kept.
# Every other conflicted path stops the push and names itself: no retry makes
# another writer's file this job's, and taking the tip's copy instead would
# delete that writer's rows at exit 0. It should never fire, because two writers
# cannot name one file - so when it does, the run log says which path and which
# job.
#
# Usage: commit-and-push.sh <path>...
#
# Environment:
#   COMMIT_MESSAGE          the commit subject
#   NOTHING_STAGED_MESSAGE  printed when the staged paths hold no change
#   PUSH_FAILED_MESSAGE     printed to stderr when the deadline is spent
#   PUSH_DEADLINE_SECONDS   optional: how long to keep trying, default 300
#   SHARD                   optional: which shard of the job this is. It names
#                           the attempt line, and it is the last element of the
#                           identity a conflicted filename is matched against.
#                           A whole number, default 0. The filename spells it
#                           with two digits, so it is padded here.
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

# Bash 5, because every attempt below is timed against `EPOCHREALTIME` and the
# deadline is read from the same clock. Said here so a host without it names the
# reason rather than failing on an unset variable.
: "${EPOCHREALTIME:?commit-and-push.sh needs bash 5 or newer: it times its attempts with EPOCHREALTIME}"

: "${COMMIT_MESSAGE:?commit-and-push.sh needs COMMIT_MESSAGE}"
: "${NOTHING_STAGED_MESSAGE:?commit-and-push.sh needs NOTHING_STAGED_MESSAGE}"
: "${PUSH_FAILED_MESSAGE:?commit-and-push.sh needs PUSH_FAILED_MESSAGE}"
REFRESH_PATHS="${REFRESH_PATHS:-}"
REGENERATE_COMMAND="${REGENERATE_COMMAND:-}"
DROP_RACED_ASSETS_COMMAND="${DROP_RACED_ASSETS_COMMAND:-}"

# The value a caller that names none gets. Every caller that has a config reader
# on its runner passes `run.push_deadline_seconds` instead, so this covers the
# jobs whose runner has no Python: this script must not need one, because it is
# what commits when a producer has already finished or already failed.
PUSH_DEADLINE_SECONDS="${PUSH_DEADLINE_SECONDS:-300}"
case "$PUSH_DEADLINE_SECONDS" in
  '' | *[!0-9]* | 0)
    echo "PUSH_DEADLINE_SECONDS must be a whole number of seconds, 1 or more" >&2
    exit 2
    ;;
esac

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

# The identity this job's own files carry. `ledger.segment_name` names a
# writer's file `<run_id>-<attempt>-<job>-<shard>`, and this project's run id is
# itself `<date>-<execution>` - so a committed name reads
# `2026-09-22-35743751882-1-work-03.csv`. That leading date is why the match
# below is not anchored to the first character: the runner hands this script the
# execution number, and the date is the plan job's to choose. The execution
# number is allocated by GitHub and is eleven digits, so finding it with the
# attempt, the job and the shard behind it names one writer and no other.
#
# The shard is two digits in the filename and written plainly on the runner, so
# it is padded here rather than compared as it arrives.
SHARD_NUMBER="${SHARD:-0}"
case "$SHARD_NUMBER" in
  '' | *[!0-9]*)
    echo "SHARD must be a whole number of shards, 0 or more" >&2
    exit 2
    ;;
esac
printf -v SHARD_PADDED '%02d' "$SHARD_NUMBER"
IDENTITY="${GITHUB_RUN_ID:-}-${GITHUB_RUN_ATTEMPT:-}-${GITHUB_JOB:-}-${SHARD_PADDED}"

# TRUE for a file this job is entitled to keep. One string comparison, and it
# reads no state. Off a runner there is no execution number, and a checkout that
# is not a job owns nothing - so that case answers no before the match runs,
# which an unanchored pattern would otherwise let through.
mine() {
  [ -n "${GITHUB_RUN_ID:-}" ] || return 1
  case "${1##*/}" in
    *"$IDENTITY"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Which version of a path survives, said as who wrote it rather than as which
# side of the graph it came from. Git's own names for the two sides invert
# between a rebase and a merge - under a rebase `--theirs` is the commit being
# replayed, which is this job's own work - so a design that reasons in them is a
# design nobody can check. That word is spelled here and nowhere else.
keep_what_this_job_wrote() {
  git checkout --theirs -- "$1" || return 1
  git add -- "$1" || return 1
}

# The tip's version, named by the tip rather than by a side: this one runs
# before the rebase starts, so there is no side to name yet.
keep_what_origin_has() {
  git checkout "$1" -- "$2" || return 1
}

# Settle every conflicted path this job wrote, and stop the push on every other
# one.
#
# A conflicted filename that carries this job's identity is this job's own work,
# so what this job wrote is kept. Every other conflicted path stops the push and
# names itself: no retry makes another writer's file this job's, and taking the
# tip's copy instead would delete that writer's rows at exit 0. A path this job
# rebuilds cannot reach here - it was handed back to the tip before the rebase -
# so one that does is a gap in the refresh list, and the same refusal names it.
#
# A path the tip has deleted is left unmerged on purpose. Git exits 0 and
# changes nothing when the side it is asked for is the deleted one, and staging
# the file instead would settle a deletion this job never made: retention and
# the closed-day fold are what remove a file named for a job. So the index is
# read again at the end, and a path still unmerged there stops the push rather
# than reaching `git rebase --continue`.
#
# One identity is printed, never two. A file named for this job that the tip has
# deleted was deleted by retention or by a person rather than by another run, so
# a second identity field would always be empty.
resolve_what_this_job_owns() {
  local tip="$1" conflicted unsettled path
  conflicted=$(git diff --name-only --diff-filter=U) || return 1
  if [ -z "$conflicted" ]; then
    echo "the rebase stopped with no conflicted path to settle" >&2
    return 1
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if ! mine "$path"; then
      echo "a conflicted path this job did not write stops the push:" >&2
      echo "  path: $path" >&2
      echo "  this job: $IDENTITY" >&2
      return 1
    fi
    # Absent upstream means the tip deleted it, which the index read below
    # refuses. Leaving it here is what makes that read find it.
    git rev-parse --verify --quiet "$tip:$path" > /dev/null || continue
    keep_what_this_job_wrote "$path" || return 1
    echo "keeping what this job wrote at $path"
  done <<< "$conflicted"
  unsettled=$(git diff --name-only --diff-filter=U) || return 1
  [ -n "$unsettled" ] || return 0
  echo "the tip has deleted a file this job wrote, so the push stops:" >&2
  while IFS= read -r path; do
    echo "  path: $path" >&2
  done <<< "$unsettled"
  echo "  this job: $IDENTITY" >&2
  return 1
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
  local tip="$1" introduced_here path
  introduced_here=$(git diff --name-only --diff-filter=A "$tip" HEAD -- "${REFRESH[@]}") || return 1
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    git rm --quiet --force -- "$path" || return 1
  done <<< "$introduced_here"
  for path in "${REFRESH[@]}"; do
    # Absent upstream means this attempt introduced it, and the loop above has
    # already removed it.
    git rev-parse --verify --quiet "$tip:$path" > /dev/null || continue
    keep_what_origin_has "$tip" "$path" || return 1
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

# What one attempt cost, split six ways, printed once per attempt. A single
# figure cannot tell a slow rebuild from a slow push, and which of the two the
# deadline is being spent on is the whole reason to collect this.
#
# Attempt 1 has no window in the retry sense. Nothing fetches before the first
# push, so its exposure is the whole job - checkout to push, two to three hours -
# which is not a retry parameter, and its zeros are the truth about it. What
# measures attempt 1 is the share of runs whose first push lands.
#
# The step summary is where an operator reads it without opening a log, and it is
# absent when a test drives this script, so the write is skipped rather than
# refused (section 1a: degrade, do not fail).
say_what_this_attempt_spent() {
  local line
  line="push attempt=$attempt job=${GITHUB_JOB:-local} shard=${SHARD:-none} outcome=$1"
  line="$line window_ms=$window_ms fetch_ms=$fetch_ms handback_ms=$handback_ms"
  line="$line rebase_ms=$rebase_ms rebuild_ms=$rebuild_ms push_ms=$push_ms"
  echo "$line"
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] || return 0
  echo "$line" >> "$GITHUB_STEP_SUMMARY"
}

# Wait before the next attempt, so that every loser of one race does not refetch
# in lockstep with the others. `min(2^(k-1), 8)` seconds for k failures so far,
# drawn against U(0.5, 1.5): the spread widens with the backoff, so collisions
# fall as more runs contend. The sleeps run 1, 2, 4, 8, 8, 8.
back_off() {
  local step jittered seconds millis
  step=$(( $1 > 4 ? 8 : 1 << ($1 - 1) ))
  jittered=$(( step * (500 + RANDOM % 1001) ))
  seconds=$(( jittered / 1000 ))
  millis=$(( jittered % 1000 ))
  printf 'waiting %d.%03ds before attempt %d\n' "$seconds" "$millis" "$(( attempt + 1 ))"
  sleep "$seconds.$(printf '%03d' "$millis")"
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

# The loop is bounded by a clock rather than by a count. A fixed number of
# attempts is spent at once however high it is set, once several runs commit
# together; an optimistic rebase-and-push converges in expectation at any commit
# rate, and a counter does not. Three attempts were what the loop allowed and
# what every failure message claimed to have spent.
#
# Microseconds, read from bash's own clock rather than from `date`, so timing an
# attempt costs no process and cannot disagree with the deadline. `10#` because
# a reading taken in the first tenth of a second carries a leading zero, and
# bash reads a leading zero as octal.
#
# Every command below is guarded. An unguarded one ends the script where it
# stands under `bash -e`, which is how a loop that looked like it retried three
# times spent one attempt and left the checkout mid-rebase.
deadline_us=$(( 10#${EPOCHREALTIME//[.,]/} + PUSH_DEADLINE_SECONDS * 1000000 ))
attempt=0
failures=0
window_opened_us=0
window_ms=0
fetch_ms=0
handback_ms=0
rebase_ms=0
rebuild_ms=0
push_ms=0
step_started_us=0
while :; do
  attempt=$(( attempt + 1 ))
  step_started_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
  if git push; then
    push_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
    window_ms=$(( window_opened_us == 0 ? 0 : (10#${EPOCHREALTIME//[.,]/} - window_opened_us) / 1000 ))
    say_what_this_attempt_spent landed || echo "could not record what this attempt spent" >&2
    report_rebased || echo "could not say whether the push rebased" >&2
    exit 0
  fi
  push_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
  window_ms=$(( window_opened_us == 0 ? 0 : (10#${EPOCHREALTIME//[.,]/} - window_opened_us) / 1000 ))
  say_what_this_attempt_spent rejected || echo "could not record what this attempt spent" >&2
  echo "push rejected, rebasing (attempt $attempt)"
  # Set before the rebase rather than after it. Every path out of here has
  # either rewritten the checkout or is about to, and a later step that skipped
  # its rebuild on a maybe is the failure this output exists to stop.
  REBASED=true
  failures=$(( failures + 1 ))
  if [ "$(( 10#${EPOCHREALTIME//[.,]/} ))" -ge "$deadline_us" ]; then
    break
  fi
  back_off "$failures" || echo "could not wait before the next attempt" >&2
  if ! discard_noise; then
    echo "could not clear the working tree before the rebase" >&2
    break
  fi
  # The next attempt's window opens here, at the fetch. What it measures is the
  # span another run has to push into before this one pushes again, so the
  # waiting above is deliberately outside it.
  window_opened_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
  fetch_ms=0
  handback_ms=0
  rebase_ms=0
  rebuild_ms=0
  step_started_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
  # A fetch that fails is a transient, and riding it out is what the deadline is
  # for. A broken token spends 300 s of a six-hour budget and says so six times.
  if git fetch origin main; then
    fetch_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
  else
    fetch_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
    echo "could not read origin/main, so this attempt waits and asks again" >&2
    continue
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
  step_started_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
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
  handback_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
  step_started_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
  # `merge.directoryRenames=false` on both spellings below. Git guesses that a
  # directory whose files all moved away was RENAMED to wherever they went, and
  # it applies that guess to a file the other side added into the emptied
  # directory. The closed-day fold replaces a day's writer files with one
  # settled file, so a sibling adding a new writer file into that day is read as
  # adding into a directory that no longer exists, and the rebase stops with
  # `CONFLICT (file location)` over a tree that was correct. Proved in a scratch
  # repository on 2026-09-22: the same replay conflicts with the guess on and
  # reports `Successfully rebased` with it off, losing nothing.
  if ! git -c merge.directoryRenames=false rebase FETCH_HEAD; then
    settled=false
    if resolve_what_this_job_owns FETCH_HEAD && GIT_EDITOR=true git -c merge.directoryRenames=false rebase --continue; then
      settled=true
    fi
    if [ "$settled" = false ]; then
      echo "the rebase did not apply cleanly" >&2
      git -c merge.directoryRenames=false rebase --abort || echo "the rebase could not be aborted" >&2
      break
    fi
  fi
  rebase_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
  [ "${#REFRESH[@]}" -gt 0 ] || continue
  # Keep the content, drop the commit: the producer is about to rewrite most of
  # it, and one run leaves one commit however many attempts it took.
  if ! git reset --soft FETCH_HEAD; then
    echo "could not reopen the commit for the rebuild" >&2
    break
  fi
  echo "rebuilding the day against origin/main"
  step_started_us=$(( 10#${EPOCHREALTIME//[.,]/} ))
  if ! "${REGENERATE[@]}"; then
    echo "the rebuild failed against origin/main" >&2
    break
  fi
  rebuild_ms=$(( (10#${EPOCHREALTIME//[.,]/} - step_started_us) / 1000 ))
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
# The attempt this run really spent, printed beside the caller's own sentence
# rather than folded into it. A conflicting rebase leaves the loop on the first
# attempt, so every recorded failure had spent one while the message said three,
# and that sentence sends the next reader to the retry count - which cannot help
# them.
report_rebased || echo "could not say whether the push rebased" >&2
echo "$PUSH_FAILED_MESSAGE" >&2
echo "the push was given up on attempt $attempt after ${PUSH_DEADLINE_SECONDS}s" >&2
exit 1
