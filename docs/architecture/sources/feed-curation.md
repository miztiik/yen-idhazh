# Selecting an editorial portfolio

**Last Updated**: 2026-10-24

This page owns how the isolated TypeScript planner chooses articles from one
screened run. Production digest planning is unchanged.

## Inputs and independent evidence

`curateArticles` in
`services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts`
accepts the screening stage's admitted candidates, their effective policies and
freshness observations, and explicit nullable factual evidence. It never fetches
an article or calls a model.

The caller supplies genuine publisher identities, configured parent domains,
optional measured operational history, optional primary-document identities,
work estimates, and bounded prior opportunity evidence. Every supplied identity
has an origin. Missing means unavailable; an empty recorded set means known
empty. A feed title is not a publisher name. A parent domain is a concentration
control, not a publisher identity.

The source's original vertical chooses its effective policy. Assigned desk,
lenses, event types, event-cluster occurrence and entities remain separate
validated labels. Curation neither infers labels from feed categories nor
copies a vertical into an unknown desk. The original candidate and article
text remain in the returned selected content.

Operational reliability retains its success fraction, attempted-feed
denominator and measured window. It is not multiplied into article quality.
The base score is the sum of the screening stage's measured recency bonus and
configured source authority: authority coefficient times source weight times
the applied tier weight.

The runner supplies the [native feed history](planner-feed-history.md) read
from the planner's named `state/raw/feed-health/` files or their compact
successors, then includes the current saved feed read. A productive read
returned at least one item. The success fraction is productive reads divided
by evidence-bearing attempts, not a census of every configured source or day.
Its `window_days` is the configured recorded-day lookback; missing days do not
become known empty days.

When enabled, a separate source-reliability penalty reduces only source
authority:

```text
production_factor = max(collect.reliability_floor, success_fraction)
source_reliability_penalty = authority * (1 - production_factor)
priority_score = base_article_score - source_reliability_penalty
```

The floor and window come from `config/idhazh.json`, which the operator edits.
There is no new coefficient. The penalty applies once to an article, not once
per carrier or outlet. Missing history has null history, factor and penalty,
and makes no ranking change; it is not recorded as measured perfect health.
Disabling the term retains known history and records a zero penalty.
Conflicting native and caller-supplied history is refused, as is inconsistent
history for two articles from one source.

Word count, byline presence and source kind are not model verdicts.
Informative and suitability verdicts remain not assessed.

Publication timing comes from screening. An unknown publication time earns no
invented recency bonus. A first-seen time remains first-seen in returned quality
evidence and persisted assessments, never relabelled publication or fetch
time. Harvest observations supply extraction and paywall outcomes when present;
their absence does not become a claimed successful observation.
Assessments retain the measured timing basis, timestamp and signed age. Ranking
may floor a near-future age at zero for its recency bonus; it does not change
the stored evidence.

## Opportunity before selection

Canonical URL duplicates and supported carrier groups are reduced first.
Carrier representatives and each source's remaining articles are ordered by
priority score, including the separate reliability penalty, with candidate
identity breaking ties. The source allowance is its configured base plus
earned configured bonuses. Each bonus type is granted at most once:

- An uncovered occurrence needs a validated event-cluster identity and a
  recorded coverage set that does not contain it.
- An underrepresented vertical needs a caller-supplied measured opportunity
  set, not just the source's vertical label.
- Unique primary evidence needs a recorded document identity held by exactly
  one canonical article in the full screened input, including suppressed
  carriers.

A canonical article can witness only one bonus type. Copies of its URL cannot
buy more allowance. Without the necessary evidence a bonus is not granted.
The result retains each witness and the actual allowance. Every article
beyond that allowance receives `SOURCE_QUOTA_EXCEEDED`, with its source
position and actual allowance in the existing rejection details.

## Marginal choices and concentration

At each greedy choice the planner recomputes every remaining candidate's score
against the actual already selected set. Each source-kind, parent
domain, vertical, assigned-desk, lens, event-type, event-cluster and entity term
is its own coefficient times the fraction of selected articles sharing at
least one value in that same dimension. Several shared labels on one selected
article count once. An empty selected set contributes zero. An unavailable
candidate label, or an unavailable selected label needed for the comparison,
makes that term unavailable, not known zero. A known empty candidate set
cannot overlap and contributes known zero.

Coverage is a separate recorded prior-coverage term: its coefficient applies
when the candidate's known occurrence is in the supplied coverage set. Unknown
occurrence or prior coverage makes it unavailable. It is not an inferred
similarity score, entity match or claim that reporting verified a fact.

The marginal score subtracts the source-reliability penalty, publisher-exposure
penalty and each available set-dependent penalty from the unchanged base article score.
Unavailable terms contribute nothing and retain their explicit status.
Source kind has no eligibility rule, quota or authority shortcut. Its zero
coefficient removes its influence.

The planned slot count is the smaller of the normalized candidate count and
the configured article limit. A null article limit adds no ceiling. Source
and parent-domain maxima are rounded up from their configured shares of that
planned count. Known event clusters also have their configured item maximum.
Unknown domains and clusters cannot be tested against those particular caps.

Until the distinct-source target is met, selection prefers viable sources
not yet represented. If no candidate clears the controls, the configured
relaxation order may remove the distinct-source preference and source-share
cap. Parent-domain and cluster caps are not silently removed: their names
are absent from the allowed relaxation vocabulary. If they prevent filling
the portfolio, the result is smaller and the terminal trace records why.

The final configured exploration share of planned slots is reserved, rounded
down, for viable sources still absent from the current portfolio. Unused slots
return to ordinary ranking when no such candidate clears the remaining caps.
No exploration slot bypasses screening, source normalization or a cap.

Each successful choice uses the existing `PortfolioChoicePayloadSchema`.
Each step also returns the selected identities before that choice, every
evaluated marginal score, blockers and current relaxations. A blocked step
is retained before a relaxation is applied. These are actual observations,
not final scores copied backwards. The later audit stage consumes this
structured evidence; the runner owns event-envelope identity and stamping.
Terminal cutoffs retain the actual blocking controls and their counts/limits.
The existing rejection row records the first binding control's numbers, not
a comparison against an article limit that was never reached.

## Story and carrier evidence

The existing story rules are owned by
[the same-story page](../publishing/autotune-content-similarity.md).
Candidates have no semantic vectors. Equal titles, shared entities and shared
event types do not establish a semantic match.

Canonical identity establishes a URL duplicate. A shared validated occurrence
from the same named label matcher can establish recorded carrier membership
between distinct explicitly recorded publishers. This is labelled
`recorded-event-cluster`, never a measured vector comparison.

Before joining such a group, the existing headline figure-clash veto is
checked. The bounded TypeScript port handles normalized ASCII headlines and
the existing written-number scales and significant-figure rounding. A
headline outside that supported reduction makes the comparison unavailable;
it does not silently gain a different Unicode matching rule. Every prospective
member must clear against every existing member. This prevents a matching
neighbour from joining two incompatible endpoints.

Each group retains all candidate and source identities, distinct known
mastheads, pair evidence, the strongest representative and suppressed-carrier
replacement identities. Unknown mastheads do not count as new outlets.
Several outlets carrying a story is coverage evidence, not independent
verification of the underlying claim.

## Persistence and verification

`persistPortfolio` writes the existing selection and terminal rejection
contracts through `@idhazh/ledger-file-writer`, using caller-supplied registered
ledger settings and prefixes from `config/ledgers.json`. Files are written
relative to the caller's state-directory output root. Selection is
unsharded; writer shard zero is provenance, not a worker assignment. Selected
rows retain candidate identity, original source and labels, effective policy,
positive rank, caller-supplied work estimate and the scores at their own
selection step. Their separate `source_reliability` evidence records the
enabled state, source-authority contribution, configured floor, measured
fraction, attempted-read denominator, window, factor and penalty. An article
removed before greedy evaluation still has no invented greedy score.
Full article text is returned to the caller, not duplicated in this ledger.

Empty writes return explicit empty file lists. A skipped or failed write is
an error, never a completed run. The audit stage must not declare completion
until all required files are durable. A partial write can leave a readable
earlier immutable file; this function does not stamp a completed attempt.

`test/curate.test.ts` reads only the named bounded
`tests/fixtures/feed-ingest-plan/portfolio-cases.json` and named configuration
files, or inputs generated by the test. It exercises real stage choices,
independent coefficient substitutions, missing evidence, source floods,
bonuses, exploration, relaxation and all-pairs figure vetoes. The persistence
case reads actual Parquet through WASM and Arrow and checks recorded identity,
schema and row expectations. It does not invoke a Python reader, access the
network or use mocks.

## Harvest and selection evidence

Harvested content retains the fetch day, correlation and policy that governed
its original screening. A later selection retains its own decision day,
correlation and effective policy. Dispatch does not rewrite either record to
make those facts equal. It requires the shared candidate and source identities,
canonical URL, and labels to match.

The native dispatch regression covers both a later selection day and a changed
freshness policy, then reads the persisted Parquet back through the current
contract. Same-day, unchanged-policy runs retain their existing behavior.

## Publisher-exposure adjustment

**Integration limit:** Production publication currently does not retain a link
to the isolated planner's recorded publisher snapshots. Nonempty production
history therefore remains unavailable and uses the approved current-run-only
fallback. Native fixtures prove the strict reader, not downstream integration.
Preserving the original planner identity through actual workers/publication
remains deferred with Plan 67 Rows 17/18; this phase does not add that producer.

Count actual publications for the publisher on the current UTC day, then add
that publisher's already-selected items in the current run. Normalize the
count by the planned selection slots, capped at 1, before applying the
configured coefficient:

```text
exposure = min(1, (published_today + selected_so_far) / planned_slots)
adjustment = -lambda_source * exposure
```

The maintainer approved reusing the current `lambda_source` value of 0.25 and
replacing the feed-crowding term rather than charging both. The approved
normalizer is actual publications today plus items already selected, divided
by planned slots and capped at 1. Known-empty history contributes zero.
Unavailable history uses current-run selections only and records that history
was unavailable. Unknown publisher identity adds no publisher count. This is
a soft preference, not a cap or a selection block.

`selectArticles`, used by `/select-articles` and `/plan`, reads the captured
UTC day's registered `published` ledger through the existing raw/compact
precedence. Published URL and item membership is the publication authority:
an extraction success, a past shadow selection or an item-health retry alone
is not a publication. Each distinct published URL counts once.

The bounded reader joins that membership to successful publish-stage health
records by item and URL, requiring one recorded run/source maintainer. It then
requires one publisher identity across the selection snapshots with that
run, source and URL. Identity comes only from the saved `source.publisher_id`,
never the current catalog, caller attribution text, feed title or domain.
Conflicting snapshots, an unknown publisher, a missing maintainer or incomplete
history make publication history unavailable. Partial known counts are not
used as a complete census. Known-empty publication membership needs no
identity join.
Malformed JSON, schema-invalid data, named native-integrity failures and
unreadable optional files report `invalid_publication_history`, emit a warning
with the precise diagnostic and use current selections. The shared reader
still refuses corrupt evidence; this optional boundary never uses its rows.
The reader marks these data refusals with `LedgerHistoryReadError`; callers do
not copy its diagnostic strings to decide whether to continue. Unrecognized
errors, including programming errors, are not suppressed.

Only today's named files are read. A publication from yesterday's selection
cannot be attributed unless today's bounded evidence supplies the required
recorded identity; otherwise it uses the current-selection-only fallback.
This deliberately gives up historical coverage rather than inventing identity
or growing the read window. The live publisher registry is still empty; real
fixture mappings prove the behavior, not live publisher coverage.

Every evaluated score records `publisher_exposure`: UTC day, nullable
publisher ID, publication-history status, nullable publication count,
already-selected count, planned slots, coefficient, normalized exposure and
nonnegative penalty. Unknown identity records zero current count and null
exposure/penalty. With missing history, known identity still records a measured
current-selection adjustment. The legacy `source` feed-crowding field remains
unavailable on new choices, so the adjustment is charged once. Older saved
scores retain their original feed term and null publisher exposure.

The stage response's `publisher_history` reports availability and named evidence
gaps even when no article is selected. The plan summary also retains the named
history file evidence. Publication-history inputs are captured once for a
selection; audit replay uses that same evidence, not a later disk read.

## Design rationale

Selection preserves three distinct answers: whether a source was operational,
what is known about its article, and what that article adds to the current
set. Combining them into one quality product would conceal which fact changed
a decision. Returning the exact greedy trace lets the later audit stage
record each answer without inventing evidence or recomputing history.

Maintainer approval, 2026-10-24, A1: reuse Python's
source-authority ranking effect as this separately recorded penalty, on by
default for the isolated TypeScript planner. Keep article quality and diversity
selection distinct. This does not require identical Python and TypeScript
selection and does not change the production Python planner or digest.

Maintainer ruling, 2026-10-24 UTC: replace the isolated
TypeScript planner's RSS reliability penalty with a normalized penalty for
cost from operations that failed to produce usable material for a supported
source-side reason. Preserve curated source weight and tier. Apply the new
penalty only after its evidence rules pass; do not stack it with RSS
reliability. This supersedes the earlier penalty choice above. It does not
change production Python planning. The formula and evidence
thresholds are proposed in
[feed-ingest feedback](../contracts/feed-ingest-feedback.md); their provisional
window, support, coverage and weight defaults are maintainer-approved. Producer
fields and exact operation-to-cost bindings remain open in D3.

Maintainer ruling, 2026-10-24 UTC: reuse the existing
`lambda_source` value of 0.25 for the soft publisher-exposure preference and
replace the feed-crowding term. Do not stack both. Count actual publications
on the current UTC day plus the publisher's already-selected items, divide by
planned selection slots and cap at 1. Known-empty history is zero; unavailable
history falls back to current-run selections and records that history was
unavailable; an unknown publisher contributes no count.

## See also

- [Planning policies](feed-ingest-policies.md) - the global switch and its removal condition.
- [Audit recording](feed-ingest-audit.md) - exact replay and completion proof.
- [Contract schemas](../contracts/schemas.md) - current and historical score evidence.
