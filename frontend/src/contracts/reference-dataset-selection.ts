// Generated from `backend/idhazh/contracts/reference_dataset.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One chosen article, as one element of `urls.json`.
 *
 * It holds the identity and the text digest, never the text. The sample points
 * at one named extraction through its metadata, so an article edited after the
 * sample was drawn stops matching instead of quietly becoming what was chosen.
 */
export interface ReferenceSelectionRow {
	version?: string;

	/** sha256 of the canonical URL, recomputed on read. */
	url_key: string;

	/** The address as supplied. */
	source_url: string;

	/** What `url_key` is derived from. */
	canonical_url: string;

	/** The registered domain. */
	source_domain: string;

	/** The host, lower case. */
	host: string;

	/** The frozen outlet key this row was allocated under. */
	publisher: string;

	/** Source context, or null. */
	vertical?: string | null;

	/** sha256 of the chosen article's text, as the named extraction holds it. */
	article_sha256: string;
}
