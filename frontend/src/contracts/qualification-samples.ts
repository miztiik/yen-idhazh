// Generated from `backend/idhazh/contracts/qualification.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** Which bytes ran. A model-card name identifies nothing. */
export interface CandidateIdentity {
	model_id: string;

	repo: string;

	/** An immutable repository revision, not a branch. */
	revision: string;

	file: string;

	quantisation: string;

	/** What the adoption target declares. */
	sha256_expected: string;

	/** What the runtime actually opened. */
	sha256_observed: string;

	bytes_expected: number;

	bytes_observed: number;

	runtime_build: string;
}

/**
 * One summary as a person would read it, beside the two numbers that judged it.
 *
 * Self-contained on purpose. A reviewer opening this file to ask whether a
 * score is believable should not have to join it against the shard to learn
 * whether the item was a brief or a long read, or open a third file to find
 * the address that would settle a claim.
 */
export interface SummarySample {
	item_id: string;

	/** Null where the drafted title missed its range and was dropped. */
	title?: string | null;

	/** The writing under judgement. Our text. */
	summary: string;

	/** The only way to check a claim. */
	source_url: string;

	/** Which length tier the extracted article fell in. */
	band_index: number;

	/** The same words are good or bad depending on how much was shown. */
	truncated: boolean;

	hhem: number;

	compression: number;
}

/**
 * The writing one shard produced, for a person to read.
 *
 * **Nothing here reaches a gate, and nothing here reaches a reader of the
 * site.** `QualificationReport` does not embed it and no scorer opens it: a
 * gate that learned to read this would be a gate reading text it also scored.
 * It is uploaded as its own artifact and thrown away with it, never committed
 * and never written under `frontend/public/`.
 *
 * Why it exists at all: a qualification run recorded what the writing measured
 * and never the writing. `output_digest` says two runs wrote the same words
 * and cannot say whether the words were any good, and `ItemScore` is eleven
 * floats over text nobody kept. Andre's ruling, 2026-09-15: what qualification
 * measured was everything except the writing.
 *
 * **This is our summary, not the publisher's text.** Section 0a bans
 * republishing an article body to a reader; the article is still only hashed,
 * and the prompt that contains it is still behind its own flag. What is here
 * is the model's output.
 *
 * Two objections, recorded rather than resolved. A human reading these is a
 * selector nobody logs, and somebody sorting by faithfulness, reading ten and
 * quietly re-running is re-rolling the corpus by hand - which the frozen
 * corpus exists to stop. And seven fields is a taste panel with no rubric, no
 * second rater and no agreement number; it will be cited as evidence and it is
 * not.
 */
export interface QualificationSamples {
	version?: string;

	date: string;

	shard: number;

	candidate: CandidateIdentity;

	samples?: SummarySample[];
}
