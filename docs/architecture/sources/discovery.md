# Source Discovery

**Last Updated**: 2026-08-26

What the Collect stage consults, how those sources are organised, and how that organisation is changed without breaking a payload an earlier run wrote. Collect is one of the two stages that see the whole day ([../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md)); this page owns the shape of what it sees.

## Three primitives, not one

The common mistake is to model every topic a reader cares about as a source list. Most topics are not source lists. Three primitives, and the distinction between them is what keeps curation affordable:

| Primitive | What it is | What it costs |
| --- | --- | --- |
| **Vertical** | A subject that has its own reporters and its own feeds. Carries a curated feed list. | ~25 feeds to curate |
| **Lens** | A question asked of items already collected. A tag, applied after the fetch. | nothing |
| **Entity** | A named organisation followed by name, with its own primary feeds. | ~1 feed |

A lens and an entity never get their own feed list. "China" is not a desk - it appears inside four verticals. "Return on AI investment" is not a desk - no outlet publishes one. Both are questions asked of items already in hand, and asking them is free.

The payoff compounds. One supply agreement between a chip maker and a datacentre operator is three verticals, two lenses, two event types and two entities: eight index entries, one fetch, one summary.

## Verticals

Each carries a feed list, a feed floor and a lifecycle status. A vertical below its floor is not published.

| id | feed floor | live feeds |
| --- | --- | --- |
| `ai` | 35 | 38 |
| `energy` | 21 | 24 |
| `business-economy` | 21 | 22 |
| `world` | 21 | 27 |
| `india` | 21 | 27 |

Live counts measured 2026-08-22 by fetching and parsing every configured feed. A feed counts as live only if it resolves, parses and carries entries.

**There is no per-vertical daily cap and no daily item ceiling.** How many items a vertical publishes is decided by supply, by the score, and by `max_per_source`. See [freshness.md](freshness.md).

**Lenses** are a closed vocabulary of cross-cutting tags. **Events** are a closed vocabulary of what happened to an item - a release, a deal, an acquisition, a funding round, a capital commitment, results, a regulatory action, research, an incident. Both are enums in the contract, not free-text strings, so a new value is a schema change with a changelog entry rather than a typo waiting to happen ([../contracts/schemas.md](../contracts/schemas.md)).

## Lenses, events and entities are declared and never assigned

Every published item carries `lenses: []`, `events: []` and `entities: []`. Not most items - every item, on every committed day.

Measured 2026-08-26 over the six committed days under `frontend/public/digest/`:

| Day | Items | With a lens | With an event | With an entity |
| --- | --- | --- | --- | --- |
| 2026-08-21 | 4 | 0 | 0 | 0 |
| 2026-08-22 | 10 | 0 | 0 | 0 |
| 2026-08-23 | 147 | 0 | 0 | 0 |
| 2026-08-24 | 731 | 0 | 0 | 0 |
| 2026-08-25 | 724 | 0 | 0 | 0 |
| 2026-08-26 | 273 | 0 | 0 | 0 |
| **Total** | **1889** | **0** | **0** | **0** |

The three fields are declared on `Article`, copied onto `DigestItem`, exported to `schemas/article.schema.json` and `schemas/digest-day.schema.json`, and typed in the frontend's payload types. Nothing writes them. The tagging step this page describes was never built.

**Lenses and events were built on 2026-08-26. Entities are still empty.** The rest of this section is the diagnosis that is now history; the rule that replaced it is the section below.

**Where the value would have been set.** `to_article` in `backend/idhazh/extract.py` builds the only ok article and passes none of the three; `_failed` in the same file does the same for a failed one. All three are declared `default_factory=list` in `backend/idhazh/contracts/article.py`, so leaving them out is legal and silent. `to_digest_item` in `backend/idhazh/assemble.py` then copies the three empty lists onto the published item. No model is involved anywhere: neither `backend/idhazh/prompts/summarize.txt` nor `backend/idhazh/prompts/route.txt` contains the word lens, event or entity.

**The entity half is worse than unwired.** `config/watchlist.json` declares `"entities": []`, so there is no registry to match a name against and the ceiling on items that could gain an entity today is zero, whatever the matcher. `backend/idhazh/cli.py` hands `plan_vertical` a hardcoded empty `watchlist_keys` for the same reason, so `watchlist_bonus` has never moved a score - the watchlist term of the ranking formula below is dead arithmetic. `EntityDef.aliases` is declared in `backend/idhazh/contracts/watchlist.py` and read nowhere, and it is the only name-matching surface any config contract has.

**The vocabulary would fire, and the match rule is the whole design.** Measured 2026-08-26 over our own published title, summary and key points - our words, never fetched text. A word-boundary match on the words inside each lens id hits 167 of 1889 items, 8.8 percent: `china` 94, `markets` 69, `cyber` 11, `ai-roi` 2. The same match for an event id as a word hits 438 items, 23.2 percent, led by `research` 179 and `incident` 72.

Those are floors, not proposals - they read the summary rather than the article, and the terms are the ids themselves rather than a curated list. What matters more is how far the count moves when the rule moves. Five plausible rules over the identical corpus:

| Match rule | Items with a lens | Share |
| --- | --- | --- |
| Word-boundary on the id's words, ignoring words of 2 letters or fewer | 167 | 8.8 percent |
| Substring on the same words | 200 | 10.6 percent |
| Substring on the display name | 189 | 10.0 percent |
| Substring on `market` rather than `markets` | 335 | 17.7 percent |
| Substring on every word in the id, `ai` included | 1666 | 88.2 percent |

The last row is the finding. Dropping the two-letter guard makes `ai-roi` match 1648 items, because `ai` is a substring of `said`, `remains` and `chair`. One unstated choice moves the answer by a factor of ten and turns a filter into noise. **The vocabulary is not the problem and the wiring is not the whole problem: the match rule is a curated artifact, and it has nowhere to live today.** That is what makes this a config-shape change rather than a missing function call.

**What it costs.** Nothing a reader sees today, because lenses and events were already kept off the topic pill row ([../publishing/frontend.md](../publishing/frontend.md)). It costs the retrieval eval its free query tier, which builds queries from entity slugs carried by three or more items and therefore builds none. And it costs this page its own claim: eight index entries per fetch is one index entry today, the vertical.

### Why this is a design consultation and not a defect fix

Assigning a tag needs a rule, and no config contract has anywhere to put one. `LensDef` carries `id`, `display_name` and a lifecycle; `EventDef` carries `id` and `display_name`. The measured spread above says the rule cannot be derived from the id, so it has to be written down, and writing it down changes a persisted config shape and pulls in `CLAUDE.md` section 11. That alone makes it Level 5 (section 6, "a persisted contract") before the rest is counted: the matcher and its tests, the wiring commit, a curated watchlist, and the `watchlist_keys` wiring - which is a live ranking change, because a bonus that starts firing reorders every future day.

**How it runs is settled. Where it runs is not.** Four places agree the tagger is deterministic, uses no model and costs no extra request: this page's own definition, `LensId` in `backend/idhazh/contracts/taxonomy.py` ("a question asked of items already collected"), Fowler's recorded ruling 1 in the plan-doc, and that plan-doc's stage diagram, which marks the plan job "(no model)". Nothing in the repository proposes asking a model.

The site is the open question, and the two candidates carry different contract costs. This page says "a tag, applied after the fetch", which puts the matcher on sanitized article text at Extract, where `Article` already holds the three fields and nothing new is persisted. The stage diagram says "rank + tag lens/entity" inside the plan job, which runs on the feed title alone before a byte is fetched, and would need three new fields on `PlannedItem` - making `run-plan` a second persisted contract to version. Picking one is the owner's call and is not settled here.

Whichever is chosen, one boundary rule holds. A matcher that reads article text reads a stranger's page, so it runs after `sanitize` and it may only ever emit a member of a closed enum ([trust-boundary.md](trust-boundary.md), Rule #11). A hostile page can then win itself a tag we already publish. It can never invent one, and it never reaches a prompt.

**There is a third outcome, and it is cheaper than either.** Fowler, consulted 2026-08-26: before asking how to build the tagger, ask whether the surface should exist. Three fields, two schemas, a frontend type and a config vocabulary are rent paid every day by a feature with no reader-facing consumer today. The consultation therefore weighs three options, not two - tag at Extract, tag in the plan job, or delete the three dimensions and their vocabularies and stop paying. Deleting is itself a breaking contract change needing a read-side migration (section 11), so it is the same class of work; it is not the cheap way out, only the honest third choice.

Filed as defect 17 in [`../../../TODO/20260823-known-defects-plan.md`](../../../TODO/20260823-known-defects-plan.md).

## The match rule

Settled 2026-08-26 by the owner: build lenses and events. This is the rule, and it is one sentence.

> **A tag is assigned when one of its curated terms appears in the item's words as a whole-word phrase, case-folded. Nothing is derived from the tag's id or its display name.**

The second sentence is the load-bearing half. Deriving terms from the id is what produced the 88.2 percent measured above, because `ai` sits inside `said`, `remains` and `chair`. `backend/idhazh/tag.py` derives nothing: the terms are curated in `config/taxonomy.json` under `keywords` on each lens and each event, and a vocabulary with no terms is never assigned. Punctuation is dropped on both sides before the comparison, so `ai-roi`, `AI/ROI` and `AI ROI` are one term. A term must be at least two characters, which the contract enforces.

**Where it runs: on the extracted article, after `sanitize`.** `cli._fetch_one` calls `tag.tagged(article, taxonomy=...)` immediately after `extract.to_article`, so the matcher reads text that has already crossed the trust boundary exactly once, `Article` already holds the three fields, and nothing new is persisted. The alternative - tagging inside the plan job - was rejected: it sees the feed title alone, and it would need three new fields on `PlannedItem`, making `run-plan` a second persisted contract to version for a worse signal. The stage diagram in [`../../../TODO/20260815-digest-pipeline-plan.md`](../../../TODO/20260815-digest-pipeline-plan.md) said "rank + tag lens/entity" in the plan job and was corrected in the same commit.

A failed article keeps its empty lists. It has no text, it never reaches a reader, and a tag on it would be a tag on a feed title.

**The tagger is deliberately not a fingerprint input.** A tag does not change a summary, so adding the vocabulary to the stamp would re-summarize every past item to produce identical words ([../contracts/determinism.md](../contracts/determinism.md) already warns that a new `PipelineInputs` field resets every fingerprint). A vocabulary edit therefore re-tags what runs next and leaves the past alone.

### Measured coverage

Two corpora, because they answer different questions. Both measured 2026-08-26 on this checkout.

**The real one: 121 article payloads with `status: ok`**, downloaded from the `items-0..3` artifacts of pipeline run `32986307407` (2026-08-26T15:54Z). This is the sanitized article text the tagger actually reads.

| | Any tag | Highest single tag | Lowest single tag |
| --- | --- | --- | --- |
| Lenses | 31 of 121, **25.6 percent** | `china` 13.2 percent | `ai-roi` 0.8 percent |
| Events | 70 of 121, **57.9 percent** | `release` 22.3 percent | `earnings` and `incident` 4.1 percent |

Full event spread: `release` 22.3, `regulation` 19.0, `deal` 13.2, `research` 12.4, `capex` 7.4, `funding` 7.4, `acquisition` 5.8, `earnings` 4.1, `incident` 4.1 percent. Fifty-one of 121 items carry no event at all, and no item carries more than four.

**The comparable one: the item's own published words** - title, summary and key points over all 2,121 committed items, which is the corpus the 8.8 / 88.2 percent spread above was measured on. Lenses reach 16.1 percent and events 39.9 percent. Article bodies are never committed (we publish a link and our own summary, never the source text), so this is the only corpus that reaches back over every published day.

**The first draft was worse and the measurement is what caught it.** A candidate vocabulary using bare `research`, `study`, `revenue` and `profit` tagged `research` on 34.7 percent of articles and `earnings` on 14.9 percent - a filter taking one article in three is not a filter. Replacing them with `researchers`, `arxiv`, `preprint`, `quarterly results` and `fiscal quarter` moved those to 12.4 and 4.1 percent. No judgement about "good keywords" would have found that; running the list over 121 real articles did.

**What is still zero: `entities`.** The watchlist declares no entity, so the ceiling on items that could gain one is zero whatever the matcher, and the retrieval eval's free query tier still builds nothing.

## Sources are tiered, and the tier is scaled by the feed's own weight

| Tier | What it is | Examples |
| --- | --- | --- |
| 1 | The institution that *is* the fact | a lab's own blog, a central bank, a statistical agency, a regulatory filing, a company newsroom |
| 2 | Trade press that covers the beat daily | a specialist outlet, a wire's section feed |
| 3 | Community and aggregators | a forum, a link aggregator |

The tier sets the authority score. **Each feed also carries its own `weight`, and it multiplies that score.** The tier says what kind of source this is; the weight says how much we trust this particular one. Two feeds can be trade press and not be equally good, and the tier alone has no way to say so.

Multiplying rather than adding is what makes the weight mean something: a weighted-down institution stays below a full-weight one of the same tier, which is the whole point of turning it down.

The weight is also the reversible half of retirement. Drop a source to 0.5, watch what changes, then retire it - one field, no payload touched.

The consequence worth stating plainly: **a link aggregator is a vote, not a source.** It contributes rank to a URL already in the pool. It never discovers, because a site with no subject taxonomy cannot be asked for a subject.

## One address per story

Deduplication is the whole point of collecting from many feeds, and it only works if the same article arriving three ways produces one address. Canonicalisation is therefore a load-bearing step, not tidying:

- The scheme and host are lowercased, a default port is dropped, and a leading `www.` goes. These are the same server.
- Campaign and click identifiers are stripped. They differ per referrer for the same article, so leaving them in means one story arrives as several.
- The fragment goes; a trailing slash goes from a non-root path.
- **What remains of the query is kept and sorted.** Stripping every parameter would be simpler and wrong: on plenty of sites the query *is* the article.

Identity is the digest of the canonical address, and it lives in a payload field - never in a path, a filename or a URL. Paths are for humans and for globs.

## An address a healthy feed should not have offered

A working news feed syndicates promotional pages. `cnn-world` carried three
`fool.com/the-ascent/` affiliate credit-card reviews into the `world` vertical on
2026-08-23 and 2026-08-24. They summarized well, scored 0.92 to 0.95
faithfulness, and published as `high`.

That is not an evaluation defect and no threshold fixes it. A page of short
declarative marketing sentences is trivially entailed, so raising the
faithfulness bar rewards the wrong source. The only honest signal available
before anything is spent is the address, so the control sits at collection:
`collect.blocked_url_markers` is a list of case-insensitive substrings that never
enter the pool.

Two rules keep it from becoming a censorship surface:

- **The entries live in `config/`, and the default is empty** (Rule #6). The knob
  is the shape; the list is a source-curation decision like the feed list beside
  it.
- **The feed's health row still counts what the feed offered.** What we accept is
  the pool's business, not the feed's. A source that syndicated a promo is not a
  source that failed, and folding the two counts together would quarantine a
  working feed.

The marker is the narrowest thing that was measured. `fool.com/the-ascent/` is
the publisher's affiliate arm; `fool.com/investing/` is not blocked, because no
item from it has been observed to fail (Rule #10).

## Ranking is arithmetic, not judgement

The day is decided before any model loads, by a score with five terms:

```
(tier weight * feed weight) * (1 + repetition_weight * (carriers - 1))
  + watchlist_bonus
  + front_page_bonus
  + recency_bonus
```

The authority of the source, scaled by that feed's own weight, multiplied by how widely the story is carried, plus a bonus for naming a watchlist entity, plus a bonus for an aggregator vote, plus a bonus for being recent. A story three independent sources carried today is the day's story.

Three details in that carry weight:

- **Authority is the best tier that carried the story, not the average.** One institution saying it makes it true however many aggregators repeated it, and averaging would let volume dilute provenance.
- **Recency is a bonus, not a filter.** It decays by half every `recency_half_life_hours` and never removes anything from the pool. Why that is a decay rather than a cutoff is [freshness.md](freshness.md).
- **Ties break on the canonical address.** Without a deterministic tie-break, two runs over identical feeds can publish different orders, and the order is part of what a shared link shows.

The consequence worth stating plainly: the planning step loads no weights, finishes in seconds, and produces the identical list on every re-run. That is what makes the expensive work shardable afterwards and a re-run cheap.

## Changing the source set without breaking history

A vertical will be retired. A feed will die quietly when a site is redesigned. Both are normal, and both are handled in config rather than in code.

- **An id is an immutable slug; the display name is a separate, freely mutable field.** Renaming what a reader sees must never orphan a payload that referenced the id.
- **Retire, never delete.** A retired vertical, lens or entity keeps its entry with a retired status and the date. Deleting an id breaks every payload written under it and forces a read-side migration; a tombstone costs one object.
- **A retired feed moves to its own key.** `config/sources.json` has a `feeds` list and a `retired` list. A tombstone kept in the live list is a tombstone every run has to filter past, and one missed filter is a request to a source we decided to stop asking. Moving it makes the live list mean exactly what it says, and the record survives either way.
- **A draft status plus a minimum-feed floor** lets a vertical be built in the open over weeks. Below the floor it is not published, so an under-sourced desk never reaches a reader.
- **Feed health is recorded, not configured.** Repeated failures rest a feed automatically, and nothing in a run ever edits `config/sources.json`. See [health.md](health.md).
- **Soft retirement before hard.** Drop a source's weight, watch what changes, then retire it. Reversible in one field.

## Design rationale

**The affiliate-page control sits at collection, not at the score (2026-08-24).** The three `fool.com/the-ascent/` items are the case that separates "the summary is wrong" from "the item should not be here". Every instrument in the eval ledger compares our summary to the article, and all of them passed. Moving the control to collection also costs nothing: a blocked address is never fetched, never summarized and never scored, which is the cheapest place a rejection can happen (Rule #2). Authority: owner, closing known defect 7.

Segmenting by subject is a source-diversity problem, not a compute one. The pipeline had spare capacity long before it had spare sources, so the binding constraint was never how many items could be summarized - it was how many were worth summarizing, and whether they covered more than one subject.

Two findings from prior art settled the shape. First, every system that publishes a multi-subject daily digest attaches a curated feed list per subject; none of them sorts a single firehose into subjects. Second, those systems enforce a floor below which a subject is not surfaced at all, because a thin list produces a thin day and the reader cannot tell the difference between a quiet day and a broken one.

The floor started as a borrowed constant: twenty-five feeds for every vertical, taken from prior art. That number is wrong here, because it does not scale with how much a vertical publishes. The systems it came from surface dozens of items per subject per day; ours surface a handful.

The floor was then set at seven times each vertical's daily cap, which is where 35 and 21 come from. **The daily cap has since been removed** - supply and the score decide the size of a day now ([freshness.md](freshness.md)) - and the floor numbers stayed behind. That is deliberate, and worth stating plainly rather than quietly re-deriving: the ratio was always a judgement, and the numbers it produced are the half that turned out to be useful. They describe a candidate pool several times larger than any day is likely to publish, which is what keeps the ranking with something to choose between when a day is quiet.

State the sequence honestly - the live counts were measured first, then the rule was written, so the rule is fitted to what the source pool supports rather than derived from an independent finding. It is recorded here so a later reader can overturn it with a real measurement instead of re-deriving it.

The floor still does its job. It is not a formality that always passes: `business-economy` clears twenty-one by one feed, and a single dead source puts it back under.

Tiering the sources was the cheap half. Once a source carries a tier, ranking needs no model, no classifier and no judgement at run time: the arithmetic of "how authoritative" times "how widely carried" reproduces most of what an editor would pick, and it reproduces it identically on every re-run.

The lifecycle rules exist because the alternative was discovered the expensive way in other projects: a config edit that deletes an identifier silently invalidates every artifact that referenced it, and the breakage surfaces months later when someone loads an old payload.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A single link aggregator as the only source | No subject taxonomy; one global front page whose only tags are post types. Keyword queries against it are lexical - a query for a subject catches every casual mention of the word - and it carries no world, energy or regional coverage at all. |
| A classifier sorting one firehose into verticals | Nobody who has shipped this does it. It also puts model time into the planning step, which today loads no weights and finishes in seconds. |
| One vertical per topic of interest | Eleven verticals is roughly 275 feeds to curate, for eleven desks that would each be under their floor. Most candidate topics turned out to be lenses or entities on inspection. |
| A market-prices vertical | A once-daily, statically-committed digest is the wrong instrument for a number that moves continuously. Kept as a lens so a structural story still surfaces. |
| Splitting a subject into two verticals by angle | The same feed list serves both, so the split doubles curation to buy one taxonomy line. The separation is recovered for free by the event vocabulary. |
| Deleting a retired entry from config | Breaks every payload written under that id and forces a read-side migration. |
| Leaving a retired feed in the live `feeds` list with a status flag | Every run has to filter past it, and one missed filter is a request to a source we decided to stop asking. |
| Adding the feed weight to the tier score instead of multiplying | Addition lets a weighted-down institution overtake a full-weight one of the same tier, which is the opposite of what turning it down meant. |
| Raising the faithfulness threshold to keep affiliate pages out | They are faithful. Short declarative marketing prose is trivially entailed, so every cut that excludes them excludes real reporting first, and the bar rewards the source it should reject. |
| Retiring `cnn-world` over the syndicated affiliate pages | It is a working feed carrying real reporting. Retiring a whole source over three items it passed through costs the vertical a desk to fix a link filter. |
| Blocking `fool.com` entirely | The publisher's editorial arm has not been observed to fail. The measured cut is the affiliate section, and nothing wider has been measured. |
| Asking the summarizer for the lens, event and entity tags | A tag decides what a reader is shown under a filter, so a page that picks its own tags writes its own index entry - fetched text steering a control (Rule #11). It also adds decode tokens to the one stage that already dominates the run. A deterministic matcher costs no model time and returns the same answer on every re-run, which is the property the rest of this page's arithmetic already has. Andre, consulted 2026-08-26. |
| A per-feed weight only, with no tier | The tier is the reusable half: it is a fact about a kind of source, and a new feed inherits it without anyone inventing a number. |
| Keeping the flat floor of twenty-five and leaving two verticals unpublished | The floor would then be measuring the borrowed constant, not the health of the desk. Two verticals stay dark for a reason that does not survive being stated. |
| Dropping the floor to whatever the thinnest vertical reached | That is tuning the target to the result with no rule behind it, and the floor stops being able to fail. |

## See also

- [freshness.md](freshness.md) - the run cadence, how age is scored, and what stops an article publishing twice.
- [health.md](health.md) - what every feed did on every run, and the quarantine that reads it.
- [trust-boundary.md](trust-boundary.md) - what happens to the text once a discovered link is fetched.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Collect stage and the invariants that hold across all stages.
- [../../concepts/config.md](../../concepts/config.md) - where the feed lists and caps live, and the knob-versus-identifier rule.
- [../contracts/schemas.md](../contracts/schemas.md) - the contracts these vocabularies are enums in, and the versioning rules.
- [../../concepts/principles.md](../../concepts/principles.md) - config-driven with sane defaults, and degrade rather than fail.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11).
