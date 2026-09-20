// Generated from `backend/idhazh/contracts/article.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

export const ARTICLE_STATUS = ['ok', 'fetch_failed', 'extract_failed', 'robots_denied'] as const;

export type ArticleStatus = (typeof ARTICLE_STATUS)[number];

/**
 * Stable failure vocabulary for item-health rows.
 *
 * **Membership is one member per knob an operator turns, not one per gate.**
 * Four HTTP members answer to one fetch, because the fix for a 404 is not the
 * fix for a rate limit. `output_truncated` and `labels_truncated` are the two
 * output budgets, derived from two different grammars, for the same reason.
 */
export const FAILURE_CODE = ['not_attempted', 'robots_denied', 'robots_unreachable', 'blocked_address', 'http_client_error', 'http_rate_limited', 'http_server_error', 'network_error', 'no_text', 'no_title', 'too_short', 'not_prose', 'boilerplate', 'paywalled', 'unsupported_form', 'model_unreachable', 'model_refused', 'model_timed_out', 'context_exceeded', 'output_truncated', 'labels_truncated', 'bad_shape', 'length_out_of_range', 'copied_source', 'leaked_address', 'shard_out_of_time', 'unknown'] as const;

export type FailureCode = (typeof FAILURE_CODE)[number];

export const SOURCE_FORM = ['article', 'abstract'] as const;

export type SourceForm = (typeof SOURCE_FORM)[number];

/** The tier IS the ranking weight (docs/architecture/sources/discovery.md). */
export const SOURCE_TIER = [1, 2, 3] as const;

export type SourceTier = (typeof SOURCE_TIER)[number];

/**
 * Which stranger's string the published headline came from.
 *
 * Both are untrusted, and they are not trusted equally. The feed is a source
 * somebody chose and the page is whoever answered the address, so the feed is
 * read first and the page only when the feed said nothing - order is a
 * control, and a page can never displace a headline we were given. The page
 * path is then held to a tighter bound than the feed path and refused over it
 * rather than cut. So this field records the outcome of a trust decision
 * rather than provenance alone: `page` says the more attacker-controlled of
 * the two strings is the one on the page.
 */
export const TITLE_SOURCE = ['feed', 'page'] as const;

export type TitleSource = (typeof TITLE_SOURCE)[number];

/** The Extract stage's output payload, one per item. */
export interface Article {
	version?: string;

	item_id: string;

	/** sha256 of canonical_url. Identity for dedupe and skip - a field, never a path. */
	url_key: string;

	/** The address as discovered. */
	source_url: string;

	/** The address after canonicalisation. url_key derives from it. */
	canonical_url: string;

	/** The feed that carried it. */
	source_id: string;

	tier: SourceTier;

	/** Declared by the feed config. Never inferred from extracted text. */
	source_form?: SourceForm;

	/** The vertical the carrying feed declares about itself, copied from the source config and never read out of the article. `item_id` is addressed from it, so it may not be repointed - see `_identity_is_rebuilt_not_trusted` below. */
	vertical: string;

	/** Where the digest publishes this story, read off the whole article rather than off the feed that carried it. Null is nothing having said, and the digest falls back to `vertical`; a null is never read as a desk. */
	desk?: string | null;

	/** The one other desk this article has a claim to, read off the same article `desk` is. It is where the day sends the story when the desk it is on is over its ceiling. One, never a list: a story on four desks is a story on no desk. Null is nothing having said, and the day falls back to `vertical`; a null is never read as a second desk and never as 'none'. */
	secondary_desk?: string | null;

	lenses?: string[];

	events?: string[];

	entities?: string[];

	/** Independent sources that carried this story today. */
	carried_by?: number;

	rank_score: number;

	title?: string | null;

	/** Where `title` came from: the feed entry, or the fetched page's own metadata when the feed carried none. Both are untrusted and they are not trusted equally - the feed is read first because it is the less attacker-controlled string, and the page path is held to a tighter bound and refused over it rather than cut. So this is the outcome of a trust decision, not provenance alone. Null on a failed payload, which publishes no headline, and on an ok payload written before the field existed. */
	title_source?: TitleSource | null;

	/** Sanitized text. Never republished. */
	text?: string | null;

	/** Words in `text`, after the cap. */
	word_count?: number;

	/** Words in the extracted body before `extract.truncation_cap_tokens` cut it. A count, never the text: the pre-cap body is not kept and is not ours to republish. None on a payload written before the field existed. */
	source_word_count?: number | null;

	token_count?: number;

	/** True when the source is short enough that summarize uses the brief tier. */
	brief?: boolean;

	truncated?: boolean;

	truncated_at_tokens?: number | null;

	published_at?: string | null;

	fetched_at: string;

	status: ArticleStatus;

	/** Typed extract failure, or a recorded extract signal on an ok article. */
	failure_code?: FailureCode | null;

	failure_detail?: string | null;

	extractor_version: string;

	sanitizer_version: string;
}
