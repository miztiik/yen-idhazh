// Generated from `backend/idhazh/contracts/reference_dataset.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One reading of one article. Every field is empty when the set is built.
 *
 * The vocabularies are `config/taxonomy.json`, so nothing here enumerates a
 * member: a label is a slug the taxonomy names, and adding a word to the
 * taxonomy may not be a schema change. Three of the five
 * label fields name a vocabulary `config/taxonomy.json` does not carry yet -
 * `article_kind`, `stances` and `sentiment` - so the 2026-09-13 pass took them
 * from `backend/utilities/label_reference_dataset.py`, which is where that
 * list sits until the taxonomy carries them.
 *
 * **`stances` is keyed and valued in slugs, which the labelling vocabulary's
 * own spelling is not.** `Slug` admits the hyphen and refuses the underscore,
 * so the axis is `stance-on-change` and the decline is `not-applicable`. The
 * underscore spelling is what the token measurement was taken on; one of the
 * two has to move, and it is not this one.
 *
 * `reference_summary` **has a writer from 2026-09-13** and it is the labeller.
 * It is a reference for classification labels and is **never** a faithfulness
 * reference - the human faithfulness ledger was dropped and only its contract
 * kept (owner, 2026-09-10).
 */
export interface ReferenceLabels {
	/** Which desk the article belongs to, read from the text. */
	desk?: string | null;

	/** Every lens the article carries. May be empty. */
	lenses?: string[];

	/** What kind of writing it is - a report, an analysis, a notice. */
	article_kind?: string | null;

	/** One stance per political question the article takes a position on. */
	stances?: Record<string, string>;

	/** Sentiment about one named subject, not about the article. */
	sentiment?: string | null;

	/** The labeller's own summary of the article. A reference for classification labels, never a faithfulness reference - the human faithfulness ledger was dropped and only its contract kept. */
	reference_summary?: string | null;

	/** Who read it. A person, never a model. */
	labelled_by?: string | null;

	/** The day they read it. */
	labelled_on?: string | null;

	/** Which `config/taxonomy.json` definition text the label was taken against. A label taken against last month's definition measures a different question. */
	definition_version?: string | null;
}

/** One article of `corpus/reference-dataset-1/dataset.jsonl`. */
export interface ReferenceDatasetRow {
	version?: string;

	/** sha256 of the canonical URL, recomputed on read. It is the join to `splits/*.txt`, to `articles/<url_key>.txt`, and to every collection this set must not overlap. */
	url_key: string;

	/** What `url_key` is derived from, never trusted from a payload. */
	canonical_url: string;

	/** The address the feed carried, kept so a person can open it. */
	source_url: string;

	/** The registrable domain, which is the unit the split is drawn on. Two articles from one outlet share boilerplate, a house style and often a wire original, so a split that separates rows rather than outlets flatters every number taken on it. */
	source_domain: string;

	/** Which feed in `config/sources.json` carried it. */
	source_id: string;

	/** The vertical the pipeline published it under, kept as context. */
	vertical: string;

	/** The day the article was published. */
	published_date: string;

	/** The headline, as published. */
	title: string;

	/** Words in the article file. Recomputed by `verify`, never trusted. */
	article_words: number;

	/** sha256 of `articles/<url_key>.txt`. What detects a text edited in place, which would silently move what a label was taken against. */
	article_sha256: string;

	/** Which extractor produced the text. */
	extractor_version: string;

	/** Which sanitizer the text crossed the trust boundary through. */
	sanitizer_version: string;

	/** The day the text was taken. The set is frozen from here. */
	fetched_on: string;

	/** The first rater's reading. */
	labels?: ReferenceLabels;

	/** A second reading of the same article. On the 2026-09-13 pass it is the same labeller's alternative reading, which is NOT an independent second rating and may not be used for a Cohen's kappa. Null is not a disagreement. */
	second_labels?: ReferenceLabels | null;
}
