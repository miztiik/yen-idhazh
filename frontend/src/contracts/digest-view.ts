// Generated from `backend/idhazh/contracts/digest_view.py` by `python -m idhazh.contracts.export`.
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
 * One other newsroom that ran the same story, and the way in to its piece.
 *
 * The link is to OUR page for that piece - our summary of it, and its own
 * `Read the original` - never straight out to the publisher. A reader who
 * wanted the publisher's version is one more click away and a reader who
 * wanted ours has not lost it.
 */
export interface DigestCoverage {
	/** The masthead, as the card prints it. */
	source_name: string;

	/** That newsroom's own story, which still has its address. */
	item_id: string;
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
 * One item, narrowed to what a page renders from it.
 *
 * Every field here has a named renderer. The list is not "the published item
 * minus the big bits" - it is traced along the render path, and a field
 * without a reader does not earn the wire.
 */
export interface DigestViewItem {
	item_id: string;

	vertical: string;

	/** Where the day publishes this story, which is the topic a reader finds it under. Null says nothing relabelled it and the page falls back to `vertical`. Null is never read as a desk of its own. */
	desk?: string | null;

	title: string;

	summary: string;

	/** Our sentence explaining a source limitation, never a badge. */
	reader_note?: string | null;

	band: ConfidenceBand;

	/** Why the item is not in the top band. Null on a `high` item and on a day published before this existed - 14 of 3,733 committed items on 2026-08-31. */
	band_reason?: BandReason | null;

	/** The reader is told before they find out by clicking through. */
	truncated?: boolean;

	visual?: DigestViewVisual | null;

	source_name: string;

	source_id: string;

	/** Who is speaking. A vendor's own copy must not look like a reporter's. */
	source_kind?: SourceKind;

	source_url: string;

	published_at?: string | null;

	/** Which clock `published_at` came from. Null reads as unknown: a page that prints a time without naming its clock cannot say which of the two it has. */
	time_source?: TimeSource | null;

	/** How many feeds carried this one address. Null is unknown, never 1. */
	carried_by?: number | null;

	/** The story names a watchlist entity. Null is unknown, never false. */
	watchlist_hit?: boolean | null;

	/** A salience feed voted for it. Null is unknown, never false. */
	on_front_page?: boolean | null;

	/** What the planning step scored the story at. Null is unknown, never 0. */
	rank_score?: number | null;

	/** How many other OUTLETS carried the same story today - a masthead, not a feed, so an outlet with four feeds counts once. It is the count and `covered_by` is the names, and the two answer different questions: this one is whole where the names are capped, so the card prints the difference as a remainder. On a card with no stack, 1 or more prints 'Also covered by N other sources today.' 0 and null both print nothing: null means the day recorded no answer, and 0 stopped printing 'Only one of our sources carried this.' on 2026-09-14 because the pass finds far too little of the day's duplication for that sentence to be true. See docs/architecture/publishing/layout.md. */
	also_covered_by?: number | null;

	/** A global fact, true for every reader, asserted without any storage. */
	introduced_by_run: number;

	lenses?: string[];

	key_points: string[];

	/** The item the page draws this story on, null on the one that is drawn. It was on the committed item and off the wire until 2026-09-16, because no page folded a group and a field with no renderer does not earn the wire. The page folds now: a story naming another is not drawn as its own card. It is not removed - it keeps its address, its archive entry and its month search entry, and the anchor's card links to it by name. */
	same_story_as?: string | null;

	/** Which other newsrooms ran this story, by name, strongest first. Empty on a story the day grouped with nothing, and empty on a day published before the pass existed - both mean the page draws no publisher stack. It is capped, so it is never the whole of the count: `also_covered_by` is how many other outlets there are, and the card prints the difference as a remainder. */
	covered_by?: DigestCoverage[];

	/** Which newsrooms ran this same story on an EARLIER published day. Copied straight off the committed item rather than derived here, because this projection can only see one day and a name it would have to fetch from another day is a name it would silently drop. Each entry is one more name in the card's stack, pointing at that day's page rather than at an anchor on this one. It folds nothing: the story keeps its own card. */
	also_ran_earlier?: EarlierStory[];
}

/**
 * The chart, as the browser that draws it needs it.
 *
 * `kind` is not here. It is read at build time off the committed tree for the
 * console's chart count, and a browser that has already been handed the marks
 * has no use for it.
 *
 * **`data_path` is the whole of what a fetched story gets**, and it replaced
 * `path` on 2026-09-13. The reader's browser draws the chart from that file, so
 * a projection that dropped the key would leave every story past the document's
 * seed unable to ask for its own picture - which is every story on a dated page.
 */
export interface DigestViewVisual {
	state: VisualState;

	/** Where this visual's marks are, relative to frontend/public/. Null on a day published before the file existed - absent and null are the same fact, and both mean the story simply has no chart. */
	data_path?: string | null;

	/** What the figure is labelled with. On a page that never runs a script it is the whole of what a reader receives for this visual. */
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

/**
 * What became of the visual. "Could not make it" and "made it then threw it
 * away" are different facts, so they never share a member.
 */
export const VISUAL_STATE = ['absent', 'rendered', 'render_failed'] as const;

export type VisualState = (typeof VISUAL_STATE)[number];

/** `<base>/digest/<YYYY>/<MM>/<DD>/digest.json`, as a browser fetches it. */
export interface DigestView {
	version?: string;

	date?: string | null;

	/** What a republish moves and nothing else does, so a browser holding this day can tell a re-fetch that changed nothing from one that did. */
	generated_at?: string | null;

	/** Null is unknown, never false: false says the run lost nothing. */
	partial?: boolean | null;

	items_planned?: number | null;

	/** Null is unknown, never 0: 0 says nothing failed. */
	items_failed?: number | null;

	/** Stated to the reader before anything is deleted. -1 is the day saying nothing is deleted; null is the payload not saying, and a page prints neither sentence for it. */
	retention_window_months?: number | null;

	runs?: DigestRunRef[] | null;

	/** Null is unknown, never an empty list: empty says the day had no desk. */
	verticals?: DigestVerticalRef[] | null;

	/** Null is the payload not saying; an empty list is the day saying it has no leading block, which is its ordinary state. Both draw nothing. */
	leads?: DigestLead[] | null;

	items: DigestViewItem[];
}
