# Why a losing push should rebuild rather than rebase

**Last Updated**: 2026-09-23

Ten jobs of one run push to one branch, so losing the push race is ordinary and
not a fault. [committing.md](committing.md) owns the loop those jobs run today.

This page owns one question that loop answers wrongly: **when a push is
rejected, the job replays its commit as a patch.** It should not. Replaying a
patch needs shared history and can ask a question nobody is there to answer.
Writing the files again on top of whatever the tip is now needs neither.

Written after run `35896533328` failed, and after reading the loop it failed in.

## The finding

### What failed

Run `35896533328`, job `assemble`, steps "Commit the day" and "Commit the folded
telemetry". Both failed the same way, nineteen seconds apart.

**222 conflict lines. 111 unique paths. Every one of them `CONFLICT (add/add)`.**

The list includes `CLAUDE.md`, `pyproject.toml`, `backend/idhazh/cli.py`,
`config/idhazh.json`, forty pages under `docs/`, seven workflow files and twenty
test files.

**The `assemble` job writes none of those.** Three telemetry projections were in
the list as well, but they were 3 of 111 and they conflicted for the same reason
`CLAUDE.md` did.

### Why every file conflicted at once

Git merges three versions of a path: the common ancestor, ours, theirs.
`CONFLICT (add/add)` is what it reports when **the common ancestor does not hold
the path at all**, so both sides look like they created it from nothing.

One path reported that way is a real collision between two writers. Every path
in the repository reported that way means something else entirely: **git found
no common ancestor.** The ancestor is not missing for `CLAUDE.md` in particular.
It is missing for everything, so every path that differed by one byte came back
as a conflict.

That single fact rules out a collision between writers. Two jobs racing for one
path cannot make `pyproject.toml` conflict.

### The cause

**All three `actions/checkout@v6` steps in `digest.yml` take the default depth.**
The default is `fetch-depth: 1`: one commit, no history. The clone knows the tip
it was handed and nothing before it. For contrast, `ci.yml` sets `fetch-depth: 0`
twice and `prune.yml` sets it on both its checkouts. `digest.yml` sets it nowhere.

The sequence, with real times from the run:

| Time | Event |
| --- | --- |
| 20:55:42 | `assemble` checks out. Shallow - one commit, no ancestors. |
| 20:56:01 | Pull request #1080 is squash-merged to `main` as `a9e80f584`. |
| 20:57:07 | `assemble` pushes. Rejected - the remote moved. |
| 20:57:22 | The loop fetches and rebases. No shared history exists. 111 conflicts. |

The tell is in the rebase output. It was replaying `b0f61fd8c`, whose message is
"Put the retry loop's guard check back, in the spelling the hazard now has".
That commit is in this repository but **is not an ancestor of `origin/main`**. It
was one of #1080's own commits, and the squash merge replaced every one of them
with a single new commit carrying a different identity.

So the runner held commits `main` no longer contained, fetched a `main` built
from a brand-new commit, and had one commit of history in which to find the
relationship between the two. At that depth there is no relationship to find.

**This is not a naming collision and not a two-writer collision.** It would have
happened with any file format, and with no data files at all.

### The guard behaved correctly

The loop printed `a conflicted path this job did not write stops the push:` and
exited 1. It did not force, it did not pick a side, it stopped and named itself.
The run failed loudly and the repository was left intact. A failed run is the
right outcome for the loop as written.

## The rationale

### The rebase already does no work

This is the finding that matters. Read what the loop does when the rebase
**succeeds**:

```sh
git -c merge.directoryRenames=false rebase FETCH_HEAD   # replay the commit
...
git reset --soft FETCH_HEAD    # throw the commit away
"${REGENERATE[@]}"             # run the producer again against origin/main
git add "$@" && git commit && git push
```

It replays the commit, then discards the replay on the next line and regenerates
the data against the new tip.

The steps *before* the rebase point the same way. `hand_back` restores origin's
copy of every refreshed path and deletes every path the attempt introduced.
`spare_the_published_assets` deletes this run's rendered assets that origin also
holds. `clear_what_the_tip_will_write_over` deletes untracked files the tip is
about to write. Then `git commit --amend` folds all of it in.

Those three functions have one purpose between them: **to leave the rebase
nothing to merge.** The loop empties the diff by hand so the replay cannot
conflict, replays the now-empty diff, and throws the result away.

The rebase is the single reason the loop needs a merge base, needs history,
needs `merge.directoryRenames=false`, needs a conflict settler that parses
filenames to decide who owns a path, and needs the ownership policy written
above it. Every one of those exists to contain a step that produces nothing.

### What the operation actually is

A job is not producing a patch. It is saying:

> these paths should hold these bytes, on top of whatever the tip is now.

That statement has no ancestor in it, so it needs none. It has no merge in it,
so it cannot conflict.

## The solution

### In plain English

**What happens today.** The push is rejected because somebody else changed the
repository while the job was working. The job responds by working out what it
changed - as a list of edits - and re-applying those edits on top of the other
person's version. Working out "what I changed" means comparing against the state
the job started from, so git needs the shared starting point. On a one-commit
clone there is no shared starting point, so git treats every file as newly
created on both sides and asks a person to settle 111 of them. No person is
there. The job fails.

**What it should do instead.** Take the other person's version of the whole
repository, write its own files over the top, and commit that. No list of edits
is worked out, so no starting point is needed, so no question can be asked. Every
path ends up as either exactly origin's bytes or exactly this job's bytes, which
is the only outcome that was ever wanted.

**The one thing to be careful about.** Taking origin's version of everything
replaces the folder the job just wrote its files into. So the job copies its own
files somewhere safe first, takes origin's version, and copies them back.

### Step by step

Today, on a rejected push:

1. Fetch `origin/main`.
2. Delete untracked files the tip is about to write.
3. Delete this run's rendered assets the tip also holds.
4. Restore origin's copy of every refreshed path, delete paths this attempt added.
5. Amend the commit to fold that in.
6. Rebase the commit onto the tip, with directory-rename detection off.
7. If it conflicts, parse each conflicted filename, decide whether this job wrote
   it, keep this job's side if so, stop the push if not.
8. Throw the commit away with `git reset --soft`.
9. Run the producer again against the new tip.
10. Stage, commit, push.

Proposed, on a rejected push:

1. Fetch `origin/main` at depth 1.
2. Copy this job's output files to a directory outside the worktree - or skip
   this when the job can regenerate them.
3. `git reset --hard FETCH_HEAD`. The worktree is now exactly origin's.
4. Put this job's files back: copy them in, or run the producer against the new
   tip where one exists.
5. Stage the named paths, commit, push.

Steps 2 to 7 of the current loop have no equivalent, because nothing they defend
against can happen.

### The controls that have to be relaxed

| id | Control | Where it is written | Why it exists | Why it does not bind here | What is needed |
| --- | --- | --- | --- | --- | --- |
| C1 | `git reset --hard` is on the avoid list | CLAUDE.md section 8 | It throws away work a person has not committed | A CI runner's checkout holds no human work. Everything in it was made by this job minutes earlier, and step 2 copies that aside first | A named exception on that line, scoped to the push loop, carrying a person's name (CLAUDE.md section 1) |
| C2 | `git checkout .` and broad `git restore .` are on the same list | CLAUDE.md section 8 | Same reason as C1 | Same reason as C1. The loop already runs `git checkout -- .` for exactly this purpose, so the exception describes what is there rather than adding something | Fold into the C1 exception |
| C3 | `git stash` is on the avoid list | CLAUDE.md section 8 | A stash that will not reapply fails the step it was meant to protect | Nothing here stashes. Step 2 is a file copy to a temp directory, deliberately not `git stash` - the same reason `--autostash` was already removed from this loop | No exception. Recorded so nobody reaches for `git stash` to do step 2 |
| C4 | The conflict-ownership policy: who wrote a path decides it, and a filename carries the identity that decides | `.github/scripts/commit-and-push.sh` header, and `committing.md` | It settled a conflicted path without a person | There are no conflicted paths, so it settles nothing | Delete it with the code. Note the consequence below |
| C5 | The never-force rule | Same header | Forcing deletes another writer's rows at exit 0 | Still true, and now unreachable | Keep it. It stops being load-bearing |
| C6 | `committing.md` documents the rebase loop as the design | `docs/architecture/publishing/committing.md` | It is a living snapshot of current behaviour | It will be wrong the moment the code changes | Rewrite in the same commit as the code |
| C7 | The workflow tests encode the rebase | `backend/tests/workflows/test_commit_script.py`, `test_closed_day_fold_push.py`, `test_prune_push.py`, `test_state_from_the_tip.py` | They hold the loop to its behaviour | The behaviour changes | Rewrite with the code, in the same commit (CLAUDE.md section 9) |

**C1 is the only real relaxation.** Everything else on that list is a deletion, a
rewrite, or a note.

**The reason behind C1 is the whole argument.** CLAUDE.md section 1 says a
guardrail quoted without its reason is a half-quote. The reason `git reset --hard`
is on the avoid list is that it destroys work a person has not committed yet. On
a GitHub runner there is no such work: the checkout is made fresh, used by one
job, and discarded. The command that is dangerous on a developer's machine is the
correct tool on a disposable one.

### What gets deleted, not relaxed

- `resolve_what_this_job_owns` and the filename parsing it does.
- `hand_back` and the amend that follows it.
- `clear_what_the_tip_will_write_over`. `git reset --hard` overwrites an
  untracked file the target tree holds, where `git checkout` refuses - so the
  untracked-file trap described at length in `committing.md` disappears with it.
- `spare_the_published_assets` and the `DROP_RACED` hook.
- `merge.directoryRenames=false` on both spellings, and the reasoning above it.
- `git rebase --abort` and the settling pass.

Roughly 300 lines, replaced by about ten.

### What stays exactly as it is

- **`fetch-depth: 1` in `digest.yml`.** It is not the bug. Under a rebase it was
  fatal; under a rebuild it is correct and cheap, and it should stay.
- **The retry loop, its wall clock and its back-off.** A push can still lose a
  race and still has to try again.
- **The attempt line printed per attempt.** It is the only record of how often
  the race is lost.
- **Explicit staging.** The rebuild stages the same named paths it stages today.
  `git add .` stays off the table (CLAUDE.md section 8).

### One consequence worth carrying forward

C4 deletes the only thing in this repository that reads a committed filename to
decide something. Any design that was shaped by "the push script must be able to
parse this name" is free of that constraint once this lands.

## Rejected alternatives

### Ways to get the bytes onto the tip

| id | Approach | Needs history | Can conflict | Cost |
| --- | --- | --- | --- | --- |
| A1 | Keep the rebase, deepen the clone on rejection with `git fetch --unshallow` | Yes | Yes | One line, and it treats the symptom. The rebase still does no work, the 300 lines of machinery stay, and a run in flight across a prune still dies because the history it wants is genuinely gone |
| A2 | Keep the rebase, set `fetch-depth: 0` on all three checkouts | Yes | Yes | Every job on every run downloads the whole history, corpus included, and the cost grows with the repository (CLAUDE.md Guardrail 12) |
| A3 | Keep the rebase, set a fixed deeper checkout such as `fetch-depth: 50` | Yes | Yes | A guess. A prune or a quiet week changes what fifty commits covers, and when it is too shallow the failure returns looking identical |
| **A4** | **Copy aside, `git reset --hard` to the tip, re-lay, commit** | **No** | **No** | **Chosen.** Deletes more code than it adds, and is the shortest move from what is written |
| A5 | Build the commit with plumbing: `hash-object`, `read-tree`, `update-index`, `write-tree`, `commit-tree`, `update-ref` | No | No | Same semantics as A4 with no worktree churn at all. More exotic shell for no behavioural gain. Worth revisiting if the worktree copy ever costs measurable time |
| A6 | GitHub GraphQL `createCommitOnBranch` with an expected head oid | No clone at all | No | Atomic and server-side; a moved head fails cleanly and the job retries with the new oid. Files go as base64, so the 29.7 MB digest is an open question. Viable for telemetry alone, which would split the commit path in two |
| A7 | Robots commit to a `data` branch, people own `main` | No | No | Removes the race by construction rather than by mechanism. Pages then has to read two refs, and every reader of the repository has to know which branch holds what |
| A8 | Jobs upload artifacts, one serialized job commits everything | No | No | Removes the race between jobs and leaves the race against a person's merge - which is the failure actually in hand. It is the intuitive fix and it addresses the wrong race |

**A4.** It removes every race below, deletes the machinery rather than feeding
it, and needs one named exception to land.

### Which race each option removes

| id | Race | Was it this failure | Removed by |
| --- | --- | --- | --- |
| B1 | Two jobs of one run pushing at once | No | A4, A5, A6, A7, A8 |
| B2 | A job racing a person's pull request merging | **Yes.** #1080 squash-merged 19 s after checkout | A4, A5, A6, A7 - not A8 |
| B3 | A job racing `prune.yml` force-pushing history | Not this failure, same shape, and it will happen | A4, A5, A6, A7 |

### Two changes that are worth making and do not fix this

**Splitting `assemble` into a commit step and a publish step.** It does not fix
this failure: the clone is shallow from the job's first second, so each half
inherits the same problem. It is still worth doing for two other reasons. It
shortens the window a rival merge can land in - `assemble` checks out, rebuilds
the site, and only then commits, and on this run that gap was 85 seconds with the
merge landing 19 seconds into it. And it separates two failures that share one
exit code today: a push race currently fails the site build, and a site build
failure currently loses the data commit.

**Allowing merge commits instead of squash-only.** Squash gives every merge a
brand-new commit identity, which is what orphaned the in-flight job's base here.
Under A4 nobody looks for an ancestor, so squash-only costs nothing and should
stay (CLAUDE.md section 8).

## See also

- [committing.md](committing.md) - the loop as it stands today, what each job
  stages, and how two runs of one day are kept from writing one path.
- [one-visual-one-file-and-the-race-between-two-runs.md](one-visual-one-file-and-the-race-between-two-runs.md) -
  why a raced chart is dropped rather than merged.
- [../../reference/github-actions.md](../../reference/github-actions.md) - which
  workflows exist and which of them commit.
- [../../../CLAUDE.md](../../../CLAUDE.md) - section 8 on git hygiene and the
  avoid list C1 asks an exception from, section 1 on how an exception is taken.
