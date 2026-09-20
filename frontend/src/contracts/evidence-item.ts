// Generated from `backend/idhazh/contracts/evidence.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One scored item's premise and summary, addressed by the measurement it belongs to. */
export interface EvidenceItem {
	version?: string;

	url_key: string;

	output_digest: string;

	scorer_version: string;

	date: string;

	run_id: string;

	item_id: string;

	source_url: string;

	title?: string | null;

	/** sha256 of `premise`, the same value the eval row carries. Recomputed on read, so an edited premise fails to load rather than reaching a labeller. */
	source_digest: string;

	/** The article after extraction, sanitizing and the truncation cap - the text the scorer read, byte for byte. Untrusted (Guardrail #11): it prints as inert terminal text and never becomes a prompt, a path or a URL. */
	premise: string;

	/** The summary the scorer scored against `premise`. The published item also carries key points; they are left out because the scorer never read them, and showing a labeller words the number does not cover would put the two of them back on different questions. */
	summary: string;
}
