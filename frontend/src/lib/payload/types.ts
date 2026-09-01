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
	count: number;
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
 * key that is absent reads as unknown. */
export interface DigestView {
	version: string;
	items: DigestViewItem[];
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
