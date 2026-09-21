// Generated from `backend/idhazh/contracts/merge_line_holdout_score.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One run's reading of the applied merge line against the hand-marked holdout. */
export interface MergeLineHoldoutScore {
	version?: string;

	/** The day the line was scored. */
	date: string;

	/** The run that scored it. */
	run_id: string;

	/** The merge line in force when these cells were counted. On the row because two rows counted under two lines answer two different questions. */
	applied_line: number;

	/** Who marked the holdout. Free text rather than a model this repository ships, because the committed labels name a model from outside the registry and a narrower column would have to refuse the truth. */
	labeller: string;

	/** The line joined the pair and the label agrees it is one story. */
	merged_and_one_story: number;

	/** The line joined two stories that the label says are not one. The invisible direction: the reader never learns the second story existed. */
	merged_and_two_stories: number;

	/** The line left one story in two pieces. The reader sees it twice and can dismiss the second, which is why this is the cheaper of the two mistakes. */
	apart_and_one_story: number;

	/** The line left the pair apart and the label agrees they are two. */
	apart_and_two_stories: number;

	/** Labelled pairs neither cell could be counted for, because retention has deleted one of the two days they name. Reported rather than dropped, so a shrinking comparison is visible instead of silent. */
	pairs_unresolved: number;

	/** How many labelled pairs are marked two stories - the population the false-merge cell is drawn from. On the row so that no rate is ever read without the denominator it came from. */
	labelled_two_story_pairs: number;

	/** Which encoder produced the cosines these cells were counted under. */
	scorer_model: 'all-minilm-l6-v2-quantized';

	/** What the cosine was worth in the score the line was applied to. On the row because a later reader comparing two runs has to know both were asked the same question. */
	cosine_weight: number;

	/** What the key-point term was worth. Same reason as the cosine weight. */
	key_point_weight: number;
}
