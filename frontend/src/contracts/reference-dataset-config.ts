// Generated from `backend/idhazh/contracts/reference_dataset.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

export interface ExtractConfig {
	/** A performance lever, not only a safety cap: prefill degrades with length. */
	truncation_cap_tokens?: number;

	/** Below this the item publishes through the brief tier. It is derived in AppConfig from summarize.bands[0].target_words_min divided by evaluation.brief_compression_ceiling. */
	min_source_words?: number;

	/** Sentences of prose needed before a page stops carrying the not_prose signal. */
	prose_sentence_min?: number;

	/** Words a sentence needs before it counts as prose for the shape signal. */
	prose_sentence_words_min?: number;

	/** Lines needed before the line-shape guard runs. */
	prose_line_count_min?: number;

	/** Minimum share of lines that must look like prose on a line-heavy page. */
	prose_line_ratio_min?: number;

	/** If true, a not_prose signal rejects the item. Default records and publishes. */
	reject_not_prose?: boolean;

	/** If true, a too_short signal rejects the item. Default records and publishes, which is Owner override O3. **A feed a curator declared `abstract` is never rejected by this, whatever it is set to.** That feed publishes abstracts because a person said so, and abstracts are short by definition - rejecting one would delete a source on the strength of the property it was registered for. The signal is still recorded on its row either way: the item IS short, and the census says so. What the form changes is the consequence, never the fact. */
	reject_too_short?: boolean;

	/** If true, a boilerplate signal rejects the item. Default records and publishes. */
	reject_boilerplate?: boolean;

	/** Share of an item's lines also seen on sibling items from the same host. */
	boilerplate_ratio_max?: number;

	/** Fallback markers used only when publisher JSON-LD does not declare the paywall. */
	paywall_markers?: string[];

	max_body_bytes?: number;

	max_retries?: number;

	backoff_initial_seconds?: number;

	backoff_multiplier?: number;

	request_timeout_seconds?: number;

	user_agent?: string;
}

/**
 * How the cleaning phase decides what is furniture and what is an article.
 *
 * The furniture rule is one sentence: a line a publisher puts on most of its
 * own articles is furniture, not news. It is per-publisher because the
 * extractor has already removed the furniture that looks like markup, and what
 * survives - a disclaimer, a standing newsletter blurb, a sponsor slot - reads
 * exactly like prose until you notice it appears forty times in a row.
 */
export interface ReferenceCleaningSettings {
	/** Below this an article is flagged short. */
	words_min?: number;

	/** The share of a publisher's articles a line must appear on to be furniture. */
	repeat_min_share?: number;

	/** And the least number of times. A phrase used twice is not a habit. */
	repeat_min_count?: number;

	/** Articles a publisher needs before the rule runs. Two samples decide nothing. */
	publisher_min_articles?: number;

	/** The safety valve. An article that would lose more than this keeps its text and is flagged instead, because a rule that can empty an article should say so rather than do it quietly. */
	max_removed_share?: number;

	/** Words a line needs before it counts as a sentence. */
	sentence_words_min?: number;

	/** Below this share of real sentences, the text is a list rather than prose. */
	fragment_ratio_min?: number;

	/** Shared five-word phrases before two articles are one story. Measured on the real corpus: 0.7, 0.5 and 0.35 all found the same 11, so these are near-exact repeats rather than a threshold to tune. */
	near_duplicate_jaccard?: number;

	/** Sales phrases before an article reads as an advertisement. Two, not one: one hit flags 82 real articles that merely carry a subscription line. */
	promo_hits?: number;

	/** Which flags keep an article out of the cleaned collection. A flagged article is still written with its flags when it is not on this list. */
	drop_flags?: ReferenceQualityFlag[];
}

/**
 * Which field a balanced sample counts as one outlet.
 *
 * `PUBLISHER` is the default because the registered domain merges every
 * newsletter on a shared platform into one allocation: 50 articles from
 * `bengoertzel.substack.com` and 50 from `chipbriefing.substack.com` are two
 * outlets to a reader and one `substack.com` to the public suffix list.
 */
export const REFERENCE_GROUP_BY = ['publisher', 'source_domain', 'host'] as const;

export type ReferenceGroupBy = (typeof REFERENCE_GROUP_BY)[number];

/**
 * What a publisher key is lengthened with when two hosts produce the same one.
 *
 * Tried in the configured order and no further than uniqueness needs, so a key
 * nobody collides with keeps its short form.
 */
export const REFERENCE_PUBLISHER_PART = ['registered_name', 'public_suffix', 'host'] as const;

export type ReferencePublisherPart = (typeof REFERENCE_PUBLISHER_PART)[number];

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
 * How many articles a sample takes, and what it counts as one outlet.
 *
 * Every number here is a knob rather than a literal in the selection loop
 * (Guardrail #6): changing the file changes the sample with no source edit.
 */
export interface ReferenceSelectionSettings {
	/** Articles wanted per group. An initial allocation, not a ceiling - a deep group may pass it while filling places a short group cannot use. */
	rows_per_domain_target?: number;

	/** A hard total cap, and never a promise to produce this many rows. */
	rows_max?: number;

	/** Whether places a short group cannot use move to groups with articles left. */
	fill_shortfall?: boolean;

	/** Which field counts as one outlet. */
	group_by?: ReferenceGroupBy;

	/** The parts a colliding publisher key is lengthened with, in order. */
	publisher_disambiguation?: ReferencePublisherPart[];

	/** Leftmost labels that name a subdomain rather than an outlet. `newsletter.semianalysis.com` is `semianalysis`, not `newsletter`. */
	generic_host_labels?: string[];
}

/**
 * Every setting `corpus/reference-dataset-2/` is built with, and it reads no other.
 *
 * It is deliberately not a block of `config/idhazh.json`. This collection is
 * built by hand once or twice a year and the pipeline runs every day, so a
 * knob that only this tool reads does not belong in the file every stage
 * loads (owner decision, 2026-09-13).
 *
 * Paths are relative to the repository root, POSIX-separated, with no `..`
 * segment (`CLAUDE.md` section 2). A path relative to this file would have to
 * climb out of the collection to name the taxonomy, and a stored `..` is the
 * one form that stops meaning the same thing when a file moves.
 */
export interface ReferenceDatasetLocalConfig {
	version?: string;

	/** The snapshotted URL list, one address a line. */
	input_file?: string;

	/** Read-only. The vertical vocabulary, never copied into this file. */
	taxonomy_file?: string;

	/** Read-only. What a host has to match before a row claims a source id. */
	sources_file?: string;

	/** The settings `fetch.fetch` already consumes. `truncation_cap_tokens` caps what a model reads and is never applied to saved text. */
	extract?: ExtractConfig;

	/** Seconds between two requests to one host. The existing builder's name. */
	request_delay_seconds?: number;

	/** How a balanced sample is drawn from the finished extraction. */
	selection?: ReferenceSelectionSettings;

	/** How publisher furniture is removed and which articles are dropped. */
	cleaning?: ReferenceCleaningSettings;
}
