// Generated from `backend/idhazh/contracts/search_index.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One published item, as browsing and searching need it.
 *
 * No summary, no source, no band. Measured 2026-08-26 over 2,237 committed
 * items: adding the summary takes an entry from 50.03 gzipped bytes to 317.52,
 * which is 6.35 times, and a 30-day month at the observed rate from 518 KB to
 * 3.21 MB. It also charges every browsing visitor the full text of every item
 * in the month. A result renders by fetching the day payload it names - at
 * most one fetch per distinct day on screen, and days already open are reused.
 */
export interface SearchIndexEntry {
	date: string;

	item_id: string;

	title: string;

	vertical: string;

	/** Byte offset of this item's vector in the sibling `.bin`, or null when the item has none. An offset rather than a position, so a reader slices the file directly instead of counting how many entries above it were skipped. */
	vector?: number | null;
}

/** `frontend/public/assist/index/<YYYY-MM>.json`. */
export interface SearchIndex {
	version?: string;

	month: string;

	/** The encoder that wrote every vector in the sibling file. One index, one encoder: two encoders in one space score as plausible nonsense rather than failing. Since 2026-09-10 the browser may load its encoder from a second origin when this site cannot serve it, so this is a comparison between two things that can differ: a shard the reader's encoder does not name keeps its items browsable and drops them from the search scope. */
	model_id: string;

	/** Components a vector. At int8 this is also its length in bytes. */
	dimensions: number;

	dtype: 'int8';

	/** Multiply a stored byte by this to get a component. Stated rather than assumed, so a later encoder can quantise against the range unit vectors actually reach without a breaking change to this file. */
	scale: number;

	entries: SearchIndexEntry[];
}
