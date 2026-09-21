// Generated from `backend/idhazh/contracts/story_similarity_pair.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * The three words a judge may answer with, and nothing else.
 *
 * Upper case on the wire deliberately. The grammar handed to the decoder emits
 * these spellings, and the three differ at the first generated token - which is
 * what makes `first_token_margin` a reading about this pair rather than about
 * where the three words happen to agree.
 */
export const SAME_STORY_VERDICT = ['YES', 'NO', 'UNCLEAR'] as const;

export type SameStoryVerdict = (typeof SAME_STORY_VERDICT)[number];

/** One pair, what it scored, and what a judge said about it in both orders. */
export interface StorySimilarityPair {
	version?: string;

	/** The digest date whose items this pair came from. */
	date: string;

	/** The run that scored the pair. Two runs of one day judge the same pair twice, and both rows stay: each read its own day. */
	run_id: string;

	/** Which judging shard owns this row. index mod shards, never a contiguous block, so a truncated draw still spreads evenly across them. */
	shard: number;

	/** The pair's identity: sha256 of the two url keys joined in sorted order. Recomputed on read, never trusted from the row. */
	pair_key: string;

	/** The lower of the two address keys. Not an item id: an id is minted per day and this pair has to be recognisable across days. */
	left_url_key: string;

	/** The higher of the two address keys. Sorted so one pair has one row rather than two. */
	right_url_key: string;

	/** The weighted score the same-story pass would have given this pair. This is the number the fitted line is compared against, and the judge never sees it. */
	composite_score: number;

	/** The cosine between the two vectors the day already carries. Recorded raw so a later reweighting can be computed from the row rather than re-run. */
	cosine: number;

	/** The share of key-point words the two items have in common, on the same 0 to 1 scale. Recorded raw for the same reason as the cosine. */
	key_point: number;

	/** Whether the two items shared a headline, which makes the score 1.0 outright instead of the weighted sum. On the row because the two paths give one number by two rules, and a reader cannot tell them apart afterwards. */
	headline: boolean;

	/** Which encoder produced the two vectors. A Literal rather than a string, so swapping the encoder is a schema diff and a changelog entry rather than a silent change of scale. */
	scorer_model: 'all-minilm-l6-v2-quantized';

	/** What the cosine was worth when this row was scored, read from the committed config at scoring time. On the row rather than in a file a reader has to go and find, so a window spanning a config edit is still readable. */
	cosine_weight: number;

	/** What the key-point term was worth. Same reason as the cosine weight. */
	key_point_weight: number;

	/** What the judge said with the items in file order. Empty until a judging shard has read the pair. */
	verdict?: SameStoryVerdict | null;

	/** What the judge said with the same two items in the other order. Two readings of one pair, which is what makes disagreement measurable. */
	verdict_swapped?: SameStoryVerdict | null;

	/** Whether the two readings agree. Only an agreed pair is counted into the record; a disagreement is a reading about the judge rather than about the pair. */
	usable?: boolean;

	/** The gap between the two likeliest VERDICTS at the first generated position of the file-order call, over the mass the grammar admits there. Each returned token is summed into the verdict its text opens, a token opening more than one is dropped as naming none, and what is left is renormalised. A margin near zero means the grammar chose and the model did not; empty means fewer than two verdicts took any mass, which a one-word window and a window of illegal tokens both are. Rows stamped before 2026-09-21T12:00 carry a raw gap between the top two TOKENS of a three-wide window instead, which subtracted one verdict from itself whenever a vocabulary spelled it two ways. */
	first_token_margin?: number | null;

	/** Which model judged. A Literal for the same reason the scorer is one. */
	judge_model?: 'qwen3-5-9b-q4-k-m' | 'qwen3-5-9b-q4-k-m-thinking' | 'ornith-1-5-9b-q5-k-m' | 'gemma-4-e4b-it-qat-ud-q4-k-xl' | null;

	/** sha256 of the rendered system turn. The prompt is content, so a digest is the only honest shape for it. */
	prompt_digest?: string | null;

	/** sha256 of the grammar handed to the decoder. A grammar edit changes what the three words can be, so it is part of what the verdict means. */
	grammar_digest?: string | null;

	/** Wall clock for both calls on this pair. A per-pair reading, so a day's spread is readable off the day file; the shard bound is sized off its own run instead. */
	decode_seconds?: number | null;

	/** Which instrument produced the verdict on this row. One member, because one judge writes this store and no other - so the column is narrowed here, where a closed set can be closed honestly. */
	judge_id?: 'content-similarity-judge';

	/** The sampler temperature both calls ran at, as the number it was set to. An operator reading a row needs the value, not a digest of it. */
	judge_temperature?: number | null;

	/** sha256 of the canonical JSON of every key the caller posted that is not excluded. Taken from the payload rather than from config, because a digest built off config cannot see a payload-builder defect. The prompt is excluded because it differs every row and would make this a pair id; the grammar and the model reference are excluded because each has a column here already. */
	decode_digest?: string | null;

	/** Whether BOTH calls of this pair opened inside the grammar. The grain here is a pair, so one call that came back outside it makes this false. Empty until a judge has read the pair: a pair nothing decoded is a different fact from a decode the grammar did not hold. */
	grammar_applied?: boolean | null;

	/** What the decoder said it could have written at the first generated position of the FILE-ORDER call, named so because a pair makes two calls and a singular column must say which. `first_token_margin` is bucketed and renormalised out of this window, so the window is what lets that number be re-derived rather than trusted - and it is the only thing that lets a later change to the margin rule be replayed over rows already written. */
	first_token_probabilities?: string | null;

	/** How many reasoning spans the file-order call decoded before its answer - 0 for a cold answer, 1 under a thinking envelope. A column of its own because `decode_digest` cannot see the envelope: the only posted key a thinking envelope moves is the prompt, and the prompt is excluded. Without this cell a margin taken after reasoning and one taken cold are one population. */
	thinking_spans?: number | null;

	/** The run that READ this pair, which `run_id` beside it does not say: that one names the digest run that published the day, so two judging runs over one date write the identical string there. It is in the settlement key, so a re-judged pair lands beside the row it replaces instead of being dropped as a repeat. Empty on every row written before this column existed. */
	judged_by_run_id?: string | null;
}
