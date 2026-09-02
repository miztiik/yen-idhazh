# Feed Health and Quarantine

**Last Updated**: 2026-09-03

What every feed did on every run, where that record lives, and how a run decides on its own to stop asking a dead source. Nothing on this page ever edits `config/sources.json`: a person owns the source list, and a run owns the evidence about it.

## From item outcome to feed rest or retirement

An item never enters quarantine or retirement. It either publishes or stops at
a stage, and its item-health row becomes evidence about the feed. A run may
rest a feed and may retire an address. Only a person may retire a **source**.

```text
FEED READ (one feed-health row)
|
+-- ok with items -> clear strike streak, clear 410 streak -> ask next run
+-- 410 Gone -> add one 410 run -> ask next run
+-- robots_denied -> keep strike streak -> ineligible until permission returns
+-- skipped -> keep strike streak -> count one rested run
`-- blocked / permanent / transient / ok with zero items -> add one strike

CONFIGURED LIMIT = collect.quarantine_after_failures (currently 5)

LIMIT CONSECUTIVE STRIKES -> REST FEED
REST FEED -> write LIMIT skipped rows -> RETRY
RETRY SUCCEEDS -> clear strike streak -> LIVE NOW
RETRY FAILS -> REST CYCLE RESUMES

CONFIGURED LIMIT = collect.feed_http_410_runs_before_retirement (currently 5)

LIMIT DISTINCT RUNS READ 410 -> RETIRE ENDPOINT -> never asked again
RETIREMENT OUTRANKS REST
CONFIGURED URL EDITED -> NEW ENDPOINT KEY -> eligible from a clean record

PLANNED ITEM (one item-health row)
|
+-- published ----------------------> positive source-yield evidence
+-- source-owned failure -----------> negative source-yield evidence
`-- pipeline-owned or neutral ------> does not count against the source

SOURCE-YIELD EVIDENCE -> NO AUTOMATIC ACTION TODAY

HUMAN SOURCE REVIEW (after at least 30 days of evidence)
|
+-- keep active
+-- lower weight and observe
`-- move from `feeds` to `retired`; set `status: retired` and `retired_on`
```

## Every feed, every run, one row

`state/feed-health/<YYYY-MM>.csv`, appended by the Collect stage. One row per feed per run, carrying the run id, the date, the feed id, the outcome, the HTTP status, how many items came back, and a short detail.

It is written **whether the run publishes or not**. The days a source is worth measuring on are the days the run went badly, and a ledger that only records good runs measures nothing.

Monthly shards, because a read looks back 31 days - just enough that a quarantine decided on the first of the month can still see the failures that caused it.

## A month past its age is deleted, and no summary replaces it

`observability.feed_health_keep_months` is 14, and a shard older than that is unlinked by `idhazh prune-state` after the day is committed. Nothing is folded first, and that is the decision rather than an omission: the quarantine reads 31 days and the console reaches at most `console.max_window_days` (366), so no total over a month fourteen months back has a reader - and writing one would persist a shape nothing consumes, for ever. Fourteen for the same reason the item-health window is: a 366-day read walks 367 inclusive days and those days can fall in fourteen calendar month files.

**Older than the oldest month kept, never merely outside a window.** `--date` takes whatever it is handed, so a run given a date in the past draws a smaller window and every shard since falls outside it. Deleting below the window's floor instead means a back-dated run deletes less rather than deleting the shard the next quarantine reads.

**`state/feed-retirements.csv` is never a candidate.** It sits beside this directory rather than in it, and it carries no time window at all: one row is one address a server reported permanently gone. The evidence that retired an address lives in shards this prune is entitled to delete, so the record has to outlive them - a run that forgot it would start asking a dead address again on the day the last 410 row aged out.

**The step ships in dry run.** It logs every file a live run would remove and removes none of them, because `.github/workflows/prune.yml` force-pushes `main` on a schedule and a state file deleted here stops being recoverable from history once that prune passes over it (`CLAUDE.md` section 8). Turning the deletion on is a one-line commit taken after a scheduled run has printed the list. Measured on this checkout on 2026-09-02: a live run removes nothing today, and the first shard it would take is `state/feed-health/2026-08.csv` on **2027-10-01**. Reading committed files against a fixed calendar is deterministic, so the spread is zero.

## One row per feed per run, enforced rather than assumed

`(run_id, feed_id)` is what makes two rows the same record - `ledger.FEED_HEALTH_KEY`. A feed is read once in a run, so two rows under one key are two accounts of one event.

**Two runs are entitled to a row each and always get one**, because a run id carries the identity of the execution that made it. What repeats the key is one execution attempted twice: the second attempt appends against a checkout frozen at the commit its run was triggered at, so it cannot see what the first attempt pushed, and `merge=union` on `state/**/*.csv` concatenates rather than conflicting. Counted raw, one bad run reads as two failures and a five-strike rest arrives in three runs.

So the shard is settled twice, and the second pass is the one that matters:

- **Before the push.** `ledger.append_health` settles the shard it just wrote. That catches a repeat inside one checkout and nothing else.
- **After the merge.** `python -m idhazh dedupe-ledgers`, run by both recording commit steps through `DROP_REPEATED_ROWS_COMMAND`, on the merged file - the only artefact that has ever held both attempts at once.

**Where two accounts conflict, the read that carried entries wins**, whichever row is newer: the attempt that got articles is the attempt that happened, and an empty retry against an address that had just delivered describes the retry rather than the feed. Between two rows that agree on that, the later `checked_at` wins. A tie leaves the row already on record. The rule is `contracts.feed_health.supersedes`, and it is the one key here settled by a rule instead of by arrival order - everywhere else a repeat is one attempt written down twice, so the two rows agree.

Measured on this developer checkout, 2026-09-02, over the committed shards: 6,577 rows carried 6,022 distinct `(run_id, feed_id)` keys, so **555 rows were a second account of an event already on record** - 8.4 percent of the ledger - and 37 of those keys held rows that disagreed about what the feed did. Four keys were settled in favour of the later attempt, each because that attempt carried articles the earlier one had not. Reading a committed file is deterministic, so the spread is zero.

**It changed no decision.** The resting set over the 31-day read is 16 feeds with the repeats and 16 feeds without them, the same 16 either way, and the same 16 under the old strike rule as under the new one. The defect was latent: it would have rested a feed early on the first day a re-run happened to land inside a failing streak. Fixing it is correctness, not the repair of a live outage.

## Fourteen cells, and two of them are still empty on every row

The row gained `endpoint_key`, `robots_outcome`, `robots_checked_at`, `robots_status` and `target_attempted` on 2026-09-02. They are appended at the end of the header. The plan stage started filling the first, the second and the last of them the same day; the two clock cells are still empty on every row, because the recheck cadence is counted in runs rather than read off a clock ([discovery.md](discovery.md)) and no decision here reads a robots status.

| Cell | What it answers |
| --- | --- |
| `endpoint_key` | Which address was asked. The sha256 of the configured feed URL, so a feed whose URL is edited is a different endpoint with no inherited record. |
| `robots_outcome` | What the site's own `robots.txt` said: `allowed`, `denied`, or `unreachable` when we could not establish permission at all. |
| `robots_checked_at` | When permission was established, so a recheck cadence has a clock. |
| `robots_status` | What `robots.txt` itself answered with, when there was a status. |
| `target_attempted` | Whether the feed address itself was requested. False for a run that stopped at `robots.txt` or rested the feed. |

**The record could not previously say which address it asked.** `feed_id` names a
line of curated config, not a URL, so an address that changed and an address that
died looked the same to every later read - and a run cannot stop asking a dead
address without being able to say which address it means.

**And a refusal read as a failed read.** `robots_denied` says the site declined,
but the row carried no evidence of the check itself, so nothing downstream could
tell "the site said no" apart from "we did not get that far".

**Every row written before that day carries five empty cells.**
Not a zero, and not an identity recomputed from today's `config/sources.json`: the
configured URL may have moved since a row was written, and a guessed endpoint
would file a later retirement against the wrong address. An empty cell says the
older run never looked, which is the only honest thing it can say.

**So the earliest an address can be retired is five runs after the writer
started filling the cell**, and not one run sooner. Measured on this checkout on
2026-09-02, before the writer landed: 6,022 settled rows, **none** carrying an
`endpoint_key`, and **none** carrying HTTP 410 at all. The retirement rule is
therefore live and unfired, which is the state it should be in - a lifecycle
rule that retires something on the day it ships was not measuring, it was
guessing.

The rewrite is `backend/utilities/migrate_feed_health.py`, and it ran in the same
commit as the contract change because `ledger.require_matching_header` compares
the committed header to the contract's column list exactly - a widened contract
against an unmigrated shard stops the next scheduled run at its first append. It
is safe to re-run: a shard already on the wide header is reported and skipped.
That is not a nicety. `state/**/*.csv` is `merge=union`, so an append that lands
while the migration is in review does not conflict - it concatenates, and the
result is one file with two headers. Taking the upstream shards whole and running
the utility over them again is the resolution, and re-running it is how that is
done.

Measured on this Windows developer checkout, 2026-09-02, over the shards this
change committed: 6,577 rows across two shards, 599,497 bytes before the widening
and 632,536 after, so five empty cells per row cost 33,039 bytes - 5.5 percent of
the ledger. Reading a committed file is deterministic, so the spread is zero. The
file grows several times an hour, so the count is a fact about that commit and
not about today.

## A run may rest a feed; only an address is ever retired automatically

`state/feed-retirements.csv` is where a run files an address the server has
reported permanently gone. One row is one endpoint: the feed, the endpoint key,
the day, the run that decided, the cause, and the runs whose results evidence
it. It ships with its header and no rows, because the plan job's commit step
stages every path it owns in one call and a path that is not in the checkout
aborts the whole step ([../contracts/schemas.md](../contracts/schemas.md)).

**`http_410` is the only cause the enum admits**, and that is the design rather
than a starting point. A 403, a 404, a paywall, a transient failure and an empty
feed all say something about today; only `410 Gone` is the server saying the
address is not coming back. Retiring on anything softer removes unique primary or
regional reporting over one bad week, and nothing here puts it back without a
person noticing it went.

**Five distinct runs, not five results.** A job that is re-run keeps its run id,
so a single bad afternoon retrying itself would otherwise retire an address on
its own. `source_health.endpoint_records` settles the rows before it counts them
and then counts run ids.

**A read that carried entries clears the count; nothing else does.** An empty
`200` adds an availability strike and leaves the `410` count exactly where it
was - it is evidence that the feed is not working and no evidence at all that
the address is gone. The same holds for a block, a 404, a timeout, a robots
refusal and a rest.

**Retirement outranks rest.** Both end in a `skipped` row and neither is asked,
and the difference is that a rest lifts itself after five skips and a retirement
never does. The plan checks the retirement ledger first, so an address that is
both never comes back on the rest's own schedule. The two rows differ in their
`detail`, which is the only cell that can say which rule held the feed back.

The record is keyed on the endpoint and not on the feed, so renaming a feed in
curated config cannot make its dead address eligible again, and editing that
feed's URL produces a different key that is eligible from a clean record. **That
is the whole reversal path**: one line of curated config, no flag to clear.

**What the rule costs the run: nothing worth measuring against what it saves.**
It is one more fold over the rows the rest decision already read, plus one small
file. Measured on this Windows developer checkout, 2026-09-02, over the 6,022
settled rows the committed ledger holds, median of 7 samples: the fold takes 1.52
ms (spread 0.24 ms) and reading the retirement ledger takes 1.2 ms (spread 2.7
ms), beside the 2.5 ms the rest decision already spends. The plan job spends
minutes asking feeds, and each retired address removes one of those requests from
every run for good.

## The feed floor counts the addresses we may ask

A vertical below `min_feeds` publishes nothing at all - the desk does not thin
out, it goes silent. From 2026-09-02 the count it is compared against is
`eligible_feeds`, and four different things take an address out of it:

| Not counted | Because |
| --- | --- |
| A curated tombstone | A person removed the source. Enforced by the shape of the config rather than by a filter. |
| A retired endpoint | The server says the address is gone. |
| A robots refusal | The publisher's stated policy is no. |
| Permission we could not establish | Unknown fails closed, so the address is never asked. |

**A resting or failing endpoint is still counted**, and that is the load-bearing
half. A rest lifts itself, so dropping a resting endpoint would let one afternoon
of outages take a desk dark - and the desk's problem then is that today went
badly, not that it is under-sourced. The floor asks how many independent sources
a desk has, which is a question about lawful diversity rather than about today's
socket results.

**An address nobody has recorded permission for is counted.** Absent is unknown
and never a refusal; every row written before 2026-09-02 carries an empty cell,
and reading those as refusals would take every desk under its floor on the day
the rule landed.

Measured on this developer checkout, 2026-09-02, over the committed config and
ledger: the two counts are identical on every desk, because no committed row
records a permission or a retirement yet. Reading committed files is
deterministic, so the spread is zero.

| Desk | Floor | Feeds a curator left active | Feeds we may ask | Margin |
| --- | --- | --- | --- | --- |
| `ai` | 35 | 43 | 43 | 8 |
| `energy` | 21 | 27 | 27 | 6 |
| `business-economy` | 21 | 25 | 25 | 4 |
| `world` | 21 | 25 | 25 | 4 |
| `india` | 21 | 24 | 24 | 3 |

The margins are what the change costs if it is wrong, and they are thin on
purpose: `india` is three refusals away from going dark, and going dark is what
the floor is for. Five feeds' newest committed row is a robots refusal today -
`anthropic-engineering`, `anthropic-research`, `axios-business`, `cbc-world` and
`cnbc-top` - and two of the five sit on `ai`, so even if every one of them
records a typed refusal on the next run, no desk moves under its floor.
`backend/tests/test_contracts.py::test_every_vertical_clears_its_own_feed_floor`
is the gate, and it reads the committed ledger rather than a fixture.

The plan payload carries both numbers per desk, and the run manifest carries
them too - `below_feed_floor` on its own says a desk went dark and neither
number that decided it, and the manifest is the only committed record of a plan.

## Six knobs name the questions the one knob used to answer

| Knob | Default | The question |
| --- | --- | --- |
| `collect.availability_strikes_before_rest` | 5 | How much evidence before a run stops asking? |
| `collect.availability_rest_runs` | 5 | How long is a rest? |
| `collect.feed_http_410_runs_before_retirement` | 5 | How many distinct runs must read `410` before an address is retired? |
| `collect.robots_denied_recheck_runs` | 1 | How long before asking `robots.txt` again after a refusal? |
| `collect.robots_unreachable_recheck_runs` | 1 | The same, after a `robots.txt` we could not read. |
| `collect.source_yield_min_complete_days` | 30 | How many complete days of item-health evidence before a yield judgement may be made at all? |

**Three of the six now decide something.**
`feed_http_410_runs_before_retirement` is the retirement rule above, and the two
recheck cadences are answered by the run itself: nothing about a refusal is
persisted, so the next run asks the host again, which is those knobs at their
configured value of one run. `collect.quarantine_after_failures` still decides
every rest, and both it and `availability_strikes_before_rest` carry 5;
`source_yield_min_complete_days` is read by nothing.

The two recheck cadences are separate because they are different facts: a refusal
is a publisher's stated policy and an unreadable `robots.txt` is our own failed
read. One number for both would mean an edit meant for one silently moved the
other.

## Six outcomes, deliberately coarser than HTTP

What a later decision needs is whether the address is worth asking again. `403` and `404` answer that the same way; `503` answers it differently.

| Outcome | What it means | Counts against the feed |
| --- | --- | --- |
| `ok` | The feed answered and parsed | **Only if it returned zero items** |
| `robots_denied` | `robots.txt` said no, or could not be read | No |
| `blocked` | We were refused | Yes |
| `permanent` | Gone, and staying gone | Yes |
| `transient` | Timed out, or the host was briefly unwell | Yes |
| `skipped` | We did not ask - the feed was resting | No |

## Eight kinds of evidence, three effects

"Counts against the feed" is two questions, and separating them is what the availability rule turns on. A row can add a strike, leave the streak where it is, or end it.

| Evidence | Effect on the streak |
| --- | --- |
| A success carrying entries | **Ends it.** The address answers now. |
| A success carrying nothing | Adds one strike |
| `blocked` | Adds one strike |
| `permanent` | Adds one strike |
| `transient` | Adds one strike |
| A robots refusal | Leaves it where it is |
| A `robots.txt` we could not read | Leaves it where it is |
| A rest | Leaves it where it is |

Three of those rows carry the whole design.

**A `200` that parses to no entries counts as a failure.** The most common way a feed dies is not a 500. It is a silent reshape that still returns 200 and an empty list. An empty answer costs the digest exactly the articles a refusal would, so it is measured the same way.

**A robots result adds no strike and clears none.** The first half is old: the source is working exactly as it asked to be treated, and resting it would be us punishing a site for saying no. The second half was missing until 2026-09-02, and it was the sharper bug. A refusal used to end the streak, so a dead address behind a site that says no had its record wiped on the run after every failure and could never reach a rest at all. Neither robots answer asked the feed whether it still works, so neither is evidence about the address either way.

**Only a read that carried entries clears the streak, and it clears the whole streak at once.** The streak answers one question - is this endpoint broken now - and a source that just delivered articles is not broken. Decrementing one success at a time was rejected: it would leave a feed that recovered on the fifth day still resting on the ninth, for failures it has already answered. Nothing is forgotten by clearing it, because the ledger keeps every failure it ever recorded and the reliability record is read over the whole file.

## Quarantine is a rest, not a retirement

A feed that has failed its last `quarantine_after_failures` (5) attempts is not asked on the next run. That is a rest.

**The rest ends on its own.** Once a feed has been skipped five times it is asked again regardless of its record. A source that came back is live on that very run; a source that is still dead costs one request per cycle instead of one per run.

**A rest is transparent.** A `skipped` row neither adds a strike nor clears one, so the count picks up where it left off when the feed is next asked. Without that, a rest would erase the evidence that caused it. A robots result is transparent for the same reason and by the same rule - see the evidence table above.

Both counters read the same knob because there is only one question here - how much evidence is enough. A second number would be a second answer to it.

The `skipped` row exists for one reason: a quarantine that writes nothing can never lift, because the failures that caused it stay the newest thing on record forever. The skip has to be recorded for the rest to end.

Feed health cannot explain why a planned article failed after discovery. That
belongs to the item-health ledger, which records one row per planned item per
run. See [item-health.md](item-health.md).

## Per-source yield is not measurable yet

Feed health can say whether a source answered. It cannot yet say whether that
source yields publishable items over time. That denominator is different: one
source can answer cleanly and still produce planned items that fail at fetch,
extract or summarize.

Per-source item yield needs at least 30 days of `state/item-health/` rows. The
ledger started on 2026-08-23, so the rubric is blocked until that window exists.
Do not retire or demote a source by item-yield rule before then. Until the
window exists, any source-yield threshold is an estimate, not a measurement.

## The run never edits the source list

Retirement of a **source** is a person moving a feed into the `retired` key of `config/sources.json`. Quarantine is a run declining to ask, based on rows it wrote itself. Retirement of an **address** is a third thing, and it is a row under `state/` for the same reason quarantine is: a run may write evidence about curation and may never write curation.

Keeping those separate is what makes a bad afternoon survivable. A run that could edit config would, over one bad week, quietly delete sources nobody voted to remove - and the diff would be authored by a robot at 06:20 on a Sunday. What the run may do instead is stop asking one address and say in a committed row why, which a person can read, argue with, and reverse by editing one line.

## Two readers, one record

- **The planning step** reads the recent tail to decide which feeds to skip this run.
- **The console** reads the same rows to show which sources are broken. It names only feeds that failed at least once; a list that names all seventy sources hides the four that matter. See [../publishing/frontend.md](../publishing/frontend.md).

They read the same file so they can never disagree about what a feed did - and, since 2026-09-02, they reduce it the same way as well. `discover.settled` and `settled` in `frontend/src/lib/feed-health.ts` are one rule in two languages, and so are `discover.streak` and `streak` beside it. Both pairs are driven from one committed fixture, `tests/fixtures/feed-health/one-result-per-run.csv`: nine rows, seven runs, one strike. A second copy of those rows in each language is a fixture that drifts, and a page that quietly disagrees with the run that produced it is the defect the shared rule exists to remove.

## The broken list needs its denominator

Naming only the broken feeds is the right list and half an answer. Four broken
feeds out of eight is a collapse; four out of two hundred is a Tuesday; and the
page drew both identically. So the console states the other half in one
sentence above the list - **how many feeds have never failed, out of how many
were asked, over how many runs** - and names the clean ones behind a
disclosure.

`reliability()` in `frontend/src/lib/feed-health.ts` is that rule, and it reads
the same `failing()` the quarantine reads, so the two halves of the section
cannot disagree about what a failure is. Three facts it settles:

- **A feed nobody has asked is in neither count.** A record of nothing but
  `skipped` rows is a rest, not a clean run of reads, and counting it as clean
  is how a dead feed joins the reliable list.
- **A polite refusal is not a failure**, here as everywhere else. A source
  honouring its own `robots.txt` has not broken.
- **The span is the whole record, not the page's window.** The streak beside
  each feed is already read that way, because the pipeline rests on the whole
  count. Two spans in one section is the defect the shared window exists to
  remove.

**A shallow record says so instead of printing a claim.** Two runs deep, "has
never failed" means "did not fail twice". Under `console.min_attempts_for_rate`
runs the sentence prints the same counts and says the record is too shallow to
read as reliability - the same knob, and the same question, as the stage rates
one section above.

Measured 2026-09-01 over the committed ledger: 5,291 rows, 182 feeds asked, 34
runs, **156 of 182 have never failed**, and 26 have. The 26 are why the list
also gained `console.feed_rows`, a cap of ten with the remainder stated in one
sentence: a ranking is read from the top and its tail is a number, never
another page of rows.

### Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A ranked "ten most reliable feeds" | Every key it could rank on ties. A feed is read once a run, so a feed that never failed has answered on every run it was asked, and the record is about 34 runs deep. `collect.max_per_source` is 2, so what a feed may carry is capped as well. A top ten of a hundred-and-fifty-way tie is charting a constant. |
| Rank by items yielded | It counts entries in a feed, so it ranks the firehose rather than the reliable. |
| A share instead of a count | The number an operator acts on is how many feeds are named below, not a percentage. `156 of 182` carries both. |

## Design rationale

The record came before the quarantine, and that order was the point: you cannot quarantine what you never measured. A rule that skips a feed after five failures is worthless without five recorded failures to read, and writing the rule first would have meant inventing the evidence.

Making a zero-item `200` a failure is the finding that justifies the whole ledger. Every other failure mode is visible in a log line at the moment it happens. A feed that quietly stops carrying entries looks healthy in every single run and is only visible as a shape across runs, which is exactly what a ledger is for.

The self-lifting rest is there because the alternative was tested by imagination and failed: a quarantine that only a human can lift is a deletion with extra steps, and the human who has to lift it will not be reading a CSV on a Sunday.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A run that edits `config/sources.json` | A robot deleting sources a person curated, in a commit nobody reviewed. |
| A quarantine only a human can lift | A deletion with extra steps. A source that recovers stays dead until someone reads a CSV. |
| Counting a robots refusal as a failure | Punishing a site for saying no, and quarantining a source that is behaving correctly. |
| Letting a robots result clear the streak | A dead address behind a site that says no would launder its record on the run after every failure, and could never reach a rest. It is not evidence either way. |
| Decrementing the streak one success at a time | A feed that recovered on the fifth day would still be resting on the ninth, for failures it has already answered. The streak asks whether the endpoint is broken now. |
| Deduplicating in Collect only, and leaving the committed shards as they were | The 555 repeats already on record would keep being read, and every reader of the file assumes the key is unique. |
| Settling repeats only before the write | The write reads a checkout frozen at the commit the run was triggered at, so it cannot see what a sibling attempt pushed afterwards. That is precisely the case that makes the repeats. |
| One credibility score across permission, availability, yield and editorial value | Four different questions with four different remedies. A single number tells an operator something is wrong and nothing about what to do. |
| Treating a zero-item `200` as success | The most common way a feed dies would be invisible, and the ledger would only catch the failures that were already obvious. |
| A separate knob for "skips before retry" | Two numbers answering one question. When they drift apart nobody remembers which was meant. |
| Backfilling `endpoint_key` from today's `config/sources.json` | The configured URL may have moved since a row was written, so the guess would file a later retirement against an address that never failed. |
| Inserting the five new columns beside the ones they relate to | The header guard compares the whole list, and an appended column is what keeps the old header a readable prefix of the new one. A cell inserted in the middle moves every historical value one place right under a reader that maps by position. |
| Retiring an address on 403, 404, a paywall, an empty feed or zero yield | None of them says the address is permanently gone, and each would eventually remove unique primary or regional reporting. |
| Retiring an address on five `410` results rather than five distinct runs | A job that is re-run keeps its run id, so one bad afternoon retrying itself would retire an address on its own. |
| Letting an empty `200` clear the pending `410` count | It is evidence that the feed is broken and no evidence that the address is alive, so it would let a dead server launder its record by returning an empty document. |
| Dropping every resting endpoint from the feed floor | A rest lifts itself, so one afternoon of outages would take a desk dark for a problem that was over by the evening. |
| Backfilling an endpoint key so a retirement could rest on older rows | The address may have moved since, so the retirement would be filed against one that never failed. Waiting five runs costs a day and buys a decision that is true. |
| Persisting a mutable status per feed instead of deriving it | A flag is a read-modify-write over the whole history, and two runs racing on it lose rows. Every state here but the retirement is derived from immutable events, and the retirement is the one that is permanent. |
| Writing no health row for a retired address | The ledger means one row per feed per run, and the console's denominator reads it. A desk with a silent feed would look like a desk with fewer feeds. |
| Logging feed results instead of committing them | A log is gone with the run. The next run needs to read what the last four did (Rule #1). |
| Recording only failures | You cannot tell "failed five times out of five" from "failed five times out of two hundred" without the successes. |

## See also

- [discovery.md](discovery.md) - the source list this measures, and its lifecycle rules.
- [freshness.md](freshness.md) - the other two ledgers under `state/`, and what they answer.
- [item-health.md](item-health.md) - the item-grain ledger that records planned item outcomes.
- [trust-boundary.md](trust-boundary.md) - what happens to the bytes a healthy feed returns.
- [../publishing/frontend.md](../publishing/frontend.md) - the console that renders this record.
- [../../concepts/config.md](../../concepts/config.md) - where `quarantine_after_failures` and the six knobs beside it live.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - degrade rather than fail, which is why a dead feed never fails a run.
