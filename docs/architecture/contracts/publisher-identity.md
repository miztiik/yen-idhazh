# Publisher identity

**Last Updated**: 2026-10-24

How is a publisher ID created once, then kept stable as names and feeds change?

**Status**: Approved naming contract; implementation awaits separate owner
confirmation. This page adds no catalog, schema field, feed assignment, API or
runtime behavior. I Feed remains a design proposal, not a deployed engine.

## The identity being named

A publisher is one editorial publication and its newsroom, following the
existing [masthead rule](../publishing/autotune-content-similarity.md).
It is not a feed, feed section, domain, hosting provider or corporate parent.
The Hindu and The Hindu BusinessLine remain separate editorial publications
despite common ownership.

`publisher_id` is the permanent curated key for that publication. Its display
name is separate and can change. Several feeds can explicitly reference one
publisher ID; their `source_id` values still identify separate feeds.

The owner-maintained [source catalog](../../../config/sources.json) currently
declares feeds, not a publisher registry or `publisher_id` references.
Existing story grouping uses the recorded `source_name` masthead through
`outlet_of`, as the masthead rule describes. That text key is not an immutable
publisher ID. This contract does not replace it or change story grouping.

## Creation and review

Apply this procedure when catalog implementation is approved, not as permission
to assign IDs to today's feeds:

1. Check the owner-controlled source catalog, including existing aliases and
   reserved or retired IDs. Establish which editorial publication the feed
   belongs to from curated provenance. Do not infer it from a feed-ID prefix,
   domain, feed title or parsed article text.
2. Reuse an existing ID when the publication is confirmed to be the same.
   If identity is uncertain, leave it unknown and obtain operator confirmation.
   Do not create a guessed publisher to complete a mapping.
3. For a confirmed new publication, choose a short, stable slug from its curated
   canonical publication name or established short name. A slug is an ASCII
   identifier made of lowercase letters or digits, with single hyphens between
   nonempty parts. This is a one-time editorial choice, not a runtime name
   conversion.
4. Check the proposed ID against all existing reservations. On a collision,
   keep the existing ID and qualify the new one with a verified stable
   distinction, such as country or editorial edition. Do not append a random
   value or an incrementing number. An edition qualifier does not by itself
   establish a separate newsroom; an uncertain distinction returns to step 2.
5. Validate the spelling with the existing `SlugSchema` in
   [primitives.ts](../../../packages/common-contracts/src/schemas/primitives.ts).
   Resolve a failed check before recording the ID; do not silently normalize
   invalid input.
6. Record the reviewed ID, separate display name and identity provenance in the
   owner-controlled source catalog, then bind feeds by explicit reference.
   Catalog location and field layout need implementation approval. This page
   does not create another registry file or assign any current feed.

Fetch, parse and later runtime stages read the recorded reference. They never
regenerate a publisher ID from a URL, title, article text or changed display
name. Feed topics, timestamps, hashes and UUIDs derived from a display name are
not publisher-ID creation rules. Event and run UUID rules name different things.

### Creation examples

These are illustrations, not approved catalog assignments or reservations:

- **Accept after identity review:** `bbc`, `the-guardian` and `straits-times`
  are valid spellings for curated publication names. Several confirmed feeds
  from the same publication would reference the same ID.
- **Keep separate:** `the-hindu` and `the-hindu-businessline` illustrate the
  existing editorial-publication distinction, not a common-parent grouping.
- **Qualify a genuine collision:** if `the-herald` already belongs to another
  publication, `the-herald-australia` is a possible new ID only when the operator
  confirms that country identifies the distinct publication. Do not rename the
  existing reservation.
- **Reject spelling:** `BBC`, `the_guardian`, `straits times`, `bbc--news`,
  `-bbc` and an empty string fail the shared slug grammar.
- **Reject creation despite valid spelling:** `bbc-2` as a collision counter,
  `bbc-world` as a topic-derived publisher, or `bbc-20261024` as a dated identity
  do not follow this procedure. A valid spelling does not prove identity.
- **Keep unknown:** a shared host, a similar feed title or matching article text
  alone cannot establish a publisher or justify merging two catalog entries.

## Preservation and historical meaning

An ID does not change when the publication changes its display name, moves
domains, adds a feed or retires a feed. Retirement reserves the ID permanently;
it must never be reassigned to another publication.

Record name aliases explicitly against the existing identity. A duplicate
registration, editorial merger or split requires owner-reviewed reconciliation
that states what each old ID meant and how future references are resolved.
Do not silently merge identities or rewrite earlier observations. The alias
and reconciliation storage and any read-side migration remain implementation
decisions, not new fields declared here.

A historical observation with no publisher ID remains unknown. Today's
feed-to-publisher mapping is not evidence that an earlier run recorded that
identity. Do not fill old observations from the current catalog or count each
unknown feed as a different publisher.

## Validation ownership

When implemented, TypeScript's `PublisherIdSchema` must alias `SlugSchema`,
not introduce another regular expression. No such alias is added by this page.
Catalog validation must refuse duplicate publisher definitions and nonnull
feed references to an undefined publisher. Several feeds referencing one
defined publisher are legal. Missing legacy IDs remain explicitly unknown.

Syntax validation cannot prove that two feeds share a newsroom, that a name
change preserves identity, or that an old reservation was not reused. Catalog
review establishes those facts; implementation must test the creation and
historical-read meanings as well as the scalar spelling.

Owner-authored catalog configuration uses reader-native validation of the
fields its readers compute on, under `CLAUDE.md` Guardrail #3. It does not need
a second persisted-payload schema just because it is configuration.
If a publisher ID is later added to a shared persisted payload read by Python,
the Pydantic model remains authoritative, with its small TypeScript copy,
version/changelog, compatible reads and named binding tests. Follow
[the schema contract](schemas.md#what-holds-the-copy-in-step), including
`backend/tests/contracts/test_feed_ingest_contracts.py`.
The planner-only TypeScript event exception stays narrow; approval of a
publisher slug does not create another exception.

## Publisher breadth boundary

Publisher breadth means the number of distinct confirmed editorial publishers
represented in a selection, not a judgment of article quality. This identity
contract enables a later proposal; it does not enable selection behavior.

The proposed independent selection step belongs after parsing and deterministic
screening, before assigning articles to worker shards. It consumes validated
candidates from the same run, with explicit bounded history and configuration.
It must not discover inputs through a growing repository scan or a new state
index. The curated source registry remains the identity authority. Fetched text
is data, never a control value, file path or outbound destination.

Do not add content deduplication to fetch or parse under this approval.
There is no new semantic deduplication, qualitative assessment or story
classification here. Existing story handling is unchanged. Day-aware publisher
preferences remain soft choices among comparably strong alternatives, not hard
caps or a reason to block selection when history is missing.
The existing [source-reliability penalty](../sources/feed-curation.md#inputs-and-independent-evidence)
measures operational delivery, not article quality.

The API route and action name, raw validated batch versus local saved-reference
inputs, exact input/output shape, policy coefficients and implementation order
require separate confirmation. This page selects none of them.

## Manual acceptance checklist

Review this contract before approving implementation; these are required
acceptance cases, not claims of executed runtime checks:

- [ ] Confirm the editorial unit and provenance before assigning an ID; uncertain
  identity stays unknown pending operator confirmation.
- [ ] Reuse a known ID across feeds; refuse duplicate publisher definitions and
  unresolved nonnull references, not repeated valid feed references.
- [ ] Check the positive and negative examples with the shared slug validator
  and the separate human identity review.
- [ ] Keep the same ID through display-name and domain changes; prevent reuse
  of a retired ID and require explicit alias or merger reconciliation.
- [ ] Keep missing historical IDs unknown, without current-catalog backfill.
- [ ] Review catalog storage, actual feed mappings, persisted-field compatibility
  and cross-language binding coverage before wiring runtime readers or writers.
- [ ] Obtain separate selection-API approval without adding fetch/parse content
  deduplication, qualitative assessment, hard day caps or history blocking.

## Design rationale

Owner decision, kumarsnaveen_microsoft, 2026-10-24 UTC, publisher option A1:
adopt an immutable curated publisher slug and document its creation before
implementation. A human-readable key makes catalog review practical; choosing
it once prevents a name or endpoint edit from changing the counted publisher.
This adopts the existing editorial unit, not its mutable masthead text as the
permanent identifier. Approval covers this contract only, not runtime wiring,
shared persisted fields, feed assignments or the separate API proposal.

## See also

- [I Feed](../sources/i-feed.md#what-we-keep) - proposed source-catalog responsibility.
- [Editorial selection](../sources/feed-curation.md) - current isolated planner behavior.
- [Schema ownership](schemas.md) - shared payloads and the planner-only event exception.
- [Feed concept](../../concepts/feed.md) - what a feed contributes.
- [Verification gates](../../how-to/run-the-gates.md) - checks when implementation is approved.
