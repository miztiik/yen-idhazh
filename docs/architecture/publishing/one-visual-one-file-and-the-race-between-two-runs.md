# One visual, one file, and the race between two runs

**Last Updated**: 2026-09-23

A visual's file is named for the item it belongs to, and nothing recomputes that
name. This page is why: two earlier naming rules each published one story's
chart under another story's address, and each failure cost a different thing.
It holds the rule in force, the two counters it replaced, the control that keeps
two overlapping runs from colliding on one path, and the one committed day that
was repaired by hand. What the file contains is
[where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md).

## The name is the item's own id, and nothing recomputes it

**A path is a function of the item and of nothing else.**
`energy-4821903756.json` on a day written before 2026-09-12 and `energy-wfyypy5sgvnwcxd3.json` after
it - the same id a reader already lands on as an anchor, in whichever of the two live shapes that
day was written under ([`layout.md`](layout.md)). Two items cannot share a path, so nothing has to
notice that they did.

That is the third answer to one defect, and the first two are worth keeping on the page because they
are what a counter costs. **A per-process counter** restarted at 1 in every run, so the second run of
2026-08-24 overwrote the first run's file while the digest still referenced both items: 32 declared
visuals over 18 files, fourteen paths claimed twice, and `india-01.svg` shared by a stock-market
story and a defence-stocks story - one of them showing a chart of the other's numbers under alt text
describing figures that were not in the picture. **A counter seeded from the day's directory** fixed
that and could not fix the next one: a run takes about three hours and the day is refreshed five
times, so a second run is planning while the first is still summarizing, neither checkout can see what
the other has not pushed, and both read the same highest ordinal. Both wrote `energy-03.svg` for
different items with different bytes. The planner never found out; the push did, and run
`32869125768` lost eight workers and a visuals job at `CONFLICT (add/add)` over four asset paths, because
git cannot rebase two adds of one path. Every summary in the day expired with the `items-*`
artifacts.

The common factor is that a counter has to be seeded from something a process can observe, and two
processes observed different things. **An identity cannot be read from a directory.** That is the
whole of the fix, and it is why no third seeding rule was tried.

## What is left is one story compiled twice, and it has one right answer

Two overlapping runs can
still both plan the same item, compile it, and disagree about the bytes - the article is re-fetched
from the open web, so a source page that moved between the two fetches yields a different element
table and a different plan. That path is now the same item on both sides, never two stories under one
name - so there is nothing to choose between. The tip's copy is published and a reader may already
hold that address, and `build_day` keeps the tip's item over this run's in any case, which makes this
run's file the one nothing will reference. Before each rebase attempt the commit step lists the paths
the tip already publishes and hands them to
[`backend/utilities/drop_raced_assets.py`](../../../backend/utilities/drop_raced_assets.py), which
deletes this run's copy of any of them. The decision payload is left naming the same path, because after
the rebase the tip's file is sitting at it.

**The renderer's own non-determinism was a second cause of differing bytes, and it left with the
renderer.** What that cost, and why the test that should have caught it did not, is in
[what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md).
An item compiled twice from unchanged inputs now writes identical bytes and git merges those without
a conflict, which is why the race is rarer than it was - and why it is not gone.

**Neither control repairs the day it already happened on.** Both stop a run standing on a path
another run published; neither revisits a payload that already names one file twice. 2026-08-24 kept
its 32 declared visuals over 18 files until it was repaired by hand on 2026-08-27, and it is the only
committed day that ever held one - the other five are one path per item. The repair nulls the visual
on **all 28** items that claimed a shared path, not one of each pair: nothing committed says which of
the two stories a chart was drawn for, so keeping one is a guess wearing a record's clothes. The four
singly claimed files keep their items. The 14 files nobody names any more are deleted - 172,164
bytes, three quarters of that day's picture weight, dead against the 1 GB Pages cap (Guardrail #2). No
reader-facing string was added: no picture is the common and correct answer and the page says nothing
about it, so a repaired item reads exactly like the 699 that never had one.

## `validate-days` is what would have caught it

It holds the three ways a payload and its
directory can disagree: no two items share a path, every declared path is a file that is there, and
every file in a day directory named for an item is named by an item. It runs inside
`idhazh validate-days` rather than as a test per committed day, because a day already published is
frozen and re-checking every one of them costs more every day the pipeline runs (Guardrail #12). The
trees it is driven against are built in `backend/tests/test_published_assets.py` - one correct, and
one for each way a payload and its directory can disagree - and a built tree can also carry a fault
the archive has never produced.

## Design rationale

**Why a raced chart is dropped rather than merged, refreshed, renumbered or picked between.**
Authority: the owner, 2026-08-27. Every cheaper-looking answer publishes a wrong picture instead of
failing, which is worse than losing a day because nobody finds out. Adding the day's directory to
`REFRESH_PATHS` makes the rebuild's hand-back delete every chart this run added that the tip lacks,
while the regenerated `digest.json` still names them - `assemble` copies the path from the decision
payload and cannot render anything - so the day publishes with broken images. Resolving the add/add
by a stated side has two outcomes and no third one; `-X theirs` gives our item the tip's picture,
`-X ours` overwrites an address a reader may already hold. **Renumbering was the answer while a path
could mean two different stories**, and it is the wrong answer now: the path names one item, so
moving this run's copy to some other name would file that item's picture under a name that is not
its own, and leave two files where the day references one. Dropping is what is left, and it costs
nothing - the rebuild keeps the tip's item, so this run's copy was never going to be referenced.

**Why the drop happens in the shell's retry loop and not inside `assemble`.** The rebase is what
fails, and it runs before `REGENERATE_COMMAND` does, so a fix that runs after it never gets to run
at all. The naming rule itself stays in `backend/idhazh/render/write.py`, which owns it: the shell
lists paths and pipes them, and a small argv wrapper under `backend/utilities/` does the work.
Bash never learns what an item id means (Guardrail #3).

**Two things about the 2026-08-24 repair are not in the record above.** Authority: owner,
2026-08-27.

The first is that no other committed day needs it. 2026-08-21 published no visual at all,
2026-08-22 and 2026-08-23 published one each, and 2026-08-25 (27 visuals over 27 files) and
2026-08-26 (40 over 40) name one file per item throughout. 2026-08-24 is the only day that ever
pointed two items at one picture, so the repair is a one-day event and not the first of a series.

The second is what that test - `backend/tests/test_published_assets.py` - costs the prune, and the
cost is the guard working rather than a false alarm. The prune - `visuals_older_than` in
[`retention.py`](../../../backend/idhazh/retention.py) - deletes an old day's SVGs and leaves the
payload that names them alone, on purpose: it removes visuals, never a day. So switching the prune
on fails the second of the test's three assertions - every declared path is a file that is there -
on the first day it prunes. The prune has to learn to null the item's `visual` as it deletes the
file before it can be enabled.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Keep the per-vertical counter and seed it better | Every seeding rule reads something a process can observe, and the defect is that two processes observe different things. A per-process counter lost 2026-08-24; a directory-seeded counter lost run `32869125768`. There is no third thing to read. |
| Name the asset from a hash of the address, `<vertical>-<url_key prefix>.svg` | It fixes the same defect as the item id and breaks a rule the item id does not: [`layout.md`](layout.md) says no hash appears in any path, filename or URL, and `backend/tests/contracts/test_repo_structure.py::test_no_hash_appears_in_any_published_path` holds it. The item id is already a published address - it is the anchor a reader lands on - so it costs the reader nothing that has not already been accepted. |
| Add the day's directory to `REFRESH_PATHS` | The hand-back deletes what the tip lacks and restores what it has, so this run's own charts are deleted while the rebuilt `digest.json` still names them, and the colliding one comes back with the other story's bytes. A broken image and a wrong image, published, instead of a job that failed loudly. |
| Resolve the add/add with `-X ours` or `-X theirs` | `theirs` puts the tip's picture under our alt text; `ours` overwrites an address a reader may already hold. Neither side of a coin flip is a correct answer to "whose chart is this". |
| Renumber a raced chart instead of dropping it | Right while a path could mean two different stories, wrong now that it names one item. Moving this run's copy would file that item's picture under a name that is not its own, and leave two files where the day references one. |
| Keep the first claimant's chart and null only the second | The order two items sit in a payload is not evidence of which one the chart was drawn for. This repairs 14 items by guessing on the other 14, and a guess that publishes is the failure being fixed. |
| Leave the 2026-08-24 day as history and let retention prune it | Retention never removes it. `retention.dry_run` is `true`, which makes every pass report-only, and the prune deletes visuals rather than days, so it would never reach a payload even switched on. "Let it age out" is not a thing that happens here; the day stays wrong until somebody edits it. |
| Re-render the 2026-08-24 day from its committed decisions | Not rejected - impossible. It was offered as the thorough option in a handover and could never have been taken: the `visuals` artifact carries `retention-days: 1` and nothing under `backend/var/` is committed, so that day's decisions expired on 2026-08-25, before anyone read the handover. |

## See also

- [visuals.md](visuals.md) - who decides a picture at all, and where the pass runs.
- [where-a-drawing-becomes-pixels.md](where-a-drawing-becomes-pixels.md) - what the file this page names actually holds.
- [layout.md](layout.md) - the published tree, the item id a reader lands on, and the no-hash-in-a-path rule.
- [committing.md](committing.md) - the retry loop the drop runs inside.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the commit loop that drops a raced chart.
