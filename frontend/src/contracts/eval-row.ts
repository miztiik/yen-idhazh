// Generated from `backend/idhazh/contracts/eval_row.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** The band, not the number, is what drives behaviour and what a reader sees. */
export const CONFIDENCE_BAND = ['high', 'medium', 'low'] as const;

export type ConfidenceBand = (typeof CONFIDENCE_BAND)[number];

/** The Evaluate stage's output, appended once per item. */
export interface EvalRow {
	version?: string;

	date: string;

	run_id: string;

	item_id: string;

	url_key: string;

	source_url: string;

	title: string;

	vertical: string;

	model_id: string;

	attempt: number;

	/** Faithfulness against the text the model saw. */
	hhem: number;

	/** Faithfulness against the article before the truncation cap. Equal to hhem on rows stamped before 2026-08-27T20:30, which scored one text twice. */
	hhem_full: number;

	/** hhem minus hhem_full, on the same 0-to-1 faithfulness scale. Derived, never independent: _delta_is_rebuilt_not_trusted recomputes it from the two scores on every read and raises if the stored cell disagrees, so it carries no information the two scores beside it do not. It is 0.0 on an article nobody cut, by construction - both scores read the same text and the scorer is deterministic - and 2,945 of the 2,945 uncut rows that carry both word counts are exactly 0.0 (measured 2026-08-30). It is non-zero on 3 of all 3,113 committed rows, because a row stamped before 2026-08-27T20:30 scored one text twice and almost no article is cut. Recorded only - no band reads it, and nothing on the published site prints it. Read it with the confound stated: measured 2026-08-29, a 3-window article scores 0.40 lower than the same article read whole, against bands at 0.80 and 0.50, so the window geometry alone is wider than the whole medium band and this number mixes the cost of the cut with the cost of the slicing. Until that settles it is not the cost of truncation on its own. See docs/concepts/evaluation.md. */
	hhem_delta: number;

	/** True when extract cut the article body before the model read it - Article.truncated, a fact from the stage that did the cutting, not a score. That is what the name always promised and what the column holds from 2026-08-29T09:00. A row stamped earlier holds a DIFFERENT fact: hhem_delta above a configured gap, which is the distance between two faithfulness scores and says nothing about a cut. Measured 2026-08-30 over all 3,113 committed rows of state/scores.csv, which are exact counts over a committed file and carry no spread. Of the 2,683 rows on the old side of the boundary it is true on 0 of the 22 genuinely cut rows, and true on exactly 1 row, which read 748 words of a 748-word article and was never cut. Of the 430 rows on the new side, 4 were cut and all 4 are flagged, and the flag agrees with the word counts on 430 of 430. Prefer the pair source_word_count > source_seen_word_count for any new reader: it is true exactly when the body was cut, on every row carrying both, with no version branch to get wrong. The pair has one hole of its own, and it prints as a hole - 142 of the 3,113 rows carry a null source_word_count, 4.6 percent, every one of them on the old side, and unknown is printed as unknown rather than as uncut. Its one reader is frontend/src/lib/server/model-work.ts, which counts it only over rows stamped from CUT_FLAG_MEANS_A_CUT_FROM. */
	truncation_flagged: boolean;

	/** Survival of the lead's entities and numbers. The instrument for omission. */
	coverage: number;

	/** Summary length over source length. Recorded, never flagged: at a fixed output budget this measures the article's length, not the summary's quality. */
	compression: number;

	/** Share of the summary's 4-grams found verbatim in the source. */
	extractiveness: number;

	/** Longest unbroken copied stretch. This is the one that names copying. */
	verbatim_run?: number;

	/** Numbers asserted by the summary that appear nowhere in the full source. */
	unsupported_numbers?: number;

	/** The source hedged and the summary asserted. A rumour became a fact. */
	hedge_dropped?: boolean;

	/** The text looks like page furniture. A faithful summary of chrome scores high. */
	extraction_suspect?: boolean;

	band: ConfidenceBand;

	/** The article before the truncation cap, counted by Article.source_word_count. Null when the length is not knowable: the pre-cap body is never persisted, so a truncated row stamped before 2026-08-27T21:00 has no full length to recover. Rows stamped before 2026-08-27T20:00 recount the post-cap text. */
	source_word_count?: number | null;

	/** What the model actually got, after truncation. Counted the same way as source_word_count, so the difference between the two is the cut. */
	source_seen_word_count?: number;

	summary_word_count: number;

	/** Null on every row written after 2026-09-12. The stamp stopped being a gate and stopped keying the eval window, so no writer fills it. The field and its ledger column survive here alone, because the console reads this column to draw the model-change boundaries on every day whose identity is a digest rather than a named input manifest, and it is the only source of them. Remove it, and the column from state/scores/, once no score row the widest console window can reach carries one. */
	pipeline_fingerprint?: string | null;

	output_digest: string;

	/** Identical inputs, different words. Counted and published, never fatal. */
	determinism_violation?: boolean;

	/** Derived, never hand-typed: the scorer, its weights, the tagger and the band thresholds, spelled so a row still explains itself years later. */
	scorer_version: string;

	scored_at: string;

	/** Milliseconds the faithfulness scorer spent on THIS one item, after the summary was already written. Not on the critical path of the published words: no digest sentence waits on it, and a run with the scorer off publishes the same text. The shard clock does wait on it, and that is the decision this column exists to size - whether the scorer stays a census or becomes a sample. observability.sample_rate is the knob that decision produced, so this is the instrument behind that knob and not a stage timing to tune. Measured 2026-08-30 over all 3,113 committed rows of state/scores.csv: median 2,763 ms an item, 95th percentile 14,814 ms, longest 51,587 ms. Per run, the heaviest of the 25 committed runs spent 859.7 s scoring 149 items - 14.3 minutes spread over that run's shards, so at today's volume of about 150 items a day the census is affordable and a rate below 1.0 is insurance rather than a rescue. Zero on the 10 rows written before the column existed, and those read as unmeasured rather than as instant. */
	score_ms?: number;

	/** Attribution markers as a share of the ARTICLE's words. How often the story says where it got a claim. Scores the source, not our summary of it. Null on a row scored before metrics-2. */
	evidential_density?: number | null;

	/** Unresolved-claim markers as a share of the ARTICLE's words. Read against evidential_density: speculation nobody is cited for is the fragile case. Null on a row scored before metrics-2. */
	speculative_density?: number | null;

	/** Share of the summary's 4-word windows that repeat one it already used. The only column that reads the summary against ITSELF: every other n-gram column reads it against the article, and a repeated sentence is perfectly supported by the article. Zero means no window repeats. Recorded only, never banded. Null on a row scored before 2026-08-26. */
	self_repetition?: number | null;

	/** The premise the faithfulness scorer read, digested whole: the article text after sanitizing and truncation. Not the fetched page, and not the summary - `output_digest` already names those words. It exists so a person labelling this item by hand can prove they are reading the same text the scorer read; without it a disagreement between them measures a premise mismatch rather than a scorer error. Null on a row scored before 2026-08-27. */
	source_digest?: string | null;

	/** Share of the item's key points that state a fact the summary prose does not already carry - the aggregate inverse of the restatement drop to_summary makes, read at the same distinctness ceiling, so a key point that counts here is exactly one the drop keeps. The instrument for whether the key-point prompt finds facts or paraphrases the summary. Lexical, and the element table supersedes it with span-anchored ids that carry no false positive. Recorded only - no band reads it, and best-of-N against it is the Goodhart form of the number. Null on a row scored before the column existed; 0.0 only on a scored reply whose every key point restated. */
	new_fact_rate?: number | null;
}
