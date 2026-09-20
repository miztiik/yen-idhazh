// Generated from `backend/idhazh/contracts/seen.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One row of `state/published/YYYY/MM/DD.csv`, appended when an item reaches a
 * committed digest.
 *
 * It carries no address. `item_id` and `published_on` join to that day's
 * committed payload, where the address is already published as `source_url` -
 * see `docs/architecture/sources/freshness.md` for the worked recovery.
 */
export interface PublishedRow {
	version?: string;

	url_key: string;

	/** The digest date, not the article's own date. */
	published_on: string;

	item_id: string;
}
