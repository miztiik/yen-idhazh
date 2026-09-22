// Generated from `backend/idhazh/contracts/content_similarity_judge_metrics.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One shard of one night: what this judge was dealt, what it read, what it cost. */
export interface ContentSimilarityJudgeMetrics {
	version?: string;

	/** Which instrument wrote this reading. One member, because this store holds the readings of one judge and no other - so the column is narrowed here, where a closed set can be closed honestly. */
	judge_id?: 'content-similarity-judge';

	/** Which weights judged. Narrowed to the sets this repository ships a model file for, so swapping the judge is a schema diff rather than a silent change in what a reading means. Empty where no model ran. */
	judge_model?: 'qwen3-5-9b-q4-k-m' | 'qwen3-5-9b-q4-k-m-thinking' | 'ornith-1-5-9b-q5-k-m' | 'gemma-4-e4b-it-qat-ud-q4-k-xl' | null;

	/** The sampler temperature, as the number it was set to. An operator reading a row needs the value, not a digest of it. */
	judge_temperature?: number | null;

	/** How many reasoning spans the call decoded before its answer - 0 for a cold answer, 1 under a thinking envelope. A column of its own because no other cell here moves with it: an envelope moves only the prompt, which nothing stamps. Without this cell a reading taken after reasoning and one taken cold are one population to every reader. */
	thinking_spans?: number | null;

	/** sha256 of the rendered system turn. */
	prompt_digest?: string | null;

	/** sha256 of the grammar handed to the decoder. */
	grammar_digest?: string | null;

	/** The digest date judged. */
	date: string;

	/** The council run this shard belonged to. */
	run_id: string;

	/** Which unit of the split this row is about. */
	shard: number;

	/** How many pairs the selection gave this shard. */
	pairs_dealt: number;

	/** How many of them got a reading inside the grammar. */
	pairs_read: number;

	/** How many read pairs answered the same way in both orders. A subset of the pairs read, never of the pairs dealt. */
	pairs_agreed: number;

	/** How many pairs the window no longer reaches, because the day either item was published on has aged out. */
	pairs_unreadable: number;

	/** How many pairs came back outside the grammar. Pairs rather than calls: a pair is two calls, so counting calls would count a pair that failed twice twice and put the funnel out on a real event rather than on a defect. */
	pairs_refused: number;

	/** How many pairs this shard owned and never reached, because it stopped on its own deadline. A column of its own so the funnel still closes on the shard the deadline exists to let report. */
	pairs_abandoned: number;

	/** What share of the pairs read answered differently in the two orders. Empty when nothing was read, because a rate over no rows is not zero. Per shard over pairs read, where the line-setting gate is per day over pairs agreed - two different quantities. */
	disagreement_rate?: number | null;

	/** What share of the pairs agreed answered UNCLEAR. Empty on a shard that agreed nothing, for the reason above, and per shard for the reason above. */
	unclear_rate?: number | null;

	/** The median gap at the deciding position, over the three verdict openings. Not comparable to another judge's reading: a flat distribution means the grammar chose here, and a legitimate middle score for a judge whose distribution is the answer. */
	first_token_margin_median?: number | null;

	/** How long the shard's calls took, added up. Empty where no call was made. */
	decode_seconds_total?: number | null;

	/** The longest single call. A shard with an ordinary total and a bad worst call is the one that runs out of clock next, and the total alone hides it. */
	decode_seconds_max?: number | null;
}
