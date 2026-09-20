// Generated from `backend/idhazh/contracts/reference_dataset.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One line of the supplied URL list, as one element of `manifest.json`.
 *
 * `source_line` is here because the list is the deliverable's input and a
 * person reading a refusal needs the line to look at. Two lines carrying
 * equivalent addresses keep both rows and share one `url_key`, so the count of
 * rows and the count of identities are different numbers on purpose.
 */
export interface ReferenceManifestRow {
	version?: string;

	/** The 1-based line of the input file this row came from. */
	source_line: number;

	/** The address as supplied, kept so a person can open it. */
	source_url: string;

	/** What `url_key` is derived from, never trusted from a payload. */
	canonical_url: string;

	/** sha256 of the canonical URL, recomputed on read. */
	url_key: string;

	/** The registered domain, which is the unit the frozen set separates on. */
	source_domain: string;

	/** The host, lower case. */
	host: string;

	/** The outlet key a balanced sample groups on, frozen at import. Derived from the host rather than the registered domain, and lengthened only where two hosts would otherwise share it. */
	publisher: string;

	/** Which feed in `config/sources.json` this host is, when exactly one is. Null is 'we do not know', and a host shared by feeds in two verticals stays null. */
	source_id?: string | null;

	/** Source context from the feed's declaration, never a reading of the article. Null rather than a word invented for the taxonomy. */
	vertical?: string | null;
}
