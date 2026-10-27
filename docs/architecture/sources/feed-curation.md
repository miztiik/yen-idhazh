# Selecting an editorial portfolio

**Last Updated**: 2026-10-27

How does the isolated planner choose articles from the admitted batch?
It uses configured numeric rules and explicit factual evidence, not a model
or an inferred subject classification.

These rules supersede the earlier proposal to reuse Python ranking choices;
that proposal is not a separate unfinished selection requirement. The
production Python ranking path is unchanged, and further numeric priority
terms still need their own approval.

## Inputs and independent evidence

Curation receives admitted candidates, their global effective policy,
publication or first-sight timing and current feed history. Publisher IDs
come only from the curated catalog. Parent domains, primary-document
identities and work estimates must be supplied as explicit evidence.
Unknown stays null; source titles and article prose do not fill it.

For article `i`, configured feed authority is multiplied by its feed weight and
applied tier weight:

$$
A_i = \alpha \, w_{\mathrm{feed},i} \, w_{\mathrm{tier},i}
$$

`alpha` is `curate_articles.source_authority_weight`; the other two values are
the configured feed weight and applied tier weight.

The source's technical article-pass rate is:

$$
p_s = \frac{P_s}{P_s + F_s}
$$

`P_s` counts original captures from source `s` that pass access, extraction,
required fields and the minimum word count. `F_s` counts known, source-attributed
technical refusals. Publication, age, category, content-policy and selection
losses do not enter either count. When the configured adjustment is enabled and
the rate is known, it reduces only feed authority:

$$
\Delta_{\mathrm{pass},i} = -A_i \left(1 - \max(f, p_s)\right)
$$

Here `f` is the configured reliability floor. Incomplete evidence or a zero
denominator leaves the adjustment unavailable and does not change the score;
disabling it gives a zero adjustment. RSS feed-read reliability remains
separate and governs feed access and rest. It is not a substitute for `p_s`
and does not add a second ranking penalty.

Publisher exposure is the known published count plus the current chosen count
for that publisher, divided by `L` and capped at one. If published linkage is
unavailable, only the current chosen count is used; an unknown publisher keeps
the term unavailable. Website-group exposure is the share of `S` already in
the candidate's group; an unknown group keeps that term unavailable. Their
weights are the configured `lambda_source` and `lambda_website_group`.

The marginal score for article `i` against the full selected set `S` is:

$$
M(i,S) = R_i + A_i + \Delta_{\mathrm{pass},i}
         - \lambda_{\mathrm{source}} E_{\mathrm{publisher}}(i,S)
         - \lambda_{\mathrm{website\_group}} E_{\mathrm{website}}(i,S)
$$

The recency contribution uses the original age in hours. A missing age gives
zero recency; near-future ages do not increase the bonus:

$$
R_i =
\begin{cases}
0 & \text{if age is unknown} \\
\mathrm{recency\_weight} \left(\frac{1}{2}\right)^{
\max(0,\mathrm{age\_hours}_i) / \mathrm{recency\_half\_life\_hours}}
& \text{otherwise}
\end{cases}
$$

The two exposure values are:

$$
E_{\mathrm{publisher}}(i,S) =
\min\left(1,\frac{B_p + N_p(S)}{L}\right),
\qquad
E_{\mathrm{website}}(i,S) =
\begin{cases}
0 & \text{if } |S| = 0 \\
\frac{N_g(S)}{|S|} & \text{otherwise}
\end{cases}
$$

`B_p` is the known published count for publisher `p` on the current UTC day;
use zero when that history is unavailable, so only current selection
contributes. `N_p(S)` counts selected articles for `p`, and `N_g(S)` counts
selected articles in the candidate's website group `g`. An unknown publisher
or website group keeps its adjustment unavailable. These weights are
configured as `lambda_source` and `lambda_website_group`. The score chooses
among permitted candidates in the active tier and age window; it does not
override tier order.

## Targets, fresh buffers and older deficits

The saved request's `article_limit`, or the configured default, is a positive
finite safe integer. `curate_articles.feed_quality_tiers` declares each tier's
share, additional fresh buffer and increasing age steps. Configured list order
sets priority; numeric tier IDs do not. Tier shares and tier weights have
different jobs: shares set count targets, while the applied tier weight
multiplies feed authority in the score above. A measured article-pass rate can
change ranking within a tier; it never moves a feed between tiers.

For requested limit `L`, tier `t` has an unrounded target and a fresh ceiling:

$$
q_t = L \, \frac{\mathrm{share\_pct}_t}{100},
\qquad
T_t = \lfloor q_t \rfloor + I_t,
\qquad
C_t = \max\left(T_t,\left\lceil
L \, \frac{\mathrm{share\_pct}_t + \mathrm{buffer\_pct}_t}{100}
\right\rceil\right)
$$

`I_t` is one for each tier receiving a remaining place: assign those places to
the largest fractional remainders of `q_t`, with configured tier order breaking
ties. This makes the integer targets sum to `L`. The ceiling adds the buffer as
percentage points; it is not a guaranteed lower bound. Older articles may fill
`T_t`, but not the fresh buffer above it. Counts come from `L`, not candidate
supply. Shares sum to 100 percent, and each share plus its buffer is at most
100 percent. The current percentages live in
[`config/feed-ingest-plan.json`](../../../config/feed-ingest-plan.json).
No fixed feed allowance or shortlist trims the complete input.

Choose fresh articles up to each target first, then remaining fresh articles
up to each ceiling. Only then open older steps for tiers below target. Older
articles fill targets, never buffers. Re-enter phase priority after each winner
or permitted relaxation, using the same full selected set and exposure counts.
Shortages do not authorize exceeding ceilings.

Canonical URL carriers stay available until one actually wins. A capped carrier
cannot remove a viable carrier from another feed. Identity breaks score ties;
labels and primary-document evidence buy no additional capacity.

## Marginal choices and concentration

Each choice recomputes remaining candidates against the actual chosen set.
The retained numeric adjustments cover article technical admission, publisher exposure
and website-group exposure. Website groups are recomputed from canonical URLs
using the configured private-suffix rule; supplied hints cannot override
them. Feed kind, form and other classification labels do not affect admission,
authority or ranking. An unavailable group or publisher produces a null
component, not a fabricated no-overlap measurement.

Configured source and website-group shares bound the planned count.
The minimum-distinct-source preference and source-share cap relax only in
their configured order. The website-group cap does not silently disappear.
Exploration reserves its configured final share, rounded down, for viable
feeds not yet represented. It bypasses no admission or cap.

### Publisher exposure adjustment

Genuine published and item-health evidence may link actual publisher
exposure for the current UTC day. Selected rows are never publication
evidence. Missing linkage uses the explicit current-selection fallback,
with a distinct recorded adjustment term. Unknown publisher IDs remain null.

## Persistence and verification

One chosen content population supplies compact metadata and the selected
text artifact. Each article retains its rank, actual base and marginal
scores, signed adjustments, tier/weight, work estimate, timing and the quota
or exploration exceptions used. No full policy, assessment or losing-score
tree is copied.

`feed_limit` records the per-feed share limit computed from requested output.
`freshness_cutoff_at` records the admitted age window against the saved age
clock; unknown age has no invented cutoff. Every unchosen parsed candidate
receives one terminal metadata row in `rejected-articles`, after all permitted
phase changes and relaxations. Screening refusals precede numeric selection;
winning duplicates precede closed older windows, global capacity, distinct-feed,
feed-share, website-share and fresh-ceiling refusals, in that order.

Only the declared metadata projection is committed. Article text remains
in the separate artifact. [Table B](../../reference/feed-planner-ledgers.md#b-selected-articles)
owns the complete field list. Partitioning adds assignments without
reranking or replacing this selection.

## Design rationale

Compact contributions explain why a chosen article ranked where it did
without preserving a second classification or audit system. Known zero
and unavailable evidence remain distinct through JSON and Parquet readback.

### Configured priority review

**Adopted behavior, unchanged:** Keep the numeric selection described above,
including separate article-pass and publisher-exposure adjustments. This
review adds no score term, matcher, config default or persisted field.

Maintainers write watchlist aliases in
[`config/watchlist.json`](../../../config/watchlist.json), theme keywords and
weights in [`config/taxonomy.json`](../../../config/taxonomy.json), and Python
bonus amounts in [`config/idhazh.json`](../../../config/idhazh.json).
The Python [planning stage](../../../backend/idhazh/stages/plan.py) matches
whole-word phrases against feed headlines through
[`tag.py`](../../../backend/idhazh/tag.py), not article bodies. A configured
theme is called a lens in that configuration.

#### Table A - Compared priorities, not approved additions

| Id | Priority | Python behavior | Current TypeScript finding |
| --- | --- | --- | --- |
| A1 | Watchlist attention | Add 0.5 score points once when an alias of any non-retired entity matches; multiple matching entities do not add more. | The retained title is available, but no watchlist match is recorded or scored. An alias hit would show configured attention, not article quality. |
| A2 | Configured theme | Add only the largest positive weight among matched non-retired themes, not their sum. | Original feed categories are retained strings, not recorded matches to curated themes. No theme bonus or inferred classification is present. |
| A3 | Repeated canonical URL | Add 0.25 score points once when multiple carriers supply the same canonical URL; further carriers add nothing. | Feed IDs and URL identities are available before duplicate removal, but no carrier witness or bonus is retained. Repeated carriage measures syndication of one address, not independent reporting or story agreement. |

The [Python score](../../../backend/idhazh/rank.py) applies those rules.
The [current TypeScript selection](../../../services/feed-ingest-plan/src/curate-article-portfolio/editorial-selection.ts)
does not. Its [maintainer-authored config](../../../config/feed-ingest-plan.json)
sets the authority coefficient to 1.0 and the maximum recency contribution to
0.6 score points. Copying Python's 0.5 or 0.25 points can change selection;
those amounts are not neutral or approved TypeScript defaults.

The [candidate](../../../packages/common-contracts/src/schemas/candidate.schema.ts)
retains title, categories, article text and feed facts.
[Additional article evidence](../../../packages/common-contracts/src/schemas/planner-stage.schema.ts)
contains only parent domain, primary-evidence identities and estimated work.
Missing matches or carrier witnesses are not measured zeroes.
[Selected metadata](../../reference/feed-planner-ledgers.md#b-selected-articles)
records actual adjustments as `term` and `value`; accepting a term name does
not approve its meaning.

**Recommendation, not approval:** Keep current ranking while the priority
decision is pending. This gives watchlist, theme and repeated-URL inputs no
extra priority; it does not close the remaining priority work.
Before adding a term, obtain approval for its exact input and matching rule,
independent meaning, config maintainer and default, no-double-counting rule,
score evidence and current-reader-before-writer sequence. No proposed priority
term, matcher or default has approval. Front-page votes, inferred
classifications and a wholesale Python-ranking port are not authorized by
this comparison.

## See also

- [Screening](feed-screening.md)
- [Feed history](planner-feed-history.md)
- [Operator APIs](feed-operator-api.md)
- [Partitioning](feed-partitioning.md)
- [Planning completion](feed-ingest-audit.md)
