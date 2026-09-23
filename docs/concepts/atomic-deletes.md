# Atomic deletes

**Last Updated**: 2026-09-17

What does "atomic" mean for a delete in this project, and why is a range not one?

**Atomic here means per member.** One delete is the unit. It either happened or
it did not, and there is no state between the two. A pass that deletes members
1, 2 and 3 and is then interrupted leaves members 1, 2 and 3 gone and member 4
onward exactly as they were. Nothing is half-done, so nothing has to be undone.

It does **not** mean all-or-nothing over a set. A pass over a collection is not
a transaction and does not try to be one.

## The three properties a pass holds

| Property | What it means | What it buys |
| --- | --- | --- |
| **Per-member** | one delete is the unit, and it either happened or it did not | an interruption needs no repair |
| **Bounded** | one pass takes at most a ceiling of members, then stops | the cost of a pass does not grow with the backlog |
| **Resumable** | the record names the member the next pass starts at | a backlog is cleared in bites nobody has to size |

The core that holds all three is
[`backend/idhazh/prune/one_at_a_time.py`](../../backend/idhazh/prune/one_at_a_time.py),
and its first sentence is the question it answers: how do I delete a
collection's members one at a time, safely, resumably, under a ceiling. A
collection reaches it as three callables - a listing that yields members, a
describe that reads one into an id, a day and a size, and a delete that acts on
exactly one. Nothing else about a collection is known to it, which is why the
same code prunes a store's day files and GitHub's workflow artifacts.

## Why a range is not atomic, whatever it does internally

A range operation has one commit point for many members. Three things follow,
and each one is a cost somebody pays later.

- **It has to collect before it can act.** Every member is held in memory before
  the first is deleted, so a collection of 3,551 members costs 3,551 members of
  memory to delete one. That is a read whose cost grows with what the repository
  has piled up ([CLAUDE.md](../../CLAUDE.md) Guardrail #12).
- **Its rollback is a second write path.** Undoing is code, it runs only when
  something has already gone wrong, and it can fail while it is undoing. It is
  the least-exercised path in the system and it runs at the worst moment.
- **It holds every member hostage to the last one.** A range of 612 that fails
  on the 611th deletes nothing. Re-running repeats 610 deletes that already
  worked, which is how a failing prune becomes a prune nobody runs.

A per-member pass has none of the three. It holds one member, it has no undo
path because it never leaves anything undone, and a failure costs the members it
had not reached yet and nothing more.

## What the word costs, stated plainly

A failed pass is **not** a no-op. Members 1 to N really are gone. An operator
whose pass stopped reads which members went from the record and re-runs from the
resume point.

That is the trade, and it is a trade rather than a free win. What buys it is
that "the tree is exactly as you found it" was never a promise this project
could keep. `.github/workflows/prune.yml` squashes and force-pushes `main` on a
schedule ([CLAUDE.md](../../CLAUDE.md) section 8), so a state file deleted here
stops being recoverable from git history once that prune passes over its range.
A rollback only ever protected one process against one failure, never the data
against being gone - and the thing it did reliably cost was a second write path.

## Design rationale

**The decision, 2026-09-17.** The owner ruled that prune utilities do short
atomic deletes rather than a range fetch followed by an attempt to delete
everything in one go, and that any existing utility not doing atomic deletes be
converted. `idhazh telemetry prune` was the one that was not.

**What it replaced.** That command collected a whole day range, renamed every
selected file into a scratch directory beside the stores, removed the directory
once every rename had worked, and put every file back if a rename failed. It was
correct and it was tested. What it could not do is stop and resume, and it could
not be pointed at a collection with 612 members and no local file system.

**The alternative that was rejected: keep the range shape and add a ceiling.**
That would have bounded the cost without buying resumability - a range that
stops at 50 still has to collect the range first, and its rollback still has to
put 49 files back if the 50th fails. It also leaves two deletion shapes in the
codebase, which is the thing a reusable core exists to prevent.

**What the change cost, named.** One test property was replaced rather than
extended: `test_a_move_that_fails_part_way_leaves_the_tree_as_it_was` asserted
the all-or-nothing rollback, which is exactly the shape the ruling removed. It
is now `test_a_delete_that_fails_part_way_keeps_what_it_already_removed` and
asserts the property that replaced it. Every other test on that module stayed as
it was.

## See also

- [../architecture/publishing/retention.md](../architecture/publishing/retention.md) - what bounds each committed tree, and the named prune over a store's day files.
- [../how-to/prune-a-collection.md](../how-to/prune-a-collection.md) - the steps for running one.
- [growing-reads.md](growing-reads.md) - why a read whose cost grows with the archive needs a window.
- [config/retention-ages.md](config/retention-ages.md) - where the `prune` knobs live.
