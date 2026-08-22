# Source Discovery

**Last Updated**: 2026-08-21

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

Each carries a feed list, a daily cap and a lifecycle status. **The feed floor is seven times the daily cap.** A vertical below its floor is not published.

| id | daily cap | feed floor | live feeds |
| --- | --- | --- | --- |
| `ai` | 5 | 35 | 38 |
| `energy` | 3 | 21 | 24 |
| `business-economy` | 3 | 21 | 22 |
| `world` | 3 | 21 | 27 |
| `india` | 3 | 21 | 27 |

Live counts measured 2026-08-22 by fetching and parsing every configured feed. A feed counts as live only if it resolves, parses and carries entries.

The caps sum to less than the daily item ceiling on purpose, so a vertical can be added without re-opening that ruling.

**Lenses** are a closed vocabulary of cross-cutting tags. **Events** are a closed vocabulary of what happened to an item - a release, a deal, an acquisition, a funding round, a capital commitment, results, a regulatory action, research, an incident. Both are enums in the contract, not free-text strings, so a new value is a schema change with a changelog entry rather than a typo waiting to happen ([../contracts/schemas.md](../contracts/schemas.md)).

## Sources are tiered, and the tier is the weight

| Tier | What it is | Examples |
| --- | --- | --- |
| 1 | The institution that *is* the fact | a lab's own blog, a central bank, a statistical agency, a regulatory filing, a company newsroom |
| 2 | Trade press that covers the beat daily | a specialist outlet, a wire's section feed |
| 3 | Community and aggregators | a forum, a link aggregator |

Ranking is deterministic and loads no model: **tier weight, multiplied by how many independent sources carried the story, plus a bonus for a watched entity and a bonus for front-page salience.** A story three independent sources carried today is the day's story. This runs in the planning step, before any weights exist in memory.

The consequence worth stating plainly: **a link aggregator is a vote, not a source.** It contributes rank to a URL already in the pool. It never discovers, because a site with no subject taxonomy cannot be asked for a subject.

## One address per story

Deduplication is the whole point of collecting from many feeds, and it only works if the same article arriving three ways produces one address. Canonicalisation is therefore a load-bearing step, not tidying:

- The scheme and host are lowercased, a default port is dropped, and a leading `www.` goes. These are the same server.
- Campaign and click identifiers are stripped. They differ per referrer for the same article, so leaving them in means one story arrives as several.
- The fragment goes; a trailing slash goes from a non-root path.
- **What remains of the query is kept and sorted.** Stripping every parameter would be simpler and wrong: on plenty of sites the query *is* the article.

Identity is the digest of the canonical address, and it lives in a payload field - never in a path, a filename or a URL. Paths are for humans and for globs.

## Ranking is arithmetic, not judgement

The day is decided before any model loads, by a score with four terms: the authority of the source, multiplied by how widely the story is carried, plus a bonus for naming a watchlist entity, plus a bonus for an aggregator vote.

Two details in that sentence carry weight:

- **Authority is the best tier that carried the story, not the average.** One institution saying it makes it true however many aggregators repeated it, and averaging would let volume dilute provenance.
- **Ties break on the canonical address.** Without a deterministic tie-break, two runs over identical feeds can publish different orders, and the order is part of what a shared link shows.

The consequence worth stating plainly: the planning step loads no weights, finishes in seconds, and produces the identical list on every re-run. That is what makes the expensive work shardable afterwards and a re-run cheap.

## Changing the source set without breaking history

A vertical will be retired. A feed will die quietly when a site is redesigned. Both are normal, and both are handled in config rather than in code.

- **An id is an immutable slug; the display name is a separate, freely mutable field.** Renaming what a reader sees must never orphan a payload that referenced the id.
- **Retire, never delete.** A retired vertical, lens or entity keeps its entry with a retired status and the date. Deleting an id breaks every payload written under it and forces a read-side migration; a tombstone costs one object.
- **A draft status plus a minimum-feed floor** lets a vertical be built in the open over weeks. The floor is seven times the vertical's daily cap. Below the floor it is not published, so an under-sourced desk never reaches a reader.
- **Feed health is recorded, not configured.** Repeated failures quarantine a feed automatically and degrade its vertical. The run never fails because a source died.
- **Soft retirement before hard.** Drop a source's weight, watch what changes, then retire it. Reversible in one field.

## Design rationale

Segmenting by subject is a source-diversity problem, not a compute one. The pipeline had spare capacity long before it had spare sources, so the binding constraint was never how many items could be summarized - it was how many were worth summarizing, and whether they covered more than one subject.

Two findings from prior art settled the shape. First, every system that publishes a multi-subject daily digest attaches a curated feed list per subject; none of them sorts a single firehose into subjects. Second, those systems enforce a floor below which a subject is not surfaced at all, because a thin list produces a thin day and the reader cannot tell the difference between a quiet day and a broken one.

The floor started as a borrowed constant: twenty-five feeds for every vertical, taken from prior art. That number is wrong here, because it does not scale with how much a vertical publishes. The systems it came from surface dozens of items per subject per day. Four of our five verticals surface three. A floor that ignores the cap asks a three-item desk to carry the same source pool as a thirty-item one.

The floor is now seven times the daily cap. Seven is a judgement, not a measurement: it is the point at which the candidate pool stays several times larger than the slots, so the ranking still has something to choose between on a quiet day. State the sequence honestly - the counts were measured first, then the rule was written, so the rule is fitted to what the source pool supports rather than derived from an independent finding. It is recorded here so a later reader can overturn it with a real measurement instead of re-deriving it.

The floor still does its job. It is not a formality that always passes: `business-economy` clears twenty-one by one feed, and a single dead source puts it back under.

Tiering the sources was the cheap half. Once a source carries a tier, ranking needs no model, no classifier and no judgement at run time: the arithmetic of "how authoritative" times "how widely carried" reproduces most of what an editor would pick, and it reproduces it identically on every re-run.

The lifecycle rules exist because the alternative was discovered the expensive way in other projects: a config edit that deletes an identifier silently invalidates every artifact that referenced it, and the breakage surfaces months later when someone loads an old payload.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A single link aggregator as the only source | No subject taxonomy; one global front page whose only tags are post types. Keyword queries against it are lexical - a query for a subject catches every casual mention of the word - and it carries no world, energy or regional coverage at all. |
| A classifier sorting one firehose into verticals | Nobody who has shipped this does it. It also puts model time into the planning step, which today loads no weights and finishes in seconds. |
| One vertical per topic of interest | Eleven verticals is roughly 275 feeds to curate and breaks the daily ceiling. Most candidate topics turned out to be lenses or entities on inspection. |
| A market-prices vertical | A once-daily, statically-committed digest is the wrong instrument for a number that moves continuously. Kept as a lens so a structural story still surfaces. |
| Splitting a subject into two verticals by angle | The same feed list serves both, so the split doubles curation to buy one taxonomy line. The separation is recovered for free by the event vocabulary. |
| Deleting a retired entry from config | Breaks every payload written under that id and forces a read-side migration. |
| Keeping the flat floor of twenty-five and leaving two verticals unpublished | The floor would then be measuring the borrowed constant, not the health of the desk. Two verticals stay dark for a reason that does not survive being stated. |
| Dropping the floor to whatever the thinnest vertical reached | That is tuning the target to the result with no rule behind it, and the floor stops being able to fail. |

## See also

- [trust-boundary.md](trust-boundary.md) - what happens to the text once a discovered link is fetched.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the Collect stage and the invariants that hold across all stages.
- [../../concepts/config.md](../../concepts/config.md) - where the feed lists and caps live, and the knob-versus-identifier rule.
- [../contracts/schemas.md](../contracts/schemas.md) - the contracts these vocabularies are enums in, and the versioning rules.
- [../../concepts/principles.md](../../concepts/principles.md) - config-driven with sane defaults, and degrade rather than fail.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract, including schema versioning (section 11).
