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
	embeddings: DigestEmbeddings | null;
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
