# Publisher identity

**Last Updated**: 2026-10-27

How is a publisher ID created once, then kept stable as names and feeds change?

**Status**: Eight reviewed publisher IDs name 20 active and retired feeds in
the catalog. Other feed mappings remain unknown until publisher-owned evidence
confirms their editorial identity. Soft publisher exposure is implemented in
the isolated planner; its
[selection contract](../sources/feed-curation.md#publisher-exposure-adjustment)
owns the behavior and missing-history fallback. I Feed remains a design proposal, not a
deployed engine.

## The identity being named

A publisher is one editorial publication and its newsroom, following the
existing [masthead rule](../publishing/autotune-content-similarity.md).
It is not a feed, feed section, domain, hosting provider or corporate parent.
The Hindu and The Hindu BusinessLine remain separate editorial publications
despite common ownership.

`publisher_id` is the permanent curated key for that publication. Its display
name is separate and can change. Several feeds can explicitly reference one
publisher ID; their `source_id` values still identify separate feeds.

The maintainer-maintained [source catalog](../../../config/sources.json) declares
the publisher registry beside feed references. Feed entries reference only
IDs with reviewed publication evidence; missing or uncertain evidence stays
null.
Existing story grouping uses the recorded `source_name` masthead through
`outlet_of`, as the masthead rule describes. That text key is not an immutable
publisher ID. This contract does not replace it or change story grouping.

## Creation and review

Apply this procedure when adding a publisher or assigning a feed:

1. Check the maintainer-controlled source catalog and its existing publisher IDs.
   Use feed metadata only to find possible matches; confirm the editorial
   publication from publisher-owned evidence before assigning an ID. AI may
   help find and compare that evidence, but a feed-ID prefix, domain, feed
   title or parsed article text alone is not proof. Leave uncertain matches
   unknown.
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
6. Record only the reviewed ID and display name in the publisher registry, then
   bind feeds by explicit `publisher_id`. The registry lives beside feed
   references in [`config/sources.json`](../../../config/sources.json), and
   each feed's `publisher_id` is nullable, with missing meaning unknown.
   Lifecycle belongs to feed entries, not publisher entries: `added_on` is the
   UTC date a feed first entered the catalog; a new feed records that date, and
   a new retirement records `retired_on` and an open lowercase
   `retirement_reason`. Missing legacy lifecycle values stay unknown. The same
   missing fields can describe either
   a legacy feed or an incomplete new edit, so runtime validation cannot tell
   those cases apart. New feed and retirement edits must include their dates and
   the retirement reason, as applicable, in curated edit review; that is an
   editorial requirement, not a runtime guarantee. Do not invent unknown dates.
   The reviewed catalog change and its Git history
   record publisher-mapping decisions; there is no extra provenance field.
   Adding or changing these values must not need per-publisher code edits.

Fetch, parse and later runtime stages read the recorded reference. They never
regenerate a publisher ID from a URL, title, article text or changed display
name. Feed topics, timestamps, hashes and UUIDs derived from a display name are
not publisher-ID creation rules. Event and run UUID rules name different things.

### Creation examples

These examples show the naming and identity rules; current assignments are in
the [source catalog](../../../config/sources.json).

- **Accept after identity review:** `bbc`, `the-guardian` and `straits-times`
  are valid spellings for curated publication names. Several confirmed feeds
  from the same publication would reference the same ID.
- **Do not infer from ownership:** separate editorial publications keep
  separate IDs even when they share a parent organization.
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

There is no separate alias or reconciliation list. A display-name change edits
`display_name`; the stable ID does not change. A merger or split changes only
the current feed-to-publisher assignments after maintainer review. Keep old IDs in
the registry and leave historical observations unchanged; do not redirect or
rewrite them.

A historical observation with no publisher ID remains unknown. Today's
feed-to-publisher mapping is not evidence that an earlier run recorded that
identity. Do not fill old observations from the current catalog or count each
unknown feed as a different publisher.

## Validation ownership

TypeScript's `PublisherIdSchema` aliases `SlugSchema`. Catalog validation
refuses duplicate publisher definitions and nonnull feed references to an
undefined publisher. Several feeds may reference one defined publisher.
Legacy configuration without `publishers` reads as an empty registry. Missing
feed IDs and lifecycle values remain unknown; readers do not fill them from the
current catalog. New retirement reasons are open lowercase text, not a closed
vocabulary.

Publisher definitions contain only `id` and `display_name`; lifecycle belongs
to feed entries. Readers check recorded lifecycle fields for consistency, but
curated review establishes whether a new feed or retirement supplied all
required values.

Syntax validation cannot prove that two feeds share a newsroom, that a name
change preserves identity, or that an old reservation was not reused. Catalog
review establishes those facts; implementation must test the creation and
historical-read meanings as well as the scalar spelling.

Maintainer-authored catalog configuration uses reader-native validation of the
fields its readers compute on, under `CLAUDE.md` Guardrail #3. It does not need
a second persisted-payload schema just because it is configuration.
Publisher identity is carried by the Pydantic-owned shared snapshot and the
TypeScript copy, with versioned compatible readers and the named binding tests.
Follow
[the schema contract](schemas.md#what-holds-the-copy-in-step), including
`backend/tests/contracts/test_native_typescript_bindings.py`.
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
classification here. Factual verification and semantic claims of novelty or new
developments are excluded; exact URL newness within a bounded seen window is
allowed and does not establish story novelty. Existing story handling is
unchanged. Day-aware publisher preferences use recorded publisher exposure and
existing numeric priority; no article-quality comparison is made. They remain
soft, not hard caps or a reason to block selection when history is missing.
The existing [source-reliability penalty](../sources/feed-curation.md#inputs-and-independent-evidence)
measures operational delivery, not article quality.

Publisher identity is recorded through the existing planning and audit flow.
The isolated planner uses that recorded ID for the separately approved
[soft exposure preference](../sources/feed-curation.md#publisher-exposure-adjustment).
This does not add mappings or change production Python selection.

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
  of an old ID and change current mappings only after maintainer review of a merger
  or split.
- [ ] Keep missing historical IDs unknown, without current-catalog backfill.
- [ ] Review catalog storage, actual feed mappings, persisted-field compatibility
  and cross-language binding coverage before wiring runtime readers or writers.
- [ ] Keep any `/select-articles` behavior within its separately approved
  contract; this identity contract does not authorize fetch/parse content
  deduplication, qualitative assessment, hard day caps or history blocking.

## Design rationale

Maintainer decision, 2026-10-24 UTC, publisher option A1:
adopt an immutable curated publisher slug and document its creation before
implementation. A human-readable key makes catalog review practical; choosing
it once prevents a name or endpoint edit from changing the counted publisher.
This adopts the existing editorial unit, not its mutable masthead text as the
permanent identifier. Approval covers this contract only, not runtime wiring,
shared persisted fields, feed assignments or the separate API implementation.

Maintainer decision, 2026-10-24 UTC: keep the publisher
registry in `config/sources.json`, beside the feed references it validates.
Use `publishers[]` entries with `id` and `display_name`; each feed has nullable
`publisher_id`. Do not add separate alias or reconciliation lists. Keep all
publisher data in config so adding or changing an entry does not need a
per-publisher code edit. A rename changes the display name; a merger or split
changes current feed assignments after maintainer review; old IDs and historical
observations remain unchanged. The reviewed catalog change and Git history
are enough provenance; do not add an `identity_provenance` field.

Maintainer ruling, 2026-10-24 UTC: AI may help identify
publisher-owned evidence for feed mappings. It must leave a feed unknown when
that evidence does not settle the publication identity.

Maintainer-approved catalog delivery, 2026-10-27 UTC: assign stable IDs only
where official publication material confirms the editorial publication. The
reviewed sources were the [BBC](https://www.bbc.com/aboutthebbc),
[CGTN](https://www.cgtn.com/about-us.html),
[CNA](https://www.channelnewsasia.com/about-us),
[The Conversation Africa](https://theconversation.com/africa/who-we-are),
[The Hindu](https://www.thehindu.com/aboutus/),
[The Hindu BusinessLine](https://www.thehindubusinessline.com/aboutus/),
[Mint](https://www.livemint.com/object/141enehrj3mssnltt8beak/aboutus.html)
and [The Economist](https://www.economistgroup.com/businesses/the-economist).
Section feeds reuse their publication's ID where review confirms one editorial
publication. Separate editorial publications keep separate IDs even when they
share a parent organization. The catalog is the source of truth for exact feed
references; all unreviewed entries stay null, and no historical record is
backfilled.

## See also

- [I Feed](../sources/i-feed.md#what-we-keep) - proposed source-catalog responsibility.
- [Editorial selection](../sources/feed-curation.md) - current isolated planner behavior.
- [Schema ownership](schemas.md) - shared payloads and the planner-only event exception.
- [Feed concept](../../concepts/feed.md) - what a feed contributes.
- [Verification gates](../../how-to/run-the-gates.md) - checks when implementation is approved.
