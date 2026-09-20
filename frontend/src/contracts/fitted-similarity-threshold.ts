// Generated from `backend/idhazh/contracts/fitted_similarity_threshold.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * What shaped the applied value, in one word.
 *
 * `CEILING` and `FLOOR` are where the line came to rest on a band wall, whether
 * or not the wall moved it that day. A line at `band_high` folds nothing at all
 * and a line at `band_low` folds everything in the band; both look from the
 * outside like the feature is switched off, so both get a word of their own
 * rather than reading as `NONE`.
 */
export const CLAMP_KIND = ['none', 'step', 'guard', 'ceiling', 'floor'] as const;

export type ClampKind = (typeof CLAMP_KIND)[number];

/** Why no fit ran today. `NONE` means one did. */
export const HELD_REASON = ['none', 'sheet_too_small', 'inputs_changed', 'judge_unstable', 'judge_uncertain', 'legs_missing'] as const;

export type HeldReason = (typeof HELD_REASON)[number];

/** One run's fit: the five steps, the gates, and what the record held when they ran. */
export interface FittedSimilarityThreshold {
	version?: string;

	/** The digest date this fit was run for. */
	date: string;

	/** The run that fitted the line. */
	run_id: string;

	/** Which record this fit read: a digest of the band, the slot width and both model stamps. A later reader can tell two rows apart that were fitted either side of an archive. */
	record_stamp: string;

	/** The line that was applied yesterday. Where today started. */
	previous: number;

	/** What step 1 read off the record before damping or clamping. The raw evidence. Empty on a held day, because no fit ran and there is nothing to report. */
	proposed?: number | null;

	/** The proposal after damping. Both directions are damped, so this differs from the proposal on a rise as well as on a fall - and equals the previous line when the proposal sat inside the dead zone and the day counted as no move. Empty whenever the proposal is, since there is nothing to damp. */
	after_damping?: number | null;

	/** The line this run wrote. What assemble will read once row 9 lands. */
	applied: number;

	/** What shaped the applied value. none is the damped proposal as it stood, step is a daily cap, guard is the step-change hold, and ceiling or floor is the line resting on a band wall. Which way a step went is read off previous against applied. */
	clamp_kind?: ClampKind;

	/** How far the clamp held the line back. A distance, so it is at or above zero whichever direction was held. Zero when nothing clamped, and zero on a ceiling or floor row where the line was already resting on the wall. */
	clamp_movement?: number;

	/** Why no fit ran today. none means one ran. A held row carries the previous line unchanged and every count that explains the hold. */
	held_reason?: HeldReason;

	/** Whether a whole week of fresh judgements stopped moving the answer. Judging drops to weekly while this is true and returns to daily on its own. */
	settled?: boolean;

	/** What share of the record's NO readings step 1 walked past before it stopped. On the row because a later reader comparing two fits has to know both were asked the same question. */
	discard_share: number;

	/** How much of a downward move the damping let through against yesterday's line. On the row for the same reason the discard share is: a later reader comparing two fits has to know both were asked the same question. */
	fall_weight: number;

	/** How much of an upward move the damping let through. Smaller than the fall weight on every legal config, because the line falls fast and rises slow. */
	rise_weight: number;

	/** The furthest the line could fall in one day, in score units. On the row because clamp_kind says a cap fired and this says what it fired against. */
	max_down_step: number;

	/** The furthest the line could rise in one day, in score units. On the row for the same reason the fall cap is. */
	max_up_step: number;

	/** How many times the typical daily shift today's shift had to beat before the guard held the line. On the row for the same reason the daily step is. */
	step_change_multiple: number;

	/** How far today alone moved the answer: the fit with today against the fit without it. Empty when either fit has no NO verdicts to walk, because a subtraction with one side missing is not a zero. */
	daily_shift?: number | null;

	/** The median daily shift over the last fourteen written rows. Empty until fourteen exist, which is how a reader sees the guard is still filling. A median rather than a sigma, because the daily shift shrinks as 1/days and is not normally distributed. */
	typical_shift?: number | null;

	/** How many distinct pairs the day file holds - what the draw dealt the legs, after pair_budget cut the band down. Equal to the budget on a day that hit the cap, which is how a truncated day reads as partial rather than as a quiet one. The count before the budget is not persisted anywhere, so no writer could put it here. */
	pairs_in_band: number;

	/** How many pairs a judging leg actually read. */
	pairs_judged: number;

	/** How many of those got two agreeing readings. Only these were folded. */
	pairs_usable: number;

	/** What share of the judged pairs the two readings disagreed about. One of the three gates, and the one that reads the judge rather than the record. */
	disagreement_rate: number;

	/** What share of the agreed readings were UNCLEAR. A judge that cannot tell is not a judge the line should move on. */
	unclear_rate: number;

	/** Agreed NO readings the whole record holds. One of the three gates, and the one that takes longest to fill. */
	negatives_on_record: number;

	/** Judged pairs at or above the applied line. These are the entire precision measurement, so they are never sampled away. */
	above_line_on_record: number;

	/** How many dates the record has folded. */
	days_on_record: number;

	/** How many groups the day published. The one number in this feature that involves no model. */
	merge_count: number;

	/** Which encoder produced the scores this fit was read off. */
	scorer_model: 'all-minilm-l6-v2-quantized';

	/** What the cosine was worth in the record this fit read. */
	cosine_weight: number;

	/** What the key-point term was worth. Same reason as the cosine weight. */
	key_point_weight: number;

	/** Which model produced the verdicts this fit read. Empty on a held day whose record has never been folded. */
	judge_model?: 'qwen3-5-9b-q4-k-m' | 'qwen3-5-9b-q4-k-m-thinking' | 'ornith-1-5-9b-q5-k-m' | 'gemma-4-e4b-it-qat-ud-q4-k-xl' | null;

	/** sha256 of the system turn those verdicts were produced under. */
	prompt_digest?: string | null;

	/** sha256 of the grammar those verdicts were produced under. */
	grammar_digest?: string | null;
}
