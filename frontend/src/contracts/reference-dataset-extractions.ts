// Generated from `backend/idhazh/contracts/reference_dataset.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

export const ARTICLE_STATUS = ['ok', 'fetch_failed', 'extract_failed', 'robots_denied'] as const;

export type ArticleStatus = (typeof ARTICLE_STATUS)[number];

/**
 * Why one URL produced no article text.
 *
 * `ArticleStatus` says which stage ended it; this says what happened there. A
 * truncated body is its own member rather than a success with less text,
 * because a download stopped by its byte limit looks exactly like a short
 * article once the reason is thrown away.
 */
export const REFERENCE_FAILURE_CODE = ['robots_denied', 'robots_unreachable', 'blocked_address', 'fetch_permanent', 'fetch_transient', 'body_truncated', 'paywalled', 'empty_text'] as const;

export type ReferenceFailureCode = (typeof REFERENCE_FAILURE_CODE)[number];

/**
 * Why one article is not worth putting in front of a classifier.
 *
 * Every member here was measured on a real extraction before it was written
 * down. Two candidates were tried and deleted instead: a global unique-word
 * ratio, which only ever flagged long essays for being long, and an ending
 * without a full stop, which called 198 complete articles truncated.
 */
export const REFERENCE_QUALITY_FLAG = ['short', 'no_sentence', 'fragmented', 'near_duplicate', 'video_or_podcast', 'promotional', 'over_cleaned'] as const;

export type ReferenceQualityFlag = (typeof REFERENCE_QUALITY_FLAG)[number];

/**
 * What one manifest identity produced, as one element of `articles.json`.
 *
 * A failure is a row, not an absence. It carries `text: null` with a typed
 * reason, so the count of URLs that were tried and the count that worked are
 * both readable from the file instead of one being inferred from the other.
 */
export interface ReferenceExtractionRow {
	version?: string;

	/** The input line, carried from the manifest row. */
	source_line: number;

	/** The address as supplied. */
	source_url: string;

	/** What `url_key` is derived from. */
	canonical_url: string;

	/** sha256 of the canonical URL, recomputed on read. */
	url_key: string;

	/** The registered domain. */
	source_domain: string;

	/** The host, lower case. */
	host: string;

	/** The frozen outlet key, carried from the manifest row. */
	publisher: string;

	/** Source context, or null. */
	vertical?: string | null;

	/** Which stage ended this attempt, in the vocabulary the pipeline uses. */
	status: ArticleStatus;

	/** What happened there. Null on a success, and only then. */
	failure_code?: ReferenceFailureCode | null;

	/** One sentence a person can act on. Never a page's own words. */
	failure_detail?: string | null;

	/** The full sanitized article prose, paragraph breaks kept. Null on a failure, and never an empty string standing in for one. */
	text?: string | null;

	/** Words in `text`. Null where there is no text. */
	article_words?: number | null;

	/** sha256 of `text`. Null where there is no text. */
	article_sha256?: string | null;

	/** When the request was made. Null where none was. */
	fetched_at?: string | null;

	/** When the text was taken. Null where none was. */
	extracted_at?: string | null;

	/** Which extractor produced the text. */
	extractor_version?: string | null;

	/** Which sanitizer the text crossed the trust boundary through. */
	sanitizer_version?: string | null;

	/** What the cleaning phase found wrong with this article. Empty on an extraction row, because the fetch judges whether a page answered and never whether the prose is worth reading. */
	quality_flags?: ReferenceQualityFlag[];
}
