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
