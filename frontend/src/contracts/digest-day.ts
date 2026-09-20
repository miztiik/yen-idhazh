// Generated from `backend/idhazh/contracts/digest_day.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Why an item did not reach the top band.
 *
 * An identifier, never copy: the sentence a reader sees is owned by the site
 * and can be rewritten without a schema change. A `high` item has no reason,
 * because there is nothing to explain.
 */
export const BAND_REASON = ['unsupported_number', 'not_scored', 'lead_missing', 'hedge_dropped', 'faithfulness'] as const;

export type BandReason = (typeof BAND_REASON)[number];

/** The band, not the number, is what drives behaviour and what a reader sees. */
export const CONFIDENCE_BAND = ['high', 'medium', 'low'] as const;

export type ConfidenceBand = (typeof CONFIDENCE_BAND)[number];

/**
 * The day's item vectors, so a browser only ever embeds a reader's query.
 *
 * Inside the day payload rather than beside it, because the per-page request
 * count is fixed and a sidecar would add one to every page whether or not a
 * reader ever searches.
 *
 * Self-describing on purpose: a reader-side decoder that guesses the width or
 * the dtype produces plausible nonsense instead of an error. Every field here
 * exists so that a mismatch fails loudly.
 *
 * This whole block is optional and strippable. A day with no `embeddings`
 * renders identically; it simply cannot be searched on the device.
 */
export interface DigestEmbeddings {
	model_id: string;

	dimensions: number;

	dtype: 'int8';

	/** item_id -> base64 of the quantised vector, one entry per embedded item. */
	vectors?: Record<string, string>;
}

/** One item as a reader consumes it. The link is a first-class element, not a footnote. */
export interface DigestItem {
	item_id: string;

	/** The vertical the carrying feed declares. `item_id` is addressed from it, so it is the story's address and never a reading of the story. */
	vertical: string;

	/** Where the day publishes this story, which is the topic a reader finds it under. Null says nothing relabelled it and a page falls back to `vertical`; null is never read as a desk of its own. */
	desk?: string | null;

	/** The one other desk this story has a claim to, and the desk the day sends it to when the one it is on is over its ceiling. It never equals the desk the day filed the story under, so a story names at most two desks. Null says nothing has named a second one, and is never read as 'no second desk'. No page draws it yet: `count` and `desk_count` both still answer for the desk a story is filed under. */
	secondary_desk?: string | null;

	title: string;

	source_url: string;

	source_id: string;

	source_name: string;

	/** Who is speaking. A vendor's own copy must not look like a reporter's. */
	source_kind?: SourceKind;

	published_at?: string | null;

	/** Which clock published_at came from - the feed's, or our first sight of the address. Null on a day published before this existed, and that reads as unknown rather than as a claim about either clock. */
	time_source?: TimeSource | null;

	summary: string;

	key_points: string[];

	lenses?: string[];

	events?: string[];

	entities?: string[];

	band: ConfidenceBand;

	/** Why the item is not in the top band. An identifier the site turns into a sentence; null on a `high` item and on a day published before this existed. */
	band_reason?: BandReason | null;

	/** Declared feed form, so a reader can see when an item is an abstract. */
	source_form?: SourceForm;

	/** Our sentence explaining a source limitation, never a badge. */
	reader_note?: string | null;

	/** The reader is told before they find out by clicking through. */
	truncated?: boolean;

	visual?: DigestVisual | null;

	/** How many feeds carried this one address today. Syndication of a single story, never 'also covered by N sources' - two outlets writing their own piece produce two addresses and both read 1. Null where the run did not record it, which is not the same as 1. */
	carried_by?: number | null;

	/** The story names a watchlist entity. Null where the run did not record it. */
	watchlist_hit?: boolean | null;

	/** A salience feed voted for it. A vote, never a discovery. Null where the run did not record it, which is not the same as false. */
	on_front_page?: boolean | null;

	/** What the planning step scored this story at, against the other stories of its own vertical. Comparable across the day because every vertical uses one scale. Null where the run did not record it, which is not the same as 0. */
	rank_score?: number | null;

	/** How many OTHER sources carried the same story today, counted over the day's own items. Not `carried_by`, which counts syndication of one address and reads 1 when two outlets write their own piece. 0 says only one of our sources carried it. Null says the pass could not tell - the day carries no vectors, or this item has none - and is never read as 0. */
	also_covered_by?: number | null;

	/** The item the default view keeps for this story. Null on the item that is kept and on an item nothing grouped with. Nothing is unpublished: a collapsed item keeps its place in this list, its anchor and its archive entry. **This day's own items only** - a story that also ran on an earlier day is in `also_ran_earlier`, because folding today's page onto a card that is not on it would leave a reader with nothing to open. */
	same_story_as?: string | null;

	/** The outlets that ran this same story on an earlier published day, strongest first. Empty on every payload written before 2026-09-16 and on every story nothing earlier matched, and the two read the same: no earlier telling was found. It is ADDITIVE and folds nothing - today's story keeps its card and its place, and each entry becomes one more name in the card's `Also covered by` stack, linking to that day's page. Recorded on the NEWER story only, so a published day is never rewritten. */
	also_ran_earlier?: EarlierStory[];

	/** A global fact, true for every reader, asserted without any storage. */
	introduced_by_run: number;

	/** Reserved. Null in every payload ever written, because no run can revise an item: `rank.plan_vertical` drops a candidate already in the published ledger under `state/published/`, `cli` supplies that set, and `assemble.build_day` drops an item the day already holds. If a run ever does revise, the rule it must keep is that the item says so. */
	updated_at?: string | null;

	/** Reserved, and null everywhere for the same reason as `updated_at`. It would name the run that wrote the words this item carries, so the join to the run manifest answers with the right model. Until then `assemble.run_that_wrote` answers with `introduced_by_run`. */
	updated_by_run?: number | null;
}

/**
 * One of the day's leading stories, and the one sentence saying why it leads.
 *
 * The story itself stays in `items` in the published order, so the block adds
 * a way in and removes nothing. Nothing here carries a position: a number
 * beside a story implies a score we would then owe the reader an explanation
 * for.
 */
export interface DigestLead {
	item_id: string;

	/** One sentence a reader can check against the story, built from our own published title and our own closed registry and never from fetched text (Guardrail #11). A lead that cannot say something true is not a lead. */
	reason: string;
}

/** A run of this date, as the page footer and the new-arrivals block need it. */
export interface DigestRunRef {
	n: number;

	at: string;

	items_added: number;
}

/**
 * One topic of the day, and why it ran what it ran.
 *
 * **It carries two counts and they answer two questions.** `count` is every
 * story whose carrying feed declares this vertical. `desk_count` is every
 * story the day publishes under this name, which is what a reader sees. They
 * are equal on every day nothing relabelled, and a page that wants the number
 * on the screen reads `desk_count` and falls back to `count`.
 *
 * Both include a story the duplicate pass grouped behind another - nothing is
 * unpublished by that pass, so the numbers are the payload's own and not what
 * the default view happens to draw.
 *
 * The three shortfall fields are vertical facts, because collection is per
 * feed and a feed declares a vertical. Each is the day's strongest reading:
 * the largest any run of the day recorded. A later run has already taken what
 * an earlier one published, so it sees a smaller pool of the same stories -
 * summing the runs would count one back-catalogue story once per run.
 *
 * All three are null together on a day published before they existed, and a
 * null is unknown rather than a zero, which would claim the feeds offered this
 * vertical nothing.
 */
export interface DigestVerticalRef {
	id: string;

	display_name: string;

	/** Stories whose carrying feed declares this vertical. It is not what the page draws where a story was relabelled - `desk_count` is - and it keeps this meaning because 22 frozen published days already carry it. */
	count: number;

	/** Stories this day publishes under this name, which is the number a reader sees. Equal to `count` on a day nothing relabelled. Null on a day published before this field existed, where a page falls back to `count`. */
	desk_count?: number | null;

	/** Distinct addresses the feeds offered this vertical today, less what the day had already published or already failed on. It is not an upper bound on `count`: each run counts its own pool and the day's stories accumulate across runs. */
	considered?: number | null;

	/** Of those, how many were past collect.max_age_hours. A vertical fed by a back catalogue thins for this reason and no other, and a thin topic that cannot say why reads as a broken run. */
	too_old?: number | null;

	/** Some run today found fewer live feeds than this vertical's floor, so that run planned nothing for it. Published for the operator surfaces; the reading page never draws a sentence from it, because how many of our feeds answered is a fact about our pipeline rather than about a story. */
	below_feed_floor?: boolean | null;
}

/**
 * Where a story's chart data is, and never the chart data itself.
 *
 * One pointer and no chart data, ever. The day payload is the record that a
 * day happened and is never deleted, so anything held inside it could not age
 * out and `retention.image_months` would have nothing to act on - which is why
 * the marks live in their own file and this says where (owner, 2026-09-13).
 *
 * **`path` retired on 2026-09-13 and the frozen days still carry it.** It
 * named the committed drawing, the drawing is deleted, and the reader's browser
 * draws from `data_path`. `Model` forbids a key it does not declare, so the 24
 * days written before this are read through a named pop rather than by widening
 * the model (`CLAUDE.md` section 11).
 */
export interface DigestVisual {
	kind: VisualKind;

	state: VisualState;

	/** Where this visual's data landed, relative to frontend/public/, as digest/<Y>/<M>/<D>/<item_id>.json beside the day payload. Null on a day published before the file existed and on a visual whose data could not be written - absent reads as no data carried, never as an empty chart. */
	data_path?: string | null;

	alt?: string | null;
}

/**
 * One outlet that ran this same story on an earlier published day.
 *
 * It is a way in and never a fold. The card prints the masthead as one more
 * name in its `Also covered by` stack, and the link goes to our page for that
 * day - our summary of that telling, and its own way out to the original.
 *
 * Its three fields are what a pill needs and nothing else. The masthead is
 * carried rather than looked up because the projector that writes a day's file
 * can only see that day, so a name it would have to fetch from another day is
 * a name it would silently drop.
 */
export interface EarlierStory {
	/** The published day that holds it, always before this one. */
	date: string;

	/** That day's story, which still has its own address. */
	item_id: string;

	/** The masthead, as the card prints it. */
	source_name: string;
}

export const SOURCE_FORM = ['article', 'abstract'] as const;

export type SourceForm = (typeof SOURCE_FORM)[number];

/**
 * What kind of speaker this is - the thing a reader uses to decide belief.
 *
 * "A company said its product is faster" and "a reporter measured it" are not
 * the same claim, and without this they arrive looking identical. The
 * dangerous case is `announcement`: forwarding a vendor's own copy without
 * knowing it was the vendor is how a reader ends up carrying an ad.
 */
export const SOURCE_KIND = ['reporting', 'announcement', 'research', 'analysis', 'government', 'community'] as const;

export type SourceKind = (typeof SOURCE_KIND)[number];

/**
 * Which clock the time on an item came from.
 *
 * `rank.appeared_at` prefers the feed's own date and falls back to when we
 * first saw the address. Both answers used to land in one field, so nothing
 * downstream could tell them apart - and the fallback is the one a reader
 * would want flagged, because it is our clock and not the publisher's.
 */
export const TIME_SOURCE = ['feed', 'first_seen', 'unknown'] as const;

export type TimeSource = (typeof TIME_SOURCE)[number];

export const VISUAL_KIND = ['chart', 'none'] as const;

export type VisualKind = (typeof VISUAL_KIND)[number];

/**
 * What became of the visual. "Could not make it" and "made it then threw it
 * away" are different facts, so they never share a member.
 */
export const VISUAL_STATE = ['absent', 'rendered', 'render_failed'] as const;

export type VisualState = (typeof VISUAL_STATE)[number];

/** `frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json`. */
export interface DigestDay {
	version?: string;

	date: string;

	generated_at: string;

	/** A run with failures publishes, and says it was partial. */
	partial: boolean;

	items_planned: number;

	items_failed: number;

	/** Stated to the reader before anything is deleted. -1 means nothing is deleted. */
	retention_window_months?: number;

	runs: DigestRunRef[];

	verticals: DigestVerticalRef[];

	items: DigestItem[];

	/** The day's leading stories, strongest first, chosen across the whole day rather than off the head of the published order. Empty is the normal state and it means the block does not render: a day with too few stories worth leading goes straight to the stream rather than padding. Every entry names an item this same day holds. */
	leads?: DigestLead[];

	embeddings?: DigestEmbeddings | null;
}
