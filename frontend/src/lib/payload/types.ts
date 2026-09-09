/** Shapes the published payload carries, mirroring `schemas/digest-day.schema.json`. */

export type ConfidenceBand = 'high' | 'medium' | 'low';
export type SourceForm = 'article' | 'abstract';

export type BandReason =
	| 'unsupported_number'
	| 'not_scored'
	| 'lead_missing'
	| 'hedge_dropped'
	| 'faithfulness';

export type SourceKind =
	| 'reporting'
	| 'announcement'
	| 'research'
	| 'analysis'
	| 'government'
	| 'community';

/** Which clock an item's `published_at` came from. `unknown` means neither the
 * feed nor our own first sight gave a time, so the item carries none. */
export type TimeSource = 'feed' | 'first_seen' | 'unknown';

export interface DigestVisual {
	kind: string;
	state: string;
	path: string | null;
	alt: string | null;
}

/** A visual as the build hands it to a component: the committed fields, plus
 * the drawing itself for the stories a prerendered document carries.
 *
 * `markup` is not in `schemas/digest-day.schema.json` and is not meant to be.
 * `dayShell()` reads the file off disk for the seed alone and attaches it here,
 * so the field exists between that loader and `ItemVisual` and nowhere else. It
 * is separate from `DigestVisual` because that type mirrors the committed
 * payload, and it is out of the served projection because a fetched day would
 * then carry every seed item's drawing a second time - `project.ts` keeps three
 * named fields of a visual and drops this one without being told to.
 *
 * The drawing has to be IN the document to be themed at all. An SVG inside an
 * `img` is a separate document: it reads none of the page's custom properties,
 * so a chart drawn in black axis type stayed black on a near-black card. */
export interface SeededVisual extends DigestVisual {
	markup?: string | null;
}

export interface DigestItem {
	item_id: string;
	vertical: string;
	title: string;
	source_url: string;
	source_id: string;
	source_name: string;
	source_kind: SourceKind;
	published_at: string | null;
	summary: string;
	key_points: string[];
	lenses: string[];
	events: string[];
	entities: string[];
	band: ConfidenceBand;
	band_reason: BandReason | null;
	source_form: SourceForm;
	reader_note: string | null;
	truncated: boolean;
	visual: DigestVisual | null;
	introduced_by_run: number;
	updated_at: string | null;
	// Optional because every day published before 2026-08-25 omits the key entirely.
	updated_by_run?: number | null;
	// The five below are optional for the same reason: every day published before
	// 2026-08-31 omits them. Absent and null both mean unknown. Never read an
	// absent `carried_by` as 0 or an absent `on_front_page` as false - that turns
	// a fact the run never recorded into a claim about the story.
	carried_by?: number | null;
	watchlist_hit?: boolean | null;
	on_front_page?: boolean | null;
	rank_score?: number | null;
	time_source?: TimeSource | null;
	// The duplicate pass, absent on every day published before 2026-09-01. 0 means
	// only one of our sources carried the story; null means the pass could not tell,
	// and prints nothing rather than a claim.
	also_covered_by?: number | null;
	/** The item the default view draws for this story. Null on the one that is drawn.
	 * A collapsed item is still in the payload, still has its anchor and still has
	 * its archive entry - it is not drawn, not removed. */
	same_story_as?: string | null;
}

export interface DigestRunRef {
	n: number;
	at: string;
	items_added: number;
}

export interface DigestVerticalRef {
	id: string;
	display_name: string;
	/** Every story the desk published, a duplicate the day grouped behind another
	 * included - that pass unpublishes nothing, so this is the payload's own count
	 * and not what the default view draws. */
	count: number;
	// Why the desk ran what it ran. Absent on every day published before
	// 2026-09-02, and the three are absent or present together. Absent means
	// unknown, never 0, which would claim the sources offered the desk nothing.
	/** Distinct addresses the sources offered this desk, less what the day had
	 * already published or already failed on. Not an upper bound on `count`: each
	 * run counts its own pool and the stories accumulate across runs. */
	considered?: number | null;
	/** Of those, how many were older than the pipeline's age gate. */
	too_old?: number | null;
	/** Some run today found fewer live sources than this desk's floor. Published
	 * for the operator surfaces; no reading page draws a sentence from it, because
	 * how many of our feeds answered is a fact about our pipeline. */
	below_feed_floor?: boolean | null;
}

/** One of the day's leading stories, and the sentence saying why it leads.
 *
 * The story itself is in `items` like every other one, so the block adds a way
 * in and removes nothing. There is no position field: a number beside a story
 * implies a score we would then owe the reader an explanation for. */
export interface DigestLead {
	item_id: string;
	reason: string;
}

export interface DigestEmbeddings {
	model_id: string;
	dimensions: number;
	dtype: 'int8';
	vectors: Record<string, string>;
}

export interface DigestDay {
	version: string;
	date: string;
	generated_at: string;
	partial: boolean;
	items_planned: number;
	items_failed: number;
	retention_window_months: number;
	runs: DigestRunRef[];
	verticals: DigestVerticalRef[];
	items: DigestItem[];
	/** Optional because every day published before 2026-09-01 omits the key.
	 * Absent and empty both mean the block does not render, which is the
	 * ordinary state of a day with too few stories worth leading. */
	leads?: DigestLead[];
	embeddings: DigestEmbeddings | null;
}

/** The rendered chart as a served item carries it, mirroring
 * `schemas/digest-view.schema.json`. `kind` is a build-time field of the
 * committed tree and never reaches a browser. */
export type DigestViewVisual = Pick<DigestVisual, 'state' | 'path' | 'alt'>;

/** One item as the served day carries it - twenty-three of the published item's
 * fields, every one with a renderer.
 *
 * Derived from `DigestItem` rather than restated, so a field cannot mean one
 * thing in the committed payload and another on the wire. The allow-list that
 * decides which names are here lives in `project.ts`, and the shape is a
 * contract: `schemas/digest-view.schema.json`, from
 * `backend/idhazh/contracts/digest_view.py`.
 *
 * `same_story_as` is on `DigestItem` and not here: no page draws a group as one
 * item yet.
 *
 * Every optional field is optional for the same reason it is on `DigestItem`:
 * a day published before it existed has no value for it, and **absent and null
 * both mean unknown**. Never read an absent `carried_by` as 0 or an absent
 * `on_front_page` as false. */
export type DigestViewItem = Pick<
	DigestItem,
	| 'item_id'
	| 'vertical'
	| 'title'
	| 'summary'
	| 'reader_note'
	| 'band'
	| 'band_reason'
	| 'truncated'
	| 'source_name'
	| 'source_id'
	| 'source_kind'
	| 'source_url'
	| 'published_at'
	| 'time_source'
	| 'carried_by'
	| 'watchlist_hit'
	| 'on_front_page'
	| 'rank_score'
	| 'also_covered_by'
	| 'introduced_by_run'
	| 'lenses'
	| 'key_points'
> & { visual: DigestViewVisual | null };

/** `<base>/digest/<YYYY>/<MM>/<DD>/digest.json` - the day a browser fetches.
 *
 * `version` is the contract's own stamp, not the committed day's. A shell that
 * does not recognise it still renders: an unknown key is ignored, and a known
 * key that is absent reads as unknown.
 *
 * **Every day-level fact is optional, and that is the read-side rule rather
 * than a softness.** A service worker keeps a day, so a shell built after
 * 2026-09-09 can be handed a payload written before it, which carries none of
 * them. Absent is unknown: never read an absent `partial` as false, an absent
 * `items_failed` as 0, or an absent `verticals` as a day with no desk. */
export interface DigestView {
	version: string;
	date?: string | null;
	generated_at?: string | null;
	partial?: boolean | null;
	items_planned?: number | null;
	items_failed?: number | null;
	/** `-1` is the day saying nothing is deleted. Null is the payload not
	 * saying, and the footer prints neither sentence for it. */
	retention_window_months?: number | null;
	runs?: DigestRunRef[] | null;
	verticals?: DigestVerticalRef[] | null;
	/** Null is the payload not saying; empty is the day saying it has no leading
	 * block, which is its ordinary state. Both draw nothing. */
	leads?: DigestLead[] | null;
	items: DigestViewItem[];
}

/** What a page needs to draw a day, from whichever carrier brought it.
 *
 * `/` reads a committed `DigestDay` off disk at build time; a dated URL fetches
 * a `DigestView`. The two agree on every name below, and this is the shape the
 * reading components take so neither carrier has to be converted into the
 * other.
 *
 * **`date` is required and the rest of the facts are not.** A page always knows
 * its own date - it is in the address - so a component may lean on it. Every
 * other fact can be absent, because a service worker keeps day payloads and a
 * shell can be handed one written before those names existed. Absent is
 * unknown: never fill one in. */
export interface DayForPage {
	date: string;
	generated_at?: string | null;
	partial?: boolean | null;
	items_planned?: number | null;
	items_failed?: number | null;
	retention_window_months?: number | null;
	runs?: DigestRunRef[] | null;
	verticals?: DigestVerticalRef[] | null;
	leads?: DigestLead[] | null;
	items: DigestItem[];
}

/** One published story as the archive's list reads it, mirroring
 * `schemas/search-index.schema.json`.
 *
 * No summary, no source and no band: the entry is what a list needs to name a
 * story, and everything else is one click away on the day page it links to.
 */
export interface SearchIndexEntry {
	date: string;
	item_id: string;
	title: string;
	vertical: string;
	/** Byte offset into the sibling vector file, or null when the story has none.
	 * Nothing reads it yet - the archive list browses, it does not search. */
	vector: number | null;
}

/** `frontend/public/assist/index/<YYYY-MM>.json` - one month of published
 * stories. It is served from `index/<YYYY-MM>.json`, outside the model
 * directory, because browsing must survive that directory being deleted. */
export interface SearchIndex {
	version: string;
	month: string;
	model_id: string;
	dimensions: number;
	dtype: 'int8';
	scale: number;
	entries: SearchIndexEntry[];
}
