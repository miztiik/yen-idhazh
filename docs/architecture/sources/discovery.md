# Source Discovery

**Last Updated**: 2026-09-13

What the Collect stage consults, how those sources are organised, and how that organisation is changed without breaking a payload an earlier run wrote. Collect is one of the two stages that see the whole day ([../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md)); this page owns the shape of what it sees.

## Three primitives, not one

The common mistake is to model every topic a reader cares about as a source list. Most topics are not source lists. Three primitives, and the distinction between them is what keeps curation affordable:

| Primitive | What it is | What it costs |
| --- | --- | --- |
| **Vertical** | A subject that has its own reporters and its own feeds. Carries a curated feed list. | ~25 feeds to curate |
| **Lens** | A question asked of items already collected. A tag, applied after the fetch. | nothing |
| **Entity** | A name followed across days: a standing organisation with its own primary feeds, or a running subject with neither. | ~1 feed, or none |

A lens and an entity never get their own feed list. "China" is not a desk - it appears inside four verticals. "Return on AI investment" is not a desk - no outlet publishes one. Both are questions asked of items already in hand, and asking them is free.

**A vertical and an entity can both be called a subject, and they are not the same thing.** A vertical is a desk with its own reporters and its own feed list. A subject in the entity registry - a pandemic, a tournament, an export-control regime - is one name we follow, with no feed of its own. `EntityKind` in `backend/idhazh/contracts/watchlist.py` is what separates that from a standing organisation.

The payoff compounds. One supply agreement between a chip maker and a datacentre operator is three verticals, two lenses, two event types and two entities: eight index entries, one fetch, one summary.

## Verticals

Each carries a feed list, a feed floor and a lifecycle status. A vertical below its floor is not published.

| id | feed floor | feeds we may ask | margin |
| --- | --- | --- | --- |
| `ai` | 35 | 43 | 8 |
| `energy` | 21 | 27 | 6 |
| `business-economy` | 21 | 25 | 4 |
| `world` | 21 | 25 | 4 |
| `india` | 21 | 24 | 3 |

Counts measured 2026-09-02 from the committed config and the committed health record, with no network involved. **A feed counts when we are allowed to ask its address**, not when it answered: a curated tombstone, an address a server reported permanently gone, a `robots.txt` refusal and a permission we could not establish are each out of the count, and a resting or failing address is in it. The rule and what it costs are in [health.md](health.md#the-feed-floor-counts-the-addresses-we-may-ask).

**There is no per-vertical daily cap and no daily item ceiling.** How many items a vertical publishes is decided by supply, by the score, and by `max_per_source`. What one feed may hold of the whole day is `max_source_share_per_day`. See [freshness.md](freshness.md).

**Lenses** are a closed vocabulary of cross-cutting tags. **Events** are a closed vocabulary of what happened to an item - a release, a deal, an acquisition, a funding round, a capital commitment, results, a regulatory action, research, an incident. **What closes them is [`../../../config/taxonomy.json`](../../../config/taxonomy.json), not the Python type**: both ids are open slugs, and the matcher can only ever emit a word that file carries, so adding one is a config edit and nothing can invent one ([../../concepts/taxonomy.md](../../concepts/taxonomy.md), [../contracts/schemas.md](../contracts/schemas.md)). A closed Python enum would charge a code change, four regenerated schemas and a release for a word.

## The match rule

The rule is one sentence.

> **A tag is assigned when one of its curated terms appears in the item's words as a whole-word phrase, case-folded. Nothing is derived from the tag's id or its display name.**

The second sentence is the load-bearing half. Derive the terms from the id and `ai-roi` matches almost every story, because `ai` sits inside `said`, `remains` and `chair` - one unstated choice turns a filter into noise. `backend/idhazh/tag.py` derives nothing: the terms are curated in `config/taxonomy.json` under `keywords` on each lens and each event, and a vocabulary with no terms is never assigned. Punctuation is dropped on both sides before the comparison, so `ai-roi`, `AI/ROI` and `AI ROI` are one term. A term must be at least two characters, which the contract enforces.

**A keyword set is curated against real articles, not by judgement.** A first draft using bare `research`, `study`, `revenue` and `profit` tagged one article in three, and a filter taking one in three is not a filter. Phrases - `researchers`, `arxiv`, `preprint`, `quarterly results`, `fiscal quarter` - are what made it selective. Running a candidate list over a sample of real articles is the only thing that finds this; no opinion about good keywords does.

**Where it runs: on the extracted article, after `sanitize`.** `stages.common._fetch_one` calls `tag.tagged(article, taxonomy=...)` immediately after `extract.to_article`, so the matcher reads text that has already crossed the trust boundary exactly once, `Article` already holds the three fields, and nothing new is persisted. The alternative - tagging inside the plan job - is rejected: it sees the feed title alone, and it would need three new fields on `PlannedItem`, making `run-plan` a second persisted contract to version for a worse signal.

A failed article keeps its empty lists. It has no text, it never reaches a reader, and a tag on it would be a tag on a feed title.

**The tagger is deliberately not a fingerprint input.** A tag does not change a summary, so adding the vocabulary to the stamp would re-summarize every past item to produce identical words ([../contracts/determinism.md](../contracts/determinism.md) already warns that a new `PipelineInputs` field resets every fingerprint). A vocabulary edit therefore re-tags what runs next and leaves the past alone.

### A lens can also score, and then two more rules apply

A lens carries a `weight`. Zero, the default, means it only labels. Above zero it adds to a story's rank at plan time, where the same match rule runs against the **headline alone** - the body has not been fetched yet. The label is unchanged: it is still matched on title plus body after summarizing, so **every scoring hit is also a label** and the reverse does not hold.

Two rules govern which lens may carry a weight, and both are about what a bonus is for. Authority: Editor, 2026-08-30.

> **A weighted lens must be an under-carried theme, never an over-carried one.**

A bonus exists to rescue a story one outlet has and nobody has repeated yet. `reach` already multiplies a story every wire carried, so a weight on a well-covered theme compounds a lead the story had anyway. That is why `trade` and `chips` carry 0.3 and `war`, `china` and `markets` carry zero despite being the three largest lenses: a tariff filing or a fab announcement breaks in one place, and a war does not.

> **A keyword that is ambiguous in a headline does not ship in a scoring set.**

A headline is eight to twelve words and the matcher has no surrounding context to disambiguate with. Bare `shares` was removed from `markets` for this - it is a verb in "OpenAI shares research" as often as a noun - and replaced with `share price` and four `shares <verb>` phrases. Bare `roi`, bare `vulnerability` and bare `nifty` went the same way. The rule binds every keyword, because one list serves both jobs.

**One fact earns one bonus.** No lens keyword may repeat a watchlist alias. ASML, Nvidia, Intel, Samsung and Huawei are entities carrying `watchlist_bonus`; putting them in the `chips` keywords would pay twice for a single fact. The lens names the thing, the watchlist names the company.

**A theme takes the largest weight it earned, never the sum.** Two themes in one headline is not twice the story, and summing would let a keyword list outweigh the fact that another feed carried it too. The shipped weight of 0.3 sits above `collect.carriage_step` (0.25), because what a second feed brings with it is a second tier's authority as well as the repeat. `backend/tests/test_discover.py::test_a_theme_is_worth_less_than_a_second_feed_carrying_the_story` asserts a themed single-sourced story ranks below the same story a better-trusted second feed carried.

### Entities, and the watchlist term they feed

An entity matches by the same one-sentence rule, with `aliases` in `config/watchlist.json` as the curated surface instead of `keywords`.

**An entity nobody has published about does not enter the registry.** A candidate is run over a real corpus before it is written down, and one that matches nothing is cut rather than kept in hope. Adding it later is one config edit the day a story needs it, and a vocabulary full of entries that never fire is decoration that every reader of the file has to think about.

**`watchlist_bonus` pays the candidates whose feed title matches an alias.** The title, not the article text, and the asymmetry is deliberate: a plan runs before a single page is fetched, so the title is all it has. An article whose body names an entity its title does not still earns the published tag at Extract. **The tag says what the item is about, the bonus says what we were already watching for.** Those are different questions and they are allowed to disagree.

**A bonus that starts firing reorders every future day and no past one.** That makes wiring one a live ranking change and an owner's decision rather than a defect fix. The published ledger under `state/published/` stops an already-published address being planned again, so no day a reader has already seen moves.

**An entry is an organisation or a subject, and only the second kind has a gap worth measuring.** `EntityDef.kind` defaults to `organisation`. A company is in the news most weeks, so the time between our own mentions of it is near zero; a running story - a pandemic, a tournament, an export-control regime - goes quiet between instalments. The field exists so the second kind can enter the vocabulary at all, which an organisation-only registry could not allow. A subject carries no SEC filer id and the contract refuses one.

**Nothing fades a subject's score across days, and one shape of that idea is refused rather than deferred.** Three different features answer to the word decay. Keeping a running story visible on a quiet day is the one worth building, and it waits on a registry entry that actually goes quiet - our silence about a name we track is short enough that a fade rate would fire on every name every day. A **running total that a subject adds to every day and a rate then shrinks is refused outright**: it grows for as long as the subject runs, so a two-year story eventually outranks every fresh story permanently, and on a day the subject did produce coverage the shared-subject term below has already counted it. Stopping one subject from leading five days running is a third thing again, and its control is the per-subject cap below rather than a rate - a rate doing that job would have to penalise a subject still producing coverage, which is exactly the case the request was protecting. Authority: Editor, 2026-08-31.

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

### A speculative term ships with the condition that retires it

A signal nobody has measured may still be worth trying, and the honest way to try one is to write down what would kill it before it ships. The aggregator vote is the worked example: it was added with the condition "retire it if it fires on under 1 percent of planned items", the condition fired, and `collect.front_page_bonus` is gone. A vote is now a published fact about a story and moves no score at all.

Two things make this a rule rather than one decision.

- **A term that moves nothing almost every time and then decides the lead is a lottery, not a ranking term.** Nobody can attribute a move to it either way, which is the property that makes it unmeasurable rather than merely small.
- **A bonus nothing earns is still a moving part.** It has to be read, tested and reasoned about on every later change, and it pays for none of that.

Raising a weight is never the repair here. A story on an aggregator's front page *and* in our pool is by definition well carried, and `reach` already scores it.

`backend/tests/test_discover.py::test_a_vote_is_for_the_article_and_never_for_the_discussion_page` pins the half that is easy to break: an aggregator also offers a feed form whose `link` is the discussion page, and reading that would cast every vote for an address no feed can offer. It would fail silently, because a vote for a URL we do not hold looks exactly like no vote.

## One address per story

Deduplication is the whole point of collecting from many feeds, and it only works if the same article arriving three ways produces one address. Canonicalisation is therefore a load-bearing step, not tidying:

- The scheme and host are lowercased, a default port is dropped, and a leading `www.` goes. These are the same server.
- Campaign and click identifiers are stripped. They differ per referrer for the same article, so leaving them in means one story arrives as several.
- The fragment goes; a trailing slash goes from a non-root path.
- **What remains of the query is kept and sorted.** Stripping every parameter would be simpler and wrong: on plenty of sites the query *is* the article.

Identity is the digest of the canonical address, and it lives in a payload field - never in a path, a filename or a URL. Paths are for humans and for globs.

## An address a healthy feed should not have offered

A working news feed syndicates promotional pages. An affiliate product review
arrives through a real outlet's real feed, summarizes cleanly, scores high on
faithfulness and publishes as a confident item.

That is not an evaluation defect and no threshold fixes it. A page of short
declarative marketing sentences is trivially entailed, so raising the
faithfulness bar rewards the wrong source and cuts real reporting first. The only
honest signal available before anything is spent is the address, so the control
sits at collection: `collect.blocked_url_markers` is a list of case-insensitive
substrings that never enter the pool.

Two rules keep it from becoming a censorship surface:

- **The entries live in `config/`, and the default is empty** (Guardrail #6). The knob
 is the shape; the list is a source-curation decision like the feed list beside
 it.
- **The feed's health row still counts what the feed offered.** What we accept is
 the pool's business, not the feed's. A source that syndicated a promo is not a
 source that failed, and folding the two counts together would quarantine a
 working feed.

**Block the narrowest thing that was measured.** `fool.com/the-ascent/` is the
publisher's affiliate arm and is blocked; `fool.com/investing/` is not, because
no item from it has been observed to fail (Guardrail #10). A marker wide enough
to catch what has not happened yet is a marker nobody can defend.

## Ranking is arithmetic, not judgement

The day is decided before any model loads, by a score with four terms and one tie-break:

```
(tier weight * feed weight * reliability)
 + carriage_step        if more than one feed carried this address
 + watchlist_bonus
 + max(LensDef.weight over the story's lenses)
 + recency_weight * 0.5 ^ (hours old / recency_half_life_hours)
```

The authority of the source - its tier, scaled by that feed's own hand-set weight and again by the reliability its recent record earned - plus a step if more than one of our feeds carried the same address, plus a bonus for naming a watchlist entity, plus the heaviest theme it matched, plus a bonus for being recent. A story the best-trusted source carried is the day's story.

**Carriage is a step and never a multiplier.** `collect.carriage_step` fires once, at two carriers, and never grows, because three carriers is not three times the story. A multiplier on that first line does two wrong things at once: it compounds without bound, so a story on six feeds takes the day, and it pays in proportion to what the story already had - the same signal buying more on an institution than on a community feed, so the more a story needed the help the less it got.

`backend/tests/test_rank.py` asserts each term moves the order on its own, and that a field the score does not read moves nothing.

### The terms, in the order an editor set them

A score that only admitted stories needed its terms to point the right way. The same number also decides the order a reader meets ([../../concepts/placement.md](../../concepts/placement.md)), so the terms are ranked, and the ranking is the editor's. Each row's bound is the most that term can move one story, which is the only comparison available between a multiplier and an addition. `backend/tests/test_rank.py::test_the_terms_rank_in_the_order_the_editor_set` reads all four off `config/`, so a weight edit moves the bound rather than leaving this table stale.

| # | Term | The most it may move a story | Today |
| ---: | --- | --- | ---: |
| 1 | authority, times the feed's own weight | the tier span, `institution` minus `community` | 0.7 |
| 2 | decayed recency | `recency_weight` | 0.6 |
| 3 | the feed's reliability | `(1 - reliability_floor)` times the best tier | 0.5 |
| 4 | a watchlist subject | `watchlist_bonus` | 0.5 |

Two terms are not in that ranking and each has a different reason. **Carriage** is a tie-break rather than a ranked term: it is bounded from both sides rather than ranked against the four, and `backend/tests/test_rank.py::test_the_carriage_step_cannot_outrank_one_tier_step` reads both walls off `config/`. It may not reach the smallest gap between two tier weights - 0.3 today - or it would promote a community story past a trade-press one, and it may not fall to `ui.lead_shared_subject_weight` - 0.2 today - or a subject that recurs across a week would outrank a story two independent feeds carried today. It sits at **0.25**, the middle of what those two rules leave, and the middle is the point: both bounds are themselves estimates a person can edit, so a step pressed against either inverts a written rule the day somebody nudges the other. **The lens** is ranked by nothing here because the weight that pays it is per lens in `config/taxonomy.json`; the heaviest today is 0.3, which sits between rows 3 and 4.

**The four rows above are not the four lines of the formula**, and the difference is deliberate. The ranking splits the formula's first line in two - the authority a tier sets, and the reliability a feed's own record earns - because a person sets those from different config keys and tunes them apart. It then leaves out the two the paragraph above names.

**Row 1 is the term that decides the head.** Flatten every tier to 1.0 and almost every head slot changes hands. Institution feeds supply a small share of the stream and hold several times that share of the head; community feeds have never held any of it, and **a weight that has never put a story in the head is not yet distinguishable from zero there** - which is the reading that would overturn the community tier's 0.3.

**Every number above is an estimate and each says what would overturn it** (Guardrail #10). All four carry their current reading in the field description on `CollectConfig`, which is where a config key's comment lives in this project - `config/idhazh.json` is JSON and holds no comments.

**A term may reorder; it may never admit.** No weight, at any value, can pull a story past a gate it failed: `too_old` runs before anything is scored, and `max_per_source` and the day ceiling are counts rather than thresholds on the score. `backend/tests/test_rank.py::test_no_weight_can_admit_a_story_the_age_gate_refused` is that promise, driven with every bonus at once against a stale story.

Three details in that carry weight:

- **Authority is the best tier that carried the story, not the average.** One institution saying it makes it true however many aggregators repeated it, and averaging would let volume dilute provenance.
- **Recency is a bonus, not a filter.** It decays by half every `recency_half_life_hours` and never removes anything from the pool. Why that is a decay rather than a cutoff is [freshness.md](freshness.md).
- **Ties break on the canonical address.** Without a deterministic tie-break, two runs over identical feeds can publish different orders, and a re-run over the same feeds has to produce the same plan.

The consequence worth stating plainly: the planning step loads no weights, finishes in seconds, and produces the identical list on every re-run. That is what makes the expensive work shardable afterwards and a re-run cheap.

**Three of those terms and the score itself reach the reader.** `carried_by`, `watchlist_hit`, `on_front_page` and `rank_score` are published unchanged - this stage computes nothing extra for them - and what each one means on the item, and what an absent one means, is [../publishing/layout.md](../publishing/layout.md#an-item-says-why-it-is-here-and-whose-clock-its-time-is). `on_front_page` is a published fact and not a term, so a reader can still be told another desk led with a story that our own arithmetic placed on its own merits.

**The run manifest records which shape produced the order.** `rank.RANK_VERSION` is bumped whenever the scoring shape changes and lands in `RunRecord.rank_version`. A bump nothing records is a bump nobody can read, so the field and the constant have to ship together. It is null on a manifest written before the field existed, which reads as unknown.

### A second order over the same day: the leading stories

The day's item order is settled above and never moves. The day also publishes a
**second order over the same stories** - at most `ui.leading_stories` of them, in
`DigestDay.leads` - so the page has a first screen. Nothing is removed, hidden or
re-ranked: a lead names a story `items` already holds, in the place it already
holds it, and every story a rule turns away still publishes in the stream. What
the block *is* for a reader is
[../../concepts/digest.md](../../concepts/digest.md#the-days-leading-stories).

It is chosen across the whole day rather than off the head of the published
order, because that head is not a ranking: the plan extends one list per desk, so
the first stories on the page are the top of whichever desk sorted first in run
1. That is an accident of assembly, not a judgement about the news.

The arithmetic is one line:

```
lead_score = rank_score + shared_subject_term
```

`rank_score` is the published term above, unchanged. The shared-subject term is
computed at assemble over the finished day, and it obeys the same two rules the
rest of this page does.

**One fact earns one bonus.** A story takes the largest weight it earned and
never the sum, which is the rule `lens_bonus` already follows: two of the day's
running subjects in one title is not twice the story. And **lens overlap is
refused outright**. Within a desk the lens that fires is the desk's own theme, so
an overlap term would restate the per-desk cap - and worse, this page already
pays a weight to *under-carried* lenses, so paying the over-carried ones a second
time in the opposite direction would break the rule in the paragraph above. What
the reader loses is nothing: the cross-desk case it would have caught is already
priced by those weights.

**The term is a step, not a ramp.** A qualifying subject adds
`ui.lead_shared_subject_weight` and a subject that does not qualify adds nothing.
No measurement supports a shape between those two, and a shape nobody measured
may not justify a design (Guardrail #10).

A subject qualifies when both hold:

- **`ui.lead_cluster_floor` distinct sources name the same registry entity in
 their published titles**, counting one story per source per entity, so a
 newsroom that filed four pieces is one source and not four.
- **The cluster holds at least one `reporting` story.** A cluster of
 announcements about one company is a press schedule, not a story.

The title, never the body and never fetched text: the matcher reads words we
wrote and may only emit a slug the committed registry already holds, so a
hostile page can win a tag we already publish and can never mint one (Guardrail #11).

**Four eligibility rules run before any score**, and each excludes whatever the
story ranked: a `low` band story, a `truncated` one, one whose `time_source` is
not the feed, and an `announcement` with no reporting in its cluster. A day
published before `time_source` existed therefore draws no block at all, because
every story reads null and a null is unknown rather than a claim about a clock.

**Four caps then bound the block**, and each answers a different question: a
desk may hold `ui.leading_per_desk`, a `source_id` may hold one, a **subject**
may hold one, and stories the feed dated to the previous day may hold
`ui.lead_max_yesterday`. The subject cap is the one that is not obvious. A
running story crosses desks and sources, so the first three do not bound it -
three of five would clear all of them - and a subject that genuinely deserves
two of five means the day had fewer than five distinct stories worth leading.
The per-desk cap matters more than it looks for the same reason: most of the
committed registry is technology companies, so the shared-subject term is
structurally biased toward the AI and business desks and this cap is the only
thing holding it.

Ties break on higher `carried_by`, then `high` before `medium`, then the newer
story, then `item_id` ascending. The last is derived from the address, so it
cannot be gamed and two builds of one day are identical.

**Below `ui.leading_min` the block does not render.** Four real leads beat five
with one filler.

**A full block is a property of a finished day.** The caps only bind when there
are stories left for them to turn away, and a day is built up over several runs
into one `date -u +%F`, so the most recent date on disk is a fraction of itself
for most of the day - few enough candidates that the block runs short with no cap
ever firing. So anything asking whether the block fills has to read a finished
day, which is any date except the newest one on disk, because an earlier date can
gain no more runs. `backend/tests/test_leading_stories.py` does exactly that, and
it counts the pool from the line the build log already writes for every story a
cap turned away, rather than running the selection a second time, so a day that
ran out of stories and a cap that refused them cannot be read as the same
failure.

#### Why a shared subject is worth less than a second carrier

**A signal is priced by how often it fires: the commoner one has to be worth
less.** A shared subject at the cluster floor fires several times as often as a
second feed carrying one address, so `ui.lead_shared_subject_weight` sits under
`collect.carriage_step`. The rule, not the arithmetic, is what is load-bearing -
a subject that recurs across a week may not outrank a story two independent feeds
carried today.

`backend/tests/contracts/test_app_config.py::test_a_shared_subject_is_worth_less_than_a_second_feed_carrying_the_story`
holds it, reading both numbers off the config rather than spelling them, so an
edit to the step moves the bound with it.

**The firing rate prices a signal; it does not by itself set the weight.** What a
weight buys has to be read against the gaps in a real day's scores, because the
same number that moves a story five places at the top of one day would leapfrog
the whole of another. A weight moved on evidence is moved by the per-run loop
that measures both, never by re-running a division.

The cluster floor follows the same reasoning in the other direction: raising it
costs a few stories a week and buys a stronger claim, because a story several
sources carried is a stronger claim than a story one did.

## Changing the source set without breaking history

A vertical will be retired. A feed will die quietly when a site is redesigned. Both are normal, and both are handled in config rather than in code.

- **An id is an immutable slug; the display name is a separate, freely mutable field.** Renaming what a reader sees must never orphan a payload that referenced the id.
- **Retire, never delete.** A retired vertical, lens or entity keeps its entry with a retired status and the date. Deleting an id breaks every payload written under it and forces a read-side migration; a tombstone costs one object.
- **A retired feed moves to its own key.** `config/sources.json` has a `feeds` list and a `retired` list. A tombstone kept in the live list is a tombstone every run has to filter past, and one missed filter is a request to a source we decided to stop asking. Moving it makes the live list mean exactly what it says, and the record survives either way.
- **A draft status plus a minimum-feed floor** lets a vertical be built in the open over weeks. Below the floor it is not published, so an under-sourced desk never reaches a reader.
- **Feed health is recorded, not configured.** Repeated failures rest a feed automatically, and nothing in a run ever edits `config/sources.json`. See the [source lifecycle flow](health.md#from-item-outcome-to-feed-rest-or-retirement).
- **Soft retirement before hard.** Drop a source's weight, watch what changes, then retire it. Reversible in one field.
- **A candidate that failed research never enters `retired`.** That list preserves the ids of feeds this project configured and later stopped asking, so that an item already published under one still resolves a name. An address nobody ever ran is not a tombstone, and filling the list with them makes it stop meaning anything.
- **A retirement date is the last day a plan could select the feed**, read off the committed health record rather than chosen. An earlier date claims a stop that did not happen.

## Feed Admission Check

The **Feed Admission Check** is the source-entry review before adding or
restoring a feed. Its instrument is
[`backend/utilities/probe_feeds.py`](../../../backend/utilities/probe_feeds.py).
It uses the production fetcher, configured user agent, public-address check,
robots policy, bounded retries, paywall detector and text extractor. It makes
no model call and changes neither curation nor the pipeline's health ledgers.

The utility is a minimum access check, not an editorial acceptance gate. Its
current limits matter when reading a green exit code:

- `--articles` defaults to one. A larger value samples the first entries in
 feed order, not a representative selection across dates or content types.
- **Any one readable article passes the feed.** Asking for three records all
 three results, but does not stop one free article hiding two blocked ones in
 the headline verdict. Review the per-article results, not only `passed`.
- A parser warning is recorded as `malformed` but does not fail the verdict.
 An undated feed can also pass, with `no_dated_entries` beside it.
- It does not apply the production freshness limit or decide whether the page
 is a single useful story. An article's successful status can carry a shape
 warning that the probe's verdict does not expose; see
 [item-health.md](item-health.md#stages-and-outcomes).
- A local pass establishes access from that machine on that date. It does
 not establish access from the GitHub runner or permission to reuse text for
 training. Publisher restrictions still apply.

Sample several articles and keep the report for review, for example:

```text
python backend/utilities/probe_feeds.py --articles 3 --report backend/var/probes/candidate-feeds.jsonl https://finshots.in/archive/rss/
```

Admission remains a curator's decision. Ongoing feed availability and article
yield answer different questions and have different controls; see
[health.md](health.md#per-source-yield-is-measured-and-since-2026-09-06-it-speaks).

### Three things a green probe does not tell you

**A feed that fails is not the same as a feed that is wrong, and the difference
is often the IP address.** A publisher can serve a valid feed to a developer
machine and refuse the runner outright. A source the runner cannot read is a
source this project cannot use, which is a retirement - but the tombstone says
that rather than blaming the publisher, and the instrument that settles it is the
item-health ledger after a week, not the probe.

**A feed read can succeed and still be worthless.** An address that answers HTTP
200 with a web page rather than a feed, or with a feed carrying zero entries,
records as a healthy read and supplies nothing to the pool. Health counts reads;
only yield counts items. A feed configured with the address of a web page can sit
green for weeks.

**Robots permission and training permission are different questions.** A
publisher can allow every ordinary crawler and name a list of AI training bots it
refuses. We are none of those user agents, so the fetch is allowed - but `corpus/`
commits article text as training samples (`CLAUDE.md` section 0a), so the
publisher's stated intent and one of our uses point in opposite directions. This
is recorded rather than resolved: the owner takes that call, and if it goes the
other way the fix is one `retired_on`.

### The feed floor counts feeds, not working feeds

`rank.plan_vertical` compares `min_feeds` against the number of feeds
**configured** as active in that vertical. It cannot count feeds that work,
because it runs before anything is fetched. So the gate can be green while the
source pool is not, and a desk can sit well under its floor on the count that
matters.

**A vertical under its floor plans nothing at all**, which is why a curation
sweep replaces rather than only removes. Retiring feeds without adding any takes
a desk silent, and silence is the one failure a reader cannot tell from a quiet
day.

The floor is not lowered to fit. Lowering it would trade a gate that reads the
wrong number for a lower gate that reads the same wrong number. What would fix it
is a floor read from the health ledger rather than from config, and that is a
contract change nobody has costed - recorded here rather than done.

**What the floor does have is a merge gate.**
`backend/tests/contracts/test_run_plan.py::test_every_vertical_clears_its_own_feed_floor`
reads the committed `config/sources.json` against the committed
`config/taxonomy.json` and fails the build when any vertical's active feed count
drops under `min_feeds`. It says what a failing vertical would cost:
`ai has 6 active feeds against a floor of 35, so it would publish nothing`.

The run-time floor is silent by design - the run succeeds, the digest publishes,
and one section is simply absent - so a config edit that emptied a desk would
reach a reader before it reached anybody's attention. The gate does not make the
floor read the right number. It makes the number it does read impossible to break
by accident.

## Design rationale

**The affiliate-page control sits at collection, not at the score.** An affiliate review that summarizes faithfully separates "the summary is wrong" from "the item should not be here" - every instrument in the eval ledger compares our summary to the article, and all of them pass. Collection is also the cheapest place a rejection can happen: a blocked address is never fetched, never summarized and never scored (Guardrail #2). Authority: owner, 2026-08-24, closing known defect 7.

Segmenting by subject is a source-diversity problem, not a compute one. The pipeline had spare capacity long before it had spare sources, so the binding constraint was never how many items could be summarized - it was how many were worth summarizing, and whether they covered more than one subject.

Two findings from prior art settled the shape. First, every system that publishes a multi-subject daily digest attaches a curated feed list per subject; none of them sorts a single firehose into subjects. Second, those systems enforce a floor below which a subject is not surfaced at all, because a thin list produces a thin day and the reader cannot tell the difference between a quiet day and a broken one.

**A borrowed constant is not a floor.** Twenty-five feeds per vertical came from prior art and is wrong here, because it does not scale with how much a vertical publishes: the systems it came from surface dozens of items per subject per day and ours surface a handful. The shipped numbers - 35 and 21 - came instead from seven times each vertical's daily cap. That cap has since been removed and the floor numbers stayed behind, which is deliberate rather than an oversight: the ratio was always a judgement, and what it produced is a candidate pool several times larger than any day is likely to publish, which is what keeps the ranking with something to choose between when a day is quiet.

State the sequence honestly - the live counts were measured first, then the rule was written, so the rule is fitted to what the source pool supports rather than derived from an independent finding. It is recorded here so a later reader can overturn it with a real measurement instead of re-deriving it.

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
| Taking the leading block from the first N of the published order | It ships the accident instead of the edit. That head is the top of whichever desk sorted first in run 1, which is a property of how the plan is assembled and not a judgement about the news. |
| A heat score for the leading block, computed in the browser | Read-time re-ranking makes a shared link show the recipient a different page from the one the sender saw, and the number behind it would be one nobody measured (Guardrail #10). Carmack, 2026-08-31. |
| `Front page at <source>.` as a lead's sentence | False. `on_front_page` says a salience feed voted, and more than one aggregator can be a salience feed - so naming the front page is wrong whenever the other one voted. |
| `Three sources covered this.` as a lead's sentence | `rank.merge` groups by canonical URL, so `carried_by` counts syndication of one address. Two outlets writing their own pieces produce two addresses and both read 1. The shipped sentence says how the report reached us, which is what the number means. |
| An `events`-based consequence proxy in the lead score | `events` names the kind of event and never its size - a seed round and a multi-billion acquisition both read `funding`. It would make every acquisition outrank every research paper, which is a rule about grammar rather than about importance. |
| Asking the summarizer for the lens, event and entity tags | A tag decides what a reader is shown under a filter, so a page that picks its own tags writes its own index entry - fetched text steering a control (Guardrail #11). It also adds decode tokens to the one stage that already dominates the run. A deterministic matcher costs no model time and returns the same answer on every re-run, which is the property the rest of this page's arithmetic already has. Andre, consulted 2026-08-26. |
| A per-feed weight only, with no tier | The tier is the reusable half: it is a fact about a kind of source, and a new feed inherits it without anyone inventing a number. |
| Keeping the flat floor of twenty-five and leaving two verticals unpublished | The floor would then be measuring the borrowed constant, not the health of the desk. Two verticals stay dark for a reason that does not survive being stated. |
| Dropping the floor to whatever the thinnest vertical reached | That is tuning the target to the result with no rule behind it, and the floor stops being able to fail. |

## See also

- [freshness.md](freshness.md) - the run cadence, how age is scored, and what stops an article publishing twice.
- [../../concepts/placement.md](../../concepts/placement.md) - what the day does with these scores: one order over every story, and the frame over its head.
- [health.md](health.md) - what every feed did on every run, and the quarantine that reads it.
- [trust-boundary.md](trust-boundary.md) - what happens to the text once a discovered link is fetched.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Collect stage and the invariants that hold across all stages.
- [../../concepts/config.md](../../concepts/config.md) - where the feed lists and caps live, and the knob-versus-identifier rule.
- [../contracts/schemas.md](../contracts/schemas.md) - the contracts these vocabularies are enums in, and the versioning rules.
- [../../concepts/principles.md](../../concepts/principles.md) - config-driven with sane defaults, and degrade rather than fail.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11).
