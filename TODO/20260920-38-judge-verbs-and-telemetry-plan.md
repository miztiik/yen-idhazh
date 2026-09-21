# The council ships, the judges measure

**Last Updated**: 2026-09-21

**Level**: 5 (a persisted contract with committed rows, a committed state tree that moves, a new meaning for a `run_id` cell, and a change to the judge's model entry)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight - the council lane and the judge lane - refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The council had no separation between its own pipeline observability and the metrics a judge produces, so a shared row was about to force judge two to file columns it cannot have. **A fifth adversarial round found the deeper fault**: the council could not be declared, built or tested without a judge present - its own record imported a judge roster, its own clock lived in a judge's config block, its repair plan opened a judge's store, and every council behaviour that had a test at all was gated through a judge's test module. **A sixth round found four more, three of them worse**: the router imports a judge at module scope, the workflow computes the council's own fan-out width out of a judge's config block, `AppConfig` imports a judge's knob module, and nothing at all owned the act of handing a tenant to the council. Four verbs name their mechanism rather than their work. And five defects the work uncovered would lose data on a live run. |
| Hard scope - in | **The ten seams that made the council depend on a judge, cut** (section 1d); the three-layer separation, written into the page that owns the council; the tenancy protocol, the tenant registry and the shipping capability a judge is reached through; the council's own shard-outcome record; the council's night plan and the repair of a dead night; the content-similarity judge's own metrics; the four verb renames and the deletion of `leg` and `fold` from the vocabulary; the five defects (a shard losing its verdicts on its own clock, the council having no run identity, the reader that cannot fill a default, the header that makes the store unappendable, and the verdict artifact a cancelled shard never writes); the measured call cost; the knob move; thinking support and the decode stamp; the store grouping under the judge slug; the line-against-holdout record; one composite action for the model block. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #2 changes what a committed `run_id` cell means - pause for sign-off. (2) **Row #8** widens a header on a store with committed rows, rewrites them, and extends a persisted key - pause for sign-off before the rewrite runs. (3) **Row #9** renames a config knob AND the workflow key that reads it, and makes the judge's block optional - if the knob and the key cannot land in one commit, stop. (4) **Row #11b** widens the record's stamp, which resets the distribution once by construction - pause for sign-off on that reset, and take its decision 6 replay **before** the reset. (5) **Row #13** renames `folded_dates`, a published schema property with committed rows behind it - pause for sign-off on the read-side migration. (6) **Row #18** moves a committed state tree - pause for sign-off on the path map before any file moves. (7) **Row #19**: if the holdout resolves fewer pairs than its floor, write the cells null and refuse the reading. (8) **Row #21a** changes the matrix width, widens the workflow permissions block and raises artifact retention - pause for sign-off on the permissions change. (9) **Row #24** rewrites the workflow that judges every night - pause for sign-off on the verb map and the matrix shape before the file changes. (10) Any row that would raise a runner budget figure (Guardrail #2). (11) **Any row that would put a judge module in the import closure of a council verb.** That is the dictum below, it is checked by row #23's second arm, and it is not a judgement call. |
| Chosen strategy | The council owns the pipe, its own execution record and the window arithmetic. Each judge owns what it measures, its own store and its own stamp rule. They meet at **one structural protocol and one shipping capability, both declared by the council, neither naming a judge**. Share the call and the plumbing, never the metric set and never the type. Owner ruling 2026-09-20, extended 2026-09-21 after the fifth round (section 1b). |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` Two, and live in two windows only: the dependency chain leaves at most two groups ready at once. |

### The dictum this plan is measured against

**The council runs one judge or many - in sequence, in parallel, or chained - and depends on none of them.** A judge's development does not wait on the council, and the council's does not wait on a judge. Owner ruling, 2026-09-21.

That sentence is worth nothing unless it is checkable, so it is five conditions and every row below answers to them.

| # | The condition | How it is checked |
| --- | --- | --- |
| 1 | `backend/idhazh/council/` imports nothing from `idhazh.similarity` and no judge contract | A static import check, row #23 arm one. The precedent is CLAUDE.md section 4, where contracts import no sibling subpackage |
| 2 | **No judge module appears in the import closure of any council verb** | Row #23 arm two, added by round six. Arm one is scoped to a directory and would never have seen `cli.py:75-78` importing four judge stages, or `app_config.py:42` importing the judge's knob module |
| 3 | Every council contract is declarable, instantiable and round-trippable with **zero judges in the repository** | No council contract names a judge type, and no council contract's field description names a judge's unit - a description is the published schema. A `Literal` with no members is not even legal Python, which is how the old roster failed this outright |
| 4 | Every council row's gates run **without a judge's test module**, and no council row waits on a judge row | Council tests live in `backend/tests/council/`. The Reckoner's `Depends-on` column carries no council-to-judge edge, which is a property of the table rather than a claim about it |
| 5 | A judge is reached **only** through a protocol the council declares, and is registered **only** from config | The council never opens a judge's store, reads a judge's stamp, or names a judge's type. `council.tenants` is a slug list; the resolver imports lazily. Registration points judge to council, never council to judge |

**One judge or N, and the shape of the night is the council's.** The night plan is a union over the tenants registered for that run, and the matrix is tenants times shards times dates under the platform's 20-job ceiling. **A chain is priced rather than assumed**: a tenant's job is pinned to the commit the run started at, so it cannot read a store a sibling committed in the same run - a chain crosses as an artifact and a `needs:` edge or it does not cross at all (row #24). **With zero tenants registered the union is empty, the plan names tonight, every job is a no-op, and every one of those steps still runs and is still asserted.** That last sentence is the test.

### The separation this plan exists to hold

| Layer | Owns | Stored | Lifetime |
| --- | --- | --- | --- |
| **Council pipeline observability** | Did the pipeline work - which shards started, which finished, which stopped on their own clock, what each cost | `state/llm-council/shard-outcomes/` | Discardable. One run a night |
| **The tenancy protocol** | The shape a judge presents to the council: its slug, the nights it is missing, and running one unit of work under a deadline. **Declared by the council, implemented by each judge, and it names no judge** | code, not data | n/a |
| **The shipping capability** | The plumbing only. Takes a validated payload a judge hands it and gets it committed. **Declares nothing about what is in it** | code, not data | n/a |
| **Judge metrics** | Entirely the judge's. Its units, its funnel, its instrument readings, its own contract | `state/<judge-id>/metrics/<YYYY>/<MM>/<DD>.csv` | The judge's to prune |

**Which readings sit where.** The council records the shard's identity, its clock, its outcome, and the aggregate cost of the work it hosted - and nothing that needs a name for the unit. The judge records units dealt, read, unusable and abandoned; whether the grammar applied; the first-token margin; and any agreement or uncertainty reading its own design produces. A judge that runs no model at all files a metrics row with no model columns, and the council's record is unchanged.

**A judge owns more than one store, and running under the council does not make any of them the council's.** The content-similarity judge owns two: `metrics/`, which is how its instrument behaved, and `merge-line-holdout-scores/`, which is how the line it produced stands against a benchmark labelled outside the loop. **The second is the one most likely to be mis-filed**, because the council is what runs it - but it measures a judge's output, so it is the judge's. The test is what the reading is ABOUT, never what executed it. A reading about the pipeline goes under `state/llm-council/`; a reading about a judge's instrument or a judge's output goes under that judge's slug, however many stores that takes.

**Why the split is not a matter of taste.** A first draft put the funnel and the margin on one shared row. The margin means "the grammar chose and the model did not" for a judge whose emitted token is the answer, and "a legitimate middle score" for a judge whose distribution is the answer. A shared column would have made one fold sum two instruments, which is the defect the judge identity exists to prevent.

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A host fingerprint on each judging shard | The council cannot say which processor ran a shard | A council reading that depends on the machine. The digest pipeline already characterises the same runner pool, and the bandwidth probe wants 1.9 GiB on a job whose two processes already hold up to 9.02 GiB of anonymous memory in 16 GB |
| Per-call spans folded into the shared span rollup | Per-call attribution. The judge's own row carries the call count, the total and the worst instead | A question the three aggregate numbers cannot answer |
| Each judging shard committing its own rows instead of uploading them | **Segments would break the job that counts the shards, not protect it.** Every checkout in the council names no ref, so each job is pinned to the commit the run was triggered at - rows a shard commits at 22:40 are invisible to a collecting job checked out at 22:00. Segments remove a conflict between many committing writers on one file; the council has one committing writer, and its day file is already settled on every write by a key carrying the run id | A judging shard whose output is too large for an artifact, or which must survive the artifact's 24-hour retention. Neither is true today |
| The council running the compaction verb | It takes no ledger filter and no date filter: it folds every waiting segment and then deletes the files it read. `origin/main` carries 21 waiting files across five ledgers right now. A council run would fold and delete all 21 while committing only its own folders. **And it raises rather than skips on a directory naming an unregistered ledger** - it is the first step of the digest run's planning job, so one unregistered directory stops publishing five times a day | **Nothing. This is refused for as long as the verb has no filter**, and it is a separate refusal from the one above |
| A shared judge metric schema | Nothing. Each judge declares its own | Never. This is the defect the plan exists to remove |
| A `Judge` base class, protocol or registry | The second judge duplicates the stage shape, about 150 lines | A third judge sharing three of the four steps |
| One workflow per judge | Every judge shares one schedule and one runner label | A judge needing different weights or a different cadence |
| The independent second-opinion judge | The holdout stays labelled outside the loop, which is correct but unmaintained | The six questions in the second-judge handover being answered |
| A real judge-against-holdout measurement | Nothing measures whether the JUDGE agrees with the labels, only whether the LINE does | A budget: 200 pairs at 94.53 s a pair is 5.25 h on one job |
| The summary-quality judge's own stages | Plan 36 owns them | Plan 36 reaching its scoring row |
| New console panels | The judgement console already renders the holdout against the applied line | An operator asking for something the committed rows cannot answer |
| Renaming `backend/var/judge/` | The scratch directory keeps a word naming one loop's selection | The parallel work already moving production artefacts out of the code tree |

## Section 1 - Status Reckoner

**A `Parallel-group` letter is one pull request, not one row.** Rows sharing a letter are written together, gated once and merged once, and are chained in `Depends-on` where they write the same files.

**Every group is on exactly one side of the line.** No pull request carries both a council row and a judge row, and that is not tidiness - it is what makes a council group's gates runnable with no judge present (dictum condition 4). **Round six caught group F breaking this**: it bundled the council's own record with three judge contracts, so the council lane could not merge until a pull request full of judge columns merged. F is split. Three groups are marked shared: the stamp every side may declare, the model boundary every caller uses, and the vocabulary scrub that touches both - and none of them names a judge.

| Group | Side | Pull request | Rows |
| --- | --- | --- | --- |
| A | council | The council gets a package: the tenancy protocol, `ShardResult` and the shipping capability | 15a |
| B | council | The council's clocks and its fan-out width move to a council block | 9 |
| C | council | The council bounds its shard and ships whatever it wrote | 1a |
| D | council | The council knows which run it is | 2 |
| E | council | The separation and the dictum, written where the next agent reads it | 3 |
| F | shared | The call stamp, and the council's own record | 4, 5 |
| G | judge | The content-similarity judge's own persisted shapes | 6, 7, 8 |
| H | judge | The judge stops safely, and its bound reads a measured number | 1b, 10 |
| I | shared | The model layer offers both spans and says what it decoded | 11a |
| J | shared | The verbs name their work, and two borrowed words leave | 12, 13 |
| K | judge | The judge reads its own margin and fills the stamp | 11b, 14 |
| L | judge | The judge fills its metrics and registers as a tenant | 15b |
| M | process | The model block becomes one composite action | 16 |
| N | council | The council runs verbs of its own over a tenant list | 24 |
| O | council | The council runs the tenant and files its own outcome row | 17 |
| P | council | The config check moves to the tenant that owns the number | 25 |
| Q | judge | The store groups under the judge that fills it | 18 |
| R | judge | Where the judge's merge line stands against its holdout | 19 |
| S | council | The council asks every tenant what it is behind on | 21a |
| T | judge | The judge answers which nights it is behind on | 21b |
| U | council | The guard is renamed, and the council runs green with no judge | 22, 23 |
| V | process | The plan pointer | 20 |

**Group A lands first and it is the whole point.** The council has no code today - `git grep -i council -- backend/idhazh` returns nothing, and its three workflow jobs are the judge's four verbs - which is why every venue row in the earlier draft had to reach into the tenant. There was no venue. A creates one.

**The council's track is A, B, C, D, E, F, N, O, P, S, U - eleven pull requests, thirteen rows, one of which (row #4) is shared, and not one of them depends on a judge row.** That is the dictum made structural rather than asserted, and round six is what made it true: the old graph had two council-to-judge edges, one direct (#22 waited on the vocabulary scrub) and one hidden inside group F's bundling. Both are cut. It is also why a later split into two plan-docs would be mechanical.

**T lands after S, and that is the round-four correction kept.** The repair re-judges a date, and re-judging without the extended pair key from G and the widened record stamp from K discards the very work it re-does.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 15a | The council's package, the tenancy protocol and the shipping capability | - | A | DONE | - | 990 | worker |
| 9 | The council's clocks and its fan-out width move to a council block | - | B | PENDING | - | - | - |
| 1a | The council bounds its shard and ships whatever it wrote | 9, 15a | C | PENDING | - | - | - |
| 2 | The council knows which run it is | 1a | D | PENDING | - | - | - |
| 3 | The separation and the dictum, written where the next agent reads it | - | E | PENDING | - | - | - |
| 4 | The judge-call stamp, declared once and naming no judge | - | F | DONE | p38f | - | worker |
| 5 | The council's own shard-outcome record | 4 | F | DONE | p38f | - | worker |
| 6 | The content-similarity judge's own metrics | 5 | G | PENDING | - | - | - |
| 7 | The content-similarity judge's merge-line benchmark record | 5 | G | PENDING | - | - | - |
| 8 | The pair row gains the stamp, and the store is rewritten | - | G | PENDING | - | - | - |
| 1b | The judge stops safely and flushes as it goes | 1a | H | PENDING | - | - | - |
| 10 | The judge's own bound reads a measured number | 9 | H | PENDING | - | - | - |
| 11a | The model layer offers both spans and says what it decoded | - | I | DONE | - | 989 | worker |
| 12 | The four verbs name their work | 9, 24 | J | PENDING | - | - | - |
| 13 | `leg` and `fold` leave the vocabulary | 12 | J | PENDING | - | - | - |
| 11b | The content-similarity judge reads its own margin | 11a | K | PENDING | - | - | - |
| 14 | The judge fills the stamp | 8, 11b, 13 | K | PENDING | - | - | - |
| 15b | The content-similarity judge fills its metrics and registers as a tenant | 6, 14, 15a | L | PENDING | - | - | - |
| 16 | The model block becomes one composite action | - | M | PENDING | - | - | - |
| 24 | The council runs verbs of its own over a tenant list | 2, 15a, 16 | N | PENDING | - | - | - |
| 17 | The council runs the tenant and files its own outcome row | 5, 15a, 24 | O | PENDING | - | - | - |
| 25 | The config check moves to the tenant that owns the number | 9, 24 | P | PENDING | - | - | - |
| 18 | The store groups under the judge that fills it | 17 | Q | PENDING | - | - | - |
| 19 | Where the content-similarity judge's merge line stands against its holdout | 7, 18 | R | PENDING | - | - | - |
| 21a | The council asks every tenant what it is behind on | 15a, 17, 24 | S | PENDING | - | - | - |
| 21b | The content-similarity judge answers which nights it is behind on | 8, 11b, 12, 21a | T | PENDING | - | - | - |
| 22 | The guard that stops a shard committing is renamed and re-reasoned | 16, 21a | U | PENDING | - | - | - |
| 23 | The council runs green with no judge in the repository | 15a, 17, 21a, 24, 25 | U | PENDING | - | - | - |
| 20 | The plan pointer | 19, 21b, 23 | V | PENDING | - | - | - |

**Two lanes, not two windows.** `Parallel N = 2` is the council lane and the judge lane. **No council row waits on a judge row anywhere in the graph** - which is a property of the table above rather than a claim about it. **They do share files**, and round seven counted nine: the council workflow, the router, the workflow test module, the ledger, two knob modules, `AppConfig`, the committed config and the council's own doc page. So the two lanes rebase against each other, and the order inside a lane is what the `Depends-on` column is for. The claim that survives is the one that matters: either lane's gates are green with the other lane's rows absent.

## Section 1a - The words this plan deletes

**The plain-meaning test.** A word earns a name only when its ordinary English meaning is what the thing does. Where you have to know which field it was borrowed from, it is a second name for something that already has one, and it is deleted rather than replaced.

| Word | Borrowed from | What it actually meant | Becomes |
| --- | --- | --- | --- |
| `leg` | relay racing | one shard of the judging work | **deleted.** `shard` is already the column, the knob and the count. **Test names included** - a scrub that leaves the word in a test's own name has not been done |
| `fold` | functional programming | collect the shards' output, commit it, count it into the record | the job is `collect`; the verb is `count-verdicts`; prose names the action |
| `draw` | a lottery | the pairs selected for judging | the verb is `pick-item-pairs`; the file is `picked-pairs.csv` |
| `arm` | clinical trials | one configuration of a comparison run | already deleted on 2026-09-15, in favour of `cases` - one test case a pass, the first being the baseline the rest are read against |

**Prose names the action, not the job.** "A day with a missing shard is not counted into the record" replaces "the fold refuses a partial day". This is the half that keeps coming back after the identifiers are fixed.

## Section 1b - What seven adversarial rounds changed

Each line is a claim a worker would otherwise re-derive. Seven rounds ran against earlier drafts, 2026-09-20 and 2026-09-21. Round three split a stamp that had started meaning three things again, added a sixth pair column and extended a persisted key; round four found the catch-up scheduled before the key it depends on, four sign-off triggers naming the wrong rows, and a three-decision chain that latched the council into judging nothing for ever; **round five asked the question none of the first four had - can the council be built and tested with no judge in the repository - and the answer was no, in six places**; **round six found four more seams, an arithmetic error that refuses a legal config, and three decode defects**; **round seven reviewed round six's own fixes and found one of them could not be built at all, one argued from a premise the code contradicts, and one blocked by a config value nothing in the plan changes** (section 1d).

| The draft said | The code says | What changed |
| --- | --- | --- |
| `if: always()` on the verdict upload fixes the cancelled shard | The shard builds a list and writes once after the loop, so a cancelled shard has written nothing and the upload takes an absent path | Rows #1a and #1b: the council bounds the shard and ships what it wrote; the judge stops safely and flushes as it goes |
| A row may inherit `CsvContract` | It is a `typing.Protocol` in the ledger; mixing it with a pydantic model is a metaclass conflict, and the import is circular | Every new row subclasses `Contract` |
| The pair row inherits the stamp mixin | Base fields are collected first, so the header reorders and the append check raises - the store becomes unappendable | The pair row declares the columns in its own body, at the tail |
| `from_csv_row` fills absent keys from defaults | It maps an absent cell to empty string, converting only when the default is `None`; a Literal refuses it and the loader stops the read | Named as new code, added to the existing by-name branch - not a general predicate, which would also pop `version` |
| The council reuses a run id | It has none, and the pair rows carry the digest run's | Row #2 mints one, from the day the council **runs** - the compaction reads a run id's first ten characters as the day the run opened and publishes it as a lag figure |
| Spans come from the existing closed set | The rollup has five members and silently skips anything else | Spans dropped entirely (scope-out), and the judge's row carries three aggregate numbers |
| The fingerprint goes before the first model call | The probe wants 1.9 GiB, and the judging job's two processes hold at most 9.02 GiB of anonymous memory that actually has to fit in 16 GB | The fingerprint is dropped entirely (scope-out), which removes the risk rather than ordering around it |
| The fold stages what the shards wrote | A shard's files are on its own runner, and the collecting job downloads only verdicts | Row #15a gives the council its own artifact path, which is what it already runs for verdicts |
| The council runs the compaction verb | It takes no filter: it files away every ledger waiting in transit and deletes the transit copies. The digest run's are often still waiting at 22:00 | The council does not run it. Its own artifact path has no shared transit to collide on, and the segment design it declines solves a conflict the council does not have - it has one committing writer, not eight |
| The plan updates the plan-queue page | A gate fails any pull request that edits it, and it already names this plan | The page is left alone |
| Widening the probability window fixes the margin | The margin is the top two of whatever came back, and the top two do not move | The margin is taken over the three verdict-opening ids, renormalised |
| A grammar failure writes `usable` false | A nullable verdict makes two failures compare equal, so `usable` goes true with no verdict and the row's validator refuses that shape | The agreement test gains a null check in the same change |
| The council's record may carry `judge_id: JudgeId` | A `Literal` with no members is not legal Python, so the council's own contract could not be declared in a repository with no judges | The column is a slug-patterned `str`; the roster is deleted (section 1d, seam 1) |
| The night plan reads the judge's distribution record | `folded_dates`, the stamp rule and the reset semantics are all judge internals, and the plan's own decisions 4 and 5 were written about them | The council declares a protocol and asks; the judge answers (seam 2) |
| Only field descriptions carry `fold` | `folded_dates` is a **field name** and a published schema property with committed rows behind it | Row #13 gains a read-side migration and a sign-off trigger (seam 6) |
| The council has somewhere to put council code | `git grep -i council -- backend/idhazh` returns nothing. **The council has no code at all today** - its three workflow jobs are the judge's four verbs | Every venue row had to reach into the tenant because there was no venue. Row #15a creates the package |
| The protocol may return the judge's metrics contract | `CouncilShardOutcome` needs an outcome and four model-cost columns, and row #6 says a judge's metrics columns are shared with nobody | Row #15a declares `ShardResult`, council-owned, carrying the metrics as an opaque `Contract` (seam 7) |
| The council can get a verb and a matrix width without touching a judge | `cli.py:75-78` imports four judge stages at module scope; `llm-council.yml:143` reads the judge's `shards` knob to size the council's own fan-out | Row #24: council verbs, a config tenant list, lazy resolution, and the width off the protocol (seams 8 and 10) |
| `AppConfig` couples two blocks as data | `app_config.py:42` imports `SECONDS_A_CALL` from the judge's `knobs/placement.py` at module scope, so no council module can read config without the judge | Row #25 moves the arm to the tenant; row #23's boundary arm widens to the whole import closure (seam 9) |
| The date cap multiplies the shard's time budget | Dates are separate jobs with separate per-job bounds, so multiplying compares parallel work against a per-job number - and refuses a legal config at two dates | Row #21a deletes the multiplier. The axis that actually compounds inside one job is tenants, and row #24 makes each tenant its own job |
| The margin is taken over the three verdict-opening ids | `prompt.py:159 first_token_ids` returns the ids of the **bare** words, and the grammar's own comment at `prompt.py:52` says the **space-prefixed** token is "the model's natural first choice" | Row #11b sums per verdict over all six legal strings before renormalising, and gains an oracle that goes red on the bare-only reading |
| The thinking span is the answer span minus its schema | `server.py:733` strips only `json_schema`, so on the grammar route span one inherits `grammar` and `n_probs` - it is constrained to three verdict words and cannot write a thinking block at all | Row #11a strips both, and asserts on the **posted body** rather than on a recorded reply |
| The reading type drops the token counts | `server.py:370-371` - `Completion` already declares `prompt_tokens` and `completion_tokens` and fills them at 928 and 944. The type that drops them is `similarity/judge.py:47`, a judge module | Row #11a's decision is struck; **row #14 widens `Reading` and `Judged`**, which is where the counts are actually lost |
| `ShardResult` may carry the judge's row as a `Contract` field | Measured on this repository, pydantic 2.13.4: a base-typed field dumps as `{'metrics': {'version': ...}}` and every subclass column is gone, silently. `Contract` also declares no `csv_row` - that is `CsvRecord` at `ledger.py:277` | `ShardResult` is a frozen dataclass; `metrics` is typed `CsvRecord` and is never dumped (section 1c) |
| The margin is taken over three bare verdict ids | `judge.py:87 margin_of` sorts **every** returned choice and subtracts the top two. It never calls `first_token_ids`, which `judge_shard.py:76` runs once a shard as a vocabulary refusal and discards. **82 committed rows carry a non-null margin** | The three-id reading never existed. Row #11b buckets the window **by prefix** per verdict, and says what an unattributable token does |
| This judge can open the thinking channel today | `config/models/qwen3.5-9b-q4km.json:50` has `thinking_close: null`, so `thinks` is False and `thinking_span` raises. The channel lives in a second entry file that also moves the summariser's decode | Row #11b gains a config decision and a model role of its own. It is a Level 5 change, not a Level 2 |
| `decode_digest` records whether the model thought | The only key a thinking envelope moves is `prompt`, and `prompt` is a named exclusion from the digest. The digest is byte-identical either way | The stamp gains a seventh field for the envelope, and the pair row a seventh column |
| The selection verb maps onto the protocol | Four judge verbs, three protocol members. `llm-council.yml:152` runs a selection step the council has no member to call | The protocol gains `prepare`, and `prepare`/`settle` file outcome rows at reserved shard values |
| The collecting job stages what a tenant wrote | `llm-council.yml:358` and `382-384` stage one judge's four paths as literals | `committed_paths` on the protocol (seam 11) |
| An empty matrix is a skipped job | No workflow in this repository has ever built a zero-width matrix, and none carries an `if:` guard on a matrix job. A matrix vector of `[]` is a strategy-evaluation failure, and the run goes red | Row #24 adds the guard and asserts the guard string rather than asserting a job runs |

## Section 1d - The eleven seams that coupled the council to a judge

Round five asked one question: **take every judge out of the repository - does the council still declare, build, test and run?** It did not, in six places. **Round six ran three independent reviews against the cut version and found four more**, three of them worse than anything round five caught - because round five looked at contracts and rows, and round six looked at the router, the workflow, the config import and the return type. **Round seven reviewed round six's own fixes and found one more seam, plus a cut that could not be built at all** (seam 7 below). Each seam is cut in this plan, each cut is a decision on a named row, and each is checkable.

| # | The seam | Why it breaks the dictum | Where it is cut |
| --- | --- | --- | --- |
| 1 | **A central `JudgeId` roster**, typed onto the council's own record | The venue's published contract changes when a tenant moves in, and judge three regenerates `council-shard-outcome.schema.json` for a shape that did not change meaning. With zero judges the type is `Literal[]`, which is not legal Python | Row #4 deletes it. The council's column becomes a slug-patterned `str` with no membership check; a judge keeps a one-member `Literal` in its own module |
| 2 | **The night plan opens the judge's store** and applies the judge's stamp and reset rules | The council cannot compute a night plan with no judge, and judge two's different stamp rule would be a second branch inside a council module | Row #21a declares `nights_outstanding` on a tenancy protocol and owns the window and the union; row #21b is the judge answering it |
| 3 | **The council's clock lives in the judge's config block**, and row #9 was moving it further in | With zero judges the council has no timeout, and the block is nested under the digest pipeline's assemble stage | Row #9 moves the bound and the wrap-up margin to a council block. The flush stays with the judge - it is denominated in pairs |
| 4 | **The shipping capability's gate is a judge's metrics contract** | The venue goes red when a tenant's columns move, and the venue's green depends on a tenant existing | Row #15a gates it on a throwaway `Contract` subclass declared in the council's own test module |
| 5 | **The council's own outcome row is written by the judge's stage** | The venue's paperwork is filed by a tenant, so only a tenant's test can assert it was filed | Row #17: the council runs the tenant and files its own row on the way out |
| 6 | **`folded_dates` is a field name, not a description** | Row #13 decision 5 said no payload migrates. It does | Row #13 gains the read-side migration and a sign-off trigger |
| 7 | **The protocol returns a judge's metrics contract, and the council's row needs five values that are not on it** | `CouncilShardOutcome` declares an outcome and four model-cost columns. Row #6 says every column on a judge's metrics contract is that judge's own and shared with nobody. So the council could fill its own row only by reading named attributes off a tenant's contract - seam 5 cut in prose and re-opened in the type | Row #15a declares `ShardResult`, a council-owned **frozen dataclass**. **Round seven had to re-cut this**: the first version was a pydantic model with `metrics: Contract`, and a base-typed field silently drops every subclass column on `model_dump()` - measured, section 1c |
| 8 | **The router and the workflow are one judge's four verbs** | `backend/idhazh/cli.py:75-78` imports four judge stages at module scope, so deleting the judge makes every council verb fail at import. `llm-council.yml:143` computes the council's own fan-out width by reading `assemble.same_story.adaptive_dedup_threshold.shards` - a judge's config path - so with no judge the planning job dies before it plans anything | Row #24: council verbs over a config-declared tenant list, resolved by lazy import; the fan-out width comes back from the protocol |
| 9 | **`AppConfig` imports the judge's knob module at module scope** | `contracts/app_config.py:42-46` imports `SECONDS_A_CALL` from `knobs/placement.py`. Every council module that calls `config.load()` imports `AppConfig`, so deleting the judge means the council cannot read its own config | Row #25 moves the constant to the tenant that owns it. **The module itself stays** - round seven found it also supplies `AssembleConfig`, `LensWeightsConfig` and `PlacementConfig`, which are the digest pipeline's, so the goal is one constant leaving, not a module vanishing |
| 10 | **There is no tenant registry, so nothing hands the council a tenant** | The protocol is declared, the judge implements it, and no row owned the act of registration. "The council resolves slugs from its own config" was prose with no knob and no row behind it | Row #24 adds `council.tenants`; **row #15b writes the slug into it**, which round seven found nothing was doing - the plan would have closed with an empty list and a council that judged nothing |
| 11 | **The collecting job stages one judge's four store paths as literals** | `llm-council.yml:358` and `382-384` name `state/story-similarity/...` directly, and `REGENERATE_COMMAND` at 379 is one judge's verb. A second tenant's output is never committed, and the council reaches a tenant by a path it spells rather than through the protocol | Row #24: `committed_paths` on the protocol, and the stage list built from the tenant tuple |

**Seams 7 to 11 are one problem seen from five altitudes: nothing owned the act of handing a tenant to the council.** The fifth round cut the couplings visible in the contracts and missed the one in the wiring, because the wiring does not exist yet and an absent thing shows up in no grep.

**What a fake tenant is, and why it is not a mock** (Guardrail #7). It is a real protocol implementation and a real `CsvRecord`, declared in the council's own test module, with nothing stubbed and nothing returning a plausible value it did not compute. Where it carries a `Contract` subclass it declares one changelog entry, because the base class refuses a subclass without one, and it hand-declares `csv_row`, `csv_columns` and `from_csv_row` like every other CSV contract. It has no `__schema_stem__` registered in the `CONTRACTS` tuple, so the exporter - which iterates that explicit tuple - never sees it and the drift gate never reports an orphan. No test declares one today; this is a new pattern, and it is the one that makes the zero-judge conditions testable rather than merely stated.

**What this does not do.** It does not make the council useful with no judge - a venue with no tenants judges nothing, and that is correct. It makes the council *buildable, testable and green* with no judge, which is what "the development of each is independent" has to mean if it means anything.

## Section 1c - The contracts, settled before any row is written

Guardrail #3. Types are the aliases in `backend/idhazh/contracts/base.py`. **Every new contract is registered in the `CONTRACTS` tuple in `backend/idhazh/contracts/export.py`** - that tuple writes `schemas/` and the frontend types, and the drift gate derives both sides from it, so an unregistered contract fails with a message about an orphan file rather than a missing registration.

### There is no `JudgeId` roster, and that is seam 1 cut

An earlier draft declared `JudgeId = Literal["content-similarity-judge", "summary-content-quality-judge"]` and typed the council's own record with it. **It is deleted.** Three reasons, and the first is the plan contradicting itself two paragraphs later.

- **A roster is the opposite of "a judge's identity is a property of its stage".** That sentence is right and it is kept; a central list of who may exist is a tunable in everything but name.
- **It puts the council's published contract downstream of the roster.** Judge three would regenerate `council-shard-outcome.schema.json` and take a changelog entry on a contract whose meaning did not move.
- **It is not declarable with zero judges.** `Literal[]` is not legal Python, so the council's record could not be imported in a repository with no judge in it - condition 3 of the dictum, failed outright.

**What replaces it, and what each side gives up.**

| Who | Type | What it gives up |
| --- | --- | --- |
| The council's own rows | `str`, `SLUG_PATTERN`, `max_length=64`. No membership check | A typo files a row under an unrecognised name and a group-by can return a slug nobody owns; the generated TypeScript is `string` rather than a union. All three are reporting nuisances, and the slug reaches the council from the tenant's own module constant, so a typo is a source edit a reviewer sees |
| A judge's own rows | A one-member `Literal` in that judge's module, beside `JudgeModelId` and `ScorerModelId`, which already live in `story_similarity_pair.py` | Nothing. A closed set, closed by the only party who can honestly close it |

**The council needs to RECORD which tenant ran. It never needs to KNOW which tenants can exist.**

### The tenancy protocol (`backend/idhazh/council/tenancy.py`)

A `typing.Protocol`, structural, declared by the council, naming no judge. It is the whole of what a judge presents: **seven members, and the count is written once here.**

| Member | Shape | Who answers |
| --- | --- | --- |
| `judge_id` | `str`, the slug | The judge, as a module constant |
| `shard_count` | `int`, `ge=1` | The judge. **A tenant with no model returns 1** - sharding exists because a model is slow, and a pure-Python tenant that got four jobs would pay four weights restores for work that uses none of them |
| `committed_paths` | `tuple[str, ...]` | The judge. The store paths its own work writes, which the collecting job stages. Without this the workflow stages one tenant's four paths as literals and a second tenant's output is never committed |
| `nights_outstanding(*, window)` | `tuple[DateStamp, ...]` - the dates this judge has not counted, inside a window the council hands it | The judge, from its own store, under its own stamp rule and its own reset semantics |
| `prepare(*, date, run_id)` | `ShardResult` | The judge, once per date before any shard. This is the selection step, and **round seven found it had no member at all** - four judge verbs were being mapped onto three protocol members, leaving the verb that picks the work with nothing to call it |
| `run_shard(*, date, run_id, shard, shards, deadline)` | `ShardResult` | The judge, which decides what a unit is and when it is safe to stop |
| `settle(*, date, run_id)` | `ShardResult` | The judge, once per date after every shard has reported - counting, fitting, or nothing at all |

**Every member that does work takes `run_id`.** Round seven found `settle` taking one and `run_shard` not, while the judge's own metrics row is keyed on `("date", "run_id", "shard")` and the pair row gains `judged_by_run_id` - so the judge was being asked to fill a required column it was never handed.

**The member is `run_shard`, not `judge`.** Row #12 decision 3 already rules that a tenant whose emitted token is discarded and whose distribution is the answer is a scorer rather than a judge. A council-declared member named `judge` puts one tenant's shape in the one file that must not carry it.

**`prepare` and `settle` are shard-shaped on purpose.** Both return a `ShardResult` and both get an outcome row, at reserved shard values below zero: `prepare` files at `-1` and `settle` at `-2`, with `shards` carrying the run's real width. Without this a settle that dies leaves the venue blind, which is the exact defect seam 5 exists to close. `ShardOutcome` needs no fourth member - a settle that had nothing to count is `nothing_to_do` like any other unit.

### `ShardResult` - what a tenant hands back (`backend/idhazh/council/tenancy.py`)

**Seam 7 cut, and round seven caught the first cut being uncuttable.** The protocol used to return "the judge's own metrics contract instance", while `CouncilShardOutcome` declares an outcome and four model-cost columns that row #6 rules are shared with nobody. The first fix declared `ShardResult` as a pydantic model carrying `metrics: Contract | None`. **Measured on this repository, pydantic 2.13.4, 2026-09-21: a field typed as the base class silently discards every subclass column on `model_dump()`** - a probe carrying `pairs_dealt=7` dumped as `{'outcome': 'completed', 'metrics': {'version': '2026-09-21'}}`, with no warning and no error. The payload the whole seam-7 cut exists to carry was being thrown away by the type chosen to carry it.

**So `ShardResult` is a frozen dataclass, not a pydantic model.** It crosses one function boundary inside one process and is never persisted as itself, so it needs no validation, no schema and no stem - and having no `model_dump` is precisely what stops anything flattening the tenant's row.

| Field | Type | Why the council owns it |
| --- | --- | --- |
| `outcome` | `ShardOutcome` | The council files it and never infers it |
| `model_calls` | `int \| None` | **Null, not zero, for a tenant with no model.** The tenant decides which, because only it knows whether it has one |
| `tokens_in` | `int \| None` | Prompt tokens across the unit |
| `tokens_out` | `int \| None` | Generated tokens across the unit |
| `model_seconds` | `float \| None` | Wall clock inside model calls |
| `metrics` | `CsvRecord \| None` | **Opaque, and typed as the ledger's own protocol rather than as `Contract`.** `Contract` declares no `csv_row`, no `csv_columns` and no `from_csv_row` - those are `CsvRecord` and `CsvContract` at `ledger.py:277` and `293`, which all 24 CSV contracts hand-declare. A value typed `Contract` cannot be written as a row at all |

The council calls `metrics.csv_row()` and the class-side `csv_columns()` and writes what comes back. **It reads no field by name, and it never dumps the object.** A tenant with nothing to report returns `None`.

**The council owns the window - floor, length, per-night cap - and the union arithmetic. The judge owns what is missing and why.** So a judge with a different stamp rule, a different store shape or no stamp at all is a different implementation of seven members, not a second branch inside a council module.

**Registration points judge to council, never council to judge - and row #24 is what makes that true.** `council.tenants` is an ordered slug list in config; the resolver maps a slug to a module path and imports it **lazily, inside the function**, so no council module carries a judge in its import closure. A slug with no module is a config error the council reports by name. Removing a judge from the repository is then a config edit and a directory delete, never a router edit.

**The static import check has a ceiling, and it is stated here rather than discovered later.** Row #23's closure arm parses import statements, so it goes green over a verb name hard-coded in the council's router and over a config path spelled in a shell step. Those are strings, not imports. **Row #24 is what removes them**; row #23 is what stops them coming back as imports.

**One, N, sequence, parallel or chain.** The council holds an ordered tuple of tenants for the run. Parallel is the matrix widening to **tenants times shards times dates** under the platform's 20-job ceiling; sequence is that tuple's order within one job. **A chain is not free and row #24 prices it**: every checkout in the council names no ref, so a tenant's job is pinned to the commit the run started at and cannot see a store a sibling committed during the same run. A chain therefore crosses as an **artifact** and a `needs:` edge, never as a commit - and until a second tenant exists there is nothing to chain, so row #24 declares the shape and builds only the single-tenant case. **With an empty tuple every step still runs and every step is still asserted.**

### `CouncilShardOutcome` - the council's own record (`backend/idhazh/contracts/council_shard_outcome.py`)

`class CouncilShardOutcome(Contract)`. `__schema_stem__ = "council-shard-outcome"`. One row per shard per run. Key: `("date", "run_id", "shard")`. Store: `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv`.

**It carries nothing that needs a name for the unit of work.** That is the whole of the separation: this row is about the pipeline, and it reads the same whether the judge it hosted made four hundred model calls or none.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date this run judged |
| `run_id` | `RunId` | - | The council run, minted from the day the council ran |
| `judge_id` | `str` | `SLUG_PATTERN`, `max_length=64` | Which tenant this shard hosted. Without it a night running two judges files rows nobody can attribute. **Recorded, not validated**: no membership check, because the council records who ran and never declares who may exist. The slug arrives from the tenant's own module constant, so a typo is a source edit a reviewer sees |
| `shard` | `int` | `ge=0` | Which shard |
| `shards` | `int` | `ge=1` | How many the work was split across. A run reporting fewer shards than it was split for left work unread, and the pair alone says so |
| `outcome` | `ShardOutcome` | - | `completed`, `stopped_on_deadline`, or `nothing_to_do`. A shard killed by the platform writes no row at all, and absence against a known shard count is what says so |
| `started_at` | `Timestamp` | - | When the shard began |
| `seconds_spent` | `float` | `ge=0` | Wall clock for the shard. Not the job - the job's own clock includes a checkout and a weights restore this row is not about |
| `model_calls` | `int \| None` | `ge=0` | How many calls the hosted work made. **Null, not zero, for a tenant that runs no model**; zero for a tenant with a model whose shard had nothing to do. **One call, one count, derived from no other column** - a tenant that stopped part way through a unit of its own made the calls it made |
| `tokens_in` | `int \| None` | `ge=0` | Prompt tokens the server reported across the shard, off `Completion.prompt_tokens` |
| `tokens_out` | `int \| None` | `ge=0` | Generated tokens, off `Completion.completion_tokens` |
| `model_seconds` | `float \| None` | `ge=0` | Wall clock inside model calls. Read against `seconds_spent`, the two say how much of a shard was the model and how much was everything else |
| `host_model` | `str \| None` | `PRINTABLE_LINE_PATTERN`, `max_length=96` | The processor name, one line read from the kernel's own file. **This is not the host fingerprint** - the 1.9 GiB bandwidth probe stays refused. Without it a slow night and a slower processor read identically, and the scope-out's "the digest pipeline already characterises the pool" has no join key a council row could use |

`ShardOutcome` is a `StrEnum` in the same module, three members, because a free-text outcome is a column that splits silently on a typo.

**Every description above is a published schema property, so a judge's unit may not appear in one.** An earlier draft explained `model_calls` as "not twice the pairs - a pair refused on its first call made one call, not two", which puts one tenant's unit and one tenant's failure mode into the council's own generated contract. Row #13's rejected alternative 2 already rules that a description is the contract. **Five values come off `ShardResult`, so none of them needs a story about pairs.**

### One stamp, and why there is not a second (`backend/idhazh/contracts/judge_call.py`)

**`JudgeConfigStamp(Model)` - what the instrument was SET TO.** Grain-free, so any row may carry it whatever its unit. **It names no judge and no judge's model**: a mixin two judges share may not import either judge's module, or judge two's contract drags judge one's vocabulary in. **Each judge narrows both fields in its own row** - pydantic allows a subclass to narrow a field's type - so the closed set is kept where it can be honestly closed and absent where it cannot.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `judge_id` | `str` | `SLUG_PATTERN`, `max_length=64`, no default. **The content-similarity judge narrows it to `Literal["content-similarity-judge"]` with that default, in its own module** | Which instrument wrote this |
| `judge_model` | `str \| None` | `PRINTABLE_LINE_PATTERN`, `max_length=96`, default `None`. **The content-similarity judge narrows it to `JudgeModelId \| None`**, which already lives in its own module | Which weights judged |
| `judge_temperature` | `float \| None` | `ge=0`, default `None` | The sampler temperature, as a number. An operator reading a row needs the value, not a hash of it |
| `decode_digest` | `Sha256 \| None` | default `None` | sha256 of the canonical JSON of **every key the body posts that is not in the named exclusion list**, taken from the payload rather than from config, because a digest built off config cannot see a payload-builder bug. The exclusions are the prompt (it differs every row and would make the digest a pair id), the grammar and the model reference (both have their own columns), each carrying its reason on the line that names it. **Not a fixed count** - round six proved the six-key spelling wrong: the grammar route posts ten keys, so `stream` and `cache_prompt` sat in neither the six nor the exclusions and the key-enumeration test would have gone red on its first run. A caller on the schema route posts a different set and the same rule covers it |
| `thinking_spans` | `int \| None` | `ge=0`, default `None` | How many reasoning spans the call decoded before the answer - `0` for a cold answer, `1` under a thinking envelope. **A seventh field, added by round seven, because `decode_digest` cannot see the envelope**: the only posted key a thinking envelope moves is the prompt, and the prompt is excluded. Without this column a margin taken after reasoning and one taken cold are one population to every reader, including row #21b's stamp filter |
| `prompt_digest` | `Sha256 \| None` | default `None` | sha256 of the rendered system turn |
| `grammar_digest` | `Sha256 \| None` | default `None` | sha256 of the grammar handed to the decoder |

**There is no per-call mixin, and that is a deliberate deletion.** An earlier draft split this in two and gave the per-call half three fields - whether the grammar applied, the first-token window and one call's clock. **Nothing inherited it.** The pair row declares its own columns at the tail because inheriting reorders a header with committed rows behind it, the shard metrics row has no single call, and neither the council's record nor the holdout row involves a model. Three fields declared for a row that does not exist is speculative generality; the second judge extracts a per-call mixin when it is the second real caller.

**The per-call fields therefore live where they are used**, and each names its own grain: the pair row's `grammar_applied` means both calls of that pair opened inside the grammar, and its `first_token_probabilities` is the file-order call's window, named so because a pair makes two calls and a singular column must say which.

**A key added to the payload builder and not to the digest is a digest gone silently narrower.** The builder and the digest are held together by a test that enumerates the payload's keys and fails on one the digest neither covers nor names as excluded.

**`first_token_probabilities` is the first model-written value this loop commits.** It is safe where it lands - a quoted CSV value, never a key, never a name - and it stays there (Guardrail #11).

### `ContentSimilarityJudgeMetrics` - the judge's own (`backend/idhazh/contracts/content_similarity_judge_metrics.py`)

`class ContentSimilarityJudgeMetrics(JudgeConfigStamp, Contract)`. `__schema_stem__ = "content-similarity-judge-metrics"`. Key: `("date", "run_id", "shard")`. Store: `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv`.

**It inherits the config stamp and not the call stamp.** A shard has no single call, so a per-call grammar flag, a per-call probability window and a per-call clock have no referent here. The three shard-level equivalents are `pairs_refused`, `first_token_margin_median` and the two decode totals below.

**Every column here is this judge's own.** A second judge declares its own contract with its own columns and shares none of them.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date judged |
| `run_id` | `RunId` | - | The council run |
| `shard` | `int` | `ge=0` | Which shard |
| `pairs_dealt` | `int` | `ge=0` | Pairs the selection gave this shard |
| `pairs_read` | `int` | `ge=0` | Pairs that got a reading inside the grammar |
| `pairs_agreed` | `int` | `ge=0` | Pairs whose two order-swapped readings matched |
| `pairs_unreadable` | `int` | `ge=0` | Pairs whose items the window no longer reaches. The stage counts this today and throws it into a log line |
| `pairs_refused` | `int` | `ge=0` | Pairs where a reading came back outside the grammar. **Pairs, not calls** - a pair is two calls, so counting calls would over-count a pair that failed twice and make the identity below go red on a real event |
| `pairs_abandoned` | `int` | `ge=0` | Pairs owned and never reached, because the shard stopped on its own deadline |
| `disagreement_rate` | `float \| None` | `ge=0, le=1` | Share of read pairs whose two readings differed. Null when nothing was read - a rate over zero rows is not zero. **Per shard over read pairs**, where the line-setting gate is per day over agreed pairs; two different quantities, and the description says so |
| `unclear_rate` | `float \| None` | `ge=0, le=1` | Share of agreed pairs answered UNCLEAR. Null on an empty shard, same reason, same caveat |
| `first_token_margin_median` | `float \| None` | `ge=0, le=1` | Median gap at the deciding position, over the three verdict openings. **Not comparable to another judge's**: a flat distribution means the grammar chose here, and a legitimate middle score for a judge whose distribution is the answer |
| `decode_seconds_total` | `float \| None` | `ge=0` | Sum over the shard's calls |
| `decode_seconds_max` | `float \| None` | `ge=0` | The longest single call. A shard with an ordinary total and a bad worst call is the one that runs out of clock next |

**The identity that closes:** `pairs_dealt = pairs_read + pairs_refused + pairs_unreadable + pairs_abandoned`, enforced by a model validator. Every term is a column, including the abandoned one - without it the identity fails on exactly the shard row #1 exists to let write a row at all.

**No bare `decode_seconds` on this row.** The two totals are named for what they are, so no reader mistakes a per-call column for the typical call.

### `MergeLineHoldoutScore` - new (`backend/idhazh/contracts/merge_line_holdout_score.py`)

`class MergeLineHoldoutScore(Contract)`. `__schema_stem__ = "content-similarity-judge-merge-line-holdout-score"`. Key: `("date", "run_id")`. Store: `state/content-similarity-judge/line-holdout-scores/<YYYY>/<MM>/<DD>.csv`.

**It does not inherit the call stamp.** No judge reads anything here: the holdout rows carry no verdict, the scoring applies a threshold to a recomputed similarity, and the labels were written by a model outside the pipeline. Eight call columns would be five nulls and one asserting an instrument that never ran.

**Counts only. No precision, recall or accuracy column** - a stored rate is a rate somebody reads without its denominator, and this denominator is four.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | When the line was scored |
| `run_id` | `RunId` | - | The run that scored it |
| `applied_line` | `float` | `ge=0, le=1` | The merge line in force when the cells were counted |
| `labeller` | `str` | `PRINTABLE_LINE_PATTERN`, `max_length=64` | Who marked the holdout. Not a `JudgeModelId`: the committed labels name a model outside the registry, and a column that could only hold pipeline models would refuse the truth |
| `merged_and_one_story` | `int` | `ge=0` | The line joined them and the label agrees |
| `merged_and_two_stories` | `int` | `ge=0` | The line joined two stories that are not one. The reader never sees the second - the invisible direction |
| `apart_and_one_story` | `int` | `ge=0` | The line left one story in two pieces. The reader sees it twice and can dismiss it |
| `apart_and_two_stories` | `int` | `ge=0` | The line left them apart and the label agrees |
| `pairs_unresolved` | `int` | `ge=0` | Labelled pairs whose two days retention has deleted. Reported, never dropped |
| `labelled_two_story_pairs` | `int` | `ge=0` | The negative population the false-merge cell is drawn from. On the row so no rate is read without it |
| `scorer_model` | `ScorerModelId` | - | Which encoder produced the cosines |
| `cosine_weight` | `float` | `ge=0, le=1` | What the cosine was worth |
| `key_point_weight` | `float` | `ge=0, le=1` | What the key-point term was worth |

**The read is bounded by the holdout, not by the archive** (Guardrail #12). Each holdout row names its own two days, so the file's length is the bound. The unbounded walk in the sheet tool exists only because that tool resolves against a different date, and this must not copy it.

### `StorySimilarityPair` - seven columns appended at the tail

The declaration is unchanged - it does **not** inherit either stamp. **Seven** fields are appended after `decode_seconds`, so the header widens and does not reorder: `judge_id`, `judge_temperature`, `decode_digest`, `grammar_applied`, `first_token_probabilities`, `thinking_spans`, and `judged_by_run_id`.

**`judge_id` here is `Literal["content-similarity-judge"]`, declared in this judge's own module, defaulting to that one member.** A closed set with one member is honest: this row is written by one judge and no other. It is not a roster, and nothing outside this judge imports it - which is the difference between narrowing your own column and publishing a list of everyone who might ever exist (section 1c).

**`judged_by_run_id: RunId | None`, and the key extends to `("date", "run_id", "pair_key", "judged_by_run_id")`.** This is what makes a re-judge possible at all. `run_id` on this row is the DIGEST run that published the day - a property of the date, so two council runs judging one date write the identical string. Under today's three-part key the append path's de-duplication keeps the first row it sees, which is the one already in the checked-out file, so **every re-judged pair would be silently discarded while the record counted the fresh verdicts** - the committed store and the fitted record would then describe two different sets with nothing able to tell.

**The ordering rule, because the column is nullable and every committed row will carry it empty.** The de-duplication compares raw cells, so an empty cell and a run id are two distinct keys and both rows survive - which is exactly what a re-judge needs. The defect is downstream: the one-row-a-pair tie-break in the counting module orders on a bare `>`, and comparing two empty values or an empty against a string raises. **The ordering is `(row.judged_by_run_id or "")`, null lowest**, so a stamped re-judge beats an unstamped original and two unstamped rows keep file order - which is today's behaviour exactly. A unit test drives two rows, one null, and asserts the newest wins.

**`grammar_applied` on this row means both calls of the pair opened inside the grammar**, because this row's grain is a pair. `first_token_probabilities` on this row is the **file-order** call's window, named so, because a pair makes two calls and a singular column must say which.

`decode_seconds` keeps its existing meaning on this row - both calls on the pair - and its description says so.

Changelog entry to prepend: version stamped the day row #8 lands, change "Added the judge-call stamp columns and the judging run id, extended the key with it, and gave `first_token_margin` a renormalised reading.", why "A verdict could not be read back to the sampler that produced it, a re-judged pair collided with the row it replaced, and the old margin was a raw top-two gap over a three-wide window."

**`first_token_margin` changes meaning, and the row above is the only thing that says so.** The 82 committed values are a raw top-two gap over a three-wide window; every value written after row #11b is a renormalised per-verdict gap over a 25-wide one. They are different quantities in one column, and the discriminator a reader has is the empty `decode_digest` cell on the old rows.

**Two migrations, both in the same commit.**

1. **Read side.** `from_csv_row` adds `judge_id` to the existing by-name branch that already special-cases the other non-null default on this row. **Not a general predicate over "any field whose default is not `None`"** - a required field's default is undefined, not `None`, so a general branch would also pop `version`, which a before-validator then refills with this build's own stamp. That is silent coercion on the one column the header migration uses as its sentinel.
2. **Write side.** The committed day files are widened in place by `migrate_header(path, StorySimilarityPair.csv_columns(), refiler(StorySimilarityPair))`. **`refiler` alone touches no file** - it returns a row-to-row function, and `migrate_header` is what writes. Nothing runs either from a command line today, so row #8 adds the operator entry point. Widening adds empty cells and changes no value any run wrote. Verified read-only on 2026-09-20: all 82 committed rows re-validate through all three model validators and re-render.

### The shipping capability (`backend/idhazh/council/metrics_sink.py`)

The council's own path, end to end, and **not** the digest pipeline's segment-and-compaction machinery.

| Step | Who | What |
| --- | --- | --- |
| 1 | the judge's stage | builds its own metrics row and calls `ship_judge_metrics(row, out_dir=...)` |
| 2 | the capability | validates through the judge's own contract, writes one file per shard under the run directory, temp-file-then-rename |
| 3 | the workflow | uploads that directory as an artifact, with an always condition |
| 4 | the collecting job | downloads every shard's artifact merged, and appends each row to the store its contract names |

**The capability declares nothing about the payload.** It takes a `Contract` instance, a judge id and an output directory. A judge that measures nothing calls it with a row carrying only its identity and its counts.

**Why not the segment store and the compaction verb.** That verb takes no filter: it files away every ledger waiting in transit and then deletes the transit copies. The digest run's own segments are often still waiting at 22:00 when the council starts - measured 2026-09-20, 21 files across five ledgers - so a council run that compacted and then committed only its own folders would delete the digest pipeline's transit copies while leaving the files they were filed into uncommitted. The council's own path has no such collision, and it is the path the council already runs for verdict files.

### Store paths and prune targets (`backend/idhazh/ledger.py`)

| Constant | Value | Store |
| --- | --- | --- |
| `COUNCIL_DIRNAME` | `"llm-council"` | `state/llm-council/shard-outcomes/` |
| `SHARD_OUTCOMES_DIRNAME` | `"shard-outcomes"` | |
| `CONTENT_SIMILARITY_JUDGE_DIRNAME` | `"content-similarity-judge"` | `state/content-similarity-judge/metrics/` |
| `JUDGE_METRICS_DIRNAME` | `"metrics"` | |
| `MERGE_LINE_HOLDOUT_SCORES_DIRNAME` | `"merge-line-holdout-scores"` | |

Day-sharded, `<group>/<store>/<YYYY>/<MM>/<DD>.csv`. **Two directory levels and no more:** the day inventory globs one and two levels, so a third is invisible to the telemetry reader and the miss is silent.

All three stores join the prune targets (CLAUDE.md 1b: a prune verb per store) and the filled-by-nothing list until their writers land.

**`STORY_SIMILARITY_DIRNAME` is deleted in row #18**, not left holding the same string as the judge constant. Two constants carrying one value re-opens the drift the closed sets exist to close, and the prune vocabulary is built by joining those constants.

### Config knobs

**Two blocks, and which one a knob lands in is the dictum applied to config.** A knob the council needs to run a night sits in `council`, or the council cannot be configured in a repository with no judge. A knob denominated in a tenant's own unit sits in that tenant's block.

| Today | Becomes | Whose |
| --- | --- | --- |
| `run.judge_shard_timeout_minutes` | `council.shard_timeout_minutes`, committed `200`, bounds unchanged | council |
| `assemble.same_story.adaptive_dedup_threshold.shards` | `council.shards`, committed `4` - **the fan-out width is a runner number, and the workflow reads it to size its own matrix** (row #9 decision 3). A tenant narrows it downward through `shard_count` | council |
| (new, row #9) | `council.shard_wrap_up_minutes`, default `12`, `ge=0` | council |
| (new, row #24) | `council.tenants`, an ordered slug list, **default empty**. The registry seam 10 left unowned. Empty is the zero-judge case and it must load | council |
| (new, row #21a) | `council.repair_window_days`, default `14`, `ge=1`, `le=60` - how far back the council asks its tenants about | council |
| (new, row #21a) | `council.repair_floor_date`, a date stamp, no default - **the council's own first night.** Without it the plan names every published day the council predates, which is 29 dates on its first run. **A tenant may raise it to its own first night**; it cannot lower it | council, per-tenant override |
| (new, row #21a) | `council.repair_dates_a_night`, default `1`, `ge=0`, `le=4` - how many outstanding dates one run may add beside tonight's. Zero switches the repair off | council |
| (new, row #1b) | `assemble.same_story.adaptive_dedup_threshold.flush_every_pairs`, default `1`, `ge=1` - **denominated in pairs, a unit only this judge has** | judge |
| (new, row #19) | `HOLDOUT_RESOLVED_FLOOR` in `knobs/placement.py`, a source constant at half the labelled population - a property of what makes the reading meaningful, not something an operator tunes down to turn a red row green | judge |

`run.shard_timeout_minutes`, the work job's own bound, does not move. The bound reader gains a dotted-path key and keeps one reader and one refusal message.

**The judge's whole block becomes optional** (row #9 decision 5), because an absent block is what "no tenant is configured" has to look like in a config file - and without that the zero-judge oracle cannot go red.

**The check that a shard fits leaves `AppConfig` entirely** (row #25). It read `SECONDS_A_CALL` - one judge's measured per-call cost - from `knobs/placement.py` at module scope, so every council module that read config pulled a judge's measurement into the contract layer. The tenant now validates its own fit against the bound the council hands it, at resolve time in the planning job.

**The deadline is a backstop with room to spare.** At the committed budget a shard draws 50 pairs; at the measured 94.53 s a pair that is 78.8 minutes and at the worst measured pair 92.5 minutes, against a 200-minute bound. `stopped_on_deadline` is reachable in the type system and will not fire on the runner until the shard count drops or the budget rises, which is why row #1a's oracle drives it against a fake tenant directly. **The flush default is 1**: a rewrite of a file of at most 50 rows is not measurable beside a pair that costs 94.53 s.

---

### Row #1a - The council bounds its shard and ships whatever it wrote

- **Side: council.** Its gates run with no judge in the repository.
- **Scope:** the council computes a wall-clock deadline from its own two clocks, hands it to the tenant as an argument, and the workflow uploads whatever the tenant wrote.
- **Files touched:** `backend/idhazh/council/deadline.py` (new), `backend/idhazh/cli.py`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_deadline.py` (new), `backend/tests/workflows/test_llm_council_workflow.py`
- **Acceptance gates:** local - the council test package, the workflow harness, ruff, mypy. CI - full suite.
- **Oracle:** the deadline the council computes from a start instant and the two knobs is the instant the fake tenant is handed, and a fake tenant that returns `stopped_on_deadline` still has its output uploaded. **Driven against the fake tenant, not a judge** - that is the point of the row. It cannot settle what the platform does on a real cancellation; the tenant's own deadline is what makes that case unreachable.
- **Readiness - the seven questions a cold reader asked, answered:**

| # | Question | Answer |
| --- | --- | --- |
| 1 | How does a knob reach the code? | `settings.app.council.shard_timeout_minutes` and `settings.app.council.shard_wrap_up_minutes`, through `config.load()` like every other knob |
| 2 | Which config block? | `council`, the new top-level block row #9 creates. **Not `run`** - that block is the digest pipeline's - and **not `assemble.same_story.adaptive_dedup_threshold`**, which is the judge's |
| 3 | What deadline pattern? | The work shard's, unchanged: `backend/idhazh/stages/work.py:439-445` computes `deadline = started + max(timeout - wrap_up, 0) * 60` over `time.monotonic()` and reads `left_s = deadline - time.monotonic()`. Same formula, new owner |
| 4 | What writes a file without a partial state? | `write_atomic(path, text)` at `backend/idhazh/assemble.py:108`; `write_atomic_bytes` at 123. Temp file then rename |
| 5 | Where is the deadline checked? | **Not here.** The council hands over an instant and checks nothing inside a unit of work; where the tenant checks it is row #1b's decision, because only the tenant knows what a unit is |
| 6 | How does the workflow pass it? | It does not, and that is the answer. The bound already reaches the job as `timeout-minutes: fromJSON(needs.draw.outputs.judge_shard_timeout_minutes)` at `llm-council.yml:163`, sourced from `backend/utilities/shard_bound.py --key ...` at line 132. The deadline is computed in-process because **only the process knows when it began** - the job clock started before a checkout, an install and a weights restore |
| 7 | What outcome value is filed? | `ShardOutcome` from row #5 - `completed`, `stopped_on_deadline`, `nothing_to_do`. The tenant returns it; the council files it and never infers it |

- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An always condition alone does not fix this. The stage builds a list and writes once after the loop, so a cancelled shard has written nothing and the upload takes an absent path. | Andre |
| 2 | **The council owns the bound and the margin, because the council owns the runner** - the job timeout, the checkout, the install, the weights restore. That is exactly why the earlier draft had to invent a wrap-up margin covering steps the tenant cannot see: the margin was always the venue's number. | Carmack |
| 3 | **The deadline crosses as a wall-clock instant, not as two knobs.** A tenant handed an instant needs no knob, no block and no config reader, which is what makes it replaceable by a two-line fake. It also deletes the earlier draft's awkward "the deadline's zero is the stage's own start". | Carmack |
| 4 | A header-only file is written before the first unit, so the artifact always exists and a no-files-found error becomes meaningful rather than permanent. **The council asserts the upload; what the header says is the tenant's.** | Andre |
| 5 | The margin is its own knob rather than a copy of the work shard's 12. `run.shard_wrap_up_minutes` belongs to a different stage with a different preamble. | Carmack |
| 6 | The upload carries an always condition. **The real exposure was never the collecting job dying - it is a shard dying**, which today ships nothing after up to 79 minutes. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | An always condition on the upload and nothing else | The oracle goes green while a cancelled shard still loses every verdict | One line, and the next overrun costs the same hours | Andre |
| 2 | Raise the bound | A bound is a backstop, not a budget | The defect survives for the next overrun | Carmack |
| 3 | Leave the clocks in the judge's block and let the judge compute its own deadline | The venue's runner budget expressed as a tenant's knob. With zero judges the council has no timeout at all | Seam 3, uncut | Carmack |

---

### Row #1b - The judge stops safely and flushes as it goes

- **Side: judge.**
- **Scope:** the judging stage takes the deadline it is handed, stops on it between units, writes its verdict file from the first pair onward, and reports which outcome it reached.
- **Files touched:** `backend/idhazh/stages/judge_shard.py`, `backend/idhazh/contracts/knobs/placement.py`, `config/idhazh.json`, `backend/tests/test_similarity_judge.py`, `schemas/app-config.schema.json` (generated)
- **Acceptance gates:** local - the similarity test module, contract export, drift gate. CI - full suite.
- **Oracle:** the stage driven against a fixture selection with a client that raises after k pairs leaves a file holding exactly k rows; a stage handed an already-passed deadline writes a header-only file, reports `stopped_on_deadline`, and exits 0.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The stage takes the deadline as an argument and reads no clock knob. It decides only **where** stopping is safe. | Carmack |
| 2 | **The flush interval is the judge's knob, because it is denominated in pairs** - a unit only this judge has. It stays in the judge's own block. **Default 1**: a rewrite of a file of at most 50 rows is not measurable beside a pair that costs 94.53 s. | Carmack |
| 3 | The file is rewritten whole every flush, not appended. A temp-file-then-rename has no partial state, which is what makes an interrupted shard's file readable. | Fowler |
| 4 | **The deadline is checked before a pair, never between its two calls.** A pair stopped between its calls has one reading and no agreement, so it is neither read nor abandoned, and the funnel identity in row #6 stops closing. | Andre |
| 5 | This makes `stopped_on_deadline` reachable, and `pairs_abandoned` is what keeps the judge's funnel identity closing when it fires. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Append to an open handle | An interrupted append leaves a half-written row the reader stops on | An unreadable tail | Fowler |
| 2 | Check the deadline inside the pair | The funnel identity stops closing on exactly the shard the deadline exists to let report | A record that goes red on a real event | Andre |

---

### Row #2 - The council knows which run it is

- **Side: council.** Its gates run with no judge in the repository.
- **Scope:** the council mints a run identity of its own, publishes it once, and hands it to every verb that writes a row.
- **Files touched:** `backend/idhazh/council/run_identity.py` (new), `backend/idhazh/cli.py`, `backend/idhazh/stages/common.py`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_run_identity.py` (new), `backend/tests/workflows/test_llm_council_workflow.py`
- **Acceptance gates:** local - the council test package, the workflow test module, ruff, mypy. CI - full suite.
- **Oracle:** a row is produced from a date and a run id passed on the command line, with no plan file on disk, and the minted id satisfies `RunId`. It cannot settle whether the id is unique across re-runs - the platform's run id is stable across attempts, which the artifact naming handles separately.
- **Readiness - the four questions a cold reader asked, answered:**

| # | Question | Answer |
| --- | --- | --- |
| 1 | What is the mint formula? | `f"{the day the council runs}-{the platform run id}"`, giving `2026-09-21-35534060762`. It satisfies `RunId` (`base.py:166`) unchanged: four digits, hyphen, two, hyphen, two, hyphen, then one or more digits. The digest pipeline's `stages/plan.py:895 _run_id` composes the same shape from an execution ordinal; **the council does not call it**, because that function resolves the next ordinal by reading the digest run's own state |
| 2 | Which verbs take a new argument? | Every verb that **writes a row**. Today that is `judge-fold` and `judge-fit`; `judge-shard` joins them when row #17 makes it file an outcome. `judge-draw` selects and writes pair rows, so it takes it too |
| 3 | How is the flag spelled? | `--run-id`, beside the `--date` all four already take. `--date` keeps its meaning - the day being judged - and is untouched |
| 4 | Where is it minted? | **Once, in Python, in the planning job**, and published as a job output the later jobs read - exactly how `judge_shard_timeout_minutes` already crosses at `llm-council.yml:59`. Not `${{ github.run_id }}` inlined at four call sites: the date prefix has to be computed once or two jobs of one run file rows under two ids |

- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council has no run id today - the string does not appear in its workflow file, and the verbs that record one read it from a plan file only the digest pipeline produces. | Carmack |
| 2 | The affected verbs take **a date and a run id**, not a plan object. Those are the only two attributes either reads off it, and a stub plan is not free - the plan contract requires a generated-at stamp beside them. | Carmack |
| 3 | The run id is minted from **the day the council runs**, not the day it judges. The compaction reads a run id's first ten characters as the day the run opened and feeds it to the console's lag figure, so a yesterday prefix would publish a standing two-day lag that is not real. The judged date is already the `date` column, which is what routes a row to its store. | Carmack |
| 4 | The run identity is minted from the platform's **run id**, which is unique per repository across every workflow - **not the run number, which is unique only within one workflow** and would let a council id equal a digest run id in a column that already carries both meanings. | Carmack |
| 5 | A reader separates the 82 pair rows carrying a digest run id from the council ids that follow by the `version` stamp the row already carries. One column, one store, two meanings across time - the stamp is the discriminator, and it is free. | Carmack |
| 6 | The minting function lives in the council's package and names no judge, so it is unit-tested in `backend/tests/council/` with nothing else imported. | Fowler |
| 7 | ESCALATE: `run_id` on a pair row means the run that published the day; on a council row it means the run that judged it. Two columns, two meanings, both written down. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Reuse the digest run's id | It claims a machine and a clock for a run that never drew them, and its date prefix is a day stale | A corrupted lag figure nobody would see | Carmack |
| 2 | Give the council a planning job so the existing verb works | A job that plans nothing, to produce one string | One job, one artifact, a stage satisfying a signature | Fowler |
| 3 | Mint it per job from `${{ github.run_id }}` | The date prefix would be computed four times, and a run crossing midnight files two ids | Rows of one run under two addresses | Carmack |

---

### Row #3 - The separation and the dictum, written where the next agent reads it

- **Side: council.** Documentation-only.
- **Scope:** the page that owns the council states the layers, the dictum and its five checkable conditions, which readings sit where, and why - so the next agent neither puts a judge's metrics on the council's row nor makes the council import a judge.
- **Files touched:** `docs/architecture/publishing/llm-council.md`, `docs/concepts/telemetry.md`
- **Acceptance gates:** local - `doc_load.py --changed`. CI - full suite. No application suite: documentation-only.
- **Oracle:** the page names every layer, its store, the rule that decides which layer a reading belongs to, and the five conditions of the dictum. It cannot settle whether a future reading is classified correctly - that is what the rule is for.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council owns the pipe, its own execution record and the window arithmetic. Each judge owns what it measures, its own store and its own stamp rule. The capability declares nothing about a payload; the protocol names no judge. | Owner, 2026-09-20 |
| 2 | **The dictum is on the page with its five conditions, not as a slogan.** "The council runs one judge or many and depends on none of them" is worth nothing unless a reader can check it, so the page carries the directory import rule, **the import-closure rule**, the zero-judge declarability rule, the test-location rule and the protocol-and-config rule - and names row #23 as the thing that checks them. **The closure rule is the one round seven nearly saw published missing**: this row is what writes the dictum into the living doc, and the plan is deleted afterwards, so a condition left out here is a condition lost. | Owner, 2026-09-21 |
| 3 | The page carries the worked example that makes the separation stick: a shared margin column would mean "the grammar chose" for one judge and "a legitimate middle score" for another, and one fold would sum two instruments. | Andre |
| 4 | A judge that runs no model is a judge. The council's record has no column that assumes one, and the judge's own contract carries model columns only if it has a model. | Owner, 2026-09-20 |
| 5 | The page also carries the plain-meaning test from section 1a, because the terms it deletes were invented on this page's own subject. | Owner, 2026-09-20 |
| 6 | **No new judge-telemetry page and no new council-architecture page.** The council page answers the venue question and the telemetry concept page owns the stores; a third would be the split the documentation standard forbids. | Guardrail #4 |
| 7 | Docs-only, no predecessor, so it can land at any time and guide every row after it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Record the separation only in this plan | A plan is a cache of the docs, and it is deleted when it closes | The next agent re-derives it, or does not | Guardrail #4 |
| 2 | A new page for judge telemetry | Two pages answering one question, and neither authoritative | A split with no question behind it | Fowler |
| 3 | State the dictum without its conditions | An unfalsifiable sentence. The first four adversarial rounds all read a version of it and none of them caught the six seams | A rule nobody can fail | Owner |

---

### Row #4 - The judge-call stamp, declared once and naming no judge

- **Side: shared.** Two judges may inherit it; the council does not, and neither does it name a judge.
- **Scope:** the columns a model-using judge's reading carries, declared as a mixin in one module, with no roster anywhere.
- **Files touched:** `backend/idhazh/contracts/judge_call.py` (new), `backend/tests/contracts/test_judge_call.py` (new)
- **Acceptance gates:** local - the new contract test, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** a `Contract` subclass inheriting the mixin round-trips every field through the CSV writer and reader, the mixin declares no schema stem so nothing generates a file for it, **and the module imports nothing from any judge package**. It cannot settle whether the fields are the right fields.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A mixin over the plain model base, inherited alongside `Contract`. Never alongside the CSV protocol, which is a `typing.Protocol` in the ledger - the combination is a metaclass conflict and the import is circular. | Fowler |
| 2 | **There is no `JudgeId` roster - seam 1.** An earlier draft declared one here and typed the council's own record with it. It contradicts "a judge's identity is a property of its stage", it puts the venue's published contract downstream of the roster, and `Literal[]` is not legal Python, so the council could not be imported in a repository with no judge. Section 1c carries the full reasoning. | Owner, 2026-09-21 |
| 3 | **The mixin names no judge and no judge's model.** `judge_id` is a slug-patterned `str` and `judge_model` a printable-line `str \| None`. Each judge narrows both in its own row, which is where a closed set can be honestly closed. | Fowler |
| 4 | The pair row does not inherit the mixin. Inheriting reorders the committed header and makes the store unappendable. | Fowler |
| 5 | `decode_seconds` on the mixin is one call and nothing else. The pair row's column of the same name is both calls, and its description says so. | Andre |
| 6 | The probability vector is a list of id and logprob pairs. A rendered token is right for one set of weights, two ids can collide as one string, and exponentiating a logprob throws away the precision the margin is computed at. | Andre |
| 7 | A judge with no model does not inherit this at all. It is the stamp for a model call, not for a judge. | Owner, 2026-09-20 |
| 8 | **This row does not touch the export tuple, and that is the carve-out rather than an omission.** The tuple is typed `tuple[type[Contract], ...]` and `export()` calls `schema_filename()` on every member, so registering a stem-less mixin crashes the exporter. The mixin is a `Model`, not a `Contract`. Every row that adds a real contract registers it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One union row across all judges | Half the columns null per judge, and the agreement field has no meaning for a judge whose input has no order | A contract asserting two instruments are one | Fowler |
| 2 | A base class with behaviour | A shared usable field would drop every ambivalent reading and bias a fitted floor with nothing red | The cheapest code, and a silently biased sample | Andre |
| 3 | A separate health table | A join key and a second write; a run dying between the two leaves a reading with no stamp | A second store and a join every reader pays | Andre |
| 4 | Keep the roster and let the council import it | Seam 1. Judge three regenerates the council's schema, and with zero judges the council will not import | The dictum, failed at condition 3 | Owner |

---

### Row #5 - The council's own shard-outcome record

- **Scope:** one row per shard per council run, saying whether the pipeline worked and what the work it hosted cost.
- **Files touched:** `backend/idhazh/contracts/council_shard_outcome.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/council-shard-outcome.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/concepts/partitions.md`, `docs/architecture/publishing/retention.md`, `backend/tests/contracts/`, `backend/tests/retention/test_prune_range.py`, `backend/tests/workflows/test_ledger_staging.py`
- **Acceptance gates:** local - the contract, retention and staging test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row round-trips through CSV, and the store path a date resolves to is matched by the two-level day glob the telemetry reader uses - so a store this row creates is visible rather than silently absent. It cannot settle whether the figures are true; row #17 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The row carries no name for the unit of work. That is the separation: it reads the same whether the judge it hosted made four hundred model calls or none. | Owner, 2026-09-20 |
| 2 | `model_calls`, `tokens_in`, `tokens_out` and `model_seconds` are nullable and **null, not zero**, for a judge that runs no model. Zero would read as a broken model judge. | Owner, 2026-09-20 |
| 3 | `judge_id` is on the row so a night running two judges files rows an operator can attribute. | Owner, 2026-09-20 |
| 4 | The outcome is a three-member enum. A shard killed by the platform writes no row at all, and absence against the recorded shard count is what says so - which is why `shards` is a column. | Carmack |
| 5 | `seconds_spent` is the stage's clock, not the job's. The job includes a checkout and a weights restore this row is not about, and the digest pipeline already records job clocks. | Carmack |
| 6 | The store joins the prune targets and the day-partition page, with no writer named yet - the wording two existing stores already use for a shape that lands ahead of its producer. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Put the council's outcome on the existing work-shard machine row | That row is one work shard of one digest run and carries 113 columns this pipeline does not fill | A discriminator column on a row describing two unrelated jobs | Carmack |
| 2 | A host fingerprint per judging shard | The probe wants 1.9 GiB on a job whose two processes already hold up to 9.02 GiB of anonymous memory in 16 GB, and the digest pipeline already characterises the same runner pool | An OOM risk for a reading nobody asked for | Carmack |
| 3 | Units dealt and completed on the council row | The council has no name for the unit, and the judge already counts it - two counts of one thing that can disagree | A duplicate that drifts | Owner |

---

### Row #6 - The content-similarity judge's own metrics

- **Scope:** the contract for what this judge measures, owned by this judge, in this judge's own store.
- **Files touched:** `backend/idhazh/contracts/content_similarity_judge_metrics.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/content-similarity-judge-metrics.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `backend/tests/contracts/`
- **Acceptance gates:** local - the contract test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** `pairs_dealt = pairs_read + pairs_refused + pairs_unreadable + pairs_abandoned` is enforced by a model validator, so a shard cannot file a funnel that does not close. It cannot settle whether the figures are true; row #15b does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every column is this judge's own. A second judge declares its own contract and shares none of them. | Owner, 2026-09-20 |
| 2 | `pairs_refused` counts **pairs, not calls**. A pair is two calls, so counting calls would over-count a pair that failed twice and make the identity go red on a real event rather than on a defect. | Andre |
| 3 | `pairs_abandoned` is a column because the deadline row #1b adds makes it reachable, and without it the identity fails on exactly the shard the deadline exists to let report. | Andre |
| 4 | Rates are nullable and null on an empty shard. A rate over zero rows is not zero. | Andre |
| 5 | The margin median carries a warning in its own description: it is not comparable to another judge's, because a flat distribution means opposite things for a verdict judge and a rated scorer. **A column may be compared across judges only when it is a count or a clock.** | Andre |
| 6 | This row is a record, not an alarm. The line-setting gates already fire on the day-grain rates, and a second threshold here would be an answer nobody could reconcile with the first. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A shared vitals mixin every judge inherits | It is the council dictating a judge's metric set, which is the coupling this plan exists to remove | Three columns judge two cannot have and one that inverts | Owner |
| 2 | A free-text metrics blob on one shared row | Nothing validates it, nothing generates a type, no schema diff fires when a judge changes what it records | Guardrail #3 broken | Fowler |
| 3 | Derive the funnel at read time from the verdict rows | A shard that wrote no verdicts becomes indistinguishable from one that never ran | The one failure the row exists to show | Andre |

---

### Row #7 - The content-similarity judge's merge-line benchmark record

- **Scope:** the persisted shape for scoring the merge line against the labelled holdout, with its store and prune target.
- **Files touched:** `backend/idhazh/contracts/merge_line_holdout_score.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/content-similarity-judge-merge-line-holdout-score.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `backend/tests/contracts/`
- **Acceptance gates:** local - the contract test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row refuses a set of cells whose sum exceeds the labelled population. It cannot settle whether the cells were counted correctly; row #19 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the LINE, not the judge. The holdout rows carry no verdict, the shipped implementation calls no model, and the labels were written outside the pipeline. | Andre |
| 2 | It does not inherit the call stamp. Eight call columns here would be five nulls and one asserting an instrument that never ran. | Andre |
| 3 | A labeller column, free text rather than a model id, because the committed labels name a model outside the registry. | Andre |
| 4 | Counts only, no stored rate. Every rate is derived at read time with the negative population in view. | Guardrail #10 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Store precision and recall | With four labelled negatives one flip moves the rate 25 points, and a stored rate loses its denominator | A number that reads as a measurement | Guardrail #10 |
| 2 | Put the call stamp on it for symmetry | Symmetry that asserts a model ran when none did | Five null columns and one false one | Andre |

---

### Row #8 - The pair row gains the stamp, and the store is rewritten

- **Scope:** the pair row gains **seven** columns at the tail and its key extends to four parts, the reader learns to fill a non-null default, and the committed file is widened so the store stays appendable.
- **Files touched:** `backend/idhazh/contracts/story_similarity_pair.py`, `backend/idhazh/ledger.py` (the key), `backend/idhazh/similarity/fold.py` (the tie-break ordering), `backend/utilities/widen_ledger_header.py` (new), `schemas/story-similarity-pair.schema.json` (generated), `frontend/src/contracts/` (generated), `state/story-similarity/scored-pairs/2026/09/18.csv`, `docs/architecture/contracts/schemas.md`, `backend/tests/contracts/`, `backend/tests/test_similarity_fold.py`, `tests/fixtures/`
- **Acceptance gates:** local - the contract and similarity test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a fixture carrying the pre-change header is widened, then a fresh row is appended to it through the ledger's own append path without raising. **The append is the load-bearing half** - a read-only oracle cannot see the header equality check that makes the store unappendable. A second case drives two rows for one pair, one with a null run stamp, and asserts the stamped one wins.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The columns are appended in the row's own body, not inherited, so the header widens rather than reorders. | Fowler |
| 2 | The reader adds one field to its existing by-name branch. A general predicate over non-`None` defaults would also pop `version`, which a before-validator refills with this build's stamp - silent coercion on the header sentinel. | Fowler |
| 3 | **Nothing in the repository can widen a header from a command line today.** The row adds an operator utility under `backend/utilities/`, which pytest does not collect, taking a store from the prune vocabulary and dry-running by default as the prune verb does. | Fowler |
| 4 | The committed file is widened in the same commit, or the append check refuses it and the next re-dispatch of that date kills the commit step and every ledger staged beside it. | Andre |
| 5 | `judge_id` carries a default rather than being required, so the widening can fill it and the selection stage - which writes these rows with verdict columns empty - does not invent an instrument. | Fowler |
| 6 | **The seventh column is `judged_by_run_id`, and the key extends with it - round six found it had no owner.** Section 1c specified the column list and a four-part key while this row's scope said five, so the one column the whole re-judge design rests on was specified and unassigned. `STORY_SIMILARITY_PAIR_KEY` becomes `("date", "run_id", "pair_key", "judged_by_run_id")` here. | Section 11 |
| 7 | **The tie-break ordering lands in this commit too**, because the column is nullable and every committed row carries it empty. The counting module's one-row-a-pair tie-break at `fold.py:95-110` compares `row.run_id > held.run_id` today, which is what decides the rebuilt-day case its own docstring describes. **The new ordering is the pair `(judged_by_run_id or "", run_id)`** - dropping `run_id` would make two unstamped rows from different runs compare equal and keep whichever came first, which is neither today's behaviour nor file order. The unit test drives three rows: one stamped, two unstamped from different runs. | Andre |
| 8 | ESCALATE: committed rows are rewritten and a persisted key widens. Sign-off before the utility runs. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Inherit the mixin here too | The header reorders and the append raises; the store dies | One declaration instead of two, and a dead store | Fowler |
| 2 | Leave the committed file alone | The check refuses it on the next append and takes the commit step down | A failed run later | Andre |
| 3 | Start a new store at the new shape | Two stores for one question, joined by every reader for ever | A permanent fork | Fowler |

---

### Row #9 - The council's clocks and its fan-out width move to a council block

- **Side: council.** Its gates run with no judge in the repository.
- **Scope:** the judging shard's bound, a new wrap-up margin and the fan-out width move out of the digest pipeline's generic run block and out of the judge's block into a block the council owns; the judge's own block becomes optional; the reader learns a dotted path.
- **Files touched:** `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/contracts/knobs/council.py` (new), `backend/idhazh/contracts/knobs/placement.py`, `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `backend/utilities/shard_bound.py`, `.github/workflows/llm-council.yml`, `frontend/src/lib/server/config.ts`, `docs/concepts/config.md`, `backend/tests/contracts/test_app_config.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `schemas/app-config.schema.json` (generated), `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the two named test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the dotted key the workflow passes and the field the contract declares resolve to the same value, the reader returns a bare positive integer, **and `AppConfig` validates with the judge's whole block absent from the config file** - which is the zero-judge condition expressed as a config test, and it can only bite once decision 5 makes that block optional. It cannot settle whether the bound is the right size.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This row reverses the earlier draft's direction, and that was seam 3.** The draft moved the council's bound *into* `assemble.same_story.adaptive_dedup_threshold` - the judge's block, itself nested under the digest pipeline's assemble stage - so with zero judges the council had no timeout at all. The bound and the margin are the venue's: they price a runner, a checkout, an install and a weights restore, none of which a tenant can see. | Owner, 2026-09-21 |
| 2 | **`council.shard_timeout_minutes` and `council.shard_wrap_up_minutes`**, a new top-level block. Committed values `200` and `12`, bounds unchanged. | Carmack |
| 3 | **`council.shards` moves too, and round six is why - it was seam 8's other half.** `llm-council.yml:143` computes the council's own fan-out width by reading `assemble.same_story.adaptive_dedup_threshold.shards`, so with no judge configured that step raises and the planning job dies before it plans anything. A fan-out width is the purest runner number there is. Committed value `4`. **A tenant may narrow it downward** through `shard_count` on the protocol; the council's knob is the ceiling and the default. | Carmack |
| 4 | **The flush knob does not move and never was the council's.** It is denominated in pairs - a unit only this judge has - so it stays in the judge's own block (row #1b). | Carmack |
| 5 | **The judge's block becomes optional, defaulting to absent.** Without this the zero-judge oracle cannot go red: `assemble` is built by a default factory, so the judge's knobs exist whether or not a judge does, and the condition would be asserted and never tested. An absent block is what "no tenant is configured" has to look like in a config file. | Fowler |
| 6 | **The validator that asserts a shard fits its bound becomes a per-tenant check, and runs only when that tenant's block is present.** Row #25 then moves the check itself out of `AppConfig`, which is where it still pulls in a judge's measured constant. This row makes the check conditional; row #25 makes it uncoupled. | Fowler |
| 7 | The bound reader resolves a dotted path rather than a leaf under a fixed block. One reader, one refusal message. | Carmack |
| 8 | A straight rename in one commit. One config file, one fixture, no payload an earlier run wrote. | Fowler |
| 9 | The hand-written frontend config mirror moves with it, or the two disagree silently. | Fowler |
| 10 | ESCALATE: the knob and the workflow key land in one commit, or the workflow resolves no bound and no width, and the shard runs to the platform ceiling. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Move the bound into the judge's block, as the earlier draft did | Seam 3. The venue's runner budget expressed as a tenant's knob, and no timeout at all with zero judges | The dictum, failed at condition 3 | Owner |
| 2 | Leave `shards` where it is | Seam 8's other half. The council cannot size its own matrix without reading a judge's config path | A planning job that dies with no judge | Carmack |
| 3 | Leave it in the run block | The validator keeps asserting something pair-specific about a generic knob, and `run` is the digest pipeline's | Two timeouts neither of which says what it bounds | Fowler |
| 4 | A block flag beside the key flag | Two ways to spell one address | A second grammar | Carmack |
| 5 | Keep the judge's block non-optional | The zero-judge oracle is unfalsifiable, which is how the first five rounds all passed a broken design | A test that cannot fail | Fowler |

---

### Row #10 - The judge's own bound reads a measured number

- **Scope:** the judge's shard bound is sized from a measured per-pair reading instead of a derived per-call one, and the reading is written up. **Nothing outside the judge's own arithmetic moves.**
- **Files touched:** `backend/idhazh/contracts/knobs/placement.py` (a new judge-specific constant beside the existing one, which does not change), `backend/idhazh/contracts/app_config.py` (the judge's validator arm only), `.github/workflows/llm-council.yml` (the header comment), `docs/reference/benchmarks/what-a-judge-pair-costs.md` (new), `backend/tests/contracts/test_app_config.py`
- **Acceptance gates:** local - the named test module, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the page's figures reproduce by re-running its stated arithmetic over the committed file it names, **and the validator arm that bounds the work shard returns the same value before and after this row**. The second half is the load-bearing one: it proves the judge's number did not move anybody else's.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The reading is **94.53 s a pair** - min 72.80, max 110.98, population sd 7.84, n = 82, judged 2026-09-18 on four stock runners, `Qwen3.5-9B-Q4_K_M`. The four shards' means spread 88.24 to 99.89 s, a 13.2 percent lottery. | Carmack |
| 2 | **`SECONDS_A_CALL` does not change.** It sizes the work shard's budget as well as the judge's, so one judge's measurement moving it drags every other budget with it - and the other consumers have no measurement behind the move. The judge gets its own constant, measured, beside the shared one. | Owner, 2026-09-21 |
| 3 | **A per-pair figure, not a per-call one.** The committed column is the sum of both calls and the second reuses the system-turn prefix, so any halving is an inference with the direction known and the magnitude unknown. Sizing a pair budget in pairs removes the need to split it at all. | Andre |
| 4 | The bound is sized against the worst measured pair, not the mean. A max 17 percent above the mean is what a bad night looks like, and the page says which statistic sizes the bound. | Carmack |
| 5 | **The council page and the handover are left alone.** Their stale figures are corrected by the rows that already touch them - row #3 rewrites the council page and row #19 the handover - rather than dragging two more files into a budget row. | Owner, 2026-09-21 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Replace the shared constant everywhere it is quoted | One judge's measurement then re-sizes the work shard's budget, the placement arithmetic and two doc pages, none of which was measured | A twelve-file row that fails on a surface nobody was changing | Owner |
| 2 | Keep the derived figure | An unlabelled 1.64x margin sizes the judge's bound | A budget built on a number nobody took | Carmack |
| 3 | Wait for a night at the cap | The cap has never run and nothing schedules it | One dispatched run | Carmack |

---

### Row #11a - The model layer offers both spans and says what it decoded

- **Side: shared.** The model layer serves the summariser today and any judge later. It imports no judge and names none.
- **Scope:** a caller may open a thinking channel, pin the probability mode, constrain a grammar at the answer position, and receive the raw first-token window at that position with a digest of what was posted.
- **Files touched:** `backend/idhazh/llm/server.py`, `backend/tests/test_decode_split.py`, `tests/fixtures/`, `docs/reference/benchmarks/which-probabilities-the-server-returns.md` (new)
- **Acceptance gates:** local - `test_decode_split.py`, `test_summarize.py`, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** two arms, and the second is the one round six had to add.
  - **The reply arm**, driven by recorded replies through the module that already owns the two-span split, **importing nothing from `idhazh.similarity`**: a reply from an entry declaring a thinking close yields a thinking span and an answer span, and the returned window is the server's list at the requested position.
  - **The posted-body arm**, asserting on the request the builder produces rather than on a reply: span one carries neither `grammar` nor `n_probs`, and every posted key is either in the digest or in the named exclusion list. **A reply-driven oracle cannot see a request-side defect**, which is exactly how the two faults in decisions 3 and 7 survived five rounds.
  - It cannot settle what a live model returns.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Thinking is supported, not refused.** An earlier draft refused a call whose model entry opened a thinking channel. That was wrong: thinking mode is a stated direction, and a guard that breaks a caller the day the feature lands is not a guard. | Owner, 2026-09-21 |
| 2 | **The machinery already exists** - the layer carries a thinking span and an answer span, the summariser's payload builder sends the template flag that turns the channel on, and `decode_split` already tests the split. This row makes the same shape reachable by a constrained caller. | Owner, 2026-09-21 |
| 3 | **`thinking_span` strips `grammar` and `n_probs` and takes its own temperature - round six found the first two and round seven the third.** `server.py:733` derives span one from the answer body by removing one key. On the grammar route span one would inherit the grammar, so the model is constrained to three verdict words **and cannot write a thinking block at all**; it would inherit `n_probs`, asking for 25 alternatives at every position; and it would inherit **temperature 0.0**, which is greedy decoding on a span whose length is uncapped by default. Greedy plus unbounded is the repetition-loop case, and the loop ends only at the marker or the context window. `n_predict` and the stop marker are already handled at `server.py:733-736`. | Andre |
| 4 | **A grammar may be constrained at the answer position rather than at position zero.** Constraining the first token forces an answer where the model meant to start reasoning. | Andre |
| 5 | **The layer returns the raw first-token window and computes no margin.** It has no idea what a verdict opening is, and it must not: row #12 decision 3 already names a tenant whose emitted token is discarded and whose distribution is the answer, so one shared margin would be two instruments in one column. **Each judge takes its own reading over the window.** | Andre |
| 6 | **The position the window is read at is an argument, defaulting to zero.** The layer's current reader is hard-pinned to position zero and justified in its own docstring by "a grammar of three literals has nothing left to be uncertain about" - one judge's grammar shape, stated as a property of the shared layer. The justification moves to the judge that holds it; the layer takes a number. | Andre |
| 7 | **The decode digest is every posted key not in a named exclusion list - not a fixed six.** Round six counted the grammar builder's body: ten keys, of which the three named exclusions (prompt, grammar, model) leave seven, so `stream` and `cache_prompt` were in neither list and the key-enumeration test would have gone red on its first run. A fixed count is also one route's key set; a second caller on the schema route posts a different one. Each exclusion carries its reason on the line that names it. | Andre |
| 8 | The window is sized by the caller, from its own grammar's legal first-token set. The layer applies the number and does not derive it. | Andre |
| 9 | The probability mode is sent explicitly rather than inherited from a build default, and which mode the server returns is measured and written up in its own benchmark record. **That measurement is a blocking predecessor of row #11b's margin rule**, not a nicety: if the returned probabilities are already post-grammar they sum to 1 over legal tokens, renormalising is a no-op, and the column loses the "the grammar chose and the model did not" signal it exists for. Until the reading is taken, any renormalising rule is an estimate (Guardrail #10). The same run reports whether the build honours `n_probs: 25`. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Refuse a call whose model entry opens a thinking channel | It breaks on the day thinking mode ships, and thinking mode is a stated direction. A guard against a feature you intend to use is a bug with a schedule | A caller that stops working when the writing improves | Owner |
| 2 | Compute the margin in the model layer | It would have to know one judge's grammar, and it would be wrong for the scorer | The model layer, coupled to a judge | Andre |
| 3 | Add the token counts here, as an earlier draft's decision 8 did | **The premise was false.** `server.py:370-371` already declares `prompt_tokens` and `completion_tokens` on the reply type and fills them at 928 and 944. The type that drops them is `similarity/judge.py:47`, a judge module this row does not touch - so the decision delivered nothing and pinned a council column to a row that could not fill it | A council column whose only producer is inside a judge | Carmack |
| 4 | Assert thinking off in the prompt wording | Prompt wording is not a control, and a template cannot close a channel the server opened | A guard that reads as one without being one | Andre |

---

### Row #11b - The content-similarity judge reads its own margin

- **Side: judge.**
- **Scope:** this judge opens the thinking channel behind a model role of its own, constrains its six legal strings at the answer span, buckets its first-token window by verdict prefix, and records which envelope ran.
- **Files touched:** `backend/idhazh/similarity/judge.py`, `backend/idhazh/similarity/prompt.py`, `backend/idhazh/similarity/stamps.py`, `backend/idhazh/similarity/fold.py` (the change detector), `backend/idhazh/contracts/story_similarity_pair.py` (the envelope column), `config/idhazh.json`, `config/models/`, `backend/tests/test_similarity_judge.py`, `tests/fixtures/`, `docs/reference/benchmarks/what-the-thinking-envelope-changes.md` (new), `schemas/story-similarity-pair.schema.json` (generated)
- **Acceptance gates:** local - the similarity test modules, contract export, drift gate, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** four cases. A recorded reply from an entry declaring a thinking close has its verdict read from the **answer** span, with the thinking span held for the assertion and never parsed as a verdict. A window whose only verdict token is **space-prefixed** yields a **non-null** margin. A window containing the bare `" "` token - which is a prefix of all three verdicts - drops it as unattributable rather than counting it three times. A window resolving to one verdict yields null.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge asks for a window sized to **the 25 non-empty prefixes of its six legal strings**, not to the count of verdict words. That is what the grammar admits at the answer position. | Andre |
| 2 | **The window is bucketed by prefix, not by spelling - round seven corrected round six's own correction.** A first-token window holds **tokens**, and a token is a prefix of a legal string rather than a legal string: if a vocabulary spells ` UNCLEAR` as ` UNC` plus `LEAR`, a rule that buckets on the six full spellings scores UNCLEAR at zero and reports a two-way gap as a three-way one. So each returned token is matched against the verdicts its stripped text opens, summed into that verdict, and **a token that opens more than one - the lone `" "` opens all three - is dropped as unattributable before renormalising.** | Andre |
| 3 | **The premise round six argued this from was false, and that is recorded rather than quietly dropped.** It claimed the margin was taken over three bare verdict ids. `judge.py:87 margin_of` sorts **every** returned choice and subtracts the top two; `first_token_ids` is called once a shard at `judge_shard.py:76` as a vocabulary refusal and thrown away. **82 committed rows carry a non-null margin**, which is the counter-evidence. The prefix rule is still the right rule - it is what makes a widened window mean anything - but it is a change, not a repair. | Andre |
| 4 | **`first_token_ids` moves to the prefix set or it is retired.** Its refusal exists because one probability read cannot tell two verdicts apart when they share an opening token, and under decision 2 the token that actually collides is the lone space - which the current bare-word check cannot see. A refusal guarding arithmetic nobody performs is worse than none. | Andre |
| 5 | **The stamp gains a seventh field for the envelope, and the pair row a seventh column.** Round seven found decisions about "recording which shape ran" with nowhere to record it: `decode_digest` is **byte-identical** with and without a thinking span, because the only posted key that moves is `prompt` and `prompt` is a named exclusion. Without the field, row #21b's stamp filter admits both envelopes as one population. | Andre |
| 6 | **The channel cannot be opened without a config change this row owns.** `config/models/qwen3.5-9b-q4km.json:50` sets `thinking_close: null`, so `thinks` is False and `thinking_span` raises. The channel lives in a second entry file that also moves the summariser's answer budget, its cache types and its batch size - so **the judge takes a model role of its own** rather than the whole pipeline moving. This makes the row Level 5, and it was drafted as though it were Level 2. | Owner |
| 7 | The change detector gains the temperature, the decode digest and the envelope field in this commit. A stamp column the detector cannot see is a stamp that lies. | Andre |
| 8 | **The envelope is not flipped on the strength of a plumbing test, and the replay is not cheap.** Both oracles drive recorded replies, which say nothing about whether reasoning changes a verdict - and this row lands in the group that erases the distribution record, so a before-and-after could never be taken afterwards. **Priced: the baseline arm is 82 pairs x 94.53 s = 2.15 h; the thinking arm at the measured 11.18 tokens a second and an estimated 800 reasoning tokens a call is about 5.4 h, and at 1,500 tokens about 8.3 h - past the 6 h job ceiling.** So it runs as a dispatched job on the council's own workflow, which already restores the weights and starts the server, as a matrix of two envelopes by four shards at about 1.4 h a job. **`max_think_tokens` is capped for the replay and the cap is named as part of the instrument.** | Andre |
| 9 | **The temperature claim is corrected.** An earlier draft argued thinking support from "the temperature is already above zero". This judge decodes at `judge_temperature: 0.0`. The conclusion stands on row #11a decision 1's reason - thinking mode is coming - and not on a number that is false for this call. | Andre |
| 10 | The thinking span is held in memory for the assertion and is **not** persisted. Note that `answer_span` already splices span one's text into span two's prompt and prices that in its own docstring, so this decision adds no injection surface and does not re-derive one. | Andre |
| 11 | ESCALATE: this changes the judge's model entry, widens the record's stamp, and resets the distribution once by construction. Sign-off on the model role and the reset. **Decision 8's replay is taken before the reset, or it cannot be taken at all.** | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the three-wide window | It is sized to the answer set rather than to what the grammar admits | A margin over the wrong tokens | Andre |
| 2 | Bucket on the six legal spellings | A window holds tokens, not strings. A verdict whose opening is split across two tokens scores zero and the column reports a two-way gap as three-way | A number that is wrong on a vocabulary nobody checked | Andre |
| 3 | Take the margin over the whole returned window | A prefix of a legal string is not a verdict, so two prefixes of one verdict read as a close call between two verdicts | A number that inverts on the case it exists to catch | Andre |
| 4 | Move the whole pipeline to the thinking model entry | It changes the summariser's answer budget, cache types and batch size for a judge's benefit | An uninstrumented change to the reader-facing writing | Owner |
| 5 | Flip the envelope and measure later | The reset erases the only baseline, so "later" is never | An instrument change with no before | Andre |

---

### Row #12 - The four verbs name their work

- **Side: judge.** It lands after row #24, which is what takes the judge's verbs out of the workflow.
- **Scope:** the same-story verbs, their stage modules and their stage functions are renamed to say what they do.
- **Files touched:** `backend/idhazh/cli.py`; `backend/idhazh/stages/judge_draw.py` -> `pick_item_pairs.py`; `judge_shard.py` -> `judge_item_pairs.py`; `judge_fold.py` -> `count_verdicts.py`; `judge_fit.py` -> `set_merge_line.py`; `backend/idhazh/similarity/fit.py`, `fold.py`, `tenant.py`; the three similarity test modules; `docs/how-to/label-the-similarity-holdout.md`; `docs/reference/repository-layout.md`; `docs/architecture/publishing/autotune-content-similarity.md`; `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the changed-test selector over the similarity modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** every renamed stage is reachable by its new name and no module resolves under the old one. **The workflow is not part of this comparison, and round seven is why**: row #24 replaces the judge's four verbs in the workflow with council verbs over a tenant list, so after it lands the workflow spells none of these names. Two rows rewriting one workflow file in opposite directions, unordered under two-lane execution, is how the second one rebases onto a file it does not recognise. It cannot settle whether the new names are better - decision 1 is the owner ruling.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `judge-draw` -> `pick-item-pairs`, `judge-shard` -> `judge-item-pairs`, `judge-fold` -> `count-verdicts`, `judge-fit` -> `set-merge-line`. | Owner, 2026-09-20 |
| 2 | A verb names its subject, and nothing is named `judge-<step>` again. That is what lets the summary-quality judge take `pick-summaries`, `score-summaries` and `count-scores` without colliding. | Fowler |
| 3 | A judge whose emitted token is the answer takes the `judge-` stem; one whose token is discarded and whose distribution is the answer takes `score-`. | Andre |
| 4 | **The workflow job ids move in row #24, not here.** They were in this row's scope while the workflow still invoked the judge directly; once the council owns the jobs, a job id is the council's name for a step and renaming it twice is work thrown away. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A two-level judge namespace | The router would hold a name registry, and only one of four steps is shared with judge two | A dispatch table and a package with no reason to exist | Fowler |
| 2 | Keep the family prefix | The prefix is what ties the verbs to one loop, which is the defect | The second judge's verbs lie or break the pattern | Fowler |
| 3 | Land this before row #24 | The workflow rename it does is deleted by #24 a week later, and under two-lane execution the two rebase against each other | Two rewrites of one file for one outcome | Carmack |

---

### Row #13 - `leg` and `fold` leave the vocabulary

- **Side: shared.** A vocabulary scrub over both sides, landing after the verb rename.
- **Scope:** the two borrowed words are deleted from identifiers, field names, field descriptions, docstrings and prose, the one persisted field among them takes a read-side migration, and the plain-meaning test that caught them is written down.
- **Files touched:** every tracked file carrying `leg` as a word - **counted by the row itself, with the exact pattern its oracle will use, as the first step**; `backend/idhazh/similarity/fold.py` -> `counting.py`; `backend/idhazh/similarity/draw.py` -> `selection.py`; `backend/idhazh/contracts/story_similarity_distribution.py` (the field), `fitted_similarity_threshold.py`, `story_similarity_pair.py`, `knobs/placement.py`, `knobs/council.py` (field descriptions); `backend/idhazh/stages/judge_fit.py`; `state/story-similarity/score-distribution.json` and its archived sibling; `schemas/` (generated); `frontend/src/contracts/` (generated); `frontend/src/lib/console/merge-line.ts`; `frontend/src/routes/console/judgement/`; `CLAUDE.md` section 0b; `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the similarity and contract test modules, contract export, drift gate, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a grep **over source, config, schemas, workflows and docs** finds no `leg`, `legs` or `fold` used as a name for a shard or for the collecting job, **and the committed record loads through the migration with its date list intact**. The grep is scoped the way row #18's is - `backend/`, `frontend/src/`, `.github/`, `docs/`, `schemas/`, `config/` - because tracked text also includes 9,989 published summaries, the corpus and every committed day file, and a gate that walks those costs more every night the pipeline runs (Guardrail #12). It cannot settle whether a future borrowed word is caught - that is what the test in section 0b is for.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `leg` is a pure synonym for `shard` wherever it names one - **every occurrence means the thing the `shard` column already names**. It is deleted, not replaced. **The row counts its own scope before it starts**: an earlier draft carried "75 occurrences across 18 files", which round six re-took as 25 files in `backend/` and `.github/` alone, plus the generated frontend contracts the file list had missed. A count of a tracked tree is a rotting number (Guardrail #10), so the property is what is written here and the count is taken on the day. | Owner, 2026-09-20 |
| 2 | `fold` is functional-programming vocabulary for the job that collects the shards' output, commits it and counts it. The job becomes `collect`, and **prose names the action, never the job**: "a day with a missing shard is not counted into the record". | Owner, 2026-09-20 |
| 3 | The repository has done this scrub before - `arm` became `cases` on 2026-09-15 with a read-side migration - so the pattern and its changelog wording already exist. | Fowler |
| 4 | Two occurrences of `leg` mean a clause of a two-part rule rather than a shard. Those become "the first of two checks". | Fowler |
| 5 | Five contract files carry the word in **field descriptions**, so the scrub regenerates schemas and takes a changelog line. | Section 11 |
| 6 | **One occurrence is a field name, not a description - seam 6.** `folded_dates` on the distribution record is a published schema property, and two committed payloads carry it: the live record and one archived sibling. It becomes `counted_dates`, and **the read-side migration ships in the same commit**: the reader accepts the old key, the record is rewritten once on the next run, and the schema takes a date stamp and a changelog entry. An earlier draft said "no field name or value moves, so no payload migrates", which was simply untrue. | Section 11 |
| 7 | The plain-meaning test goes into section 0b, where the voice rules live, because this is the fourth borrowed word this repository has had to remove. | Owner, 2026-09-20 |
| 8 | ESCALATE: the field name, the migration and the schema stamp land in one commit, or a run reads a record it cannot parse and the fitted line is lost. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Invent a new word for a shard | There is nothing to name - the concept already has a name used everywhere else | A third synonym | Fowler |
| 2 | Leave the field descriptions and fix only identifiers | The descriptions are the generated schema, so the word survives in the published contract | A word deleted from code and kept in the artifact | Section 11 |
| 3 | Scrub `fit` as well | "Fit a line to evidence" is ordinary English, and the verb rename already fixed the surface a person types | Churn with no reader gain | Fowler |
| 4 | Leave `folded_dates` alone because it is persisted | The word is the one this row exists to delete, and the record is two files | The scrub, half done, with the word surviving in the published contract | Owner |

---

### Row #14 - The judge fills the stamp, and starts counting what its calls cost

- **Side: judge.**
- **Scope:** the judging stage records, per reading, which judge read it, at what temperature, under which posted sampler, whether both calls opened inside the grammar, and what the returned window held - **and the two reply types start carrying the call counts the council's record needs.**
- **Files touched:** `backend/idhazh/stages/judge_item_pairs.py`, `backend/idhazh/similarity/judge.py`, `backend/idhazh/similarity/counting.py`, `backend/idhazh/similarity/stamps.py`, `backend/tests/test_similarity_judge.py`, `tests/fixtures/`
- **Acceptance gates:** local - the similarity test modules, ruff, mypy. CI - full suite.
- **Oracle:** a recorded reply whose window omits a verdict opening produces a row with the grammar flag recorded, `usable` false, `verdict` null, and the counting step skips it - and the stage exits 0. **The margin is not asserted against the vector**, because both derive from one tuple and that assertion is a tautology that cannot go red. A second case drives a pair whose first call failed and asserts the call count is 1, not 2.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A grammar failure is recorded rather than raised. Today it raises and the stage dies, so absence means two things an operator cannot separate. | Andre |
| 2 | **The agreement test gains a null check in the same change.** It compares the two verdicts today, and a nullable verdict makes two failures compare equal - so `usable` would go true with no verdict, and the pair row's own validator refuses exactly that shape. The writer that reaches for the verdict's value maps null to empty rather than raising on it. | Andre |
| 3 | The grammar flag means **both calls** opened inside the grammar, and the judge's `pairs_refused` counts rows where it is false. | Andre |
| 4 | **Both calls always run.** A first-call failure does not skip the second, or the pair row's decode seconds - documented as both calls - silently becomes one. | Andre |
| 5 | The judging stage is the only writer of the stamp's model-side columns. The selection stage writes the row with verdict columns empty and carries only the defaulted judge identity. | Fowler |
| 6 | **The two reply types gain the counts the council's record has no other producer for - round seven found the gap and it was round six's defect repeated one level down.** `Reading` at `judge.py:47` carries `prompt_tokens` and no completion count; `Judged` at `judge.py:56` carries neither and collapses `decode_seconds` to the pair's sum, so the stage at `judge_shard.py:87` never sees a per-call figure. `Reading` gains `completion_tokens`; `Judged` gains `prompt_tokens`, `completion_tokens`, `calls` and `decode_seconds_max`. **Three of `ShardResult`'s four cost fields and the judge's own `decode_seconds_max` all die without this**, and until round seven no row named the file. | Carmack |
| 7 | `calls` is counted, never derived as twice the pairs. A pair whose first call failed made one call. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep raising on a grammar failure | Absence means two different things and an operator cannot separate them | A failure that reads as a missing shard | Andre |
| 2 | Assert the margin against the stored vector | Both derive from one tuple, so the oracle passes in every failure world | A green test that proves nothing | Andre |

---

### Row #15a - The council's package, the tenancy protocol and the shipping capability

- **Side: council.** This row creates the council's package. Its gates run with no judge in the repository.
- **Scope:** the shipping capability and the tenancy protocol, declared with no tenant present.
- **Files touched:** `backend/idhazh/council/__init__.py` (new), `backend/idhazh/council/tenancy.py` (new), `backend/idhazh/council/metrics_sink.py` (new), `backend/idhazh/ledger.py`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_metrics_sink.py` (new), `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/test_marks.py`, `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the council test package, the staging test module, the workflow harness, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** **a throwaway `Contract` subclass declared inside the council's own test module** is written, uploaded under a name the collecting job's download pattern matches, and appended to the store its own contract names. **Not `ContentSimilarityJudgeMetrics`** - gating the venue on a tenant's contract gives the venue a false red the day that tenant moves a column, and it makes the venue's test unrunnable in a repository with no judge. **Not "the staged path list mentions the store"** either: staging a path on a machine where the file was never written stages nothing and exits 0, so that assertion goes green over an instrument that records nothing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The capability declares nothing about the payload.** It takes a `CsvRecord`, a judge identity and an output directory, calls the record's own `csv_row()` and the class-side `csv_columns()`, and writes one file a shard with a temp-file-then-rename. **`CsvRecord`, not `Contract`** - the base class declares no CSV surface at all, so a value typed `Contract` cannot be written as a row. | Owner, 2026-09-20 |
| 2 | **The throwaway contract is a fixture, not a mock - seam 4.** It returns no plausible value and stands in for no real implementation; it is a two-column row that exists so the venue's test names no tenant. A mock would be a fake judge asserted as if it judged. Guardrail #7 is about the second thing. It is never registered in the export tuple, so no schema is generated and the drift gate never sees it. **It declares one changelog entry**, because the base class refuses a subclass without one, and it hand-declares `csv_row`, `csv_columns` and `from_csv_row` like every other CSV contract. | Guardrail #7 |
| 3 | **The tenancy protocol is declared here, and it names no judge.** Seven members: the judge's slug, its shard count, the store paths it commits, the nights it is behind on, and the three units of work - prepare, run a shard, settle. A `typing.Protocol` is structural, so the council never imports a judge to type against it. Section 1c carries the signatures and is where the count is written once. | Fowler |
| 4 | **The council's own artifact path, and the reason is that a commit would not reach the reader.** Every checkout in the council names no ref, so each job is pinned to the commit the run started at. A shard that commits its rows at 22:40 puts them where the collecting job - checked out at 22:00 - cannot see them, and the counting step decides whether every shard reported by counting the files it downloaded. Moving the rows into the tree does not make them safer; it makes them unreachable. | Fowler |
| 5 | **Segments solve a conflict this workflow does not have.** The compaction's own docstring says they are where a writer puts its rows when more than one job writes one ledger. The digest pipeline has four to eight committing shards on one day file; the council has one committing writer, and its day file is already settled on every write by a key carrying the run id - which is the property segments exist to provide. | Fowler |
| 6 | **The trigger that adopts segments, stated so it is a condition rather than a preference:** a judging shard whose output is too large for an artifact, or which must survive the artifact's 24-hour retention. Adopting them then also requires giving the collecting job a way to see commits made during its own run, which it does not have today. | Owner, 2026-09-20 |
| 7 | The collecting job appends each row to the store its own contract names, so a second judge needs no change here. | Fowler |
| 8 | The staging drift guard is widened in this row to every workflow reaching a store writer, not only the daily one. | Carmack |
| 9 | New test modules carry no mark, so they are named in the unmarked-module registry or the mark census fails. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Gate the capability on the judge's metrics contract | Seam 4. The venue goes red when a tenant renames a column, and the venue's test cannot run with no tenant | The dictum, failed at condition 4 | Owner |
| 2 | Shards commit segments; the digest pipeline's compaction files them later | The collecting job cannot see commits made during its own run, so a re-run finds an empty directory. It also makes the council able to stop publishing: the compaction parses every waiting row through its contract and runs before the digest run plans a day, so one malformed judge row ends that run | Rows the counting step cannot reach, a cross-pipeline outage path, and three closed sets widened per judge | Fowler |
| 3 | The collecting job writes segments instead of appending | One writer cannot conflict with itself, and the rows then wait for another pipeline's schedule - up to 4.8 hours - to become readable | A dependency on someone else's cron for no gain | Fowler |
| 4 | Segments plus the council running the compaction verb | The verb has no filter and the transit directory is shared | Twenty-one waiting files deleted, their heads uncommitted | Carmack |
| 5 | A capability that defines the metric columns | That is the council dictating a judge's metrics - the coupling this plan removes | Judge two files columns it cannot have | Owner |
| 6 | An abstract base class instead of a protocol | The council would have to be imported by every judge, and a judge would inherit the venue | A dependency pointing the wrong way | Fowler |

---

### Row #15b - The content-similarity judge fills its metrics and registers as a tenant

- **Side: judge.**
- **Scope:** this judge counts its own funnel, files its row through the capability, satisfies the tenancy protocol, and **registers itself in the council's tenant list**.
- **Files touched:** `backend/idhazh/similarity/tenant.py` (new), `backend/idhazh/stages/judge_item_pairs.py`, `backend/idhazh/stages/count_verdicts.py`, `config/idhazh.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `backend/tests/test_similarity_judge.py`, `backend/tests/test_similarity_fold.py`
- **Acceptance gates:** local - the similarity and app-config test modules, ruff, mypy. CI - full suite.
- **Oracle:** a shard driven against a fixture selection writes a metrics row whose funnel identity closes, the row appended by the collecting job is byte-identical to the one the shard wrote, **and the committed config names this judge's slug** - so the night the plan closes, the council has a tenant. It cannot settle whether the counts describe a real night.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge imports the protocol and the capability from the council. **That direction is the allowed one** - a tenant knows its venue, a venue knows no tenant. | Fowler |
| 2 | **The committed value of `council.tenants` becomes `["content-similarity-judge"]` here, and round seven is why.** Row #24 created the list and defaulted it empty; no row wrote a slug into it. Every other knob in this plan names its committed value, and this one was going to ship empty - so the whole plan would have landed, every gate green, and the nightly run would have judged nothing. | Carmack |
| 3 | The judge narrows its own id to a one-member `Literal` in its own module, which is where a closed set can be honestly closed. | Fowler |
| 4 | `pairs_refused` counts pairs, not calls, and the funnel identity is enforced by the contract from row #6 rather than re-checked here. | Andre |
| 5 | The upload carries an always condition, and the shard uploads as it goes rather than once at the end. **The real exposure was never the collecting job dying - it is a shard dying**, which today ships nothing at all after up to 79 minutes of judging. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Register the tenant in a council-side table | The council would name a judge, in code, at import time | The dictum, failed at condition 1 | Fowler |

---

### Row #16 - The model block becomes one composite action

- **Scope:** the weights cache, the fetch, the checksum verify, the server start and the health probe become one composite action, used by the two workflows that run all five steps.
- **Files touched:** `.github/actions/model-server/action.yml` (new), `.github/workflows/llm-council.yml`, `.github/workflows/digest.yml`, `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/workflows/test_model_server_jobs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`
- **Acceptance gates:** local - the workflow harness across both files. CI - full suite.
- **Oracle:** the cache key literal inside the action matches a committed fixture character for character. **Not a comparison against the daily workflow** - once the key moves into the action there is nothing left there to compare against.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measured across all eleven workflow files - one ends `.yaml`, which is how an earlier count missed it: four call the shared fetch script, three spell the server-start step verbatim, and one runs all five under its own names. This row converts the two that run the five identically. | Carmack |
| 2 | **This row lands before row #17**, because row #17's oracle asks where a step sits relative to the server start and this row moves that step into the action. | Carmack |
| 3 | Every test that looks a weights step up by name moves with it. Four modules do, including two tables in the shared harness pinning three step names for three jobs. | Carmack |
| 4 | A composite action carries no job-level knob, so the bound, the matrix and the runner label stay in the workflow. The cache-hit output is declared explicitly or the fetch condition silently stops working. | Carmack |
| 5 | The one-server-per-shard guard survives by reading the action's step list rather than the job's. It is what stops a second server landing on a 16 GB runner. | Carmack |
| 6 | Whether a composite step sees the caller's workflow-level environment is verified on a branch first; if it does not, the port becomes an action input. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A callable workflow | Its only unique benefit is a per-caller runner label and permission set, and nothing needs either | A restructure for a differentiation nothing uses | Carmack |
| 2 | Convert all six cache blocks | Four share one of the five steps; folding them in makes the action a parameter soup | Four callers using a tenth of it | Carmack |

---

### Row #17 - The council runs the tenant and files its own outcome row

- **Side: council.** Its gates run against a fake tenant, with no judge in the repository.
- **Scope:** the council invokes the tenant through the protocol, times it, files its own outcome row on the way out, ships it, and the collecting job commits it.
- **Files touched:** `backend/idhazh/council/session.py` (new), `backend/idhazh/council/metrics_sink.py`, `backend/idhazh/cli.py`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_session.py` (new), `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/workflows/test_staged_paths.py`, `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/test_marks.py`, `state/llm-council/.gitkeep`
- **Acceptance gates:** local - the council test package and the three workflow test modules. CI - full suite.
- **Oracle:** a run that records three of four shards leaves a store an operator can read as "one shard is missing", because the recorded shard count and the row count disagree - **driven by a fake tenant whose third shard raises**. A second case: a fake tenant that returns `stopped_on_deadline` still has its row filed. It cannot settle why a real shard is missing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The council writes its own row - seam 5.** An earlier draft had the judge's two stages write it, so the venue's record existed only because a tenant remembered to file it, and a judge that forgot would leave the venue blind. The council owns the invocation, so it owns the outcome: it starts the clock, calls the tenant, catches what comes back, and files the row in a `finally`. | Owner, 2026-09-21 |
| 2 | The council records the shard's identity, its clock, its outcome and the aggregate cost of the work it hosted - and nothing that needs a name for the unit. | Owner, 2026-09-20 |
| 3 | **The five values the council files come off `ShardResult`, not out of a judge's store or off a judge's contract - seam 7.** The protocol used to return the judge's own metrics contract, and row #6 rules that those columns are shared with nobody, so the council could have filled its own row only by reading named attributes off a tenant. A tenant with no model returns nulls. The council looks inside nothing. | Owner, 2026-09-21 |
| 4 | **No host fingerprint.** The probe wants 1.9 GiB on a job whose two processes already hold up to 9.02 GiB of anonymous memory in 16 GB, the council's data is discardable, and the digest pipeline already characterises the same runner pool. Dropping it removes the only memory risk in this plan rather than ordering around it. **The number is 9.02 and not 14.31**: the 14.31 GiB reading is summed RSS across two processes and its own source says so in its title, counting every shared page twice - round six found it quoted here against the caveat it carries at home (Guardrail #10). | Carmack |
| 5 | **No per-call spans and no span rollup.** The judge's own row carries the call count, the total and the worst, which is what the three questions actually need. | Owner, 2026-09-20 |
| 6 | The outcome row is written by the same capability the judge metrics use, so there is one shipping path and not two. | Fowler |
| 7 | The store is seeded with a `.gitkeep`, **not a header-only day file**. A header-only file at a day path is a real day file to the partition walker - a permanent phantom day in the prune target and the day inventory. The three seeded directories in this repository are all `.gitkeep`. | Fowler |
| 8 | **A tenant with no model returns `shard_count = 1`.** Sharding exists because a model is slow; a pure-Python tenant given four jobs pays four weights restores for work that uses none of them. The width is the protocol's answer, not a council constant. | Carmack |
| 9 | This row assumes plan 37's corrected sampler and does not wait for it. Nothing here reads the sampler. | Owner, 2026-09-20 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Let the judge's stages write the council's row, as the earlier draft did | Seam 5. The venue's record depends on a tenant's diligence, and a tenant that dies before its last line files nothing | A blind venue, exactly when a shard failed | Owner |
| 2 | Import the digest workflow's observability set | Half of it answers questions a judge does not have, and its item-health row carries 113 columns this pipeline does not fill | Stores that stay empty or carry meaningless rows | Owner |
| 3 | Record the machine per shard | The runner pool is already characterised, and the probe is the only OOM risk in the plan | A reading nobody asked for | Carmack |

---

### Row #18 - The store groups under the judge that fills it

- **Scope:** the committed same-story tree moves under the judge slug that produced it, and every reader, workflow path and document naming the old tree moves with it.
- **Files touched:** `backend/idhazh/ledger.py`, `backend/utilities/sample_sheet.py`, `state/story-similarity/` -> `state/content-similarity-judge/`, `.github/workflows/llm-council.yml`, `.gitattributes`, `frontend/src/lib/server/similarity-holdout.ts`, `frontend/src/routes/console/judgement/+page.server.ts`, `docs/reference/repository-layout.md`, `docs/architecture/publishing/autotune-content-similarity.md`, `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/publishing/retention.md`, `docs/how-to/label-the-similarity-holdout.md`, `TODO/20260920-a-second-judge-in-the-council-handover.md`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/retention/test_prune_range.py`, `backend/tests/`
- **Acceptance gates:** local - the ledger and similarity test modules, the workflow harness, the frontend build, `doc_load.py --changed`. CI - full suite, plus the published-site smoke.
- **Oracle:** no reader in backend, frontend, workflows or docs resolves a path under the old name - a grep over tracked files, asserted once. **The file-by-file byte comparison is an operator check run during the move**, not a committed test: walking the tree every run is a growing read.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group, so the store a judge produces sits under the judge's name, beside its metrics store. | Owner, 2026-09-20 |
| 2 | The stores under it keep their names - scored pairs, fitted thresholds, the distribution record, the holdout and the archive all move unchanged. | Fowler |
| 3 | The council workflow names the old paths in its commit step. It moves here, or the next run's staging aborts under a failing shell and costs the ledgers beside it. | Carmack |
| 4 | **`STORY_SIMILARITY_DIRNAME` is deleted**, not left holding the new string. Two constants carrying one value re-opens the drift the closed sets exist to close, and the prune vocabulary is built by joining those constants - so the prune words move with them. | Fowler |
| 5 | `git mv` per file, so history follows and the move reviews as a rename. A rename of the tree, not a rewrite of its rows. | Fowler |
| 6 | ESCALATE: this moves committed data. The path map is signed off before any file moves. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the tree and put only new judges under slugs | Two organising schemes, and the oldest judge looks like the exception | A layout no reader can infer a rule from | Fowler |
| 2 | Leave a compatibility path | A second name for one store | One path that works and one that used to | Fowler |

---

### Row #19 - Where the content-similarity judge's merge line stands against its holdout

- **Scope:** the merge line is scored against the labelled holdout and the four counts are committed, with the negative population beside them and a floor below which the reading is refused.
- **Files touched:** `backend/idhazh/similarity/holdout.py` (new), `backend/idhazh/stages/score_merge_line_holdout.py` (new), `backend/idhazh/cli.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/knobs/placement.py`, `frontend/src/lib/server/similarity-holdout.ts`, `frontend/src/routes/console/judgement/+page.server.ts`, `docs/architecture/publishing/autotune-content-similarity.md`, `docs/how-to/label-the-similarity-holdout.md`, `docs/concepts/growing-reads.md`, `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/`
- **Acceptance gates:** local - the similarity and contract test modules, ruff, mypy, `doc_load.py --changed`, the frontend build. CI - full suite, plus the published-site smoke.
- **Oracle:** the four cells plus the unresolved count sum to the labelled population, **and** the resolved count clears the floor - without the floor, a run that resolved nothing satisfies the sum with four zeros and a full unresolved count, and the row reads as a measurement.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the line, not the judge. A judge-against-holdout measurement is a different row and a different budget, named in the scope-out table. | Andre |
| 2 | A shipped implementation already does this in the console's server layer. This row commits the counts so the reading survives the page, and the console then reads the committed row instead of recomputing beside it - two answers to one question is what the commit exists to stop. On a date with no row the console says the line has not been scored, never an error. | Andre |
| 3 | The read is bounded by the holdout file, whose rows name their own two days. | Guardrail #12 |
| 4 | ESCALATE: the floor is **half the labelled population**, a constant beside the frozen two-story maximum rather than a config knob, because it is a property of what makes the reading meaningful and not something to tune down to make a red row green. Retention deletes days the holdout still names, so this floor is reached by the calendar rather than by a bug. | Owner, 2026-09-20 |
| 5 | The frozen two-story maximum in the knobs module is reconciled with this row or retired, so one number does not have two sources. | Andre |
| 6 | The verb is `score-merge-line-holdout`. A person types it; nothing in the daily pipeline calls it. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish one accuracy figure | With 196 of 200 pairs on one side, always answering "one story" scores 98 percent and measures nothing | A number that looks excellent while the line is useless | Andre |
| 2 | Have the judge label more holdout pairs | The holdout's authority comes from being labelled outside the loop | The floor becomes a copy of the line it polices | Andre |
| 3 | Keep only the console panel | A reading that exists only while a page renders cannot be compared across weeks | No history | Andre |

---

### Row #20 - The plan pointer

- **Scope:** the index that lists live plans learns this one exists, and the findings that outlive the plan reach the pages that own them.
- **Files touched:** `AGENTS.md`, `docs/reference/agent-notes/`, `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local - `doc_load.py --changed`. CI - full suite. No application suite: documentation-only closure.
- **Oracle:** every live plan file is named by the agent index, and every entry names a file that exists.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A plan absent from the index is invisible to the next agent. | Fowler |
| 2 | **The plan-queue page is not touched.** A gate refuses any pull request that edits it and tells the author to restore it from the trunk; one job writes it after merge, and it discovers plans structurally - it already names this plan. | Fowler |
| 3 | The findings that outlive the plan go to the living doc that owns them. The separation itself went to the council page in row #3, which is why it is not repeated here. | Guardrail #4 |

---

### Row #21a - The council asks every tenant what it is behind on

- **Side: council.** Its gates run against a fake tenant, with no judge in the repository.
- **Scope:** the council builds tonight's date list from the union of its tenants' answers, inside a window it owns, floored at its own first night and capped per night; and it carries that list through the matrix, the artifact names and the collecting job. **No operator action repairs a dead night.**
- **Files touched:** `backend/idhazh/council/night_plan.py` (new), `backend/idhazh/council/tenancy.py`, `backend/idhazh/cli.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/council.py` (the window, the floor and the per-night cap), `config/idhazh.json`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_night_plan.py` (new), `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/contracts/test_app_config.py`, `docs/architecture/publishing/llm-council.md`, `schemas/app-config.schema.json` (generated), `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the council, workflow and app-config test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** **with zero tenants registered the plan names tonight and nothing else, and every later step still runs** - that is dictum condition 3, expressed as a test. With two fake tenants returning overlapping date lists the plan is their union, ordered, floored, capped. **The read is bounded by the window it is asked about** (Guardrail #12). It cannot settle whether a recovery succeeds on a runner.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The council asks; it does not look - seam 2.** An earlier draft had the council's night plan open a judge's distribution record and read its counted-dates list, so the venue knew a tenant's storage layout and could not plan at all without one. The plan calls `nights_outstanding(window=...)` on each registered tenant and unions what comes back. **With no tenants the union is empty and tonight is the plan.** | Owner, 2026-09-21 |
| 2 | **The window, the floor and the per-night cap are the council's**, because they price a runner and a matrix. What counts as outstanding is the tenant's, because only the tenant knows what it has read. | Fowler |
| 3 | **The window has a floor: the council's first night, and a tenant may raise it to its own.** The store holds one day file against 30 published days, so an unfloored window names 29 dates on its first run and cannot tell "this night died" from "the council did not exist yet". **The same sentence applies to a tenant that moves in later**: with only the council's floor it reports every date back to the council's own birth as outstanding. The floor is therefore per tenant, defaulting to the council's. | Carmack |
| 4 | **A per-night cap with a committed value of 1**, plus the floor. A cap without a floor only slows a 29-date backfill to 29 nights. | Carmack |
| 5 | **The judging job's timeout is per job, so a catch-up date costs wall clock, not headroom.** At the committed budget a shard judges 50 pairs at the measured 94.53 s a pair - 78.8 minutes against a 200-minute bound, per job, per date. | Carmack |
| 6 | **The matrix's parallel width is tenants times shards times dates**, capped at the platform's 20-job ceiling. Row #24 adds the tenant axis; this row adds the date axis. The timeout clock starts when a job begins executing, not when it is queued, so a queued job still gets its full bound. | Carmack |
| 7 | **There is no date multiplier on the config check, and round six is why.** An earlier draft multiplied the per-shard time budget by the date cap. Dates are a **parallel** axis - each date is its own job with its own bound, which decision 5 already says - so multiplying compares parallel work against a per-job number. It also refuses a legal config: 50 pairs x 94.53 s x 3 dates is 14,179 s against a 12,000 s bound, so `AppConfig` would reject `repair_dates_a_night = 2` while the knob's own bound admits 4. **A knob whose top half will not load is a lying bound.** The axis that genuinely compounds inside one job is tenants, and row #24 gives each tenant its own job. | Carmack |
| 8 | **Every artifact name carries the date, and row #24 adds the tenant to the same names.** Two dates in one run would either fail the job on an immutable name or silently overwrite the first date's verdicts - and the identical sentence is true of two tenants at shard zero, which would also collide on the merged filename. The collecting job's download pattern moves with them. | Carmack |
| 9 | **Recovery needs two things the workflow does not have, and neither is a stored secret.** The permissions block declares one scope and a declared block sets every unlisted scope to none, so cross-run download needs `actions: read` and the default credential passed explicitly. And **the uploads expire after one day**, before the next night's collecting job reaches them - so verdict retention rises to the cap plus two. A shard file is about 27 KB, so a week of four shards is under a megabyte. | Carmack |
| 10 | **The collecting job loops dates inside one job - it does not run per date.** Its two verbs, both commit messages and the command that rebuilds the derived record after a lost push all name a single date today, so a two-date night needs the loop either way. **What it must not become is two jobs**: the concurrency group is workflow-level and does not serialise jobs inside one run, so two collecting jobs would both push `main`. Row #24 decision 10 owns the shape. | Carmack |
| 11 | **An explicit dispatched date replaces the night plan entirely** and judges exactly that date. An operator naming a date is asserting something the plan cannot know. | Carmack |
| 12 | **No operator action repairs a dead night. An instrument change is a person's decision, and it is already one** - the model entry, the temperature, the prompt and the grammar all reach a runner through a reviewed commit, and rows #8 and #11b both carry a sign-off trigger. The person approves the instrument at the commit, not at 22:00 on a runner. | Andre |
| 13 | **This does not depend on anything noticing.** There is no alarm to read: the next run finds the gap because finding the gap is how it chooses its work. | Owner, 2026-09-20 |
| 14 | The house pattern is "the next run finishes the dead run's work". **The mechanism is new** - the digest run's catch-up drains whatever is waiting and takes no date at all, so there is no code to copy, only the principle. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | The council opens the judge's record, as the earlier draft did | Seam 2. The venue knows a tenant's storage layout, and with zero tenants it cannot plan a night at all | The dictum, failed at conditions 1 and 3 | Owner |
| 2 | An alarm reporting a night with no evidence, and a person re-dispatches | Manual effort with a notification in front of it, and it fails exactly when it is needed - a run that dies quietly is one nobody is watching for | A repair that happens only when somebody is looking | Owner |
| 3 | Accept the loss because the first fitted line is far away | **Builds for today's data rather than for the pipeline being built.** More judges are coming and the line will be wired to a published day | A record with gaps nobody can account for later | Owner |
| 4 | Have the council re-trigger itself through the platform API | The default credential cannot start a new run, so it needs a stored personal token | A credential to manage, for a repair the next scheduled run already does | Carmack |

---

### Row #21b - The content-similarity judge answers which nights it is behind on

- **Side: judge.**
- **Scope:** this judge implements the outstanding-nights member from its own record, keeps a memory of which nights it has seen that survives an instrument change, and admits only matching rows when it counts.
- **Files touched:** `backend/idhazh/similarity/tenant.py`, `backend/idhazh/contracts/story_similarity_distribution.py`, `backend/idhazh/similarity/fold.py`, `backend/idhazh/stages/count_verdicts.py`, `backend/tests/test_similarity_fold.py`, `backend/tests/contracts/test_story_similarity.py`, `schemas/story-similarity-distribution.schema.json` (generated)
- **Acceptance gates:** local - the similarity and contract test modules, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** driven against a fixture record and store, the answer names a date whose day file holds **three of four shards' rows** - the shape the dominant failure actually produces - and does not name a date the record has counted. A second case resets the counts and asserts the date memory survives.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The gap predicate is "the record has not counted this date", never "no committed evidence".** A run that lost one shard still commits the other three shards' rows, so a date with 75 percent of its pairs on disk is the common failure and reads as evidence. The one value meaning "this date is not in the fit" is the record's own counted-dates list. | Andre |
| 2 | **The record keeps a second date list that survives a reset.** Resetting the counts is correct when the instrument moves - the old counts were taken under a different instrument. Resetting the memory of WHICH dates were read is not: the stamp governs the counts and has nothing to say about which nights the council saw. So `judged_dates` persists across the archive-and-empty, and the answer reads it. **Without this the design latches**: widening the stamp empties the record, every date becomes outstanding, decision 3 refuses all of them, no judging job runs, so nothing ever empties the record again and nothing on the schedule can clear it. | Andre |
| 3 | **A date is refused only when the record previously counted it under an instrument that has since moved.** A date the council has never seen is judged normally whatever the stamps say, which is what keeps tonight working through an instrument change. | Andre |
| 4 | **The counting step admits only rows the record's own stamp matches**, and that filter runs BEFORE the one-row-a-pair de-duplication - otherwise a discarded row from the old instrument can still win a tie-break against a fresh one. Every value the filter needs is already a column on the pair row. | Andre |
| 5 | **Widening the stamp resets the record exactly once, and that is correct rather than a defect.** Nobody recorded the temperature or the posted body behind today's counts, and row #8 fills those cells empty rather than inventing them. Measured 2026-09-21: the record holds one date and eight agreed NO readings against gates of ten days and 200 negatives, so the reset costs four percent of the evidence the line needs before it can move at all. It lands in row #11b's commit beside the record widening, so the council judges that night as on any other night. Three existing surfaces record it - the archived file in the run's commit, the run log's report, and that date's fitted row carrying its held reason beside the new stamp. No new state, no new alarm. | Andre |
| 6 | The answer is computed against this judge's own record, inside the window the council passes in. A judge added later implements the same member against its own storage and the council changes by nothing. | Fowler |
| 7 | **The new date list takes a schema stamp, a changelog line and a read-side migration**, because two committed payloads carry the record today and neither has the field. | Section 11 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Re-judge without extending the pair key | The re-judged rows collide with the partial run's on a key that cannot tell two council runs apart, and the de-duplication keeps the row already on disk - so the fresh verdicts are discarded while the record counts them | Four shards of model time discarded on write, and a record that cannot be re-derived from the tree it summarises | Andre |
| 2 | Record both readings and let the counting step split the window at a fingerprint change | Splitting needs a per-date stamp the record does not have and a fit that can weight two populations | Two features to build before the first repair works | Andre |
| 3 | Reset the date memory with the counts | The design latches on the first instrument change and no schedule can clear it | A council that stops judging and says nothing | Andre |

---

### Row #22 - The guard that stops a shard committing is renamed and re-reasoned

- **Scope:** the guard keeps its assertion, loses a name carrying a deleted word, loses a dead reason, and learns to see a commit issued from a composite action.
- **Files touched:** `backend/tests/workflows/test_llm_council_workflow.py`, `.github/workflows/llm-council.yml`, `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the workflow harness, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the guard still refuses a judging job that commits, **and it detects one issued from a composite action** rather than only from an inline script. It cannot settle whether the new reason is the best one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The test's own name carries the word this plan deletes**, so it is renamed here with every other occurrence. A vocabulary scrub that leaves the word in a test name has not been done. | Owner, 2026-09-20 |
| 2 | The assertion stays. The reason goes: it says four shards would push into one union-merged file, and union merging left the judged-pairs store on 2026-09-19. Quoting it today quotes a dead fact and invites a reader to retire the guard with it. | Fowler |
| 3 | The reason that replaces it cannot be retired by a config edit: **the job that counts the shards is pinned to the commit the run started at, so rows a shard commits during the run are invisible to it.** | Fowler |
| 4 | The same dead premise is repeated in the workflow's own comment and is corrected in the same pass. | Carmack |
| 5 | **The guard is a substring search over the job's inline scripts, so it sees nothing issued from a composite action** - and the composite-action row moves the model block into exactly such an action. It is widened here rather than discovered later. | Carmack |
| 6 | The council page asserts the upload choice and has never priced it. It gains a `## Design rationale` naming the pinned checkout, the conflict segments solve, and the trigger that would change the answer. | Guardrail #4 |

---

### Row #23 - The council runs green with no judge in the repository

- **Side: council.** This is the row that makes the dictum checkable. It imports no judge, by assertion.
- **Scope:** a static import boundary over the council's package, and one end-to-end council run driven by a fake tenant with no judge anywhere in the call.
- **Files touched:** `backend/tests/council/conftest.py` (new, the fake tenant), `backend/tests/council/test_council_runs_without_a_judge.py` (new), `backend/tests/contracts/test_repo_structure.py`, `backend/tests/test_marks.py`, `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the council test package, the repo-structure test module, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** three arms, and the second is the one round six had to add.
  - **The directory arm** parses every module under `backend/idhazh/council/` and fails on any import naming `idhazh.similarity`, any module under a judge package, or any judge contract. The precedent is the existing repo-structure check, which already parses imports to hold the contracts package at the bottom of the graph.
  - **The closure arm** walks the **whole static import closure of the council's entry point** - `cli.py` and `AppConfig` included - and fails on a judge module reached at import time from any council verb. A directory arm alone would never have seen either of the two real couplings: `cli.py:75-78` imports four judge stages at module scope, and `app_config.py:42` imports the judge's knob module, so every council module that reads config carried a judge in its closure.
  - **The run arm** drives mint a run id -> resolve tenants from config -> build the night plan -> run the tenant under a deadline -> ship its row -> file the council's outcome row, against a fake tenant declared in the council's own `conftest.py`. **The module imports nothing from `idhazh.similarity`**, and that is asserted rather than assumed.
  - It cannot settle whether a real judge works. That is what every judge-side row's own oracle is for.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The empty case is the test.** With zero tenants registered the union is empty, the plan names tonight, every job is a no-op, and every one of those steps still runs and is still asserted. A venue that only works when somebody has moved in is not a venue. | Owner, 2026-09-21 |
| 2 | **The closure arm is the one that would have caught round six's findings, so it is not optional.** A boundary check scoped to a directory only ever proves something about that directory. The question the dictum asks is about what happens when a judge is deleted, and the answer is decided by the whole import graph a council verb pulls in. | Owner, 2026-09-21 |
| 3 | **The fake tenant is a fixture, not a mock.** It implements five protocol members over a fixed list and returns a real `ShardResult`; nothing asserts that it judged anything. Guardrail #7 forbids a stub asserted as if it were the real implementation, which is a different object. It is declared once in the council's `conftest.py` so every council row can reach it. | Guardrail #7 |
| 4 | **The boundary arms are static, not runtime import checks.** A runtime check passes whenever the judge happens to be installed, which is always, so it would never go red. Parsing the import statements is the only arm that catches the coupling on the commit that adds it. | Fowler |
| 5 | Two fake tenants are registered in one case, returning overlapping date lists and different shard counts, so the union, the ordering and the per-tenant width are exercised rather than assumed from one caller. **One judge or many is a property of the union, and this is where it is checked.** | Owner, 2026-09-21 |
| 6 | **Sequence and parallel are the matrix's. Chain is neither, and row #24 owns it.** A tenant's job is pinned to the commit the run started at, so it cannot read a store a sibling committed during the same run - a chain crosses as an artifact and a `needs:` edge or it does not cross at all. This row asserts the shape row #24 declares; it does not invent one. | Carmack |
| 7 | This row lands **last among the council rows and before any judge-side row is called done**, because it is the gate that proves the seams stayed cut. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Trust the review to keep the boundary | Six adversarial rounds read this plan. Round five found six seams; round six found four more in the version that had just been corrected | A rule nobody can fail, which is the state this row ends | Owner |
| 2 | The directory arm alone | It is scoped to the one place the coupling was already cut, and blind to the two places it still lived | A green gate over `cli.py` importing four judge stages | Owner |
| 3 | Drive the run arm with the real judge | It is the coupling, written as a test. The venue would then go red whenever a tenant moved | The dictum, failed at condition 4 | Owner |
| 4 | One combined arm | An import that crosses the boundary would surface as a failure in a run test, naming the wrong thing | A red test that does not say what broke | Fowler |

---

### Row #24 - The council runs verbs of its own over a tenant list

- **Side: council.** Its gates run with no judge in the repository. **This is seams 8 and 10.**
- **Scope:** council verbs replace the judge's four in the workflow, a config-declared tenant list replaces the router's module-scope imports, and the fan-out width comes back from the protocol.
- **Files touched:** `backend/idhazh/council/registry.py` (new), `backend/idhazh/council/session.py`, `backend/utilities/council_matrix.py` (new), `backend/idhazh/cli.py`, `backend/idhazh/contracts/knobs/council.py`, `config/idhazh.json`, `docs/concepts/config.md`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `.github/workflows/llm-council.yml`, `backend/tests/council/test_registry.py` (new), `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/test_marks.py`, `docs/architecture/publishing/llm-council.md`, `schemas/app-config.schema.json` (generated), `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the council test package, the workflow harness, contract export, drift gate, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** with `council.tenants` empty, every council verb runs and exits 0, the matrix emitter prints `matrix=[]`, **the judging job carries the guard string that stops an empty matrix reaching the strategy evaluator**, and **no judge module appears in the import closure of any council verb**. With one fake slug registered, the emitter's cells carry the slug, its own shard count and the date. A slug naming no module is refused by name. It cannot settle whether a real tenant's module resolves on a runner - that is the workflow's own smoke.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The router is the registration today, and it points the wrong way - seam 8.** `cli.py:75-78` imports four judge stages at module scope, so deleting the judge makes every council verb fail at import. The plan's own sentence "registration points judge to council, never council to judge" had no implementation behind it. | Fowler |
| 2 | **Removing the imports is not the whole change, and round seven found the rest.** The four verb names also sit in the `STAGES` tuple at `cli.py:133-136`, in the help string at 431, and in four dispatch branches at 532-574. **Row #23's closure arm parses imports, so it goes green over a verb name still hard-coded here** - this row is what removes the strings, and the checker's ceiling is stated in section 1c rather than discovered later. | Fowler |
| 3 | **`council.tenants` is an ordered slug list in config, and it may be empty.** Guardrail #6: a tenant list in source is a hard-coded roster wearing a different hat, and it is the `JudgeId` roster coming back through the side door. **Row #15b writes the first slug into it** - round seven found nothing did, so the plan would have closed with an empty list and a council that ran every step correctly and judged nothing. | Guardrail #6 |
| 4 | **The resolver imports lazily, inside the function.** A module-scope import of a tenant would put a judge in the council's closure and fail row #23's second arm. A slug with no module is a config error reported by name, never a silent skip. | Fowler |
| 5 | **The matrix is a flat list of cells, not a cross product, and a utility emits it.** Per-tenant shard counts are not a product of three axes, so a cell carries `{tenant, date, shard, shards}` and the shard argument travels on the cell rather than on one job output. The planning job must load config, resolve every tenant, ask each for its nights, union and floor and cap the dates, and emit `matrix=`, `max_parallel=` and `dates=` into the step output - which is not the `python -c` one-liner at `llm-council.yml:143`. **The house pattern is a utility under `backend/utilities/` printing key-value pairs**, as `model_refs.py` and `shard_bound.py` already do. | Carmack |
| 6 | **An empty matrix is not a skipped job - it is a strategy-evaluation failure and the run goes red.** No workflow in this repository has ever built a zero-width matrix and none carries a guard, so there was no pattern to copy and the plan was asserting platform behaviour nobody checked. The judging job takes `if: <matrix> != '[]'`; the collecting job keeps `if: always()`. **Row #23's zero-tenant test asserts the guard string**, because it cannot assert that a job which does not exist ran. | Carmack |
| 7 | **`max-parallel` binds to the smaller of 20 and the cell count, not to the shard count.** It is `max-parallel: fromJSON(needs.draw.outputs.shards)` today - 4 - so two tenants over two dates is 16 cells in four waves: about 5.4 h typical and 6.3 h worst, finishing after the 02:20 digest cron and across the 23:37 prune force-push. No single job busts the 6 h ceiling, because each is bounded at 200 minutes. One wave is about 81 minutes. | Carmack |
| 8 | **Every artifact name carries the tenant and the date**, and the selection artifact carries them too. `judge-draw` at `llm-council.yml:156` carries none of the three and is downloaded by `name:` rather than by pattern, so two tenants at shard zero collide on the artifact name **and** on the merged filename. The download moves to `pattern:` with `merge-multiple`. | Carmack |
| 9 | **The collecting job builds its stage list from `committed_paths` - seam 11.** It stages four literal one-tenant paths today at `llm-council.yml:358` and `382-384`, and its regeneration command is one judge's verb. A second tenant's output would never be committed. | Fowler |
| 10 | **The collecting job loops dates inside one job rather than running per date.** Row #21a's earlier draft made it per date, which would put two jobs of one run pushing `main` - and the workflow-level `concurrency` group does not serialise jobs inside a run. One collecting job, a loop over dates, one push. | Carmack |
| 11 | **A chain crosses as an artifact and a `needs:` edge, or it does not cross.** Every checkout in the council names no ref, so a tenant is pinned to the commit the run started at and cannot see a sibling's commit from the same run. **The shape is declared here and only the single-tenant case is built** - there is no second tenant to chain to yet. What this row owes is that adding one later is a workflow edit, not a redesign. | Carmack |
| 12 | **The deadline stays per job.** One cell is one CLI invocation, so one cell is one tenant and row #1a's in-process computation is correct. It would be wrong if two tenants shared a job - each would be handed the full span - which is the second reason the tenant axis is a matrix dimension rather than a loop. | Carmack |
| 13 | **The wrap-up margin is checked against the measured preamble, not assumed.** The job clock starts before provisioning (0.41 min), a cache restore (0.63 to 1.58 min), a checksum verify (0.12 min) and a health poll bounded at **10 minutes** - about 12.1 minutes worst against a 12-minute margin, so on a slow model load the in-process deadline fires after the platform's own kill and the margin protects nothing. Either the margin rises or `timeout-minutes` becomes the bound plus the preamble. | Carmack |
| 14 | ESCALATE: this rewrites the workflow that judges every night. The verb map, the matrix shape and the empty-matrix guard are signed off before the file changes. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the workflow calling the judge's verbs | The council's entire runtime is then one tenant's four verbs, which is the seam restated. Every other cut in this plan is decoration without this one | The dictum, failed at conditions 1, 3 and 5 | Owner |
| 2 | A source-level tenant registry | A roster in Python. It is seam 1 rebuilt one layer up, and it makes adding a judge a code change | Guardrail #6 broken, and the roster back | Fowler |
| 3 | Import tenants at module scope and guard with a try | A judge in the closure, and a failure that reads as "no tenants" | A silent zero-tenant night | Fowler |
| 4 | Keep the matrix as a cross product of three vectors | Per-tenant shard counts are not expressible in it, so every tenant gets the widest tenant's width | Weights restores for work that does not exist | Carmack |
| 5 | Keep `max-parallel` at the shard count | Two tenants over two dates take four waves and finish across two other schedules | 5.4 h of wall clock for 81 minutes of work | Carmack |
| 6 | Build the chain join now | There is no second tenant to chain to, and the join shape depends on what that tenant reads | A feature for a caller that does not exist | Carmack |

---

### Row #25 - The config check moves to the tenant that owns the number

- **Side: council.** Its gates run with no judge in the repository. **This is seam 9.**
- **Scope:** the one judge-owned constant leaves `AppConfig`, so reading config no longer pulls a judge's measurement into the contract layer.
- **Files touched:** `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/placement.py`, `backend/idhazh/similarity/tenant.py`, `backend/idhazh/council/registry.py`, `backend/tests/contracts/test_app_config.py`, `backend/tests/council/`, `backend/tests/test_similarity_judge.py`
- **Acceptance gates:** local - the app-config, council and similarity test modules, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** `git grep SECONDS_A_CALL -- backend/idhazh/contracts/app_config.py` is empty, `AppConfig` validates with the judge's block absent, and a tenant whose shard does not fit its bound is still refused - **with the refusal raised by the planning job's tenant resolve, not by the config layer and not by the judging job.** It cannot settle whether the bound is the right size.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`AppConfig` imports the judge's measured constant at module scope - seam 9.** `app_config.py:42-46` imports `SECONDS_A_CALL` from `knobs/placement.py` and uses it at 239. Every council module that calls `config.load()` imports `AppConfig`, so the council could not read its own config without pulling in one judge's per-call cost. | Fowler |
| 2 | **The module itself stays, and round seven corrected the earlier framing.** `knobs/placement.py` is not "the judge's knob module" - the same import also supplies `AssembleConfig`, `LensWeightsConfig` and `PlacementConfig`, which are the digest pipeline's. So the oracle cannot be "validates with that file absent"; it is the narrower thing this row actually achieves. | Fowler |
| 3 | **The check is the tenant's, because the number is the tenant's.** `SECONDS_A_CALL` is one judge's measured per-call cost, with exactly one production consumer - the judge's own fit validator. The tenant validates its own fit against the council's bound when it is resolved, and refuses with the same message and the same knobs to lower. | Fowler |
| 4 | **The refusal stays before any weights restore because row #24 decision 5 makes the planning job resolve tenants** to build the matrix. That is the reason, stated so a regression that moved resolution into the judging job would be visible: "before any model call" is also true of a point after a 1.58-minute cache restore and a 10-minute server start, so it is not the property worth asserting. | Carmack |
| 5 | **The refusal message keeps naming the knobs to lower**, which is the part an operator uses. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the arm in `AppConfig` and call it data | It is a module-scope import, not data. The earlier draft said "it is data rather than an import" and the line above it in the file says otherwise | Conditions 2 and 3, failed, with a green boundary test over a directory that does not contain the fault | Owner |
| 2 | Import it lazily inside the validator | The coupling survives in a form no static check catches, which is worse than the one we can see | A seam that the next round cannot find | Fowler |
| 3 | Move `SECONDS_A_CALL` into the council block | It is one judge's measured per-call cost. A second tenant's call costs something else | A council knob that is one tenant's measurement | Carmack |

