// Generated from `backend/idhazh/contracts/counterfactual_score.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One candidate, scored twice. */
export interface CounterfactualScoreRow {
	version?: string;

	/** The digest date the run was planning. */
	date: string;

	/** The run that scored it. */
	run_id: string;

	/** The desk the candidate was scored on. Desks are planned separately, so a score is only ever comparable with another score from the same desk. */
	vertical: string;

	/** The candidate's address key, which is what makes two rows about one story recognisable across runs. Not an item id: a refused candidate never gets one. */
	url_key: string;

	/** Whether this candidate was in the run's plan after every later pass - the day-wide duplicate fold and the run's own safety ceiling included. False is the interesting value and the one nothing else records. */
	taken: boolean;

	/** The lens whose weight this row's counterfactual moves, empty when the headline matched none. One story takes the largest weight it earned and never the sum, so this names one lens and never a list. */
	lens_id?: string;

	/** What `lens_id` was worth in the run, read from the committed taxonomy. 0.0 when no lens matched, and then both scores are the same number. */
	lens_bonus: number;

	/** What the counterfactual multiplied the committed lens weight by. On the row rather than in a config file a reader would have to go and find, so a window of rows spanning a config change is still readable. */
	lens_multiplier: number;

	/** What `rank.score` returned at the committed weights. This is the score that decided the day. */
	score_committed: number;

	/** What `rank.score` returned at the candidate weight, over the same candidates in the same call shape. It decided nothing. */
	score_counterfactual: number;
}
